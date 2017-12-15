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
Tests for the eeprom extensions module.
"""

import unittest
import os

from master.eeprom_extension import EepromExtension


class EepromExtensionTest(unittest.TestCase):
    """ Tests for EepromExtension. """

    FILE = "test.db"

    def setUp(self):
        """ Run before each test. """
        _ = self
        if os.path.exists(EepromExtensionTest.FILE):
            os.remove(EepromExtensionTest.FILE)

    def tearDown(self):
        """ Run after each test. """
        _ = self
        if os.path.exists(EepromExtensionTest.FILE):
            os.remove(EepromExtensionTest.FILE)

    @staticmethod
    def _get_extension():
        """ Get a EepromExtension using FILE. """
        return EepromExtension(EepromExtensionTest.FILE)

    def test_read_write(self):
        """ Test reading written data """
        ext = EepromExtensionTest._get_extension()
        ext.write_data([('model_name', 0, 'some_field', 'value_0'),
                        ('model_name', 1, 'some_field', 'value_1'),
                        ('model_name', 2, 'some_field', 'value_2')])
        self.assertEqual('value_0', ext.read_data('model_name', None, 'some_field'))
        self.assertEqual('value_0', ext.read_data('model_name', 0, 'some_field'))
        self.assertEqual('value_1', ext.read_data('model_name', 1, 'some_field'))
        self.assertEqual('value_2', ext.read_data('model_name', 2, 'some_field'))
        self.assertIsNone(ext.read_data('model_name', 3, 'some_field'))


if __name__ == "__main__":
    unittest.main()
