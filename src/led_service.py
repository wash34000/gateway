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
Service that drives the leds and checks the switch on the front panel of the gateway.
This service allows other services to set the leds over dbus and check whether the
gateway is in authorized mode.
"""

import gobject
import sys
import dbus
import dbus.service
import dbus.mainloop.glib
import fcntl
import time
from threading import Thread
from ConfigParser import ConfigParser

from platform_utils import Hardware
import constants

AUTH_MODE_LEDS = [Hardware.Led.ALIVE, Hardware.Led.CLOUD, Hardware.Led.VPN, Hardware.Led.COMM_1, Hardware.Led.COMM_2]


class LOGGER(object):
    @staticmethod
    def log(line):
        sys.stdout.write('{0}\n'.format(line))
        sys.stdout.flush()


class StatusObject(dbus.service.Object):
    """
    The StatusObject contains the methods exposed over dbus, the serial and network activity
    checkers and the 'authorized' button checker.
    """

    def __init__(self, bus, path, i2c_device, i2c_address, input_button):
        dbus.service.Object.__init__(self, bus, path)
        self._i2c_device = i2c_device
        self._i2c_address = i2c_address
        self._input_button = input_button
        self._input_button_pressed_since = None

        self._network_enabled = False
        self._network_activity = False
        self._network_bytes = 0

        self._serial_activity = {4: False, 5: False}
        self._enabled_leds = {}
        self._previous_leds = {}
        self._last_i2c_led_code = 0

        self._authorized_mode = False
        self._authorized_timeout = 0

        self._check_states_thread = None

        self._gpio_led_config = Hardware.get_gpio_led_config()
        self._i2c_led_config = Hardware.get_i2c_led_config()
        for led in self._gpio_led_config.keys() + self._i2c_led_config.keys():
            self._enabled_leds[led] = False
            self._write_leds()

    def start(self):
        """ Start the leds and buttons thread. """
        self._check_states_thread = Thread(target=self._check_states)
        self._check_states_thread.daemon = True
        self._check_states_thread.start()

    @dbus.service.method("com.openmotics.status", in_signature='sb', out_signature='')
    def set_led(self, led_name, enable):
        """ Set the state of a LED, enabled means LED on in this context. """
        self._enabled_leds[led_name] = bool(enable)

    @dbus.service.method("com.openmotics.status", in_signature='s', out_signature='')
    def toggle_led(self, led_name):
        """ Toggle the state of a LED. """
        self._enabled_leds[led_name] = not self._enabled_leds.get(led_name, False)

    @dbus.service.method("com.openmotics.status", in_signature='i', out_signature='')
    def serial_activity(self, port):
        """ Report serial activity on the given serial port. Port is 4 or 5. """
        self._serial_activity[port] = True

    @dbus.service.method("com.openmotics.status", in_signature='', out_signature='b')
    def in_authorized_mode(self):
        """
        Returns whether the gateway is in authorized mode. Authorized mode is enabled when the
        button on the top panel is pushed and lasts for 60 seconds.
        """
        return self._authorized_mode

    @staticmethod
    def _is_button_pressed(gpio_pin):
        """ Read the input button: returns True if the button is pressed, False if not. """
        with open('/sys/class/gpio/gpio{0}/value'.format(gpio_pin), 'r') as fh_inp:
            line = fh_inp.read()
        return int(line) == 0

    def _write_leds(self):
        """ Set the LEDs using the current status. """
        try:
            # Get i2c code
            code = 0
            for led in self._i2c_led_config.keys():
                if self._enabled_leds.get(led, False) is True:
                    code |= self._i2c_led_config[led]
            if self._authorized_mode:
                # Light all leds in authorized mode
                for led in AUTH_MODE_LEDS:
                    code |= self._i2c_led_config.get(led, 0)
            code = (~ code) & 255

            # Push code if needed
            if code != self._last_i2c_led_code:
                self._last_i2c_led_code = code
                with open(self._i2c_device, 'r+', 1) as i2c:
                    fcntl.ioctl(i2c, Hardware.IOCTL_I2C_SLAVE, self._i2c_address)
                    i2c.write(chr(code))
        except Exception as exception:
            LOGGER.log('Error while writing to i2c: {0}'.format(exception))

        for led in self._gpio_led_config.keys():
            on = self._enabled_leds.get(led, False)
            if self._previous_leds.get(led) != on:
                self._previous_leds[led] = on
                try:
                    gpio = self._gpio_led_config[led]
                    with open('/sys/class/gpio/gpio{0}/value'.format(gpio), 'w') as fh_s:
                        fh_s.write('1' if on else '0')
                except IOError:
                    pass  # The GPIO doesn't exist or is read only

    def _check_states(self):
        """ Checks various states of the system (network) """
        while True:
            try:
                with open('/sys/class/net/eth0/carrier', 'r') as fh_up:
                    line = fh_up.read()
                self._network_enabled = int(line) == 1

                with open('/proc/net/dev', 'r') as fh_stat:
                    for line in fh_stat.readlines():
                        if 'eth0' in line:
                            received, transmitted = 0, 0
                            parts = line.split()
                            if len(parts) == 17:
                                received = parts[1]
                                transmitted = parts[9]
                            elif len(parts) == 16:
                                (_, received) = tuple(parts[0].split(':'))
                                transmitted = parts[8]
                            new_bytes = received + transmitted
                            if self._network_bytes != new_bytes:
                                self._network_bytes = new_bytes
                                self._network_activity = True
                            else:
                                self._network_activity = False
            except Exception as exception:
                LOGGER.log('Error while checking states: {0}'.format(exception))
            time.sleep(0.5)

    def drive_leds(self):
        """ This drives different leds (status, alive and serial) """
        try:
            # Calculate network led/gpio states
            self.set_led(Hardware.Led.STATUS, not self._network_enabled)
            if self._network_activity:
                self.toggle_led(Hardware.Led.ALIVE)
            else:
                self.set_led(Hardware.Led.ALIVE, False)
            # Calculate serial led states
            comm_map = {4: Hardware.Led.COMM_1,
                        5: Hardware.Led.COMM_2}
            for uart in [4, 5]:
                if self._serial_activity[uart]:
                    self.toggle_led(comm_map[uart])
                else:
                    self.set_led(comm_map[uart], False)
                self._serial_activity[uart] = False
            # Update all leds
            self._write_leds()
        except Exception as exception:
            LOGGER.log('Error while driving leds: {0}'.format(exception))
        gobject.timeout_add(250, self.drive_leds)

    def check_button(self):
        """ Handles input button presses """
        try:
            if self._authorized_mode:
                if time.time() > self._authorized_timeout:
                    self._authorized_mode = False
            else:
                if StatusObject._is_button_pressed(self._input_button):
                    if self._input_button_pressed_since is None:
                        self._input_button_pressed_since = time.time()
                    if time.time() > self._input_button_pressed_since + 5:
                        self._authorized_mode = True
                        self._authorized_timeout = time.time() + 60
                        self._input_button_pressed_since = None
                else:
                    self._input_button_pressed_since = None
        except Exception as exception:
            LOGGER.log('Error while checking button: {0}'.format(exception))
        gobject.timeout_add(250, self.check_button)


def main():
    """
    The main function runs a loop that waits for dbus calls, drives the leds and reads the
    switch.
    """
    try:
        config = ConfigParser()
        config.read(constants.get_config_file())

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        system_bus = dbus.SystemBus()
        _ = dbus.service.BusName("com.openmotics.status", system_bus)  # Initializes the bus
        # The above `_ = dbus...` need to be there, or the bus won't be initialized

        i2c_device = Hardware.get_i2c_device()
        i2c_address = int(config.get('OpenMotics', 'leds_i2c_address'), 16)

        status = StatusObject(system_bus, '/com/openmotics/status', i2c_device, i2c_address, Hardware.get_gpio_input())
        status.start()

        status.set_led(Hardware.Led.POWER, True)

        LOGGER.log("Running led service.")
        mainloop = gobject.MainLoop()

        gobject.timeout_add(250, status.drive_leds)
        gobject.timeout_add(250, status.check_button)

        mainloop.run()
    except Exception as exception:
        LOGGER.log('Error starting led service: {0}'.format(exception))


if __name__ == '__main__':
    main()
