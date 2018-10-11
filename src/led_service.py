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
from platform_utils import hardware

import constants


IOCTL_I2C_SLAVE = 0x0703
CODES = {'uart4': 64, 'uart5': 128, 'vpn': 16, 'stat1': 0, 'stat2': 0, 'alive': 1, 'cloud': 4}
AUTH_CODE = 1 + 4 + 16 + 64 + 128

AUTH_LOOP = [True, False, True, False, False, False, False, False]


class LOGGER(object):
    @staticmethod
    def log(line):
        sys.stdout.write('{0}\n'.format(line))
        sys.stdout.flush()


def is_button_pressed(gpio_pin):
    """ Read the input button: returns True if the button is pressed, False if not. """
    with open('/sys/class/gpio/gpio{0}/value'.format(gpio_pin), 'r') as fh_inp:
        line = fh_inp.read()
    return int(line) == 0


def detect_button(gpio_1, gpio_2):
    """
    Detect which gpio pin is connected the input button. If the button is not connected, the
    pin will look as if the button is pressed. So if there is one input that is not pressed, it
    must be connected to the button. If both pins look pressed, it defaults to the first given
    gpio.
    """
    first_pressed = is_button_pressed(gpio_1)
    second_pressed = is_button_pressed(gpio_2)

    if not first_pressed:
        return gpio_1
    elif not second_pressed:
        return gpio_2
    else:
        return gpio_1


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
        self._enabled_gpio = {}
        self._previous_gpio = {}
        self._last_code = 0

        self._authorized_mode = False
        self._authorized_timeout = 0
        self._authorized_index = 0

        self._check_states_thread = None

        self._is_bbb = hardware.is_beagle_bone_black()
        self._gpios = hardware.get_gpios()

        self.clear_leds()

    def start(self):
        """ Start the leds and buttons thread. """
        self._check_states_thread = Thread(target=self._check_states)
        self._check_states_thread.daemon = True
        self._check_states_thread.start()

    @dbus.service.method("com.openmotics.status", in_signature='', out_signature='')
    def clear_leds(self):
        """ Turn all LEDs off. """
        for led in CODES:
            self._enabled_leds[led] = False
        self._write_leds()

    @dbus.service.method("com.openmotics.status", in_signature='sb', out_signature='')
    def set_led(self, led_name, enable):
        """ Set the state of a LED, enabled means LED on in this context. """
        self._enabled_leds[led_name] = bool(enable)

    @dbus.service.method("com.openmotics.status", in_signature='s', out_signature='')
    def toggle_led(self, led_name):
        """ Toggle the state of a LED. """
        self._enabled_leds[led_name] = not self._enabled_leds[led_name]

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

    def set_gpio(self, gpio, on):
        """ Sets GPIO on/off """
        self._enabled_gpio[gpio] = on

    def _write_leds(self):
        """ Set the LEDs using the current status. """
        try:
            # Get i2c code
            code = 0
            for led in CODES:
                if self._enabled_leds[led] is True:
                    code |= CODES[led]
            if self._authorized_mode:
                # Light all leds in authorized mode
                code |= AUTH_CODE
            code = (~ code) & 255

            # Push code if needed
            if code != self._last_code:
                self._last_code = code
                with open(self._i2c_device, 'r+', 1) as i2c:
                    fcntl.ioctl(i2c, IOCTL_I2C_SLAVE, self._i2c_address)
                    i2c.write(chr(code))
        except Exception as exception:
            LOGGER.log('Error while writing to i2c: {0}'.format(exception))

    def _write_gpio(self):
        """ Sets the GPIO using the current status. """
        for gpio in self._enabled_gpio:
            on = self._enabled_gpio[gpio]
            if self._previous_gpio.get(gpio) != on:
                self._previous_gpio[gpio] = on
                try:
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
            if not self._is_bbb:
                self.set_gpio(self._gpios["ETH_LEFT_BB"], self._network_enabled)
                self.set_gpio(self._gpios["ETH_RIGHT_BB"], self._network_activity)
            else:
                self.set_gpio(self._gpios["ETH_STATUS_BBB"], not self._network_enabled)
                if self._network_activity:
                    self.toggle_led('alive')
                else:
                    self.set_led('alive', False)
            # Calculate serial led states
            for uart in [4, 5]:
                uart_name = 'uart{0}'.format(uart)
                if self._serial_activity[uart]:
                    self.toggle_led(uart_name)
                else:
                    self.set_led(uart_name, False)
                self._serial_activity[uart] = False
            # Update all leds & gpio
            self._write_leds()
            self._write_gpio()
        except Exception as exception:
            LOGGER.log('Error while driving leds: {0}'.format(exception))
        gobject.timeout_add(250, self.drive_leds)

    def check_button(self):
        """ Handles input button presses """
        try:
            if self._authorized_mode:
                if time.time() > self._authorized_timeout:
                    self._authorized_mode = False
                    self.set_gpio(self._gpios["HOME"], True)
                else:
                    self.set_gpio(self._gpios["HOME"], AUTH_LOOP[self._authorized_index])
                    self._authorized_index = (self._authorized_index + 1) % len(AUTH_LOOP)
                    # Still in authorized mode...
            else:
                if is_button_pressed(self._input_button):
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

        i2c_device = hardware.get_i2c_device()
        i2c_address = int(config.get('OpenMotics', 'leds_i2c_address'), 16)

        # @todo Check with team what are the situations on the field?
        # Issue is that Black shouldn't export gpio38 to userspace as it's used  for MMC !
        #gpio_input = detect_button(gpios["GPIO_INPUT_BUTTON_GW"], gpios["GPIO_INPUT_BUTTON_GW_M"])
        gpios = hardware.get_gpios()
        gpio_input = gpios["GPIO_INPUT_BUTTON_GW_M"] if hardware.is_beagle_bone_black() else gpios["GPIO_INPUT_BUTTON_GW"]

        status = StatusObject(system_bus, '/com/openmotics/status', i2c_device, i2c_address, gpio_input)
        status.start()

        status.set_gpio(gpios["POWER_BBB"], True)

        LOGGER.log("Running led service.")
        mainloop = gobject.MainLoop()

        gobject.timeout_add(250, status.drive_leds)
        gobject.timeout_add(250, status.check_button)

        mainloop.run()
    except Exception as exception:
        LOGGER.log('Error starting led service: {0}'.format(exception))


if __name__ == '__main__':
    main()
