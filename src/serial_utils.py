"""
Serial tools contains the RS485 wrapper, printable and CommunicationTimedOutException. 

Created on Dec 29, 2012

@author: fryckbos
"""
import struct
import fcntl

class CommunicationTimedOutException(Exception):
    """ An exception that is raised when the master did not respond in time. """
    def __init__(self):
        Exception.__init__(self)

def printable(string):
    """ Converts non-printable characters into hex notation """
    
    hex = " ".join(['%3d' % ord(c) for c in string])
    readable = "".join([c if ord(c) > 32 and ord(c) <= 126 else '.' for c in string])
    return hex + "    " + readable 

class RS485:
    """ Replicates the pyserial interface. """

    def __init__(self, serial):
        """ Initialize a rs485 connection using the serial port. """
        self.__serial = serial
        fd = serial.fileno()
        serial_rs485 = struct.pack('hhhhhhhh', 3, 0, 0, 0, 0, 0, 0, 0)
        fcntl.ioctl(fd, 0x542F, serial_rs485)
        serial.timeout = 1
    
    def write(self, data):
        """ Write data to serial port """
        self.__serial.write(data)
    
    def read(self, size):
        """ Read size bytes from serial port """
        return self.__serial.read(size)
    
    def inWaiting(self): #pylint: disable-msg=C0103
        """ Get the number of bytes pending to be read """
        return self.__serial.inWaiting()
