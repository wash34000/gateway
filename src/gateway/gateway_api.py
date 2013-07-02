'''
The GatewayApi defines high level functions, these are used by the interface
and call the master_api to complete the actions. 

Created on Sep 16, 2012

@author: fryckbos
'''
import logging
LOGGER = logging.getLogger("openmotics")

import time as pytime
import datetime
import traceback
import math
from threading import Timer

from serial_utils import CommunicationTimedOutException

import master.master_api as master_api
from master.outputs import OutputStatus
from master.inputs import InputStatus
from master.thermostats import ThermostatStatus
from master.master_communicator import BackgroundConsumer

import power.power_api as power_api

def checkNaN(number):
    """ Convert NaN to 0. """
    return 0.0 if math.isnan(number) else number

class GatewayApi:
    """ The GatewayApi combines master_api functions into high level functions. """
    
    def __init__(self, master_communicator, power_communicator, power_controller):
        self.__master_communicator = master_communicator
    
        self.__last_maintenance_send_time = 0
        self.__maintenance_timeout_timer = None
        
        self.__output_status = None
        self.__master_communicator.register_consumer(
                    BackgroundConsumer(master_api.output_list(), 0, self.__update_outputs))
        
        self.__input_status = InputStatus()
        self.__master_communicator.register_consumer(
                    BackgroundConsumer(master_api.input_list(), 0, self.__update_inputs))
        
        self.__thermostat_status = None
        
        self.__power_communicator = power_communicator
        self.__power_controller = power_controller
        
        self.init_master()    
        self.__run_master_timer()
    
    def init_master(self):
        """ Initialize the master: disable the async RO messages, enable async OL messages. """
        try:
            eeprom_data = self.__master_communicator.do_command(master_api.eeprom_list(),
                { "bank" : 0 })['data']
            
            write = False
            
            if eeprom_data[11] != chr(255):
                LOGGER.info("Disabling async RO messages.")
                self.__master_communicator.do_command(master_api.write_eeprom(),
                    { "bank" : 0, "address": 11, "data": chr(255) })
                write = True
            
            if eeprom_data[18] != chr(0):
                LOGGER.info("Enabling async OL messages.")
                self.__master_communicator.do_command(master_api.write_eeprom(),
                    { "bank" : 0, "address": 18, "data": chr(0) })
                write = True
            
            if eeprom_data[20] != chr(0):
                LOGGER.info("Enabling async IL messages.")
                self.__master_communicator.do_command(master_api.write_eeprom(),
                    { "bank" : 0, "address": 20, "data": chr(0) })
                write = True
            
            if write:
                self.__master_communicator.do_command(master_api.activate_eeprom(), { 'eep' : 0 })
            
        except CommunicationTimedOutException:
            LOGGER.error("Got CommunicationTimedOutException during gateway_api initialization.")
    
    def __run_master_timer(self):
        """ Run the master timer, this sets the masters clock every day at 2:01am and 3:01 am. """
        self.sync_master_time()
        
        # Calculate the time to sleep until the next sync.
        now = datetime.datetime.now()
        today = datetime.datetime(now.year, now.month, now.day)
        if now.hour < 3: # Check again at 3:01 am
            next_check = today + datetime.timedelta(0, 3600 * 3 + 60)
        else:
            next_check = today + datetime.timedelta(1, 3600 * 2 + 60)
        
        to_sleep = (next_check - now).seconds
        if to_sleep <= 0:
            to_sleep = 60 
        
        Timer(to_sleep, self.__run_master_timer).start()
    
    def sync_master_time(self):
        """ Set the time on the master. """
        LOGGER.info("Setting the time on the master.")
        now = datetime.datetime.now()
        try:
            self.__master_communicator.do_command(master_api.set_time(), 
                      {'sec': now.second, 'min': now.minute, 'hours': now.hour,
                       'weekday': now.isoweekday(), 'day': now.day, 'month': now.month,
                       'year': now.year % 100 })
        except:
            LOGGER.error("Got error while setting the time on the master.")
            traceback.print_exc()
    
    ###### Maintenance functions
    
    def start_maintenance_mode(self, timeout=600):
        """ Start maintenance mode, if the time between send_maintenance_data calls exceeds the
        timeout, the maintenance mode will be closed automatically. """
        try:
            self.set_master_status_leds(True)
        except Exception as exception:
            msg = "Exception while setting status leds before maintenance mode:" + str(exception)
            LOGGER.warning(msg)
            
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
        if self.__output_status != None:
            self.__output_status.force_refresh()
        
        if self.__thermostat_status != None:
            self.__thermostat_status.force_refresh()
        
        if self.__maintenance_timeout_timer != None:
            self.__maintenance_timeout_timer.cancel()
            self.__maintenance_timeout_timer = None
        
        try:
            self.set_master_status_leds(False)
        except Exception as exception:
            msg = "Exception while setting status leds after maintenance mode:" + str(exception)
            LOGGER.warning(msg)
    
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
    
    def set_output_floor_level(self, output_nr, floor_level):
        """ Set the floor level of an output. 
        
        :param output_nr: The id of the output to set
        :type output_nr: Integer [0, 240]
        :param floor_level: The new floor level
        :type floor_level: Integer
        :returns: empty dict.
        """
        if output_nr < 0 or output_nr > 240:
            raise ValueError("Output_nr not in [0, 240]: %d" % output_nr)
        
        module = output_nr / 8
        output = output_nr % 8
        
        self.__master_communicator.do_command(master_api.write_eeprom(),
            { "bank" : 33 + module, "address": 157 + output, "data": chr(floor_level) })
        
        # Make sure the floor level is updated on the next get_outputs
        if self.__output_status != None:
            self.__output_status.force_refresh()
        
        return dict()
        
    
    def set_all_lights_off(self):
        """ Turn all lights off.
        
        :returns: empty dict.
        """
        self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : master_api.BA_ALL_LIGHTS_OFF, "action_number" : 0 })
        
        return dict()
    
    def set_all_lights_floor_off(self, floor):
        """ Turn all lights on a given floor off.
        
        :returns: empty dict.
        """
        self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : master_api.BA_LIGHTS_OFF_FLOOR, "action_number" : floor })
        
        return dict()
    
    def set_all_lights_floor_on(self, floor):
        """ Turn all lights on a given floor on.
        
        :returns: empty dict.
        """
        self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : master_api.BA_LIGHTS_ON_FLOOR, "action_number" : floor })
        
        return dict()
    
    ###### Input functions
    
    def __update_inputs(self, api_data):
        """ Update the InputStatus with data from an IL message. """
        self.__input_status.add_data((api_data['input'], api_data['output']))
    
    def get_last_inputs(self):
        """ Get the 5 last pressed inputs during the last 5 minutes. 
        
        :returns: a list of tuples (input, output).
        """
        return self.__input_status.get_status()
    
    ###### Thermostat functions
    
    def get_thermostats(self):
        """ Get the configuration of the thermostats.
        
        :returns: dict with global status information about the thermostats: 'thermostats_on',
        'automatic' and 'setpoint' and a list ('thermostats') with status information for each
        active thermostats, each element in the list is a dict with the following keys:
        'thermostat', 'act', 'csetp', 'psetp0', 'psetp1', 'psetp2', 'psetp3', 'psetp4', 'psetp5',
        'sensor_nr', 'output0_nr', 'output1_nr', 'output0', 'output1', 'outside', 'mode', 'name',
        'pid_p', 'pid_i', 'pid_d', 'pid_ithresh', 'threshold_temp', 'days', 'hours', 'minutes',
        'mon_start_d1', 'mon_stop_d1', 'mon_start_d2', 'mon_stop_d2', 'tue_start_d1', 'tue_stop_d1',
        'tue_start_d2', 'tue_stop_d2', 'wed_start_d1', 'wed_stop_d1', 'wed_start_d2', 'wed_stop_d2',
        'thu_start_d1', 'thu_stop_d1', 'thu_start_d2', 'thu_stop_d2', 'fri_start_d1', 'fri_stop_d1',
        'fri_start_d2', 'fri_stop_d2', 'sat_start_d1', 'sat_stop_d1', 'sat_start_d2', 'sat_stop_d2',
        'sun_start_d1', 'sun_stop_d1', 'sun_start_d2', 'sun_stop_d2', 'mon_temp_d1', 'tue_temp_d1',
        'wed_temp_d1', 'thu_temp_d1', 'fri_temp_d1', 'sat_temp_d1', 'sun_temp_d1', 'mon_temp_d2',
        'tue_temp_d2', 'wed_temp_d2', 'thu_temp_d2', 'fri_temp_d2', 'sat_temp_d2', 'sun_temp_d2',
        'mon_temp_n', 'tue_temp_n', 'wed_temp_n', 'thu_temp_n', 'fri_temp_n', 'sat_temp_n',
        'sun_temp_n'.
        """
        mode = self.__master_communicator.do_command(master_api.thermostat_mode())['mode']
        
        thermostats_on = (mode & 128 == 128)
        automatic = (mode & 8 == 8)
        setpoint = (mode & 7)
        
        thermostats = []
        for thermostat_id in range(0, 24):
            thermostat = self.__master_communicator.do_command(master_api.read_setpoint(),
                            { 'thermostat' :  thermostat_id })
            
            # Check if the thermostat is activated
            if (thermostat['sensor_nr'] < 30 or thermostat['sensor_nr'] == 240) and thermostat['output0_nr'] < 240:
                # Convert the Svt temperature instances into temperatures
                for temperature_key in [ 'act', 'csetp', 'psetp0', 'psetp1', 'psetp2', 'psetp3',
                                         'psetp4', 'psetp5', 'outside', 'threshold_temp',
                                         'mon_temp_d1', 'tue_temp_d1', 'wed_temp_d1', 'thu_temp_d1',
                                         'fri_temp_d1', 'sat_temp_d1', 'sun_temp_d1', 'mon_temp_d2',
                                         'tue_temp_d2', 'wed_temp_d2', 'thu_temp_d2', 'fri_temp_d2',
                                         'sat_temp_d2', 'sun_temp_d2', 'mon_temp_n', 'tue_temp_n',
                                         'wed_temp_n', 'thu_temp_n', 'fri_temp_n', 'sat_temp_n',
                                         'sun_temp_n' ]:
                    thermostat[temperature_key] = thermostat[temperature_key].get_temperature()
                
                # Convert the Svt time instances into times (HH:MM)
                for time_key in [ 'mon_start_d1', 'mon_stop_d1', 'mon_start_d2', 'mon_stop_d2',
                                  'tue_start_d1', 'tue_stop_d1', 'tue_start_d2', 'tue_stop_d2',
                                  'wed_start_d1', 'wed_stop_d1', 'wed_start_d2', 'wed_stop_d2',
                                  'thu_start_d1', 'thu_stop_d1', 'thu_start_d2', 'thu_stop_d2',
                                  'fri_start_d1', 'fri_stop_d1', 'fri_start_d2', 'fri_stop_d2',
                                  'sat_start_d1', 'sat_stop_d1', 'sat_start_d2', 'sat_stop_d2',
                                  'sun_start_d1', 'sun_stop_d1', 'sun_start_d2', 'sun_stop_d2' ]:
                    thermostat[time_key] = thermostat[time_key].get_time()
                
                for output_key in [ 'output0', 'output1' ]:
                    thermostat[output_key] = master_api.dimmer_to_percentage(thermostat[output_key])
                
                thermostats.append(thermostat)

        return { 'thermostats_on' : thermostats_on, 'automatic' : automatic,
                 'setpoint' : setpoint, 'thermostats' : thermostats }
    
    def __get_all_thermostats(self):
        """ Get basic information about all thermostats.
        
        :returns: array containing 24 dicts (one for each thermostats) with the following keys: \
        'active', 'sensor_nr', 'output0_nr', 'output1_nr', 'name'.
        """
        thermostats = []
        for thermostat_id in range(0, 24):
            thermostat = self.__master_communicator.do_command(master_api.read_setpoint(),
                                                               { 'thermostat' :  thermostat_id })
            info = {}
            info['active'] = (thermostat['sensor_nr'] < 30 or thermostat['sensor_nr'] == 240) and thermostat['output0_nr'] < 240
            info['sensor_nr'] = thermostat['sensor_nr']
            info['output0_nr'] = thermostat['output0_nr']
            info['output1_nr'] = thermostat['output1_nr']
            info['name'] = thermostat['name']
            
            thermostats.append(info)
        
        return thermostats
    
    def get_thermostats_short(self):
        """ Get the short configuration of the thermostats.
        
        :returns: dict with global status information about the thermostats: 'thermostats_on',
        'automatic' and 'setpoint' and a list ('thermostats') with status information for all
        thermostats, each element in the list is a dict with the following keys:
        'thermostat', 'act', 'csetp', 'output0', 'output1', 'outside', 'mode', 'name', 'sensor_nr'.
        """
        if self.__thermostat_status == None:
            self.__thermostat_status = ThermostatStatus(self.__get_all_thermostats(), 1800)
        elif self.__thermostat_status.should_refresh():
            self.__thermostat_status.update(self.__get_all_thermostats())
        cached_thermostats = self.__thermostat_status.get_thermostats()
        
        thermostat_info = self.__master_communicator.do_command(master_api.thermostat_list())
        
        mode = thermostat_info['mode']
        
        thermostats_on = (mode & 128 == 128)
        automatic = (mode & 8 == 8)
        setpoint = (mode & 7)
        
        thermostats = []
        outputs = self.get_outputs()
        
        for thermostat_id in range(0, 24):
            if cached_thermostats[thermostat_id]['active'] == True:
                thermostat = { 'thermostat' : thermostat_id }
                thermostat['act'] = thermostat_info['tmp' + str(thermostat_id)].get_temperature()
                thermostat['csetp'] = thermostat_info['setp' + str(thermostat_id)].get_temperature()
                thermostat['outside'] = thermostat_info['outside'].get_temperature()
                thermostat['mode'] = thermostat_info['mode']
                
                output0_nr = cached_thermostats[thermostat_id]['output0_nr']
                if output0_nr < len(outputs) and outputs[output0_nr]['status'] == 1:
                    thermostat['output0'] = outputs[output0_nr]['dimmer']
                else:
                    thermostat['output0'] = 0
                
                output1_nr = cached_thermostats[thermostat_id]['output1_nr']
                if output1_nr < len(outputs) and outputs[output1_nr]['status'] == 1:
                    thermostat['output1'] = outputs[output1_nr]['dimmer']
                else:
                    thermostat['output1'] = 0
                
                thermostat['name'] = cached_thermostats[thermostat_id]['name']
                thermostat['sensor_nr'] = cached_thermostats[thermostat_id]['sensor_nr']
                
                thermostats.append(thermostat)
        
        return { 'thermostats_on' : thermostats_on, 'automatic' : automatic,
                 'setpoint' : setpoint, 'thermostats' : thermostats }
    
    def __check_thermostat(self, thermostat):
        """ :raises ValueError if thermostat not in range [0, 24]. """
        if thermostat not in range(0, 25):
            raise ValueError("Thermostat not in [0,24]: %d" % thermostat)
    
    def __check_day_of_week(self, day_of_week):
        """ :raises ValueError if day_of_week not in range [1, 7]. """
        if day_of_week not in range(1, 8):
            raise ValueError("Day of week not in [1, 7]: %d" % day_of_week)
    
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
        self.__check_thermostat(thermostat)
        if setpoint not in range(0, 6):
            raise ValueError("Setpoint not in [0,5]: %d" % setpoint)
        
        ret = self.__master_communicator.do_command(master_api.write_setpoint(),
            { 'thermostat' : thermostat, 'config' : setpoint + 1,
              'temp' : master_api.Svt.temp(temperature) })
        ret['temp'] = ret['temp'].get_temperature()
        
        # If we are currently in manual mode and in this setpoint, set the mode to update to the new
        # configuration value.
        mode = self.__master_communicator.do_command(master_api.thermostat_mode())['mode']
        (on, automatic, csetp) = (mode & 128 == 128, mode & 8 == 8, mode & 7) 
        
        if not automatic and csetp == setpoint:
            self.set_thermostat_mode(on, automatic, csetp)
        
        return ret
    
    def set_current_setpoint(self, thermostat, temperature):
        """ Set the current setpoint of a thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param temperature: The temperature to set in degrees Celcius
        :type temperature: float
        :returns: dict with 'thermostat', 'config' and 'temp'
        """
        self.__check_thermostat(thermostat)
        
        ret = self.__master_communicator.do_command(master_api.write_setpoint(),
            { 'thermostat' : thermostat, 'config' : 0, 'temp' : master_api.Svt.temp(temperature) })
        ret['temp'] = ret['temp'].get_temperature()
        
        return ret
    
    def set_thermostat_automatic_configuration(self, thermostat, day_of_week, temperature_night,
                                          start_time_day1, stop_time_day1, temperature_day1,
                                          start_time_day2, stop_time_day2, temperature_day2):
        """ Set the configuration for automatic mode for a certain thermostat for a given day of 
        the week. This contains the night and 2 day temperatures and the start and stop times for
        the 2 day periods.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param day_of_week: The day of the week
        :type day_of_week: Integer [1, 7]
        :param temperature_night: The low temperature (in degrees Celcius)
        :type temperature_night: float
        :param start_time_day1: The start time of the first high period.
        :type start_time_day1: String HH:MM format
        :param stop_time_day1: The stop time of the first high period.
        :type stop_time_day1: String HH:MM format
        :param temperature_day1: The temperature for the first high interval (in degrees Celcius)
        :type temperature_day1: float
        :param start_time_day2: The start time of the second high period.
        :type start_time_day2: String HH:MM format
        :param stop_time_day2: The stop time of the second high period.
        :type stop_time_day2: String HH:MM format
        :param temperature_day2: The temperature for the second high interval (in degrees Celcius)
        :type temperature_day2: float
        :return: empty dict
        """
        self.__check_thermostat(thermostat)
        self.__check_day_of_week(day_of_week)
        
        day_of_week = day_of_week - 1
        
        for config in [ (18 + day_of_week * 4 + 0, master_api.Svt.time(start_time_day1)),
                        (18 + day_of_week * 4 + 1, master_api.Svt.time(stop_time_day1)),
                        (18 + day_of_week * 4 + 2, master_api.Svt.time(start_time_day2)),
                        (18 + day_of_week * 4 + 3, master_api.Svt.time(stop_time_day2)),
                        (46 + day_of_week,         master_api.Svt.temp(temperature_day1)),
                        (53 + day_of_week,         master_api.Svt.temp(temperature_day2)),
                        (60 + day_of_week,         master_api.Svt.temp(temperature_night)) ]:
            self.__master_communicator.do_command(master_api.write_setpoint(),
                { 'thermostat' : thermostat, 'config' : config[0], 'temp' : config[1] })
        
        # If we are currently in automatic mode, set the mode to update to the new
        # configuration value.
        mode = self.__master_communicator.do_command(master_api.thermostat_mode())['mode']
        (on, automatic, csetp) = (mode & 128 == 128, mode & 8 == 8, mode & 7) 
        
        if automatic:
            self.set_thermostat_mode(on, automatic, csetp)
        
        return dict()
    
    def set_thermostat_automatic_configuration_batch(self, batch):
        """ Set a batch of automatic configurations. For more info see
        set_thermostat_automatic_configuration.
        
        :param batch: array of dictionaries with keys 'thermostat', 'day_of_week', \
        'temperature_night', 'start_time_day1', 'stop_time_day1', 'temperature_day1', \
        'start_time_day2', 'stop_time_day2', 'temperature_day2'.
        """
        for settings in batch:
            self.__check_thermostat(settings['thermostat'])
            self.__check_day_of_week(settings['day_of_week'])
        
        for settings in batch:
            self.set_thermostat_automatic_configuration(
                settings['thermostat'], settings['day_of_week'], settings['temperature_night'],
                settings['start_time_day1'], settings['stop_time_day1'],
                settings['temperature_day1'], settings['start_time_day2'],
                settings['stop_time_day2'], settings['temperature_day2'])
    
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
        
        if automatic:
            checked(self.__master_communicator.do_command(master_api.basic_action(),
                    { 'action_type' : master_api.BA_THERMOSTAT_AUTOMATIC, 'action_number' : 255 }))
        else:
            checked(self.__master_communicator.do_command(master_api.basic_action(),
                { 'action_type' : master_api.BA_THERMOSTAT_AUTOMATIC, 'action_number' : 0 }))
            
            checked(self.__master_communicator.do_command(master_api.basic_action(),
                { 'action_type' : master_api.__dict__['BA_ALL_SETPOINT_' + str(setpoint)],
                  'action_number' : 0 }))
        
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
        

    ###### Group actions
    
    def do_group_action(self, group_action_id):
        """ Execute a group action.
        
        :param group_action_id: The id of the group action
        :type group_action_id: Integer (0 - 159)
        :returns: empty dict.
        """
        if group_action_id < 0 or group_action_id > 159:
            raise ValueError("group_action_id not in [0, 160]: %d" % group_action_id)
        
        self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : master_api.BA_GROUP_ACTION,
                      "action_number" : group_action_id })
        
        return dict()

    def get_group_actions(self):
        """ Get the id and names of the available group actions.
        
        :returns: array with dicts containing 'id' and 'name'.
        """
        group_actions = []
        
        names = []
        for bank in range(158, 168):
            data = self.__master_communicator.do_command(master_api.eeprom_list(),
                { 'bank' : bank })['data']
            for offset in range(0, 256, 16):
                names.append(data[offset:offset+16].replace('\xff', ''))
        
        for id in range(0, 160):
            group_actions.append({ 'id':id, 'name':names[id] })
                    
        return group_actions

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

    ###### Status led functions
    
    def set_master_status_leds(self, status):
        """ Set the status of the leds on the master.
        
        :param status: whether the leds should be on or off.
        :type status: boolean.
        :returns: empty dict.
        """
        on = 1 if status == True else 0
        self.__master_communicator.do_command(master_api.basic_action(),
                    { "action_type" : master_api.BA_STATUS_LEDS, "action_number" : on })
        return dict()

    ###### Pulse counter functions
    
    def get_pulse_counters(self):
        """ Get the id, name, linked input and count value of the pulse counters.
        
        :returns: array with dicts containing 'id', 'name', 'input' and 'count'. 
        """
        pulse_counters = []
        
        name_data = self.__master_communicator.do_command(master_api.eeprom_list(),
                                                     { 'bank' : 195 })['data']
        
        input_data = self.__master_communicator.do_command(master_api.eeprom_list(),
                                                           { 'bank' : 0 })['data']

        value_data = self.__master_communicator.do_command(master_api.pulse_list())

        for id in range(0, 8):
            input = ord(input_data[160+id])
            if input != 255:
                pulse_counters.append({ 'id':id, 
                                        'name': name_data[id*16:(id+1)*16].replace('\xff', ''),
                                        'input': ord(input_data[160+id]),
                                        'count': value_data['pv%d'%id] })
        
        return pulse_counters
    
    def get_pulse_counter_values(self):
        """ Get the pulse counter values.
        
        :returns: array with the 8 pulse counter values.
        """
        out_dict = self.__master_communicator.do_command(master_api.pulse_list())
        return [ out_dict['pv0'], out_dict['pv1'], out_dict['pv2'], out_dict['pv3'],
                 out_dict['pv4'], out_dict['pv5'], out_dict['pv6'], out_dict['pv7'] ]

    ###### Power functions
    
    def get_power_modules(self):
        """ Get information on the power modules.
        
        :returns: List of dictionaries with the following keys: 'id', 'name', 'address', \
        'input0', 'input1', 'input2', 'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', \
        'sensor1', 'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', 'times0', \
        'times1', 'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        """
        modules = self.__power_controller.get_power_modules().values();
        def translate_address(module):
            module['address'] = "E" + str(module['address'])
            return module
        return map(translate_address, modules)
    
    def set_power_modules(self, modules):
        """ Set information for the power modules.
        
        :param modules: list of dicts with keys: 'id', 'name', 'input0', 'input1', \
        'input2', 'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', 'sensor1', \
        'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', 'times0', 'times1', \
        'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        :returns: empty dict.
        """
        for module in modules:
            self.__power_controller.update_power_module(module)
            addr = self.__power_controller.get_address(module['id'])
            
            self.__power_communicator.do_command(addr, power_api.set_sensor_types(),
                    module["sensor0"], module["sensor1"], module["sensor2"], module["sensor3"],
                    module["sensor4"], module["sensor5"], module["sensor6"], module["sensor7"])
        
        return dict()
    
    def get_realtime_power(self):
        """ Get the realtime power measurement values.
        
        :returns: dict with the module id as key and the following array as value: \
        [voltage, frequency, current, power].
        """
        output = dict()
        
        modules = self.__power_controller.get_power_modules()
        for id in sorted(modules.keys()):
            addr = modules[id]['address']
            
            volt = self.__power_communicator.do_command(addr, power_api.get_voltage())[0]
            freq = self.__power_communicator.do_command(addr, power_api.get_frequency())[0]
            current = self.__power_communicator.do_command(addr, power_api.get_current())
            power = self.__power_communicator.do_command(addr, power_api.get_power())
            
            out = []
            for i in range(0, 8):
                out.append([ checkNaN(volt), checkNaN(freq), checkNaN(current[i]),
                             checkNaN(power[i]) ])
            
            output[str(id)] = out
        
        return output
    
    def get_total_energy(self):
        """ Get the total energy (kWh) consumed by the power modules.
        
        :returns: dict with the module id as key and the following array as value: [day, night]. 
        """
        output = dict()
        
        modules = self.__power_controller.get_power_modules()
        for id in sorted(modules.keys()):
            addr = modules[id]['address']
            
            day = self.__power_communicator.do_command(addr, power_api.get_day_energy())
            night = self.__power_communicator.do_command(addr, power_api.get_night_energy())
            
            out = []
            for i in range(0, 8):
                out.append([ checkNaN(day[i]), checkNaN(night[i]) ])
            
            output[str(id)] = out
        
        return output
    
    def start_power_address_mode(self):
        """ Start the address mode on the power modules.
        
        :returns: empty dict.
        """
        self.__power_communicator.start_address_mode()
        return dict()
    
    def stop_power_address_mode(self):
        """ Stop the address mode on the power modules.
        
        :returns: empty dict
        """
        self.__power_communicator.stop_address_mode()
        return dict()

    def in_power_address_mode(self):
        """ Check if the power modules are in address mode
        
        :returns: dict with key 'address_mode' and value True or False.
        """
        return { 'address_mode' : self.__power_communicator.in_address_mode() }

    def set_power_voltage(self, module_id, voltage):
        """ Set the voltage for a given module.
        
        :param module_id: The id of the power module.
        :param voltage: The voltage to set for the power module.
        :returns: empty dict
        """
        addr = self.__power_controller.get_address(module_id)
        self.__power_communicator.do_command(addr, power_api.set_voltage(), voltage)
        return dict()
