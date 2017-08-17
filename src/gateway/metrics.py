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
The metrics module collects and re-distributes metric data
"""

import time
import logging
from threading import Thread
from collections import deque
try:
    import json
except ImportError:
    import simplejson as json

LOGGER = logging.getLogger("openmotics")


class MetricsController(object):
    """
    The Metrics Controller collects all metrics and pushses them to all subscribers
    """

    def __init__(self, plugin_controller, metrics_collector):
        """
        :param plugin_controller: Plugin Controller
        :type plugin_controller: plugins.base.PluginController
        :param metrics_collector: Metrics Collector
        :type metrics_collector: gateway.metrics_collector.MetricsCollector
        """
        self._thread = None
        self._stopped = False
        self._plugin_controller = plugin_controller
        self._metrics_collector = metrics_collector
        self._definitions = {}
        self._metrics_cache = {}
        self._collector_plugins = None
        self._collector_openmotics = None
        self._internal_stats = None
        self._distributor_plugins = None
        self._distributor_openmotics = None
        self._metrics_queue_plugins = deque()
        self._metrics_queue_openmotics = deque()
        self._inbound_rates = {'total': 0}
        self._outbound_rates = {'total': 0}
        self._load_definitions()
        self._openmotics_receivers = []

    def start(self):
        self._collector_plugins = Thread(target=self._collect_plugins)
        self._collector_plugins.setName('Metrics Controller collector for plugins')
        self._collector_plugins.daemon = True
        self._collector_plugins.start()
        self._collector_openmotics = Thread(target=self._collect_openmotics)
        self._collector_openmotics.setName('Metrics Controller collector for OpenMotics')
        self._collector_openmotics.daemon = True
        self._collector_openmotics.start()
        self._internal_stats = Thread(target=self._generate_internal_stats)
        self._internal_stats.setName('Metrics Controller collector for OpenMotics')
        self._internal_stats.daemon = True
        self._internal_stats.start()
        self._distributor_plugins = Thread(target=self._distribute_plugins)
        self._distributor_plugins.setName('Metrics Controller distributor for plugins')
        self._distributor_plugins.daemon = True
        self._distributor_plugins.start()
        self._distributor_openmotics = Thread(target=self._distribute_openmotics)
        self._distributor_openmotics.setName('Metrics Controller distributor for OpenMotics')
        self._distributor_openmotics.daemon = True
        self._distributor_openmotics.start()

    def stop(self):
        self._stopped = True

    def add_receiver(self, receiver):
        self._openmotics_receivers.append(receiver)

    def _load_definitions(self):
        # {
        #     "type": "energy",
        #     "name": "power",
        #     "description": "Total energy consumed (in kWh)",
        #     "mtype": "counter",
        #     "unit": "kWh",
        #     "tags": ["device", "id"]
        # }
        required_keys = {'type': str,
                         'name': str,
                         'description': str,
                         'mtype': str,
                         'unit': str,
                         'tags': list}
        definitions = self._plugin_controller.get_metric_definitions()
        for plugin, plugin_definitions in definitions.iteritems():
            log = self._plugin_controller.get_logger(plugin)
            for definition in plugin_definitions:
                definition_ok = True
                for key, key_type in required_keys.iteritems():
                    if key not in definition:
                        log('Metric definition should contain keys: {0}'.format(', '.join(required_keys.keys())))
                        definition_ok = False
                        break
                    if not isinstance(definition[key], key_type):
                        log('Metric definition key {0} should be of type {1}'.format(key, key_type))
                        definition_ok = False
                        break
                if definition_ok is True:
                    if plugin not in self._definitions:
                        self._definitions[plugin] = []
                    self._definitions[plugin].append(definition)

    def receiver(self, metric, definition):
        """
        Collects all metrics made available by the MetricsCollector and the plugins. These metrics
        are cached locally for:
        * TODO: Configurable (and optional) pushing metrics to the Cloud
        * TODO: Making the last values for all metrics available through a new API call
        """
        pass
    
    def _put(self, metric, definition):
        rate_key = '{0}.{1}'.format(metric['source'].lower(), metric['type'].lower())
        if rate_key not in self._inbound_rates:
            self._inbound_rates[rate_key] = 0
        self._inbound_rates[rate_key] += 1
        self._inbound_rates['total'] += 1
        self._metrics_queue_plugins.appendleft([metric, definition])
        self._metrics_queue_openmotics.appendleft([metric, definition])

    def _generate_internal_stats(self):
        inbound_definition = {'type': 'system',
                              'name': 'metrics_in',
                              'description': 'Inbound metrics processed',
                              'mtype': 'counter',
                              'unit': '',
                              'tags': ['name', 'namespace']}
        outbound_definition = {'type': 'system',
                               'name': 'metrics_out',
                               'description': 'Outbound metrics processed',
                               'mtype': 'counter',
                               'unit': '',
                               'tags': ['name', 'namespace']}
        queue_length_definition = {'type': 'system',
                                   'name': 'queue_length',
                                   'description': 'Metrics queue length',
                                   'mtype': 'gauge',
                                   'unit': '',
                                   'tags': ['name', 'target']}
        while not self._stopped:
            now = time.time()
            try:
                metric = {'source': 'OpenMotics',
                          'type': 'system',
                          'metric': 'queue_length',
                          'timestamp': now,
                          'name': 'gateway',
                          'target': 'plugins',
                          'value': len(self._metrics_queue_plugins)}
                self._put(metric, queue_length_definition)
                metric = {'source': 'OpenMotics',
                          'type': 'system',
                          'metric': 'queue_length',
                          'timestamp': now,
                          'name': 'gateway',
                          'target': 'openmotics',
                          'value': len(self._metrics_queue_openmotics)}
                self._put(metric, queue_length_definition)
                for plugin in self._plugin_controller.metric_receiver_queues.keys():
                    metric = {'source': 'OpenMotics',
                              'type': 'system',
                              'metric': 'queue_length',
                              'timestamp': now,
                              'name': 'gateway',
                              'target': plugin,
                              'value': len(self._plugin_controller.metric_receiver_queues[plugin])}
                    self._put(metric, queue_length_definition)
                for key in self._inbound_rates:
                    metric = {'source': 'OpenMotics',
                              'type': 'system',
                              'metric': 'metrics_in',
                              'timestamp': now,
                              'name': 'gateway',
                              'namespace': key,
                              'value': self._inbound_rates[key]}
                    self._put(metric, inbound_definition)
                for key in self._outbound_rates:
                    metric = {'source': 'OpenMotics',
                              'type': 'system',
                              'metric': 'metrics_out',
                              'timestamp': now,
                              'name': 'gateway',
                              'namespace': key,
                              'value': self._outbound_rates[key]}
                    self._put(metric, outbound_definition)
            except Exception as ex:
                LOGGER.error('Could not collect metric metrics: {0}'.format(ex))
            if not self._stopped:
                time.sleep(10)

    def _collect_plugins(self):
        """
        > example_definition = {"type": "energy",
        >                       "name": "power",
        >                       "description": "Total energy consumed (in kWh)",
        >                       "mtype": "counter",
        >                       "unit": "Wh",
        >                       "tags": ["device", "id"]}
        > example_metric = {"source": "OpenMotics",
        >                   "type": "energy",
        >                   "metric": "power",
        >                   "timestamp": 1497677091,
        >                   "device": "OpenMotics energy ID1",
        >                   "id": 0,
        >                   "value": 1234}
        """
        while not self._stopped:
            start = time.time()
            for metric in self._plugin_controller.collect_metrics():
                # Validation, part 1
                source = metric['source']
                log = self._plugin_controller.get_logger(source)
                required_keys = {'type': str,
                                 'metric': str,
                                 'timestamp': (float, int),
                                 'value': (float, int)}
                metric_ok = True
                for key, key_type in required_keys.iteritems():
                    if key not in metric:
                        log('Metric should contain keys {0}'.format(', '.join(required_keys.keys())))
                        metric_ok = False
                        break
                    if not isinstance(metric[key], key_type):
                        log('Metric key {0} should be of type {1}'.format(key, key_type))
                        metric_ok = False
                        break
                if metric_ok is False:
                    continue
                # Get metric definition
                definitions = self._definitions.get(metric['source'])
                if definitions is None:
                    continue
                definition = [_def for _def in definitions if _def['name'] == metric['metric']]
                if len(definition) != 1:
                    continue
                definition = definition[0]
                # Validate metric
                for tag in definition['tags']:
                    if tag not in metric or metric[tag] is None:
                        log('Metric tag {0} should be defined'.format(tag))
                        metric_ok = False
                if metric_ok is False:
                    continue
                self._put(metric, definition)
            if not self._stopped:
                time.sleep(max(0.1, 1 - (time.time() - start)))

    def _collect_openmotics(self):
        while not self._stopped:
            start = time.time()
            for metric, definition in self._metrics_collector.collect_metrics():
                self._put(metric, definition)
            if not self._stopped:
                time.sleep(max(0.1, 1 - (time.time() - start)))

    def _distribute_plugins(self):
        while not self._stopped:
            try:
                metric, definition = self._metrics_queue_plugins.pop()
                delivery_count = self._plugin_controller.distribute_metric(metric, definition)
                if delivery_count > 0:
                    rate_key = '{0}.{1}'.format(metric['source'].lower(), metric['type'].lower())
                    if rate_key not in self._outbound_rates:
                        self._outbound_rates[rate_key] = 0
                    self._outbound_rates[rate_key] += delivery_count
                    self._outbound_rates['total'] += delivery_count
            except IndexError:
                time.sleep(0.1)

    def _distribute_openmotics(self):
        while not self._stopped:
            try:
                metric, definition = self._metrics_queue_openmotics.pop()
                for receiver in self._openmotics_receivers:
                    receiver(metric, definition)
                    rate_key = '{0}.{1}'.format(metric['source'].lower(), metric['type'].lower())
                    if rate_key not in self._outbound_rates:
                        self._outbound_rates[rate_key] = 0
                    self._outbound_rates[rate_key] += 1
                    self._outbound_rates['total'] += 1
            except IndexError:
                time.sleep(0.1)
