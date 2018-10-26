import requests

try:
    import json
except ImportError:
    import simplejson as json

# For backwards compatibility: name of all params per call
call_params = {
    'reset_master': [],
    'module_discover_start': [],
    'module_discover_stop': [],
    'module_discover_status': [],
    'get_module_log': [],
    'get_modules': [],
    'get_features': [],
    'flash_leds': ['type', 'id'],
    'get_status': [],
    'get_output_status': [],
    'set_output': ['id', 'is_on', 'dimmer', 'timer'],
    'set_all_lights_off': [],
    'set_all_lights_floor_off': ['floor'],
    'set_all_lights_floor_on': ['floor'],
    'get_last_inputs': [],
    'get_shutter_status': [],
    'do_shutter_down': ['id'],
    'do_shutter_up': ['id'],
    'do_shutter_stop': ['id'],
    'do_shutter_group_down': ['id'],
    'do_shutter_group_up': ['id'],
    'do_shutter_group_stop': ['id'],
    'get_thermostat_status': [],
    'set_current_setpoint': ['thermostat', 'temperature'],
    'set_thermostat_mode': ['thermostat_on', 'automatic', 'setpoint', 'cooling_mode', 'cooling_on'],
    'set_per_thermostat_mode': ['thermostat_id', 'automatic', 'setpoint'],
    'get_airco_status': [],
    'set_airco_status': ['thermostat_id', 'airco_on'],
    'get_sensor_temperature_status': [],
    'get_sensor_humidity_status': [],
    'get_sensor_brightness_status': [],
    'set_virtual_sensor': ['sensor_id', 'temperature', 'humidity', 'brightness'],
    'do_basic_action': ['action_type', 'action_number'],
    'do_group_action': ['group_action_id'],
    'set_master_status_leds': ['status'],
    'master_restore': ['data'],
    'get_errors': [],
    'master_clear_error_list': [],
    'get_output_configuration': ['id', 'fields'],
    'get_output_configurations': ['fields'],
    'set_output_configuration': ['config'],
    'set_output_configurations': ['config'],
    'get_shutter_configuration': ['id', 'fields'],
    'get_shutter_configurations': ['fields'],
    'set_shutter_configuration': ['config'],
    'set_shutter_configurations': ['config'],
    'get_shutter_group_configuration': ['id', 'fields'],
    'get_shutter_group_configurations': ['fields'],
    'set_shutter_group_configuration': ['config'],
    'set_shutter_group_configurations': ['config'],
    'get_input_configuration': ['id', 'fields'],
    'get_input_configurations': ['fields'],
    'set_input_configuration': ['config'],
    'set_input_configurations': ['config'],
    'get_thermostat_configuration': ['id', 'fields'],
    'get_thermostat_configurations': ['fields'],
    'set_thermostat_configuration': ['config'],
    'set_thermostat_configurations': ['config'],
    'get_sensor_configuration': ['id', 'fields'],
    'get_sensor_configurations': ['fields'],
    'set_sensor_configuration': ['config'],
    'set_sensor_configurations': ['config'],
    'get_pump_group_configuration': ['id', 'fields'],
    'get_pump_group_configurations': ['fields'],
    'set_pump_group_configuration': ['config'],
    'set_pump_group_configurations': ['config'],
    'get_cooling_configuration': ['id', 'fields'],
    'get_cooling_configurations': ['fields'],
    'set_cooling_configuration': ['config'],
    'set_cooling_configurations': ['config'],
    'get_cooling_pump_group_configuration': ['id', 'fields'],
    'get_cooling_pump_group_configurations': ['fields'],
    'set_cooling_pump_group_configuration': ['config'],
    'set_cooling_pump_group_configurations': ['config'],
    'get_global_rtd10_configuration': ['fields'],
    'set_global_rtd10_configuration': ['config'],
    'get_rtd10_heating_configuration': ['id', 'fields'],
    'get_rtd10_heating_configurations': ['fields'],
    'set_rtd10_heating_configuration': ['config'],
    'set_rtd10_heating_configurations': ['config'],
    'get_rtd10_cooling_configuration': ['id', 'fields'],
    'get_rtd10_cooling_configurations': ['fields'],
    'set_rtd10_cooling_configuration': ['config'],
    'set_rtd10_cooling_configurations': ['config'],
    'get_group_action_configuration': ['id', 'fields'],
    'get_group_action_configurations': ['fields'],
    'set_group_action_configuration': ['config'],
    'set_group_action_configurations': ['config'],
    'get_scheduled_action_configuration': ['id', 'fields'],
    'get_scheduled_action_configurations': ['fields'],
    'set_scheduled_action_configuration': ['config'],
    'set_scheduled_action_configurations': ['config'],
    'get_pulse_counter_configuration': ['id', 'fields'],
    'get_pulse_counter_configurations': ['fields'],
    'set_pulse_counter_configuration': ['config'],
    'set_pulse_counter_configurations': ['config'],
    'get_startup_action_configuration': ['fields'],
    'set_startup_action_configuration': ['config'],
    'get_dimmer_configuration': ['fields'],
    'set_dimmer_configuration': ['config'],
    'get_global_thermostat_configuration': ['fields'],
    'set_global_thermostat_configuration': ['config'],
    'get_can_led_configuration': ['id', 'fields'],
    'get_can_led_configurations': ['fields'],
    'set_can_led_configuration': ['config'],
    'set_can_led_configurations': ['config'],
    'get_room_configuration': ['id', 'fields'],
    'get_room_configurations': ['fields'],
    'set_room_configuration': ['config'],
    'set_room_configurations': ['config'],
    'get_reset_dirty_flag': [],
    'get_power_modules': [],
    'set_power_modules': ['modules'],
    'get_realtime_power': [],
    'get_total_energy': [],
    'start_power_address_mode': [],
    'stop_power_address_mode': [],
    'in_power_address_mode': [],
    'set_power_voltage': ['module_id', 'voltage'],
    'get_pulse_counter_status': [],
    'get_energy_time': ['module_id', 'input_id'],
    'get_energy_frequency': ['module_id', 'input_id'],
    'get_version': [],
    'get_update_output': [],
    'set_timezone': ['timezone'],
    'get_timezone': [],
    'schedule_action': ['timestamp', 'action'],
    'add_schedule': ['name', 'start', 'schedule_type', 'arguments', 'repeat', 'duration', 'end'],
    'list_scheduled_actions': [],
    'list_schedules': [],
    'remove_scheduled_action': ['id'],
    'remove_schedule': ['schedule_id'],
    'get_plugins': [],
    'self_test': [],
    'get_metric_definitions': ['source', 'metric_type']
}

