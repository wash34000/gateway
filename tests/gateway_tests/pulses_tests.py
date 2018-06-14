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
Tests for the pulses module.

@author: fryckbos
"""

import unittest
import time
import os
from threading import Lock

from master.master_communicator import MasterCommunicator
from gateway.pulses import PulseCounterController

import master.master_api as master_api
from master_tests.eeprom_controller_tests import get_eeprom_controller_dummy
from serial_tests import SerialMock, sout, sin

class PulseCounterControllerTest(unittest.TestCase):
    """ Tests for PulseCounterController. """

    FILE = 'test.db'

    def setUp(self):  # pylint: disable=C0103
        """ Run before each test. """
        if os.path.exists(PulseCounterControllerTest.FILE):
            os.remove(PulseCounterControllerTest.FILE)

    def tearDown(self):  # pylint: disable=C0103
        """ Run after each test. """
        if os.path.exists(PulseCounterControllerTest.FILE):
            os.remove(PulseCounterControllerTest.FILE)

    @staticmethod
    def _get_controller(master_communicator):
        """ Get a PulseCounterController using FILE. """
        banks = []
        for i in xrange(255):
            banks.append("\xff" * 256)

        eeprom_controller = get_eeprom_controller_dummy(banks)

        return PulseCounterController(PulseCounterControllerTest.FILE, master_communicator, eeprom_controller)

    def test_pulse_counter_up_down(self):
        """ Test adding and removing pulse counters. """
        controller = self._get_controller(None)

        # Only master pulse counters
        controller.set_pulse_counter_amount(24)
        self.assertEquals(24, controller.get_pulse_counter_amount())

        # Add virtual pulse counters
        controller.set_pulse_counter_amount(28)
        self.assertEquals(28, controller.get_pulse_counter_amount())

        # Add virtual pulse counter
        controller.set_pulse_counter_amount(29)
        self.assertEquals(29, controller.get_pulse_counter_amount())

        # Remove virtual pulse counter
        controller.set_pulse_counter_amount(28)
        self.assertEquals(28, controller.get_pulse_counter_amount())

        # Set virtual pulse counters to 0
        controller.set_pulse_counter_amount(24)
        self.assertEquals(24, controller.get_pulse_counter_amount())

        # Set the number of pulse counters to low
        try:
            controller.set_pulse_counter_amount(23)
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEquals('amount should be 24 or more', str(e))

    def test_pulse_counter_status(self):
        action = master_api.pulse_list()

        in_fields = {}
        out_fields = {'pv0':0, 'pv1':1, 'pv2':2, 'pv3':3, 'pv4':4, 'pv5':5, 'pv6':6, 'pv7':7,
                      'pv8':8, 'pv9':9, 'pv10':10, 'pv11':11, 'pv12':12, 'pv13':13, 'pv14':14,
                      'pv15':15, 'pv16':16, 'pv17':17, 'pv18':18, 'pv19':19, 'pv20':20, 'pv21':21,
                      'pv22':22, 'pv23':23, 'crc':[67, 1, 20]}

        serial_mock = SerialMock(
                        [sin(action.create_input(1, in_fields)),
                         sout(action.create_output(1, out_fields))])

        master_communicator = MasterCommunicator(serial_mock, init_master=False)
        master_communicator.start()

        controller = self._get_controller(master_communicator)
        controller.set_pulse_counter_amount(26)
        controller.set_pulse_counter_status(24, 123)
        controller.set_pulse_counter_status(25, 456)

        status = controller.get_pulse_counter_status()
        self.assertEquals([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,123,456], status)

        # Set pulse counter for unexisting pulse counter
        try:
            controller.set_pulse_counter_status(26, 789)
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEquals('could not find pulse counter 26', str(e))

        # Set pulse counter for physical pulse counter
        try:
            controller.set_pulse_counter_status(23, 789)
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEquals('cannot set pulse counter status for 23 (should be > 23)', str(e))

    def test_config(self):
        controller = self._get_controller(None)

        controller.set_pulse_counter_amount(26)

        controller.set_configurations([
            {'id':1,'name':'Water','input':10,'room':1},
            {'id':4,'name':'Gas','input':11,'room':2},
            {'id':25,'name':'Electricity','input':-1,'room':3}
        ])

        configs = controller.get_configurations()

        self.assertTrue([{'input': 255, 'room': 255, 'id': 0, 'name': ''},
                          {'input': 10, 'room': 1, 'id': 1, 'name': 'Water'},
                          {'input': 255, 'room': 255, 'id': 2, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 3, 'name': ''},
                          {'input': 11, 'room': 2, 'id': 4, 'name': 'Gas'},
                          {'input': 255, 'room': 255, 'id': 5, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 6, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 7, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 8, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 9, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 10, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 11, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 12, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 13, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 14, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 15, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 16, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 17, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 18, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 19, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 20, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 21, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 22, 'name': ''},
                          {'input': 255, 'room': 255, 'id': 23, 'name': ''},
                          {'input': -1, 'room': 255, 'id': 24, 'name': ''},
                          {'input': -1, 'room': 3, 'id': 25, 'name': 'Electricity'}], configs)

        # Try to set input on virtual pulse counter
        try:
            controller.set_configuration({'id':25,'name':'Electricity','input':22,'room':3})
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEquals('virtual pulse counter 25 can only have input -1', str(e))

        # Get configuration for existing master pulse counter
        self.assertEquals({'input': 10, 'room': 1, 'id': 1, 'name': 'Water'}, controller.get_configuration(1))
        
        # Get configuration for existing virtual pulse counter
        self.assertEquals({'input': -1, 'room': 3, 'id': 25, 'name': 'Electricity'}, controller.get_configuration(25))

        # Get configuration for unexisting pulse counter
        try:
            controller.set_configuration({'id':26,'name':'Electricity','input':-1,'room':3})
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEquals('could not find pulse counter 26', str(e))

        # Set configuration for unexisting pulse counter
        try:
            controller.get_configuration(26)
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEquals('could not find pulse counter 26', str(e))


if __name__ == '__main__':
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
