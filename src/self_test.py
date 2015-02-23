"""
The self test scripts runs the 'echo + 1' routine on the RS485 and 2 RS232
ports.
"""

import threading
import sys
import time

from serial import Serial
from serial_utils import RS485

def echo_plus_one(name, serial):
    ''' For each character received on the rx channel of the serial port,
    the character + 1 is send on transmit channel of the serial port.
    '''
    while True:
        try:
            data = serial.read(1)
            if data != None and len(data) > 0 and data[0] != '\x00':
                print "Read '%s' from %s" % (data, name)
                serial.write(chr((ord(data[0]) + 1) % 256))
        except:
            traceback.print_exc()

def start_echo_plus_one(name, serial):
    ''' Runs echo_plus_one in a separate thread. '''
    thread = threading.Thread(target=echo_plus_one, args=(name, serial))
    thread.setName("Echo thread %s" % name)
    thread.start()

if __name__ == "__main__":
    print "Starting tty echo's..."
    for tty in [ "/dev/ttyO1", "/dev/ttyO2", "/dev/ttyO5" ]:
        sys.stdout.write("Starting tty echo on %s... " % tty)
        start_echo_plus_one(tty, Serial(tty, 115200))
        sys.stdout.write("Done\n")

    for rs485 in [ "/dev/ttyO4" ]:
        sys.stdout.write("Starting rs485 echo on %s... " % rs485)
        start_echo_plus_one(rs485, RS485(Serial(rs485, 115200)))
        sys.stdout.write("Done\n")
