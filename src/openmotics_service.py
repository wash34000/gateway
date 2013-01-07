'''
The main module for the OpenMotics

Created on Sep 23, 2012

@author: fryckbos
'''
import logging
import sys
import time
import threading

from serial import Serial
from signal import signal, SIGTERM
from ConfigParser import ConfigParser

import constants

from serial_utils import RS485

from gateway.webservice import WebService
from gateway.gateway_api import GatewayApi
from gateway.users import UserController

from frontend.physical_frontend import PhysicalFrontend

from master.maintenance import MaintenanceService
from master.master_communicator import MasterCommunicator
from master.passthrough import PassthroughService

from power.power_communicator import PowerCommunicator
from power.power_controller import PowerController

def setup_logger():
    """ Setup the OpenMotics logger. """
    logger = logging.getLogger("openmotics")
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def led_driver(physical_frontend, master_communicator):
    """ Blink the serial leds if necessary. """
    read = 0
    written = 0
    while True:
        if read != master_communicator.get_bytes_read() \
                or written != master_communicator.get_bytes_written():
            physical_frontend.serial_activity(5) # TODO Get the real port number !
        read = master_communicator.get_bytes_read()
        written = master_communicator.get_bytes_written()
        time.sleep(0.100)

def main():
    """ Main function. """
    config = ConfigParser()
    config.read(constants.get_config_file())
    
    defaults = { 'username' : config.get('OpenMotics', 'cloud_user'),
                 'password': config.get('OpenMotics', 'cloud_pass') }
    
    user_controller = UserController(constants.get_user_database_file(), defaults, 3600)
    
    physical_frontend = PhysicalFrontend()
    
    controller_serial_port = config.get('OpenMotics', 'controller_serial')
    passthrough_serial_port = config.get('OpenMotics', 'passthrough_serial')
    power_serial_port = config.get('OpenMotics', 'power_serial')
    
    controller_serial = Serial(controller_serial_port, 19200)
    passthrough_serial = Serial(passthrough_serial_port, 19200)
    power_serial = RS485(Serial(power_serial_port, 115200))
    
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
    
    web_service = WebService(user_controller, gateway_api, maintenance_service,
                             physical_frontend.in_authorized_mode)
    web_service.start()
    
    physical_frontend.set_led('stat2', True)
    
    led_thread = threading.Thread(target=led_driver, args=(physical_frontend, master_communicator))
    led_thread.setName("Serial led driver thread")
    led_thread.daemon = True
    led_thread.start()
    
    def stop(signum, frame):
        """ This function is called on SIGTERM. """
        sys.stderr.write("Shutting down")
        physical_frontend.set_led('stat2', False)
        web_service.stop()
    
    signal(SIGTERM, stop)


if __name__ == "__main__":
    setup_logger()
    main()
    