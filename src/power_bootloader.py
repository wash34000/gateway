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
Tool to bootload the power modules from the command line.

@author: fryckbos
"""

import sys
import argparse
from ConfigParser import ConfigParser

from platform_utils import System
System.import_eggs()

import intelhex

from serial import Serial
from serial_utils import RS485

import constants

from power.power_communicator import PowerCommunicator
from power.power_controller import PowerController
from power.power_api import bootloader_goto, bootloader_read_id, bootloader_write_code, \
                            bootloader_jump_application, bootloader_erase_code, get_version, \
                            POWER_API_8_PORTS, POWER_API_12_PORTS


class HexReader(object):
    """ Reads the hex from file and returns it in the OpenMotics format. """

    def __init__(self, hex_file):
        """ Constructor with the name of the hex file. """
        self.__ih = intelhex.IntelHex(hex_file)
        self.__crc = 0

    def get_bytes_8(self, address):
        """ Get the 192 bytes from the hex file, with 3 address bytes prepended. """
        bytes = []

        bytes.append(address % 256)
        bytes.append((address % 65536) / 256)
        bytes.append(address / 65536)

        iaddress = address * 2

        for i in range(64):
            data0 = self.__ih[iaddress + 4*i + 0]
            data1 = self.__ih[iaddress + 4*i + 1]
            data2 = self.__ih[iaddress + 4*i + 2]

            if address == 0 and i == 0: # Set the start address to the bootloader: 0x400
                data1 = 4

            bytes.append(data0)
            bytes.append(data1)
            bytes.append(data2)

            if not (address == 43904 and i >= 62): # Don't include the CRC bytes in the CRC
                self.__crc += data0 + data1 + data2

        if address == 43904: # Add the CRC at the end of the program
            bytes[-1] = self.__crc % 256
            bytes[-2] = (self.__crc % (256 * 256)) / 256
            bytes[-3] = (self.__crc % (256 * 256 * 256)) / (256 * 256)
            bytes[-4] = (self.__crc % (256 * 256 * 256 * 256)) / (256 * 256 * 256)

        return bytes

    def int_to_array_12(self, integer):
        """ Convert an integer to an array for the 12 port energy module. """
        return [integer % 256, (integer % 65536) / 256, (integer / 65536) % 256, (integer / 65536) / 256]

    def get_bytes_12(self, address):
        """ Get the 128 bytes from the hex file, with 4 address bytes prepended. """
        bytes = []

        bytes.extend(self.int_to_array_12(address))

        for i in range(32):
            data0 = self.__ih[address + 4*i + 0]
            data1 = self.__ih[address + 4*i + 1]
            data2 = self.__ih[address + 4*i + 2]
            data3 = self.__ih[address + 4*i + 3]

            bytes.append(data0)
            bytes.append(data1)
            bytes.append(data2)
            bytes.append(data3)

            if not (address == 486801280 and i == 31):
                self.__crc += data0 + data1 + data2 + data3

        if address == 486801280:
            bytes = bytes[:-4]
            bytes.extend(self.int_to_array_12(self.get_crc()))

        return bytes

    def get_crc(self):
        """ Get the crc for the block that have been read from the HexReader. """
        return self.__crc


def bootload_8(paddr, hex_file, power_communicator, verbose=False):
    """ Bootload a 8 port power module.

    :param paddr: The address of a power module (integer).
    :param hex_file: The filename of the hex file to write.
    :param power_communicator: Communication with the power modules.
    :param verbose: Show serial command on output if verbose is True.
    """
    reader = HexReader(hex_file)

    print "E%d - Going to bootloader" % paddr
    power_communicator.do_command(paddr, bootloader_goto(), 10)

    print "E%d - Reading chip id" % paddr
    id = power_communicator.do_command(paddr, bootloader_read_id())
    if id[0] != 213:
        raise Exception("Unknown chip id: %d" % id[0])

    print "E%d - Writing vector tabel" % paddr
    for address in range(0, 1024, 128):      # 0x000 - 0x400
        print " Writing %d" % address
        bytes = reader.get_bytes_8(address)
        power_communicator.do_command(paddr, bootloader_write_code(POWER_API_8_PORTS), *bytes)

    print "E%d -  Writing code" % paddr
    for address in range(8192, 44032, 128):  # 0x2000 - 0xAC00
        print " Writing %d" % address
        bytes = reader.get_bytes_8(address)
        power_communicator.do_command(paddr, bootloader_write_code(POWER_API_8_PORTS), *bytes)

    print "E%d - Jumping to application" % paddr
    power_communicator.do_command(paddr, bootloader_jump_application())


def bootload_12(paddr, hex_file, power_communicator, verbose=False):
    """ Bootload a 12 port power module.

    :param paddr: The address of a power module (integer).
    :param hex_file: The filename of the hex file to write.
    :param power_communicator: Communication with the power modules.
    :param verbose: Show serial command on output if verbose is True.
    """
    reader = HexReader(hex_file)

    print "E%d - Going to bootloader" % paddr
    power_communicator.do_command(paddr, bootloader_goto(), 10)

    print "E%d - Erasing code" % paddr
    for page in range(6, 64):
        power_communicator.do_command(paddr, bootloader_erase_code(), page)

    print "E%d -  Writing code" % paddr
    for address in range(0x1D006000, 0x1D03FFFB, 128):
        bytes = reader.get_bytes_12(address)
        power_communicator.do_command(paddr, bootloader_write_code(POWER_API_12_PORTS), *bytes)

    print "E%d - Jumping to application" % paddr
    power_communicator.do_command(paddr, bootloader_jump_application())


def version(paddr, power_communicator):
    """ Get the version of a power module.

    :param paddr: The address of a power module (integer).
    :param power_communicator: Communication with the power modules.
    """
    version = power_communicator.do_command(paddr, get_version())[0]
    return version.split("\x00")[0]


def main():
    """ The main function. """
    parser = argparse.ArgumentParser(description='Tool to bootload a power module.')
    parser.add_argument('--address', dest='address', type=int,
                        help='the address of the power module to bootload')
    parser.add_argument('--all', dest='all', action='store_true',
                        help='bootload all power modules')
    parser.add_argument('--file', dest='file',
                        help='the filename of the hex file to bootload')
    parser.add_argument('--8', dest='old', action='store_true',
                        help='bootload for the 8-port power modules')
    parser.add_argument('--version', dest='version', action='store_true',
                        help='display the version of the power module(s)')
    parser.add_argument('--verbose', dest='verbose', action='store_true',
                        help='show the serial output')

    args = parser.parse_args()

    config = ConfigParser()
    config.read(constants.get_config_file())

    port = config.get('OpenMotics', 'power_serial')
    power_serial = RS485(Serial(port, 115200))
    power_communicator = PowerCommunicator(power_serial, None, time_keeper_period=0,
                                           verbose=args.verbose)
    power_communicator.start()

    if args.address or args.all:
        power_controller = PowerController(constants.get_power_database_file())
        power_modules = power_controller.get_power_modules()
        if args.all:
            for module_id in power_modules:
                module = power_modules[module_id]
                addr = module['address']
                if args.version:
                    print "E%d - Version: %s" % (addr, version(addr, power_communicator))
                if args.file:
                    if args.old and module['version'] == POWER_API_8_PORTS:
                        bootload_8(addr, args.file, power_communicator, verbose=args.verbose)
                    elif not args.old and module['version'] == POWER_API_12_PORTS:
                        bootload_12(addr, args.file, power_communicator, verbose=args.verbose)

        else:
            addr = args.address
            modules = [module for module in power_modules.keys() if module['address'] == addr]
            if len(modules) != 1:
                print 'ERROR: Could not determine energy module version. Aborting'
                sys.exit(1)
            if args.version:
                print "E%d - Version: %s" % (addr, version(addr, power_communicator))
            if args.file:
                if args.old and module['version'] == POWER_API_8_PORTS:
                    bootload_8(addr, args.file, power_communicator, verbose=args.verbose)
                elif not args.old and module['version'] == POWER_API_12_PORTS:
                    bootload_12(addr, args.file, power_communicator, verbose=args.verbose)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
