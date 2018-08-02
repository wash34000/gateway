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
The LedService class communicates over dbus with the led service
and can be used to set the status of the leds or read the authorized mode.
"""

import dbus
import sys


def check_for_errors(default_ret):
    """ Decorator that checks if dbus is active and catches exceptions.
    If an exception is thrown, default_ret is returned.
    """
    def wrapped(func):
        """ Wrapped function. """
        def new_func(self, *args, **kwargs):
            """ New function checks bus and catches exceptions. """
            if self.bus is None:
                self.bus = LedService.get_bus()
            if self.bus is not None:
                try:
                    return func(self, *args, **kwargs)
                except:
                    sys.stderr.write("Failed to communicate with led_service\n")
                    self.bus = None
            return default_ret
        return new_func
    return wrapped


class LedService(object):
    """ Communicates with the leds service using dbus. """

    LEDS = ['uart4', 'uart5', 'vpn', 'stat1', 'stat2', 'alive', 'cloud']

    def __init__(self):
        self.bus = LedService.get_bus()

    @staticmethod
    def get_bus():
        """"
        Try to get the dbus interface to the led_service.

        :returns: None on Exception
        """
        try:
            system_bus = dbus.SystemBus()
            return system_bus.get_object('com.openmotics.status', '/com/openmotics/status')
        except Exception as ex:
            sys.stderr.write("Could not initialize dbus to led_service: {0}\n".format(ex))
            sys.stderr.flush()
            return None

    @check_for_errors(None)
    def set_led(self, led_name, enabled):
        """ Set the status of a LED. """
        self.bus.set_led(led_name, enabled, dbus_interface='com.openmotics.status')

    @check_for_errors(None)
    def toggle_led(self, led_name):
        """ Toggle the status of a LED. """
        self.bus.toggle_led(led_name, dbus_interface='com.openmotics.status')

    @check_for_errors(None)
    def serial_activity(self, uart):
        """ Register serial activity on a given UART. """
        self.bus.serial_activity(uart, dbus_interface='com.openmotics.status')

    @check_for_errors(False)
    def in_authorized_mode(self):
        """ Check if the gateway is in authorized mode. """
        return self.bus.in_authorized_mode(dbus_interface='com.openmotics.status')
