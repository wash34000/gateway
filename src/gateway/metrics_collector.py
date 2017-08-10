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
from Queue import Queue, Empty
from master.master_communicator import BackgroundConsumer
from serial_utils import CommunicationTimedOutException

LOGGER = logging.getLogger("openmotics")


class MetricsCollector(object):
    """
    The Metrics Collector collects OpenMotics metrics and makes them available.
    """

    def __init__(self, master_communicator, gateway_api):
        """
        :param master_communicator: Master communicator
        :type master_communicator: master.master_communicator.MasterCommunicator
        :param gateway_api: Gateway API
        :type gateway_api: gateway.gateway_api.GatewayApi
        """
        self._start = time.time()
        self._last_service_uptime = 0
        self._stopped = True
        self._environment = {'inputs': {},
                             'outputs': {},
                             'sensors': {},
                             'pulse_counters': {}}
        self._gateway_api = gateway_api
        self._metrics_queue = Queue()
        master_communicator.register_consumer(
            BackgroundConsumer(master_api.output_list(), 0, self._on_output, True)
        )
        master_communicator.register_consumer(
            BackgroundConsumer(master_api.input_list(), 0, self._on_input)
        )

    def start(self):
        self._start = time.time()
        self._stopped = False
        MetricsCollector._start_thread(self._run_system, 'system', 60)
        MetricsCollector._start_thread(self._run_outputs, 'outputs', 60)
        MetricsCollector._start_thread(self._run_sensors, 'sensors', 60)
        MetricsCollector._start_thread(self._run_thermostats, 'thermostats', 60)
        MetricsCollector._start_thread(self._run_errors, 'errors', 120)
        MetricsCollector._start_thread(self._run_pulsecounters, 'pulsecounters', 30)
        MetricsCollector._start_thread(self._run_power_openmotics, 'power_openmotics', 10)
        MetricsCollector._start_thread(self._run_power_openmotics_analytics, 'power_openmotics_analytics', 60)
        MetricsCollector._start_thread(self._load_environment_configurations, 'load_configuration', 900)

    def stop(self):
        self._stopped = True

    def collect_metrics(self):
        # Yield all metrics in the Queue
        try:
            while True:
                yield self._metrics_queue.get(False)
        except Empty:
            pass
        
    @staticmethod
    def _log(message, level='exception'):
        getattr(LOGGER, level)(message)
        print message

    def _enqueue_metrics(self, metric_type, data, tags, timestamp):
        """
        metric_type = 'system'
        data = [{'name': 'service_uptime',
                 'description': 'OpenMotics service uptime',
                 'mtype': 'gauge',
                 'unit': 's',
                 'value': service_uptime}],
        tags = {'name': 'gateway'}
        timestamp = 12346789
        """
        if not isinstance(data, list):
            data = [data]
        for data_entry in data:
            metric = {'plugin': 'OpenMotics',
                      'type': metric_type,
                      'metric': data_entry['name'],
                      'value': data_entry['value'],
                      'timestamp': timestamp}
            metric.update(tags)
            definition = {'type': metric_type,
                          'name': data_entry['name'],
                          'description': data_entry['description'],
                          'mtype': data_entry['mtype'],
                          'unit': data_entry['unit'],
                          'tags': tags.keys()}
            self._metrics_queue.put([metric, definition])

    @staticmethod
    def _start_thread(workload, name, interval):
        print 'Starting collector for {0}'.format(name)
        thread = Thread(target=workload, args=(interval,))
        thread.setName('Metric controller ({0})'.format(name))
        thread.daemon = True
        thread.start()
        return thread

    @staticmethod
    def _pause(start, interval):
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
            self._process_outputs(changed_output_ids)
        except Exception as ex:
            MetricsCollector._log('Error processing outputs: {0}'.format(ex))

    def _process_outputs(self, output_ids):
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
                    self._enqueue_metrics(metric_type='output',
                                          data={'name': 'output',
                                                'description': 'Output state',
                                                'mtype': 'gauge',
                                                'unit': '',
                                                'value': int(level)},
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
                                      data={'name': 'event',
                                            'description': 'OpenMotics event',
                                            'mtype': 'gauge',
                                            'unit': 'event',
                                            'value': 'True'},
                                      tags=tags,
                                      timestamp=now)
        except Exception as ex:
            MetricsCollector._log('Error processing input: {0}'.format(ex))

    def _run_system(self, interval):
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
                self._enqueue_metrics(metric_type='system',
                                      data=[{'name': 'service_uptime',
                                             'description': 'Service uptime',
                                             'mtype': 'gauge',
                                             'unit': 's',
                                             'value': service_uptime},
                                            {'name': 'system_uptime',
                                             'description': 'System uptime',
                                             'mtype': 'gauge',
                                             'unit': 's',
                                             'value': system_uptime}],
                                      tags={'name': 'gateway'},
                                      timestamp=now)
            except Exception as ex:
                MetricsCollector._log('Error sending system data: {0}'.format(ex))
            if self._stopped:
                return
            MetricsCollector._pause(start, interval)

    def _run_outputs(self, interval):
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
            self._process_outputs(self._environment['outputs'].keys())
            if self._stopped:
                return
            MetricsCollector._pause(start, interval)

    def _run_sensors(self, interval):
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
                    data = []
                    if temperatures[sensor_id] is not None:
                        data.append({'name': 'temp',
                                     'description': 'Temperature',
                                     'mtype': 'gauge',
                                     'unit': 'degree C',
                                     'value': temperatures[sensor_id]})
                    if humidities[sensor_id] is not None:
                        data.append({'name': 'hum',
                                     'description': 'Humidity',
                                     'mtype': 'gauge',
                                     'unit': '%',
                                     'value': humidities[sensor_id]})
                    if brightnesses[sensor_id] is not None:
                        data.append({'name': 'bright',
                                     'description': 'Brightness',
                                     'mtype': 'gauge',
                                     'unit': '%',
                                     'value': brightnesses[sensor_id]})
                    self._enqueue_metrics(metric_type='sensor',
                                          data=data,
                                          tags=tags,
                                          timestamp=now)
            except CommunicationTimedOutException:
                LOGGER.error('Error getting sensor status: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting sensor status: {0}'.format(ex))
            if self._stopped:
                return
            MetricsCollector._pause(start, interval)

    def _run_thermostats(self, interval):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                thermostats = self._gateway_api.get_thermostat_status()
                tags = {'id': 'G.0',
                        'name': 'Global configuration'}
                self._enqueue_metrics(metric_type='thermostat',
                                      data=[{'name': 'on',
                                             'description': 'Indicates whether the thermostat is on',
                                             'mtype': 'gauge',
                                             'unit': '',
                                             'value': thermostats['thermostats_on']},
                                            {'name': 'cooling',
                                             'description': 'Indicates whether the thermostat is on cooling',
                                             'mtype': 'gauge',
                                             'unit': '',
                                             'value': thermostats['cooling']}],
                                      tags=tags,
                                      timestamp=now)
                for thermostat in thermostats['status']:
                    data = [{'name': 'setpoint',
                             'description': 'Setpoint identifier (values 0-5)',
                             'mtype': 'gauge',
                             'unit': '',
                             'value': int(thermostat['setpoint'])},
                            {'name': 'output0',
                             'description': 'State of the primary output valve',
                             'mtype': 'gauge',
                             'unit': '',
                             'value': float(thermostat['output0'])},
                            {'name': 'output1',
                             'description': 'State of the secondairy output valve',
                             'mtype': 'gauge',
                             'unit': '',
                             'value': float(thermostat['output1'])},
                            {'name': 'mode',
                             'description': 'Thermostat mode',
                             'mtype': 'gauge',
                             'unit': '',
                             'value': int(thermostat['mode'])},
                            {'name': 'thermostat_type',
                             'description': 'Thermostat type',
                             'mtype': 'gauge',
                             'unit': '',
                             'value': 'tbs' if thermostat['sensor_nr'] == 240 else 'normal'},
                            {'name': 'automatic',
                             'description': 'Automatic indicator',
                             'mtype': 'gauge',
                             'unit': '',
                             'value': thermostat['automatic']},
                            {'name': 'current_setpoint',
                             'description': 'Current setpoint',
                             'mtype': 'gauge',
                             'unit': 'degree C',
                             'value': thermostat['csetp']}]
                    if thermostat['outside'] is not None:
                        data.append({'name': 'outside',
                                     'description': 'Outside sensor value',
                                     'mtype': 'gauge',
                                     'unit': 'degree C',
                                     'value': thermostat['outside']})
                    if thermostat['sensor_nr'] != 240 and thermostat['act'] is not None:
                        data.append({'name': 'temperature',
                                     'description': 'Current temperature',
                                     'mtype': 'gauge',
                                     'unit': 'degree C',
                                     'value': thermostat['act']})
                    self._enqueue_metrics(metric_type='thermostat',
                                          data=data,
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
            MetricsCollector._pause(start, interval)

    def _run_errors(self, interval):
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
                    tags = {'module_type': types[om_module[0]],
                            'id': om_module,
                            'name': '{0} {1}'.format(types[om_module[0]], om_module)}
                    self._enqueue_metrics(metric_type='error',
                                          data=[{'name': 'amount',
                                                 'description': 'Amount of errors',
                                                 'mtype': 'gauge',
                                                 'unit': '',
                                                 'value': int(count)}],
                                          tags=tags,
                                          timestamp=now)
            except CommunicationTimedOutException:
                LOGGER.error('Error getting module errors: CommunicationTimedOutException')
            except Exception as ex:
                MetricsCollector._log('Error getting module errors: {0}'.format(ex))
            if self._stopped:
                return
            MetricsCollector._pause(start, interval)

    def _run_pulsecounters(self, interval):
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
                    tags = {'name': counter['name'],
                            'input': counter['input']}
                    self._enqueue_metrics(metric_type='counter',
                                          data=[{'name': 'pulses',
                                                 'description': 'Number of received pulses',
                                                 'mtype': 'gauge',
                                                 'unit': '',
                                                 'value': int(counter['count'])}],
                                          tags=tags,
                                          timestamp=now)
            if self._stopped:
                return
            MetricsCollector._pause(start, interval)

    def _run_power_openmotics(self, interval):
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
                        tags = {'brand': 'openmotics',
                                'id': device_id,
                                'name': device['name']}
                        data = [{'name': 'voltage',
                                 'description': 'Current voltage',
                                 'mtype': 'gauge',
                                 'unit': 'V',
                                 'value': device['voltage']},
                                {'name': 'current',
                                 'description': 'Current current',
                                 'mtype': 'gauge',
                                 'unit': 'A',
                                 'value': device['current']},
                                {'name': 'frequency',
                                 'description': 'Current frequency',
                                 'mtype': 'gauge',
                                 'unit': 'Hz',
                                 'value': device['frequency']},
                                {'name': 'power',
                                 'description': 'Current power consumption',
                                 'mtype': 'gauge',
                                 'unit': 'W',
                                 'value': device['power']},
                                {'name': 'power_counter',
                                 'description': 'Total energy consumed',
                                 'mtype': 'counter',
                                 'unit': 'Wh',
                                 'value': float(device['counter'])},
                                {'name': 'power_counter_day',
                                 'description': 'Total energy consumed during daytime',
                                 'mtype': 'counter',
                                 'unit': 'Wh',
                                 'value': device['counter_day']},
                                {'name': 'power_counter_night',
                                 'description': 'Total energy consumed during nighttime',
                                 'mtype': 'counter',
                                 'unit': 'Wh',
                                 'value': device['counter_night']}]
                        self._enqueue_metrics(metric_type='energy',
                                              data=data,
                                              tags=tags,
                                              timestamp=now)
                    except Exception as ex:
                        MetricsCollector._log('Error processing OpenMotics power device {0}: {1}'.format(device_id, ex))
            if self._stopped:
                return
            MetricsCollector._pause(start, interval)

    def _run_power_openmotics_analytics(self, interval):
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
                            self._enqueue_metrics(metric_type='energy_analytics',
                                                  data=[{'name': 'current',
                                                         'description': 'Time-based current',
                                                         'mtype': 'gauge',
                                                         'unit': 'A',
                                                         'value': result[str(i)]['current'][j]},
                                                        {'name': 'voltage',
                                                         'description': 'Time-based voltage',
                                                         'mtype': 'gauge',
                                                         'unit': 'V',
                                                         'value': result[str(i)]['voltage'][j]}],
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
                            self._enqueue_metrics(metric_type='energy_analytics',
                                                  data=[{'name': 'current_harmonics',
                                                         'description': 'Current harmonics',
                                                         'mtype': 'gauge',
                                                         'unit': '',
                                                         'value': result[str(i)]['current'][0][j]},
                                                        {'name': 'current_phase',
                                                         'description': 'Current phase',
                                                         'mtype': 'gauge',
                                                         'unit': '',
                                                         'value': result[str(i)]['current'][1][j]},
                                                        {'name': 'voltage_harmonics',
                                                         'description': 'Voltage harmonics',
                                                         'mtype': 'gauge',
                                                         'unit': '',
                                                         'value': result[str(i)]['voltage'][0][j]},
                                                        {'name': 'voltage_phase',
                                                         'description': 'Voltage phase',
                                                         'mtype': 'gauge',
                                                         'unit': '',
                                                         'value': result[str(i)]['voltage'][1][j]}],
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
            MetricsCollector._pause(start, interval)

    def _load_environment_configurations(self, interval=None):
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
            if interval is None or self._stopped:
                return
            MetricsCollector._pause(start, interval)
