""" The physical frontend are the leds and switch on the front panel of the gateway.
This service allows other services to set the leds over dbus and check whether the
gateway is in authorized mode.
"""

import gobject

import dbus
import dbus.service
import dbus.mainloop.glib
import fcntl
import time

from ConfigParser import ConfigParser

import constants


I2C_DEVICE = '/dev/i2c-2'
IOCTL_I2C_SLAVE = 0x0703
I2C_SLAVE_ADDRESS = None # Read from config file
CODES = { 'uart4':64, 'uart5':128, 'vpn':16, 'stat1':0, 'stat2':32, 'alive':1, 'cloud':4 }

HOME = 75

ETH_LEFT = 60
ETH_RIGHT = 49

AUTH_LOOP = [ '1', '0', '1', '0', '0', '0', '0', '0' ]

class StatusObject(dbus.service.Object):
    """ The StatusObject contains the methods exposed over dbus, the serial and network activity
    checkers and the 'authorized' button checker. """

    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)
        self.__network_enabled = False
        self.__network_activity = False
        self.__network_bytes = 0
        
        self.__serial_activity = { 4: False, 5: False }
        self.__enabled_leds = {}
        self.__last_code = 0
        
        self.__authorized_mode = False
        self.__authorized_timeout = 0
        self.__authorized_index = 0
        
        self.clear_leds()

    @dbus.service.method("com.openmotics.status", in_signature='', out_signature='')
    def clear_leds(self):
        """ Turn all LEDs off. """
        for led in CODES:
            self.__enabled_leds[led] = False
        self.__set_output()

    @dbus.service.method("com.openmotics.status", in_signature='sb', out_signature='')
    def set_led(self, led_name, enable):
        """ Set the state of a LED, enabled means LED on in this context. """
        self.__enabled_leds[led_name] = enable
        self.__set_output()
    
    @dbus.service.method("com.openmotics.status", in_signature='s', out_signature='')
    def toggle_led(self, led_name):
        """ Toggle the state of a LED. """
        self.__enabled_leds[led_name] = not self.__enabled_leds[led_name]
        self.__set_output()

    @dbus.service.method("com.openmotics.status", in_signature='i', out_signature='')
    def serial_activity(self, port):
        """ Report serial activity on the given serial port. Port is 4 or 5. """
        self.__serial_activity[port] = True

    @dbus.service.method("com.openmotics.status", in_signature='', out_signature='b')
    def in_authorized_mode(self):
        """ Returns whether the gateway is in authorized mode. Authorized mode is enabled when the
        button on the top panel is pushed and lasts for 60 seconds. """
        return self.__authorized_mode

    def __get_i2c_code(self):
        """ Generates the i2c code for the LEDs. """
        code = 0
        for led in CODES:
            if self.__enabled_leds[led] == True:
                code |= CODES[led]
        return (~ code) & 255

    def __set_output(self):
        """ Set the LEDs using the current status. """
        try:
            new_code = self.__get_i2c_code()
            if new_code != self.__last_code:
                self.__last_code = new_code
                i2c = open(I2C_DEVICE, 'r+', 1)
                fcntl.ioctl(i2c, IOCTL_I2C_SLAVE, I2C_SLAVE_ADDRESS)
                i2c.write(chr(self.__get_i2c_code()))
                i2c.close()
        except Exception as exception:
            print "Error while writing to i2c: ", exception

    def serial(self):
        """ Function that toggles the UART LEDs in case there was activity on the port. 
        This function registers itself with the gobject creating a loop that runs every 100 ms. 
        """
        for uart in [4, 5]:
            if self.__serial_activity[uart]:
                self.toggle_led('uart' + str(uart))
            else:
                self.set_led('uart' + str(uart), False)
            self.__serial_activity[uart] = False
        gobject.timeout_add(100, self.serial)

    def network(self):
        """ Function that set the LEDs on the ethernet port using the statistics from /proc/net. 
        This function registers itself with the gobject creating a loop that runs every 100 ms. 
        """
        fh_up = open('/sys/class/net/eth0/carrier', 'r')
        line = fh_up.read()
        fh_up.close()
        self.__network_enabled = int(line) == 1
        
        fh_stat = open('/proc/net/dev', 'r')
        for line in fh_stat.readlines():
            if 'eth0' in line:
                parts = line.split()
                if len(parts) == 17:
                    received = parts[1]
                    transmitted = parts[9]
                elif len(parts) == 16:
                    (_, received) = tuple(parts[0].split(':'))
                    transmitted = parts[8]
                new_bytes = received + transmitted
                if self.__network_bytes != new_bytes:
                    self.__network_bytes = new_bytes
                    self.__network_activity = not self.__network_activity
                else:
                    self.__network_activity = False
        fh_stat.close()
        
        self.__set_network()
        gobject.timeout_add(100, self.network)

    def __set_network(self):
        """ Set the LEDs on the ethernet port using the current state. """
        fh_r = open("/sys/class/gpio/gpio%i/value" % ETH_LEFT, 'w')
        fh_r.write('1' if self.__network_enabled else '0')
        fh_r.close()
        
        fh_l = open("/sys/class/gpio/gpio%i/value" % ETH_RIGHT, 'w')
        fh_l.write('1' if self.__network_activity else '0')
        fh_l.close()
    
    def input(self):
        """ Read the input button on the top panel. Enables authorized mode for 60 seconds when the
        button is pushed. This function registers itself with the gobject creating a loop that runs
        every 100 ms. While the gateway is in authorized mode, the input button is not checked.
        """
        fh_inp = open('/sys/class/gpio/gpio38/value', 'r')
        line = fh_inp.read()
        fh_inp.close()
        button_pressed = (int(line) == 0)
        if button_pressed:
            self.__authorized_mode = True
            self.__authorized_timeout = time.time() + 60
            gobject.timeout_add(100, self.__authorized)
        else:
            gobject.timeout_add(100, self.input)
    
    def __authorized(self):
        """ The authorized loop runs when the gateway is in authorized mode: it makes the LED in the
        OpenMotics logo flash and checks whether the timeout for the authorized mode is reached.
        """
        if time.time() > self.__authorized_timeout:
            self.__authorized_mode = False
            self.__authorized_timeout = 0
            self.__set_home('1')
            gobject.timeout_add(100, self.input)
        else:
            self.__set_home(AUTH_LOOP[self.__authorized_index])
            self.__authorized_index = (self.__authorized_index + 1) % len(AUTH_LOOP)
            gobject.timeout_add(100, self.__authorized)
    
    def __set_home(self, value):
        """ Set the status of the LED in the OpenMotics logo. """
        fh_home = open("/sys/class/gpio/gpio%i/value" % HOME, 'w')
        fh_home.write(value)
        fh_home.close()

def main():
    """ The main function runs a loop that waits for dbus calls, drives the leds and reads the
    switch. """
    config = ConfigParser()
    config.read(constants.get_config_file())
    
    global I2C_SLAVE_ADDRESS
    I2C_SLAVE_ADDRESS = int(config.get('OpenMotics', 'leds_i2c_address'), 16)
    
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    system_bus = dbus.SystemBus()
    name = dbus.service.BusName("com.openmotics.status", system_bus)
    status = StatusObject(system_bus, '/com/openmotics/status')

    mainloop = gobject.MainLoop()
    gobject.timeout_add(100, status.network)
    gobject.timeout_add(100, status.serial)
    gobject.timeout_add(100, status.input)
    
    print "Running physical frontend service."
    mainloop.run()


if __name__ == '__main__':
    main()
