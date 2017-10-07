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
The main module for the OpenMotics

@author: fryckbos
"""

import logging
import sys
import os
import time
import threading

os.environ['PYTHON_EGG_CACHE'] = '/tmp/.eggs-cache/'
for egg in os.listdir('/opt/openmotics/python/eggs'):
    if egg.endswith('.egg'):
        sys.path.insert(0, '/opt/openmotics/python/eggs/{0}'.format(egg))

from serial import Serial
from signal import signal, SIGTERM
from ConfigParser import ConfigParser

import constants

from serial_utils import RS485

from gateway.webservice import WebInterface, WebService
from gateway.gateway_api import GatewayApi
from gateway.users import UserController
from gateway.metrics import MetricsController
from gateway.metrics_collector import MetricsCollector
from gateway.config import ConfigurationController

from bus.led_service import LedService

from master.maintenance import MaintenanceService
from master.master_communicator import MasterCommunicator, BackgroundConsumer
from master.passthrough import PassthroughService
from master import master_api

from power.power_communicator import PowerCommunicator
from power.power_controller import PowerController

from plugins.base import PluginController


def setup_logger():
    """ Setup the OpenMotics logger. """
    logger = logging.getLogger("openmotics")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


def led_driver(led_service, master_communicator, power_communicator):
    """ Blink the serial leds if necessary. """
    master = (0, 0)
    power = (0, 0)

    while True:
        if master[0] != master_communicator.get_bytes_read() \
                or master[1] != master_communicator.get_bytes_written():
            led_service.serial_activity(5)

        if power[0] != power_communicator.get_bytes_read() \
                or power[1] != power_communicator.get_bytes_written():
            led_service.serial_activity(4)

        master = (master_communicator.get_bytes_read(), master_communicator.get_bytes_written())
        power = (power_communicator.get_bytes_read(), power_communicator.get_bytes_written())
        time.sleep(0.100)


def main():
    """ Main function. """
    config = ConfigParser()
    config.read(constants.get_config_file())

    defaults = {'username': config.get('OpenMotics', 'cloud_user'),
                'password': config.get('OpenMotics', 'cloud_pass')}
    controller_serial_port = config.get('OpenMotics', 'controller_serial')
    passthrough_serial_port = config.get('OpenMotics', 'passthrough_serial')
    power_serial_port = config.get('OpenMotics', 'power_serial')
    gateway_uuid = config.get('OpenMotics', 'uuid')

    user_controller = UserController(constants.get_config_database_file(), defaults, 3600)
    config_controller = ConfigurationController(constants.get_config_database_file())

    led_service = LedService()

    controller_serial = Serial(controller_serial_port, 115200)
    passthrough_serial = Serial(passthrough_serial_port, 115200)
    power_serial = RS485(Serial(power_serial_port, 115200, timeout=None))

    master_communicator = MasterCommunicator(controller_serial)
    master_communicator.start()

    power_controller = PowerController(constants.get_power_database_file())

    power_communicator = PowerCommunicator(power_serial, power_controller)
    power_communicator.start()

    gateway_api = GatewayApi(master_communicator, power_communicator, power_controller)

    maintenance_service = MaintenanceService(gateway_api, constants.get_ssl_private_key_file(),
                                             constants.get_ssl_certificate_file())

    passthrough_service = PassthroughService(master_communicator, passthrough_serial)
    passthrough_service.start()

    web_interface = WebInterface(user_controller, gateway_api,
                                 constants.get_scheduling_database_file(), maintenance_service,
                                 led_service.in_authorized_mode, config_controller)

    plugin_controller = PluginController(web_interface)

    web_interface.set_plugin_controller(plugin_controller)
    gateway_api.set_plugin_controller(plugin_controller)

    metrics_collector = MetricsCollector(gateway_api)
    metrics_controller = MetricsController(plugin_controller, metrics_collector, config_controller, gateway_uuid)

    metrics_collector.set_controllers(metrics_controller, plugin_controller)
    metrics_collector.set_plugin_intervals(plugin_controller.metric_intervals)

    metrics_controller.add_receiver(metrics_controller.receiver)
    metrics_controller.add_receiver(web_interface.distribute_metric)

    plugin_controller.set_metrics_controller(metrics_controller)
    web_interface.set_metrics_collector(metrics_collector)
    web_interface.set_metrics_controller(metrics_controller)

    web_service = WebService(web_interface)

    def _on_output(*args, **kwargs):
        metrics_collector.on_output(*args, **kwargs)
        gateway_api.on_outputs(*args, **kwargs)
    
    def _on_input(*args, **kwargs):
        metrics_collector.on_input(*args, **kwargs)
        gateway_api.on_inputs(*args, **kwargs)

    master_communicator.register_consumer(
        BackgroundConsumer(master_api.output_list(), 0, _on_output, True)
    )
    master_communicator.register_consumer(
        BackgroundConsumer(master_api.input_list(), 0, _on_input)
    )

    plugin_controller.start_plugins()
    metrics_controller.start()
    metrics_collector.start()
    web_service.start()

    led_service.set_led('stat2', True)

    led_thread = threading.Thread(target=led_driver, args=(led_service,
                                                           master_communicator, power_communicator))
    led_thread.setName("Serial led driver thread")
    led_thread.daemon = True
    led_thread.start()

    def stop(signum, frame):
        """ This function is called on SIGTERM. """
        _ = signum, frame
        sys.stderr.write("Shutting down")
        led_service.set_led('stat2', False)
        web_service.stop()
        metrics_collector.stop()
        metrics_controller.stop()
        plugin_controller.stop()

    signal(SIGTERM, stop)


if __name__ == "__main__":
    setup_logger()
    main()

