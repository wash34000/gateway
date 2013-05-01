'''
Tool to bootload the power modules from the command line.

Created on Apr 20, 2013

@author: fryckbos
'''
import argparse
from ConfigParser import ConfigParser

import intelhex

from serial import Serial
from serial_utils import RS485

import constants

from power.power_communicator import PowerCommunicator
from power.power_api import bootloader_goto, bootloader_read_id, bootloader_write_code, bootloader_write_configuration, bootloader_jump_application

class HexReader:
    """ Reads the hex from file and returns it in the OpenMotics format. """
    
    def __init__(self, hex_file):
        """ Constructor with the name of the hex file. """
        self.__ih = intelhex.IntelHex(hex_file)
        self.__crc = 0
    
    def get_bytes(self, address):
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
    
    def get_crc(self):
        """ Get the crc for the block that have been read from the HexReader. """
        return self.__crc


def bootload(port, paddr, hex_file, verbose=False):
    """ Bootload a power module.
    
    :param paddr: The address of a power module (integer).
    :param hex_file: The filename of the hex file to write.
    :param verbose: Show serial command on output if verbose is True.
    """
    power_serial = RS485(Serial(port, 115200))
    
    power_communicator = PowerCommunicator(power_serial, None, time_keeper_period=0, verbose=verbose)
    power_communicator.start()

    reader = HexReader(hex_file)
    
    print("Going to bootloader")
    power_communicator.do_command(paddr, bootloader_goto(), 10)

    print("Reading chip id")
    id = power_communicator.do_command(paddr, bootloader_read_id())
    if id[0] != 213:
        raise Exception("Unknown chip id: %d" % id[0])

    print("Writing vector tabel")
    for address in range(0, 512, 128):      # 0x000 - 0x200
        print(" Writing %d" % address)
        bytes = reader.get_bytes(address)
        power_communicator.do_command(paddr, bootloader_write_code(), *bytes)

    print("Writing code")
    for address in range(8192, 44032, 128): # 0x2000 - 0xAC00
        print(" Writing %d" % address)
        bytes = reader.get_bytes(address)
        power_communicator.do_command(paddr, bootloader_write_code(), *bytes)
    
    print("Jumping to application")
    power_communicator.do_command(paddr, bootloader_jump_application())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tool to bootload a power module.')
    parser.add_argument('--address', dest='address', type=int,
                        help='the address of the power module to bootload')
    parser.add_argument('--file', dest='file',
                        help='the filename of the hex file to bootload')
    parser.add_argument('--verbose', dest='verbose', action='store_true',
                        help='show the serial output')
    
    args = parser.parse_args()
    
    config = ConfigParser()
    config.read(constants.get_config_file())
    
    port = config.get('OpenMotics', 'power_serial')
    
    if args.address and args.file:
        bootload(port, args.address, args.file, verbose=args.verbose)
    else:
        parser.print_help()
