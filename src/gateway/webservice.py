""" Includes the WebService class """
import threading
import random
import ConfigParser
import subprocess
import os
from types import MethodType
import traceback

try:
    import json
except ImportError:
    import simplejson as json

class FloatWrapper(float):
    """ Wrapper for float value that limits the number of digits when printed. """
     
    def __repr__(self):
        return '%.2f' % self

def limit_floats(struct):
    """ Usage: json.dumps(limit_floats(struct)). This limits the number of digits in the json
    string.
    """
    if isinstance(struct, (list, tuple)):
        return map(limit_floats, struct)
    elif isinstance(struct, dict):
        return dict((key, limit_floats(value)) for key, value in struct.items())
    elif isinstance(struct, float):
        return FloatWrapper(struct)
    else:
        return struct

import cherrypy

import constants
from master.master_communicator import InMaintenanceModeException

class GatewayApiWrapper:
    """ Wraps the GatewayApi, catches the InMaintenanceModeException and converts
    the exception in a HttpError(503).
    """
    
    def __init__(self, gateway_api):
        self.__gateway_api = gateway_api

    def __getattr__(self, name):
        if hasattr(self.__gateway_api, name):
            return lambda *args, **kwargs: \
                    self._wrap(getattr(self.__gateway_api, name), args, kwargs)
        else:
            raise AttributeError(name)

    def _wrap(self, func, args, kwargs):
        """ Wrap a function, convert the InMaintenanceModeException to a HttpError(503). """
        try:
            if type(func) == MethodType:
                result = func(*args, **kwargs) #pylint: disable-msg=W0142
            else:
                result = func(self.__gateway_api, *args, **kwargs) #pylint: disable-msg=W0142
            return result
        except InMaintenanceModeException:
            raise cherrypy.HTTPError(503, "In maintenance mode")


