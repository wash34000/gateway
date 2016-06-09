"""
Serial tools contains the RS485 wrapper, printable and CommunicationTimedOutException.

Created on Dec 29, 2012

@author: fryckbos
"""
import time
import struct
import fcntl
from threading import Thread
from Queue import Queue


class CommunicationTimedOutException(Exception):
    """ An exception that is raised when the master did not respond in time. """
    def __init__(self):
        Exception.__init__(self)


def printable(string):
    """ Converts non-printable characters into hex notation """

    hex_notation = " ".join(['%3d' % ord(c) for c in string])
    readable = "".join([c if 32 < ord(c) <= 126 else '.' for c in string])
    return hex_notation + "    " + readable


class RS485(object):
    """ Replicates the pyserial interface. """

    def __init__(self, serial):
        """ Initialize a rs485 connection using the serial port. """
        self.__serial = serial
        fileno = serial.fileno()
        serial_rs485 = struct.pack('hhhhhhhh', 3, 0, 0, 0, 0, 0, 0, 0)
        fcntl.ioctl(fileno, 0x542F, serial_rs485)
        serial.timeout = None
        self.__thread = Thread(target=self._reader)
        self.__thread.daemon = True
        self.__thread.start()
        self.read_queue = Queue()

    def write(self, data):
        """ Write data to serial port """
        self.__serial.write(data)

    def _reader(self):
        try:
            while True:
                byte = self.__serial.read(1)
                if len(byte) == 1:
                    self.read_queue.put(byte)
                size = self.__serial.inWaiting()
                if size > 0:
                    for byte in self.__serial.read(size):
                        self.read_queue.put(byte)
        except Exception as ex:
            print 'Error in reader: {0}'.format(ex)
