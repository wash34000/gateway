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
Tool to control the master from the command line.

@author: fryckbos
"""

import argparse
import sys
from ConfigParser import ConfigParser

from serial import Serial

import constants

import master.master_api as master_api
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
    parser.add_argument('--wipe', dest='wipe', action='store_true',
                        help='wip the master eeprom')

    args = parser.parse_args()

    config = ConfigParser()
    config.read(constants.get_config_file())

    port = config.get('OpenMotics', 'controller_serial')

    if args.port:
        print port
    elif args.sync or args.version or args.reset or args.wipe:
        master_serial = Serial(port, 115200)
        master_communicator = MasterCommunicator(master_serial)
        master_communicator.start()

        if args.sync:
            try:
                master_communicator.do_command(master_api.status())
            except CommunicationTimedOutException:
                print "Failed"
                sys.exit(1)
            else:
                print "Done"
                sys.exit(0)
        elif args.version:
            status = master_communicator.do_command(master_api.status())
            print "%d.%d.%d H%d" % (status['f1'], status['f2'], status['f3'], status['h'])
        elif args.reset:
            master_communicator.do_command(master_api.reset())
            print "Reset !"
        elif args.wipe:
            (num_banks, bank_size, write_size) = (256, 256, 10)
            print "Wiping the master"
            for bank in range(0, num_banks):
                print " Wiping bank %d" % bank
                for addr in range(0, bank_size, write_size):
                    master_communicator.do_command(master_api.write_eeprom(),
                        {'bank': bank, 'address': addr, 'data': '\xff' * write_size})

            master_communicator.do_command(master_api.activate_eeprom(), {'eep' : 0})
            print "Done wiping the master"

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
