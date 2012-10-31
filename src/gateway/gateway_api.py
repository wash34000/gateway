'''
The GatewayApi defines high level functions, these are used by the interface
and call the master_api to complete the actions. 

Created on Sep 16, 2012

@author: fryckbos
'''
import logging
LOGGER = logging.getLogger("openmotics")

import time as pytime
from threading import Timer

import master_api
import master_command
from outputs import OutputStatus
from master_communicator import BackgroundConsumer 

class GatewayApi:
    """ The GatewayApi combines master_api functions into high level functions. """
    
    def __init__(self, master_communicator):
        self.__master_communicator = master_communicator
    
        self.__last_maintenance_send_time = 0
        self.__maintenance_timeout_timer = None
        
        self.__output_status = None
        self.__master_communicator.register_consumer(
                    BackgroundConsumer(master_api.output_list(), 0, self.__update_outputs))    
    
    ###### Maintenance functions
    
    def start_maintenance_mode(self, timeout=600):
        """ Start maintenance mode, if the time between send_maintenance_data calls exceeds the
        timeout, the maintenance mode will be closed automatically. """
        self.__master_communicator.start_maintenance_mode()
        
        def check_maintenance_timeout():
            """ Checks if the maintenance if the timeout is exceeded, and closes maintenance mode
            if required. """
            if self.__master_communicator.in_maintenance_mode():
                current_time = pytime.time()
                if self.__last_maintenance_send_time + timeout < current_time:
                    self.stop_maintenance_mode()
                else:
                    wait_time = self.__last_maintenance_send_time + timeout - current_time
                    self.__maintenance_timeout_timer = Timer(wait_time, check_maintenance_timeout)
                    self.__maintenance_timeout_timer.start()
        
        self.__maintenance_timeout_timer = Timer(timeout, check_maintenance_timeout)
        self.__maintenance_timeout_timer.start()
        
    
    def send_maintenance_data(self, data):
        """ Send data to the master in maintenance mode.
        
        :param data: data to send to the master
        :type data: string
        """
        self.__last_maintenance_send_time = pytime.time()
        self.__master_communicator.send_maintenance_data(data)
    
    def get_maintenance_data(self):
        """ Get data from the master in maintenance mode.
        
        :returns: string containing unprocessed output
        """
        return self.__master_communicator.get_maintenance_data()
    
    def stop_maintenance_mode(self):
        """ Stop maintenance mode. """
        self.__master_communicator.stop_maintenance_mode()
        if self.__maintenance_timeout_timer != None:
            self.__maintenance_timeout_timer.cancel()
            self.__maintenance_timeout_timer = None
    
    def get_status(self):
        """ Get the status of the Master.
        
        :returns: dict with 'time' (HH:MM), 'date' (DD:MM:YYYY), 'mode', 'version' (a.b.c) 
                  and 'hw_version' (hardware version)
        """
        out_dict = self.__master_communicator.do_command(master_api.status())
        return { 'time' : '%02d:%02d' % (out_dict['hours'], out_dict['minutes']),
                 'date' : '%02d/%02d/%d' % (out_dict['day'], out_dict['month'], out_dict['year']),
                 'mode' : out_dict['mode'],
                 'version' : "%d.%d.%d" % (out_dict['f1'], out_dict['f2'], out_dict['f3']),
                 'hw_version' : out_dict['h']
               }
    
    def __read_outputs(self):
        """ Read all output information from the MasterApi.
        
        :returns: a list of dicts with all fields from master_api.read_output.
        """
        ret = self.__master_communicator.do_command(master_api.number_of_io_modules())
        num_outputs = ret['out'] * 8
        
        outputs = []
        for i in range(0, num_outputs):
            outputs.append(self.__master_communicator.do_command(master_api.read_output(),
                                                                 { 'output_nr' : i }))
        return outputs
    
    def __update_outputs(self, ol_output):
        """ Update the OutputStatus when an OL is received. """
        on_outputs = ol_output['outputs']
        if self.__output_status != None:
            self.__output_status.partial_update(on_outputs)
    
    def get_outputs(self):
        """ Get a list containing the status of the Outputs. 
        
        :returns: A list is a dicts containing the following keys: output_nr, name, floor_level,
        light, type, controller_out, timer, ctimer, max_power, status and dimmer. 
        """
        if self.__output_status == None:
            self.__output_status = OutputStatus(self.__read_outputs())
        
        if self.__output_status.should_refresh():
            self.__output_status.full_update(self.__read_outputs())
        
        outputs = self.__output_status.get_outputs()
        return [ { 'status':output['status'], 'floor_level':output['floor_level'],
                   'output_nr':output['output_nr'], 'name':output['name'], 'light':output['light'],
                   'timer':output['timer'], 'ctimer':output['ctimer'],
                   'max_power':output['max_power'], 'dimmer':output['dimmer'],
                   'type':output['type'] } for output in outputs ]
    
    def set_output(self, output_nr, is_on, dimmer=None, timer=None):
        """ Set the status, dimmer and timer of an output. 
        
        :param output_nr: The id of the output to set
        :type output_nr: Integer [0, 240]
        :param is_on: Whether the output should be on
        :type is_on: Boolean
        :param dimmer: The dimmer value to set, None if unchanged
        :type dimmer: Integer [0, 100] or None
        :param timer: The timer value to set, None if unchanged
        :type timer: Integer in [150, 450, 900, 1500, 2220, 3120]
        :returns: emtpy dict.
        """
        if not is_on:
            if dimmer != None or timer != None:
                raise ValueError("Cannot set timer and dimmer when setting output to off")
            else:
                self.set_output_status(output_nr, False)
        else:
            if dimmer != None:
                self.set_output_dimmer(output_nr, dimmer)
            
            self.set_output_status(output_nr, True)
            
            if timer != None:
                self.set_output_timer(output_nr, timer)
        
        return dict()
    
    def set_output_status(self, output_nr, is_on):
        """ Set the status of an output. 
        
        :param output_nr: The id of the output to set
        :type output_nr: Integer [0, 240]
        :param is_on: Whether the output should be on
        :type is_on: Boolean
        :returns: empty dict.
        """
        if output_nr < 0 or output_nr > 240:
            raise ValueError("Output_nr not in [0, 240]: %d" % output_nr)
        
        if is_on:
            self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : master_api.BA_LIGHT_ON, "action_number" : output_nr })
        else:
            self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : master_api.BA_LIGHT_OFF, "action_number" : output_nr })
        
        return dict()
    
    def set_output_dimmer(self, output_nr, dimmer):
        """ Set the dimmer of an output. 
        
        :param output_nr: The id of the output to set
        :type output_nr: Integer [0, 240]
        :param dimmer: The dimmer value to set, None if unchanged
        :type dimmer: Integer [0, 100] or None
        :returns: empty dict.
        """
        if output_nr < 0 or output_nr > 240:
            raise ValueError("Output_nr not in [0, 240]: %d" % output_nr)
        
        if dimmer < 0 or dimmer > 100:
            raise ValueError("Dimmer value not in [0, 100]: %d" % dimmer)
        
        dimmer = int(dimmer) / 10 * 10
        
        if dimmer == 0:
            dimmer_action = master_api.BA_DIMMER_MIN
        elif dimmer == 100:
            dimmer_action = master_api.BA_DIMMER_MAX
        else:
            dimmer_action = master_api.__dict__['BA_LIGHT_ON_DIMMER_' + str(dimmer)]
        
        self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : dimmer_action, "action_number" : output_nr })
        
        return dict()
    
    def set_output_timer(self, output_nr, timer):
        """ Set the timer of an output. 
        
        :param output_nr: The id of the output to set
        :type output_nr: Integer [0, 240]
        :param timer: The timer value to set, None if unchanged
        :type timer: Integer in [150, 450, 900, 1500, 2220, 3120]
        :returns: empty dict.
        """
        if output_nr < 0 or output_nr > 240:
            raise ValueError("Output_nr not in [0, 240]: %d" % output_nr)
        
        if timer not in [150, 450, 900, 1500, 2220, 3120]:
            raise ValueError("Timer value not in [150, 450, 900, 1500, 2220, 3120]: %d" % timer)
        
        timer_action = master_api.__dict__['BA_LIGHT_ON_TIMER_'+str(timer)+'_OVERRULE']
        
        self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : timer_action, "action_number" : output_nr })
        
        return dict()
    
    ###### Thermostat functions
    
    def get_thermostats(self):
        """ Get the configuration of the thermostats.
        
        :returns: dict with global status information about the thermostats: 'thermostats_on',
        'automatic' and 'setpoints' and a list ('thermostats') with status information for each
        active thermostats, each element in the list is a dict with the following keys:
        'thermostat', 'act', 'csetp', 'psetp0', 'psetp1', 'psetp2', 'psetp3', 'psetp4', 'psetp5',
        'sensor_nr', 'output0_nr', 'output1_nr', 'output0', 'output1', 'outside', 'mode', 'name',
        'pid_p', 'pid_i', 'pid_d', 'pid_ithresh', 'threshold_temp', 'days', 'hours', 'minutes',
        'mon_start_d1', 'mon_stop_d1', 'mon_start_d2', 'mon_stop_d2', 'tue_start_d1', 'tue_stop_d1',
        'tue_start_d2', 'tue_stop_d2', 'wed_start_d1', 'wed_stop_d1', 'wed_start_d2', 'wed_stop_d2',
        'thu_start_d1', 'thu_stop_d1', 'thu_start_d2', 'thu_stop_d2', 'fri_start_d1', 'fri_stop_d1',
        'fri_start_d2', 'fri_stop_d2', 'sat_start_d1', 'sat_stop_d1', 'sat_start_d2', 'sat_stop_d2',
        'sun_start_d1', 'sun_stop_d1', 'sun_start_d2', 'sun_stop_d2' and 'crc'.
        """
        mode = self.__master_communicator.do_command(master_api.thermostat_mode())['mode']
        
        thermostats_on = (mode & 128 == 128)
        automatic = (mode & 8 == 8)
        setpoint = (mode & 7)
        
        thermostats = []
        for thermostat_id in range(0, 24):
            (success, tries) = (False, 0)
            while not success and tries < 3:
                # Try 3 times, if not OK after 3 times: add error message to output
                (success, tries, msg) = (True, tries + 1, '')
                
                thermostat = self.__master_communicator.do_command(master_api.read_setpoint(),
                                { 'thermostat' :  thermostat_id })
                
                if thermostat['thermostat'] != thermostat_id:
                    success = False
                    msg = 'Got information for wrong thermostat, asked %d, got %d' % \
                                (thermostat_id, thermostat['thermostat'])
                    LOGGER.error(msg)
                
                if self.check_crc(master_api.read_setpoint(), thermostat) == False:
                    success = False
                    msg = 'Error while calculating CRC for rs on thermostat %d' % thermostat_id
                    LOGGER.error(msg)
                
                # Check if the thermostat is activated
                if success and thermostat['sensor_nr'] <= 31 and thermostat['output0_nr'] < 240:
                    # Convert the Svt instances into temperatures
                    for temperature_key in [ 'act', 'csetp', 'psetp0', 'psetp1', 'psetp2', 'psetp3',
                                             'psetp4', 'psetp5', 'outside', 'threshold_temp' ]:
                        thermostat[temperature_key] = thermostat[temperature_key].get_temperature()
                    
                    for output_key in [ 'output0', 'output1' ]:
                        thermostat[output_key] = \
                            master_api.dimmer_to_percentage(thermostat[output_key])
                    
                    thermostats.append(thermostat)
                
                if tries == 3 and not success:
                    thermostats.append({ 'thermostat' : thermostat_id, 'error' : msg })

        return { 'thermostats_on' : thermostats_on, 'automatic' : automatic,
                 'setpoint' : setpoint, 'thermostats' : thermostats }
    
    def check_crc(self, masterCommandSpec, result):
        """ Check the CRC of the result of a certain master command.
        
        :param masterCommandSpec: instance of MasterCommandSpec.
        :param result: A dict containing the result of the master command.
        :returns: boolean.
        """
        crc = 0
        for field in masterCommandSpec.output_fields:
            if field.name == 'crc':
                break
            else:
                for byte in field.encode(result[field.name]):
                    crc += ord(byte)
        
        return result['crc'] == [ 67, (crc / 256), (crc % 256) ]
    
    def set_programmed_setpoint(self, thermostat, setpoint, temperature):
        """ Set a programmed setpoint of a thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param setpoint: The number of programmed setpoint
        :type setpoint: Integer [0, 5]
        :param temperature: The temperature to set in degrees Celcius
        :type temperature: float
        :returns: dict with 'thermostat', 'config' and 'temp'
        """
        if thermostat not in range(0, 25):
            raise ValueError("Thermostat not in [0,24]: %d" % thermostat)
        if setpoint not in range(0, 6):
            raise ValueError("Setpoint not in [0,5]: %d" % setpoint)
        
        ret = self.__master_communicator.do_command(master_api.write_setpoint(),
            { 'thermostat' : thermostat, 'config' : setpoint + 1,
              'temp' : master_api.Svt.temp(temperature) })
        ret['temp'] = ret['temp'].get_temperature()
        return ret
        
    
    def set_current_setpoint(self, thermostat, temperature):
        """ Set the current setpoint of a thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param temperature: The temperature to set in degrees Celcius
        :type temperature: float
        :returns: dict with 'thermostat', 'config' and 'temp'
        """
        if thermostat not in range(0, 25):
            raise ValueError("Thermostat not in [0,24]: %d" % thermostat)
        ret = self.__master_communicator.do_command(master_api.write_setpoint(),
            { 'thermostat' : thermostat, 'config' : 0, 'temp' : master_api.Svt.temp(temperature) })
        ret['temp'] = ret['temp'].get_temperature()
        return ret
    
    def set_setpoint_start_time(self, thermostat, day_of_week, setpoint, time):
        """ Set the start time of setpoint 0 or 2 for a certain day of the week and thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param day_of_week: The day of the week
        :type day_of_week: Integer [1, 7]
        :param setpoint: The id of the setpoint to set
        :type setpoint: Integer: 0 or 2
        :param time: The start or end (see start) time of the interval
        :type time: String HH:MM format
        
        :returns: dict with 'thermostat', 'config' and 'temp'
        """
        return self.__set_setpoint_time(thermostat, day_of_week, setpoint, time, True)
    
    def set_setpoint_stop_time(self, thermostat, day_of_week, setpoint, time):
        """ Set the stop time of setpoint 0 or 2 for a certain day of the week and thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param day_of_week: The day of the week
        :type day_of_week: Integer [1, 7]
        :param setpoint: The id of the setpoint to set
        :type setpoint: Integer: 0 or 2
        :param time: The start or end (see start) time of the interval
        :type time: String HH:MM format
        
        :returns: dict with 'thermostat', 'config' and 'temp'
        """
        return self.__set_setpoint_time(thermostat, day_of_week, setpoint, time, False)
        
    def __set_setpoint_time(self, thermostat, day_of_week, setpoint, time, start):
        """ Set the start or stop time (boolean start) of setpoint 0 or 2 for a certain day of the
        week and thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param day_of_week: The day of the week
        :type day_of_week: Integer [1, 7]
        :param setpoint: The id of the setpoint to set
        :type setpoint: Integer: 0 or 2
        :param time: The start or end (see start) time of the interval
        :type time: String HH:MM format
        :param start: Set the start time if True, set the end time if False
        :type start: boolean
        
        :returns: dict with 'thermostat', 'config' and 'temp'
        """
        if setpoint != 0 and setpoint != 2:
            raise ValueError("Setpoint is not 0 nor 2: %d" % setpoint)
        if day_of_week not in range(1, 8):
            raise ValueError("Day of week not in [1, 7]: %d" % day_of_week)
    
        config_point = 18 + ((day_of_week-1) * 4)
        config_point += 0 if start else 1
        config_point += setpoint
        
        ret = self.__master_communicator.do_command(master_api.write_setpoint(),
            { 'thermostat' : thermostat, 'config' : config_point,
              'temp' : master_api.Svt.time(time) })
        ret['temp'] = ret['temp'].get_time()
        return ret
    
    def set_thermostat_mode(self, thermostat_on, automatic, setpoint):
        """ Set the mode of the thermostats. Thermostats can be on or off, automatic or manual
        and is set to one of the 6 setpoints.
        
        :param thermostat_on: Whether the thermostats are on
        :type thermostat_on: boolean
        :param automatic: Automatic mode (True) or Manual mode (False)
        :type automatic: boolean
        :param setpoint: The current setpoint
        :type setpoint: Integer [0, 5]
        
        :returns: dict with 'resp'
        """
        def checked(ret_dict):
            if ret_dict['resp'] != 'OK':
                raise ValueError("Setting thermostat mode did not return OK !")
        
        if setpoint not in range(0, 6):
            raise ValueError("Setpoint not in [0,5]: " + str(setpoint))
        mode = 128 if thermostat_on else 0
        mode += 8 if automatic else 0
        mode += setpoint
        checked(self.__master_communicator.do_command(master_api.basic_action(),
            { 'action_type' : master_api.BA_THERMOSTAT_MODE, 'action_number' : mode }))
        
        checked(self.__master_communicator.do_command(master_api.basic_action(),
                { 'action_type' : master_api.BA_THERMOSTAT_AUTOMATIC, 'action_number' : 255 }))
        
        if not automatic:
            checked(self.__master_communicator.do_command(master_api.basic_action(),
                { 'action_type' : master_api.__dict__['BA_ALL_SETPOINT_' + str(setpoint)],
                  'action_number' : 0 }))
            
            checked(self.__master_communicator.do_command(master_api.basic_action(),
                { 'action_type' : master_api.BA_THERMOSTAT_AUTOMATIC, 'action_number' : 0 }))
        
        return { 'resp': 'OK' }

    def set_thermostat_threshold(self, threshold):
        """ Set the outside temperature threshold of the thermostats.
        
        :param threshold: Temperature in degrees celcius
        :type threshold: integer
        
        :returns: dict with 'resp'
        """
        self.__master_communicator.do_command(master_api.write_eeprom(),
            { "bank" : 0, "address": 17, "data": master_api.Svt.temp(threshold).get_byte() })
        
        self.__master_communicator.do_command(master_api.activate_eeprom(), { 'eep' : 0 })
        return { 'resp': 'OK' }
        

    ###### Backup and restore functions
    
    def get_master_backup(self):
        """ Get a backup of the eeprom of the master.
        
        :returns: String of bytes (size = 64kb). 
        """
        output = ""
        for bank in range(0, 256):
            output += self.__master_communicator.do_command(master_api.eeprom_list(),
                { 'bank' : bank })['data']
        return output
    
    def master_restore(self, data):
        """ Restore a backup of the eeprom of the master.
        
        :param data: The eeprom backup to restore.
        :type data: string of bytes (size = 64 kb).
        :returns: dict with 'output' key (contains an array with the addresses that were written). 
        """
        ret = []
        (num_banks, bank_size, write_size) = (256, 256, 10)
 
        for bank in range(0, num_banks):
            read = self.__master_communicator.do_command(master_api.eeprom_list(),
                                                         { 'bank' : bank })['data']
            for addr in range(0, bank_size, write_size):
                orig = read[addr:addr + write_size]
                new = data[bank * bank_size + addr : bank * bank_size + addr + len(orig)]
                if new != orig:
                    ret.append("B" + str(bank) + "A" + str(addr))
                    
                    self.__master_communicator.do_command(master_api.write_eeprom(),
                        { 'bank': bank, 'address': addr, 'data': new })
                    
        self.__master_communicator.do_command(master_api.activate_eeprom(), { 'eep' : 0 })
        ret.append("Activated eeprom")
        
        return { 'output' : ret }

    def master_reset(self):
        """ Reset the master.
        
        :returns: emtpy dict.
        """
        self.__master_communicator.do_command(master_api.reset())
        return dict()
