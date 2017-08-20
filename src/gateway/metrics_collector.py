# Copyright (C) 2016 OpenMotics BVBA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
This module collects OpenMotics metrics and makes them available to the MetricsController
"""

import time
import logging
import master.master_api as master_api
from threading import Thread
from collections import deque
from master.master_communicator import BackgroundConsumer
from serial_utils import CommunicationTimedOutException

LOGGER = logging.getLogger("openmotics")


class MetricsCollector(object):
    """
    The Metrics Collector collects OpenMotics metrics and makes them available.
    """

    def __init__(self, master_communicator, gateway_api, plugin_intervals):
        """
        :param master_communicator: Master communicator
        :type master_communicator: master.master_communicator.MasterCommunicator
        :param gateway_api: Gateway API
        :type gateway_api: gateway.gateway_api.GatewayApi
        :param plugin_intervals: Intervals requested by plugins
        :type plugin_intervals: list
        """
        self._start = time.time()
        self._last_service_uptime = 0
        self._stopped = True
        self._environment = {'inputs': {},
                             'outputs': {},
                             'sensors': {},
                             'pulse_counters': {}}
        self._min_intervals = {'load_configuration': 900,
                               'system': 60,
                               'output': 60,
                               'sensor': 5,
                               'thermostat': 30,
                               'error': 120,
                               'counter': 30,
                               'energy': 1,
                               'energy_analytics': 60}
        self.intervals = {metric_type: 900 for metric_type in self._min_intervals}
        self._plugin_intervals = {metric_type: [] for metric_type in self._min_intervals}
        self._websocket_intervals = {metric_type: {} for metric_type in self._min_intervals}
        self._cloud_intervals = {metric_type: 900 for metric_type in self._min_intervals}
        for interval_info in plugin_intervals:
            if interval_info['source'] is not None and not interval_info['source'].match('OpenMotics'):
                continue
            for metric_type in self.intervals:
                if metric_type == 'load_configuration':
                    continue
                if interval_info['metric_type'] is None or interval_info['metric_type'].match(metric_type):
                    self._plugin_intervals[metric_type].append(interval_info['interval'])
                    self._update_intervals(metric_type)

        self._gateway_api = gateway_api
        self._metrics_queue = deque()
        master_communicator.register_consumer(
            BackgroundConsumer(master_api.output_list(), 0, self._on_output, True)
        )
        master_communicator.register_consumer(
            BackgroundConsumer(master_api.input_list(), 0, self._on_input)
        )

    def start(self):
        self._start = time.time()
        self._stopped = False
        MetricsCollector._start_thread(self._load_environment_configurations, 'load_configuration')
        MetricsCollector._start_thread(self._run_system, 'system')
        MetricsCollector._start_thread(self._run_outputs, 'output')
        MetricsCollector._start_thread(self._run_sensors, 'sensor')
        MetricsCollector._start_thread(self._run_thermostats, 'thermostat')
        MetricsCollector._start_thread(self._run_errors, 'error')
        MetricsCollector._start_thread(self._run_pulsecounters, 'counter')
        MetricsCollector._start_thread(self._run_power_openmotics, 'energy')
        MetricsCollector._start_thread(self._run_power_openmotics_analytics, 'energy_analytics')

    def stop(self):
        self._stopped = True

    def collect_metrics(self):
        # Yield all metrics in the Queue
        try:
            while True:
                yield self._metrics_queue.pop()
        except IndexError:
            pass

    def set_cloud_interval(self, metric_type, interval):
        self._cloud_intervals[metric_type] = interval
        self._update_intervals(metric_type)

    def set_websocket_interval(self, client_id, metric_type, interval):
        for mtype in self._websocket_intervals:
            if metric_type is None or metric_type.match(mtype):
                if interval is None:
                    if client_id in self._websocket_intervals[mtype]:
                        del self._websocket_intervals[mtype][client_id]
                else:
                    self._websocket_intervals[mtype][client_id] = interval
                self._update_intervals(mtype)
        
    @staticmethod
    def _log(message, level='exception'):
        getattr(LOGGER, level)(message)
        print message

    def _update_intervals(self, metric_type):
        min_interval = self._min_intervals[metric_type]
        interval = max(min_interval, self._cloud_intervals[metric_type])
        if len(self._plugin_intervals[metric_type]) > 0:
            interval = min(interval, *[max(min_interval, i) for i in self._plugin_intervals[metric_type]])
        if len(self._websocket_intervals[metric_type]) > 0:
            interval = min(interval, *[max(min_interval, i) for i in self._websocket_intervals[metric_type].values()])
        self.intervals[metric_type] = interval

    def _enqueue_metrics(self, metric_type, values, tags, timestamp):
        """
        metric_type = 'system'
        values = {'service_uptime': service_uptime},
        tags = {'name': 'gateway'}
        timestamp = 12346789
        """
        for name, value in values.iteritems():
            metric = {'source': 'OpenMotics',
                      'type': metric_type,
                      'metric': name,
                      'value': value,
                      'timestamp': timestamp}
            metric.update(tags)
            self._metrics_queue.appendleft(metric)

    @staticmethod
    def _start_thread(workload, name):
        thread = Thread(target=workload, args=(name,))
        thread.setName('Metric controller ({0})'.format(name))
        thread.daemon = True
        thread.start()
        return thread

    def _pause(self, start, metric_type):
        interval = self.intervals[metric_type]
        elapsed = time.time() - start
        sleep = max(0.1, interval - elapsed)
        time.sleep(sleep)

    def _on_output(self, data):
        try:
            on_outputs = {entry[0]: entry[1] for entry in data['outputs']}
            outputs = self._environment['outputs']
            changed_output_ids = []
            for output_id in outputs:
                status = outputs[output_id].get('status')
                dimmer = outputs[output_id].get('dimmer')
                if status is None or dimmer is None:
                    continue
                changed = False
                if output_id in on_outputs:
                    if status != 1:
                        changed = True
                        outputs[output_id]['status'] = 1
                    if dimmer != on_outputs[output_id]:
                        changed = True
                        outputs[output_id]['dimmer'] = on_outputs[output_id]
                elif status != 0:
                    changed = True
                    outputs[output_id]['status'] = 0
                if changed is True:
                    changed_output_ids.append(output_id)
            self._process_outputs(changed_output_ids, 'output')
        except Exception as ex:
            MetricsCollector._log('Error processing outputs: {0}'.format(ex))

    def _process_outputs(self, output_ids, metric_type):
        try:
            now = time.time()
            outputs = self._environment['outputs']
            for output_id in output_ids:
                output_name = outputs[output_id].get('name')
                status = outputs[output_id].get('status')
                dimmer = outputs[output_id].get('dimmer')
                if output_name != '' and status is not None and dimmer is not None:
                    if outputs[output_id]['module_type'] == 'output':
                        level = 100
                    else:
                        level = dimmer
                    if status == 0:
                        level = 0
                    tags = {'id': output_id,
                            'name': output_name}
                    for key in ['module_type', 'output_type', 'floor']:
                        if key in outputs[output_id]:
                            tags[key] = outputs[output_id][key]
                    self._enqueue_metrics(metric_type=metric_type,
                                          values={'output': int(level)},
                                          tags=tags,
                                          timestamp=now)
        except Exception as ex:
            MetricsCollector._log('Error processing outputs {0}: {1}'.format(output_ids, ex))

    def _on_input(self, data):
        self._process_input(data['input'])

    def _process_input(self, input_id):
        try:
            now = time.time()
            inputs = self._environment['inputs']
            if input_id not in inputs:
                return
            input_name = inputs[input_id]['name']
            if input_name != '':
                tags = {'event_type': 'input',
                        'id': input_id,
                        'name': input_name}
                self._enqueue_metrics(metric_type='events',
                                      values={'event': True},
                                      tags=tags,
                                      timestamp=now)
        except Exception as ex:
            MetricsCollector._log('Error processing input: {0}'.format(ex))

    def _run_system(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                with open('/proc/uptime', 'r') as f:
                    system_uptime = float(f.readline().split()[0])
                service_uptime = time.time() - self._start
                if service_uptime > self._last_service_uptime + 3600:
                    self._start = time.time()
                    service_uptime = 0
                self._last_service_uptime = service_uptime
                self._enqueue_metrics(metric_type=metric_type,
                                      values={'service_uptime': service_uptime,
                                              'system_uptime': system_uptime},
                                      tags={'name': 'gateway'},
                                      timestamp=now)
            except Exception as ex:
                MetricsCollector._log('Error sending system data: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_outputs(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                result = self._gateway_api.get_output_status()
                for output in result:
                    output_id = output['id']
                    if output_id not in self._environment['outputs']:
                        continue
                    self._environment['outputs'][output_id]['status'] = output['status']
                    self._environment['outputs'][output_id]['dimmer'] = output['dimmer']
            except CommunicationTimedOutException:
                LOGGER.error('Error getting output status: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting output status: {0}'.format(ex))
            self._process_outputs(self._environment['outputs'].keys(), metric_type)
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_sensors(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                temperatures = self._gateway_api.get_sensor_temperature_status()
                humidities = self._gateway_api.get_sensor_humidity_status()
                brightnesses = self._gateway_api.get_sensor_brightness_status()
                for sensor_id, sensor in self._environment['sensors'].iteritems():
                    name = sensor['name']
                    if name == '' or name == 'NOT_IN_USE':
                        continue
                    tags = {'id': sensor_id,
                            'name': name}
                    values = {}
                    if temperatures[sensor_id] is not None:
                        values['temp'] = temperatures[sensor_id]
                    if humidities[sensor_id] is not None:
                        values['hum'] = humidities[sensor_id]
                    if brightnesses[sensor_id] is not None:
                        values['bright'] = brightnesses[sensor_id]
                    self._enqueue_metrics(metric_type=metric_type,
                                          values=values,
                                          tags=tags,
                                          timestamp=now)
            except CommunicationTimedOutException:
                LOGGER.error('Error getting sensor status: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting sensor status: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_thermostats(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                thermostats = self._gateway_api.get_thermostat_status()
                self._enqueue_metrics(metric_type=metric_type,
                                      values={'on': thermostats['thermostats_on'],
                                              'cooling': thermostats['cooling']},
                                      tags={'id': 'G.0',
                                            'name': 'Global configuration'},
                                      timestamp=now)
                for thermostat in thermostats['status']:
                    values = {'setpoint': int(thermostat['setpoint']),
                              'output0': float(thermostat['output0']),
                              'output1': float(thermostat['output1']),
                              'mode': int(thermostat['mode']),
                              'thermostat_type': 'tbs' if thermostat['sensor_nr'] == 240 else 'normal',
                              'automatic': thermostat['automatic'],
                              'current_setpoint': thermostat['csetp']}
                    if thermostat['outside'] is not None:
                        values['outside'] = thermostat['outside']
                    if thermostat['sensor_nr'] != 240 and thermostat['act'] is not None:
                        values['temperature'] = thermostat['act']
                    self._enqueue_metrics(metric_type=metric_type,
                                          values=values,
                                          tags={'id': '{0}.{1}'.format('C' if thermostats['cooling'] is True else 'H',
                                                                       thermostat['id']),
                                                'name': thermostat['name']},
                                          timestamp=now)
            except CommunicationTimedOutException:
                LOGGER.error('Error getting thermostat status: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting thermostat status: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_errors(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                errors = self._gateway_api.master_error_list()
                for error in errors:
                    om_module = error[0]
                    count = error[1]
                    types = {'i': 'Input',
                             'I': 'Input',
                             'T': 'Temperature',
                             'o': 'Output',
                             'O': 'Output',
                             'd': 'Dimmer',
                             'D': 'Dimmer',
                             'R': 'Shutter',
                             'C': 'CAN',
                             'L': 'OLED'}
                    self._enqueue_metrics(metric_type=metric_type,
                                          values={'amount': int(count)},
                                          tags={'module_type': types[om_module[0]],
                                                'id': om_module,
                                                'name': '{0} {1}'.format(types[om_module[0]], om_module)},
                                          timestamp=now)
            except CommunicationTimedOutException:
                LOGGER.error('Error getting module errors: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting module errors: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_pulsecounters(self, metric_type):
        while not self._stopped:
            start = time.time()
            now = time.time()
            counters_data = {}
            try:
                for counter_id, counter in self._environment['pulse_counters'].iteritems():
                    counters_data[counter_id] = {'name': counter['name'],
                                                 'input': counter['input']}
            except Exception as ex:
                MetricsCollector._log('Error getting pulse counter configuration: {0}'.format(ex))
            try:
                result = self._gateway_api.get_pulse_counter_status()
                counters = result
                for counter_id in counters_data:
                    if len(counters) > counter_id:
                        counters_data[counter_id]['count'] = counters[counter_id]
            except CommunicationTimedOutException:
                LOGGER.error('Error getting pulse counter status: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting pulse counter status: {0}'.format(ex))
            for counter_id in counters_data:
                counter = counters_data[counter_id]
                if counter['name'] != '':
                    self._enqueue_metrics(metric_type=metric_type,
                                          values={'pulses': int(counter['count'])},
                                          tags={'name': counter['name'],
                                                'input': counter['input']},
                                          timestamp=now)
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_power_openmotics(self, metric_type):
        while not self._stopped:
            start = time.time()
            now = time.time()
            mapping = {}
            power_data = {}
            try:
                result = self._gateway_api.get_power_modules()
                for power_module in result:
                    device_id = '{0}.{{0}}'.format(power_module['address'])
                    mapping[str(power_module['id'])] = device_id
                    if power_module['version'] in [8, 12]:
                        for i in xrange(power_module['version']):
                            power_data[device_id.format(i)] = {'name': power_module['input{0}'.format(i)]}
            except CommunicationTimedOutException:
                LOGGER.error('Error getting power modules: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting power modules: {0}'.format(ex))
            try:
                result = self._gateway_api.get_realtime_power()
                for module_id, device_id in mapping.iteritems():
                    if module_id in result:
                        for index, entry in enumerate(result[module_id]):
                            if device_id.format(index) in power_data:
                                usage = power_data[device_id.format(index)]
                                usage.update({'voltage': entry[0],
                                              'frequency': entry[1],
                                              'current': entry[2],
                                              'power': entry[3]})
            except CommunicationTimedOutException:
                LOGGER.error('Error getting realtime power: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting realtime power: {0}'.format(ex))
            try:
                result = self._gateway_api.get_total_energy()
                for module_id, device_id in mapping.iteritems():
                    if module_id in result:
                        for index, entry in enumerate(result[module_id]):
                            if device_id.format(index) in power_data:
                                usage = power_data[device_id.format(index)]
                                usage.update({'counter': entry[0] + entry[1],
                                              'counter_day': entry[0],
                                              'counter_night': entry[1]})
            except CommunicationTimedOutException:
                LOGGER.error('Error getting total energy: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting total energy: {0}'.format(ex))
            for device_id in power_data:
                device = power_data[device_id]
                if device['name'] != '':
                    try:
                        self._enqueue_metrics(metric_type=metric_type,
                                              values={'voltage': device['voltage'],
                                                      'current': device['current'],
                                                      'frequency': device['frequency'],
                                                      'power': device['power'],
                                                      'power_counter': float(device['counter']),
                                                      'power_counter_day': device['counter_day'],
                                                      'power_counter_night': device['counter_night']},
                                              tags={'brand': 'openmotics',
                                                    'id': device_id,
                                                    'name': device['name']},
                                              timestamp=now)
                    except Exception as ex:
                        MetricsCollector._log('Error processing OpenMotics power device {0}: {1}'.format(device_id, ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_power_openmotics_analytics(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                result = self._gateway_api.get_power_modules()
                for power_module in result:
                    device_id = '{0}.{{0}}'.format(power_module['address'])
                    if power_module['version'] != 12:
                        continue
                    result = self._gateway_api.get_energy_time(power_module['id'])
                    abort = False
                    for i in xrange(12):
                        if abort is True:
                            break
                        name = power_module['input{0}'.format(i)]
                        if name == '':
                            continue
                        timestamp = now
                        length = min(len(result[str(i)]['current']), len(result[str(i)]['voltage']))
                        for j in xrange(length):
                            self._enqueue_metrics(metric_type=metric_type,
                                                  values={'current': result[str(i)]['current'][j],
                                                          'voltage': result[str(i)]['voltage'][j]},
                                                  tags={'id': device_id.format(i),
                                                        'name': name,
                                                        'domain': 'time'},
                                                  timestamp=timestamp)
                            timestamp += 0.250  # Stretch actual data by 1000 for visualtisation purposes
                    result = self._gateway_api.get_energy_frequency(power_module['id'])
                    abort = False
                    for i in xrange(12):
                        if abort is True:
                            break
                        name = power_module['input{0}'.format(i)]
                        if name == '':
                            continue
                        timestamp = now
                        length = min(len(result[str(i)]['current'][0]), len(result[str(i)]['voltage'][0]))
                        for j in xrange(length):
                            self._enqueue_metrics(metric_type=metric_type,
                                                  values={'current_harmonics': result[str(i)]['current'][0][j],
                                                          'current_phase': result[str(i)]['current'][1][j],
                                                          'voltage_harmonics': result[str(i)]['voltage'][0][j],
                                                          'voltage_phase': result[str(i)]['voltage'][1][j]},
                                                  tags={'id': device_id.format(i),
                                                        'name': name,
                                                        'domain': 'frequency'},
                                                  timestamp=timestamp)
                            timestamp += 0.250  # Stretch actual data by 1000 for visualtisation purposes
            except CommunicationTimedOutException:
                LOGGER.error('Error getting power analytics: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting power analytics: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _load_environment_configurations(self, metric_type):
        while not self._stopped:
            start = time.time()
            # Inputs
            try:
                result = self._gateway_api.get_input_configurations()
                ids = []
                for config in result:
                    input_id = config['id']
                    ids.append(input_id)
                    self._environment['inputs'][input_id] = config
                for input_id in self._environment['inputs'].keys():
                    if input_id not in ids:
                        del self._environment['inputs'][input_id]
            except CommunicationTimedOutException:
                MetricsCollector._log('Error while loading input configurations: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error while loading input configurations: {0}'.format(ex))
            # Outputs
            try:
                result = self._gateway_api.get_output_configurations()
                ids = []
                for config in result:
                    if config['module_type'] not in ['o', 'O', 'd', 'D']:
                        continue
                    output_id = config['id']
                    ids.append(output_id)
                    self._environment['outputs'][output_id] = {'name': config['name'],
                                                               'module_type': {'o': 'output',
                                                                               'O': 'output',
                                                                               'd': 'dimmer',
                                                                               'D': 'dimmer'}[config['module_type']],
                                                               'floor': config['floor'],
                                                               'output_type': 'relay' if config['type'] == 0 else 'light'}
                for output_id in self._environment['outputs'].keys():
                    if output_id not in ids:
                        del self._environment['outputs'][output_id]
            except CommunicationTimedOutException:
                LOGGER.error('Error while loading output configurations: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error while loading output configurations: {0}'.format(ex))
            # Sensors
            try:
                result = self._gateway_api.get_sensor_configurations()
                ids = []
                for config in result:
                    input_id = config['id']
                    ids.append(input_id)
                    self._environment['sensors'][input_id] = config
                for input_id in self._environment['sensors'].keys():
                    if input_id not in ids:
                        del self._environment['sensors'][input_id]
            except CommunicationTimedOutException:
                LOGGER.error('Error while loading sensor configurations: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error while loading sensor configurations: {0}'.format(ex))
            # Pulse counters
            try:
                result = self._gateway_api.get_pulse_counter_configurations()
                ids = []
                for config in result:
                    input_id = config['id']
                    ids.append(input_id)
                    self._environment['pulse_counters'][input_id] = config
                for input_id in self._environment['pulse_counters'].keys():
                    if input_id not in ids:
                        del self._environment['pulse_counters'][input_id]
            except CommunicationTimedOutException:
                LOGGER.error('Error while loading pulse counter configurations: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error while loading pulse counter configurations: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def get_definitions(self):
        """
        > example_definition = {"type": "energy",
        >                       "name": "power",
        >                       "description": "Total energy consumed (in kWh)",
        >                       "mtype": "counter",
        >                       "unit": "Wh",
        >                       "tags": ["device", "id"]}
        """
        _ = self  # Easier as non-static method
        return [
            # system
            {'type': 'system',
             'name': 'service_uptime',
             'description': 'Service uptime',
             'mtype': 'gauge',
             'unit': 's',
             'tags': ['name']},
            {'type': 'system',
             'name': 'system_uptime',
             'description': 'System uptime',
             'mtype': 'gauge',
             'unit': 's',
             'tags': ['name']},
            # inputs / events
            {'type': 'events',
             'name': 'event',
             'description': 'OpenMotics event',
             'mtype': 'gauge',
             'unit': 'event',
             'tags': ['event_type', 'id', 'name']},
            # output
            {'type': 'output',
             'name': 'output',
             'description': 'Output state',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name', 'module_type', 'output_type', 'floor']},
            # sensor
            {'type': 'sensor',
             'name': 'temp',
             'description': 'Temperature',
             'mtype': 'gauge',
             'unit': 'degree C',
             'tags': ['id', 'name']},
            {'type': 'sensor',
             'name': 'hum',
             'description': 'Humidity',
             'mtype': 'gauge',
             'unit': '%',
             'tags': ['id', 'name']},
            {'type': 'sensor',
             'name': 'bright',
             'description': 'Brightness',
             'mtype': 'gauge',
             'unit': '%',
             'tags': ['id', 'name']},
            # thermostat
            {'type': 'thermostat',
             'name': 'on',
             'description': 'Indicates whether the thermostat is on',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'cooling',
             'description': 'Indicates whether the thermostat is on cooling',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'setpoint',
             'description': 'Setpoint identifier (values 0-5)',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'output0',
             'description': 'State of the primary output valve',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'output1',
             'description': 'State of the secondairy output valve',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'mode',
             'description': 'Thermostat mode',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'thermostat_type',
             'description': 'Thermostat type',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'automatic',
             'description': 'Automatic indicator',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'current_setpoint',
             'description': 'Current setpoint',
             'mtype': 'gauge',
             'unit': 'degree C',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'outside',
             'description': 'Outside sensor value',
             'mtype': 'gauge',
             'unit': 'degree C',
             'tags': ['id', 'name']},
            {'type': 'thermostat',
             'name': 'temperature',
             'description': 'Current temperature',
             'mtype': 'gauge',
             'unit': 'degree C',
             'tags': ['id', 'name']},
            # error
            {'type': 'error',
             'name': 'amount',
             'description': 'Amount of errors',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['module_type', 'id', 'name']},
            # counter
            {'type': 'counter',
             'name': 'pulses',
             'description': 'Number of received pulses',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['name', 'input']},
            # energy
            {'type': 'energy',
             'name': 'voltage',
             'description': 'Current voltage',
             'mtype': 'gauge',
             'unit': 'V',
             'tags': ['brand', 'id', 'name']},
            {'type': 'energy',
             'name': 'current',
             'description': 'Current current',
             'mtype': 'gauge',
             'unit': 'A',
             'tags': ['brand', 'id', 'name']},
            {'type': 'energy',
             'name': 'frequency',
             'description': 'Current frequency',
             'mtype': 'gauge',
             'unit': 'Hz',
             'tags': ['brand', 'id', 'name']},
            {'type': 'energy',
             'name': 'power',
             'description': 'Current power consumption',
             'mtype': 'gauge',
             'unit': 'W',
             'tags': ['brand', 'id', 'name']},
            {'type': 'energy',
             'name': 'power_counter',
             'description': 'Total energy consumed',
             'mtype': 'counter',
             'unit': 'Wh',
             'tags': ['brand', 'id', 'name']},
            {'type': 'energy',
             'name': 'power_counter_day',
             'description': 'Total energy consumed during daytime',
             'mtype': 'counter',
             'unit': 'Wh',
             'tags': ['brand', 'id', 'name']},
            {'type': 'energy',
             'name': 'power_counter_night',
             'description': 'Total energy consumed during nighttime',
             'mtype': 'counter',
             'unit': 'Wh',
             'tags': ['brand', 'id', 'name']},
            # energy_analytics
            {'type': 'energy_analytics',
             'name': 'current',
             'description': 'Time-based current',
             'mtype': 'gauge',
             'unit': 'A',
             'tags': ['id', 'name', 'domain']},
            {'type': 'energy_analytics',
             'name': 'voltage',
             'description': 'Time-based voltage',
             'mtype': 'gauge',
             'unit': 'V',
             'tags': ['id', 'name', 'domain']},
            {'type': 'energy_analytics',
             'name': 'current_harmonics',
             'description': 'Current harmonics',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name', 'domain']},
            {'type': 'energy_analytics',
             'name': 'current_phase',
             'description': 'Current phase',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name', 'domain']},
            {'type': 'energy_analytics',
             'name': 'voltage_harmonics',
             'description': 'Voltage harmonics',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name', 'domain']},
            {'type': 'energy_analytics',
             'name': 'voltage_phase',
             'description': 'Voltage phase',
             'mtype': 'gauge',
             'unit': '',
             'tags': ['id', 'name', 'domain']},
        ]