class WebInterface:
    """ This class defines the web interface served by cherrypy. """

    def __init__(self, user_controller, gateway_api, maintenance_service, authorized_check):
        """ Constructor for the WebInterface.
        
        :param user_controller: used to create and authenticate users.
        :type user_controller: instance of :class`UserController`.
        :param gateway_api: used to communicate with the master.
        :type gateway_api: instance of :class`GatewayApi`.
        :param maintenance_service: used when opening maintenance mode.
        :type maintenance_server: instance of :class`MaintenanceService`.
        :param authorized_check: check if the gateway is in authorized mode.
        :type authorized_check: function (called without arguments).
        """
        self.__user_controller = user_controller
        self.__gateway_api = GatewayApiWrapper(gateway_api)
        self.__maintenance_service = maintenance_service
        self.__authorized_check = authorized_check

    def __check_token(self, token):
        """ Check if the token is valid, raises HTTPError(401) if invalid. """
        if cherrypy.request.remote.ip == '127.0.0.1':
            # Don't check tokens for localhost
            return
        if not self.__user_controller.check_token(token):
            raise cherrypy.HTTPError(401, "Unauthorized")

    def __error(self, msg):
        """ Returns a dict with 'success' = False and a 'msg' in json format. """
        return json.dumps({"success": False, "msg": msg})
    
    def __success(self, **kwargs):
        """ Returns a dict with 'success' = True and the keys and values in **kwargs. """
        return json.dumps(limit_floats(dict({"success" : True}.items() + kwargs.items())))

    @cherrypy.expose
    def index(self):
        """ Index page of the web service.
        
        :returns: msg (String)
        """
        return self.__success(msg="OpenMotics is up and running !")
    
    @cherrypy.expose
    def login(self, username, password):
        """ Login to the web service, returns a token if successful, 401 otherwise.
        
        :returns: token (String)
        """
        token = self.__user_controller.login(username, password)
        if token == None:
            raise cherrypy.HTTPError(401, "Unauthorized")
        else:
            return self.__success(token=token)

    @cherrypy.expose
    def create_user(self, username, password):
        """ Create a new user using a username and a password. """
        if self.__authorized_check():
            self.__user_controller.create_user(username, password, 'admin', True)
            return self.__success()
        else:
            raise cherrypy.HTTPError(401, "Unauthorized")

    @cherrypy.expose
    def open_maintenance(self, token):
        """ Open maintenance mode, return the port of the maintenance socket.
        
        :returns: dict with key 'port' (Integer between 6000 and 7000)
        """
        self.__check_token(token)
        
        port = random.randint(6000, 7000)
        self.__maintenance_service.start_in_thread(port)
        return self.__success(port=port)

    @cherrypy.expose
    def get_status(self, token):
        """ Get the status of the master.
        
        :returns: dict with keys 'time' (HH:MM), 'date' (DD:MM:YYYY), 'mode', 'version' (a.b.c) \
        and 'hw_version' (hardware version)
        """
        self.__check_token(token)
        return self.__success(**self.__gateway_api.get_status())

    @cherrypy.expose
    def get_outputs(self, token):
        """ Get the status of the master.
        
        :returns: dict with key 'outputs' (List of dictionaries with the following keys: output_nr,\
        name, floor_level, light, type, controller_out, timer, ctimer, max_power, status and dimmer.
        """
        self.__check_token(token)
        return self.__success(outputs=self.__gateway_api.get_outputs())
    
    @cherrypy.expose
    def set_output(self, token, output_nr, is_on, dimmer=None, timer=None):
        """ Set the status, dimmer and timer of an output. 
        
        :param output_nr: The id of the output to set
        :type output_nr: Integer [0, 240]
        :param is_on: Whether the output should be on
        :type is_on: Boolean
        :param dimmer: The dimmer value to set, None if unchanged
        :type dimmer: Integer [0, 100] or None
        :param timer: The timer value to set, None if unchanged
        :type timer: Integer in [150, 450, 900, 1500, 2220, 3120]
        :returns: dict with success field.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_output(
                                        int(output_nr), is_on.lower() == "true",
                                        int(dimmer) if dimmer is not None else None,
                                        int(timer) if timer is not None else None))
    
    @cherrypy.expose
    def set_output_floor_level(self, token, output_nr, floor_level):
        """ Set the floor level of an output. 
        
        :param output_nr: The id of the output to set
        :type output_nr: Integer [0, 240]
        :param floor_level: The new floor level
        :type floor_level: Integer
        :returns: empty dict.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_output_floor_level(
                                        int(output_nr), int(floor_level)))
    
    @cherrypy.expose
    def get_thermostats(self, token):
        """ Get the configuration of the thermostats.
        
        :returns: dict with global status information about the thermostats: 'thermostats_on', \
        'automatic' and 'setpoints' and a list ('thermostats') with status information for each \
        active thermostats, each element in the list is a dict with the following keys: \
        'thermostat', 'act', 'csetp', 'psetp0', 'psetp1', 'psetp2', 'psetp3', 'psetp4', 'psetp5', \
        'sensor_nr', 'output0_nr', 'output1_nr', 'output0', 'output1', 'outside', 'mode', 'name', \
        'pid_p', 'pid_i', 'pid_d', 'pid_ithresh', 'threshold_temp', 'days', 'hours', 'minutes', \
        'mon_start_d1', 'mon_stop_d1', 'mon_start_d2', 'mon_stop_d2', 'tue_start_d1', \
        'tue_stop_d1', 'tue_start_d2', 'tue_stop_d2', 'wed_start_d1', 'wed_stop_d1', \
        'wed_start_d2', 'wed_stop_d2', 'thu_start_d1', 'thu_stop_d1', 'thu_start_d2', \
        'thu_stop_d2', 'fri_start_d1', 'fri_stop_d1', 'fri_start_d2', 'fri_stop_d2', \
        'sat_start_d1', 'sat_stop_d1', 'sat_start_d2', 'sat_stop_d2', 'sun_start_d1', \
        'sun_stop_d1', 'sun_start_d2', 'sun_stop_d2' and 'crc'.
        """
        self.__check_token(token)
        return self.__wrap(self.__gateway_api.get_thermostats)
        
    @cherrypy.expose
    def set_programmed_setpoint(self, token, thermostat, setpoint, temperature):
        """ Set a programmed setpoint of a thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param setpoint: The number of programmed setpoint
        :type setpoint: Integer [0, 5]
        :param temperature: The temperature to set in degrees Celcius
        :type temperature: float
        :returns: dict with 'thermostat', 'config' and 'temp'
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_programmed_setpoint(
                                            int(thermostat), int(setpoint), float(temperature)))
    
    @cherrypy.expose
    def set_current_setpoint(self, token, thermostat, temperature):
        """ Set the current setpoint of a thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param temperature: The temperature to set in degrees Celcius
        :type temperature: float
        :return: dict with 'thermostat', 'config' and 'temp'
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_current_setpoint(
                                            int(thermostat), float(temperature)))
    
    @cherrypy.expose
    def set_setpoint_start_time(self, token, thermostat, day_of_week, setpoint, time):
        """ Set the start time of setpoint 0 or 2 for a certain day of the week and thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param day_of_week: The day of the week
        :type day_of_week: Integer [1, 7]
        :param setpoint: The id of the setpoint to set
        :type setpoint: Integer: 0 or 2
        :param time: The start or end (see start) time of the interval
        :type time: String HH:MM format
        
        :return: dict with 'thermostat', 'config' and 'temp'
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_setpoint_start_time(
                                            int(thermostat), int(day_of_week), int(setpoint), time))
    
    @cherrypy.expose
    def set_all_lights_off(self, token):
        """ Turn all lights off.
        
        :returns: empty dict.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_all_lights_off())
    
    @cherrypy.expose
    def set_all_lights_floor_off(self, token, floor):
        """ Turn all lights on a given floor off.
        
        :returns: empty dict.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_all_lights_floor_off(int(floor)))
    
    @cherrypy.expose
    def set_all_lights_floor_on(self, token, floor):
        """ Turn all lights on a given floor on.
        
        :returns: empty dict.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_all_lights_floor_on(int(floor)))
    
    @cherrypy.expose
    def set_setpoint_stop_time(self, token, thermostat, day_of_week, setpoint, time):
        """ Set the stop time of setpoint 0 or 2 for a certain day of the week and thermostat.
        
        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param day_of_week: The day of the week
        :type day_of_week: Integer [1, 7]
        :param setpoint: The id of the setpoint to set
        :type setpoint: Integer: 0 or 2
        :param time: The start or end (see start) time of the interval
        :type time: String HH:MM format
        
        :return: dict with 'thermostat', 'config' and 'temp'
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_setpoint_stop_time(
                                            int(thermostat), int(day_of_week), int(setpoint), time))

    @cherrypy.expose
    def set_thermostat_mode(self, token, thermostat_on, automatic, setpoint):
        """ Set the mode of the thermostats. Thermostats can be on or off, automatic or manual
        and is set to one of the 6 setpoints.
        
        :param thermostat_on: Whether the thermostats are on
        :type thermostat_on: boolean
        :param automatic: Automatic mode (True) or Manual mode (False)
        :type automatic: boolean
        :param setpoint: The current setpoint
        :type setpoint: Integer [0, 5]
        
        :return: dict with 'resp'
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_thermostat_mode(
                       thermostat_on.lower() == 'true', automatic.lower() == 'true', int(setpoint)))
    
    @cherrypy.expose
    def set_thermostat_threshold(self, token, threshold):
        """ Set the outside temperature threshold of the thermostats.
        
        :param threshold: Temperature in degrees celcius
        :type threshold: integer
        
        :returns: dict with 'resp'
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_thermostat_threshold(float(threshold)))
    
    @cherrypy.expose
    def set_master_status_leds(self, token, status):
        """ Set the status of the leds on the master.
        
        :param status: whether the leds should be on (true) or off (false).
        :returns: empty dict.
        """
        self.__check_token(token)
        return self.__wrap(
                    lambda: self.__gateway_api.set_master_status_leds(status.lower() == "true"))
    
    @cherrypy.expose
    def get_master_backup(self, token):
        """ Get a backup of the eeprom of the master.
        
        :returns: String of bytes (size = 64kb). 
        """
        self.__check_token(token)
        cherrypy.response.headers['Content-Type'] = 'application/octet-stream'
        return self.__gateway_api.get_master_backup() 
    
    @cherrypy.expose
    def master_restore(self, token, data):
        """ Restore a backup of the eeprom of the master.
        
        :param data: The eeprom backup to restore.
        :type data: multipart/form-data encoded bytes (size = 64 kb).
        :returns: dict with 'output' key (contains an array with the addresses that were written). 
        """
        self.__check_token(token)
        data = data.file.read()
        return self.__wrap(lambda: self.__gateway_api.master_restore(data))
    
    @cherrypy.expose
    def get_power_modules(self, token):
        """ Get information on the power modules.
        
        :returns: dict with key 'modules' (List of dictionaries with the following keys: id', \
        'name', 'uid', 'address', 'input0', 'input1', 'input2', 'input3', 'input4', 'input5', \
        'input6', 'input7'.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.get_power_modules())
    
    @cherrypy.expose
    def set_power_modules(self, token, modules):
        """ Set information (module and input names) for the power modules.
        
        :param modules: list of dicts with keys: 'id', 'name', 'input0', 'input1', 'input2', \
        'input3', 'input4', 'input5', 'input6', 'input7'.
        :returns: empty dict.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_power_modules(modules))
    
    @cherrypy.expose
    def get_realtime_power(self, token):
        """ Get the realtime power measurements.
        
        :returns: dict with the module id as key and the follow array as value: \
        [voltage, frequency, current, power].
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.get_realtime_power())
    
    @cherrypy.expose
    def start_power_address_mode(self, token):
        """ Start the address mode on the power modules.
        
        :returns: empty dict.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.start_power_address_mode())
    
    @cherrypy.expose
    def stop_power_address_mode(self, token):
        """ Stop the address mode on the power modules.
        
        :returns: empty dict.
        """
        self.__check_token(token)
        return self.__wrap(lambda: self.__gateway_api.stop_power_address_mode())
    
    @cherrypy.expose
    def get_version(self, token):
        """ Get the version of the openmotics software.
        
        :returns: dict with 'version' key.
        """
        self.__check_token(token)
        config = ConfigParser.ConfigParser()
        config.read(constants.get_config_file())
        return self.__success(version=str(config.get('OpenMotics', 'version')))
    
    @cherrypy.expose
    def update(self, token, version, md5, update_data):
        """ Perform an update.
        
        :param version: the new version number.
        :type version: string
        :param md5: the md5 sum of update_data.
        :type md5: string
        :param update_data: a tgz file containing the update script (update.sh) and data.
        :type update_data: multipart/form-data encoded byte string.
        :returns: dict with 'msg'.
        """
        
        self.__check_token(token)
        update_data = update_data.file.read()

        if not os.path.exists(constants.get_update_dir()):
            os.mkdir(constants.get_update_dir())
        
        update_file = open(constants.get_update_file(), "wb")
        update_file.write(update_data)
        update_file.close()

        output_file = open(constants.get_update_output_file(), "w")
        output_file.write('\n')
        output_file.close()
        
        subprocess.Popen(constants.get_update_cmd(version, md5), close_fds=True)
        
        return self.__success(msg='Started update')
    
    @cherrypy.expose
    def get_update_output(self, token):
        """ Get the output of the last update.
        
        :returns: dict with 'output'.
        """
        self.__check_token(token)
        
        output_file = open(constants.get_update_output_file(), "r")
        output = output_file.read()
        output_file.close()
        
        return self.__success(output=output)
    
    def __wrap(self, func):
        """ Wrap a gateway_api function and catches a possible ValueError. 
        
        :returns: {'success': False, 'msg': ...} on ValueError, otherwise {'success': True, ...}
        """
        try:
            ret = func()
        except ValueError:
            return self.__error(traceback.format_exc())
        else:
            return self.__success(**ret)


class WebService:
    """ The web service serves the gateway api over http. """
    
    name = 'web'

    def __init__(self, user_controller, gateway_api, maintenance_service, authorized_check):
        self.__user_controller = user_controller
        self.__gateway_api = gateway_api
        self.__maintenance_service = maintenance_service
        self.__authorized_check = authorized_check

    def run(self):
        """ Run the web service: start cherrypy. """
        cherrypy.config.update({
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 443,
            'engine.autoreload_on': False,

            'server.ssl_module':'pyopenssl',
            'server.ssl_certificate':constants.get_ssl_certificate_file(),
            'server.ssl_private_key':constants.get_ssl_private_key_file(),
        })
        cherrypy.server.socket_timeout = 60
        cherrypy.quickstart(WebInterface(self.__user_controller, self.__gateway_api,
                                         self.__maintenance_service, self.__authorized_check))
        
    def start(self):
        """ Start the web service in a new thread. """
        thread = threading.Thread(target=self.run)
        thread.setName("Web service thread")
        thread.start()
            
    def stop(self):
        """ Stop the web service. """
        cherrypy.engine.exit()
