'''
Tool to control the master from the command line.

Created on Oct 4, 2012

@author: fryckbos
'''
import argparse
import sys
import time
from ConfigParser import ConfigParser

from serial import Serial

import constants
from gateway.gateway_api import GatewayApi
from master.master_communicator import MasterCommunicator
from serial_utils import CommunicationTimedOutException


def main():
    """ The main function. """
    parser = argparse.ArgumentParser(description='Tool to control the master.')
    parser.add_argument('--port', dest='port', action='store_true',
                        help='get the serial port device')
    parser.add_argument('--sync', dest='sync', action='store_true',
                        help='sync the serial port')
    parser.add_argument('--reset', dest='reset', action='store_true',
                        help='reset the master')
    parser.add_argument('--version', dest='version', action='store_true',
                        help='get the version of the master')
    
    args = parser.parse_args()
    
    config = ConfigParser()
    config.read(constants.get_config_file())
    
    port = config.get('OpenMotics', 'controller_serial')
    
    if args.port:
        print port
    elif args.sync or args.version or args.reset:
        master_serial = Serial(port, 19200)
        master_communicator = MasterCommunicator(master_serial)
        master_communicator.start()
        gateway_api = GatewayApi(master_communicator)
        time.sleep(10) # Wait 10 seconds for communictor initialization
        
        if args.sync:
            try:
                _ = gateway_api.get_status()
            except CommunicationTimedOutException:
                print "Failed"
                sys.exit(1)
            else:
                print "Done"
                sys.exit(0)
        elif args.version:
            status = gateway_api.get_status()
            print status['version'] + " H" + str(status['hw_version'])
        elif args.reset:
            gateway_api.master_reset()
            print "Reset !"
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