class WebInterfaceDispatcher(object):

    def __init__(self, logger, hostname='localhost', port=80):
        self.__logger = logger
        self.__hostname = hostname
        self.__port = port
        self.__warned = False

    def __getattr__(self, attribute):
        if attribute in call_params:
            wrapper = self.get_wrapper(attribute)
            setattr(self, attribute, wrapper)
            return wrapper
        raise AttributeError()

    def warn(self):
        if self.__warned is False:
            self.__logger('[W] Deprecation warning:')
            self.__logger('[W] - Plugins should not pass \'token\' to API calls')
            self.__logger('[W] - Plugins should use keyword arguments for API calls')
            self.__warned = True

    def get_wrapper(self, name):
        params = call_params[name]

        def wrapper(*args, **kwargs):
            # 1. Try to remove a possible "token" parameter, which is now deprecated
            args = list(args)
            if 'token' in kwargs:
                del kwargs['token']
                self.warn()
            elif len(args) > 0:
                self.warn()
                if len(args) + len(kwargs) > len(params) or len(kwargs) == 0:
                    del args[0]
            # 2. Convert to kwargs, so it's possible to do parameter parsing
            for i in xrange(len(args)):
                kwargs[params[i]] = args[i]
            # 3. Perform the http call
            request = requests.post("http://%s:%d/%s/" % (self.__hostname, self.__port, name),
                                    data=kwargs, timeout=30.0)
            return json.loads(request.text)

        return wrapper
