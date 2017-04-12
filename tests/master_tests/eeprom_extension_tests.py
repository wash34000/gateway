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

@author: fryckbos
"""
import unittest
import time
import os

from master.eeprom_extension import EepromExtension
from master.eeprom_controller import EextByte, EextString, EepromModel, EepromId, EepromByte


class EepromExtensionTest(unittest.TestCase):
    """ Tests for EepromExtension. """

    FILE = "test.db"

    def setUp(self): #pylint: disable=C0103
        """ Run before each test. """
        if os.path.exists(EepromExtensionTest.FILE):
            os.remove(EepromExtensionTest.FILE)

    def tearDown(self): #pylint: disable=C0103
        """ Run after each test. """
        if os.path.exists(EepromExtensionTest.FILE):
            os.remove(EepromExtensionTest.FILE)

    def __get_extension(self):
        """ Get a EepromExtension using FILE. """
        return EepromExtension(EepromExtensionTest.FILE)

    def test_empty(self):
        """ Test an empty database. """
        ext = self.__get_extension()
        self.assertEquals(255, ext.read_extension_data('TestModel', 1, EextByte(),'test'))
        self.assertEquals("", ext.read_extension_data('TestModel', 1, EextString(),'test'))

        self.assertEquals(255, ext.read_extension_data('TestModel', 2, EextByte(),'test'))
        self.assertEquals("", ext.read_extension_data('TestModel', 2, EextString(),'test'))
        
    def test_write_read_int(self):
        """ Test read and write using integer data. """
        ext = self.__get_extension()
        ext.write_extension_data('TestModel', 1, EextByte(), 'test', 123)
        self.assertEquals(123, ext.read_extension_data('TestModel', 1, EextByte(), 'test'))

        ext.write_extension_data('TestModel', 1, EextByte(), 'test', 456)
        self.assertEquals(456, ext.read_extension_data('TestModel', 1, EextByte(),'test'))

        ext.write_extension_data('TestModel', 2, EextByte(), 'test', 789)
        self.assertEquals(456, ext.read_extension_data('TestModel', 1, EextByte(),'test'))
        self.assertEquals(789, ext.read_extension_data('TestModel', 2, EextByte(), 'test'))
        
    def test_write_read_string(self):
        """ Test read and write using string data. """
        ext = self.__get_extension()
        ext.write_extension_data('TestModel', 1, EextString(),'another', 'test')
        self.assertEquals('test', ext.read_extension_data('TestModel', 1, EextString(),'another'))

        ext.write_extension_data('TestModel', 1, EextString(),'another', 'new')
        self.assertEquals('new', ext.read_extension_data('TestModel', 1, EextString(),'another'))

        ext.write_extension_data('TestModel', 2, EextString(),'another', 'newer')
        self.assertEquals('new', ext.read_extension_data('TestModel', 1, EextString(),'another'))
        self.assertEquals('newer', ext.read_extension_data('TestModel', 2, EextString(),'another'))

    def test_read_model_empty(self):
        """ Test reading an empty model. """
        class TestModel(EepromModel):
            id = EepromId(102)
            normal_eeprom_field = EepromByte((0, 6))
            int_field = EextByte()
            str_field = EextString()

        ext = self.__get_extension()
        field_dict = ext.read_model(TestModel, 1)
        self.assertEquals({'int_field':255, 'str_field':''}, field_dict)

    def test_write_read_model(self):
        """ Test writing and reading a model. """
        class TestModel(EepromModel):
            id = EepromId(102)
            normal_eeprom_field = EepromByte((0, 6))
            int_field = EextByte()
            str_field = EextString()

        ext = self.__get_extension()
        ext.write_model(TestModel(id=1, normal_eeprom_field=6, int_field=7, str_field='hello'))

        field_dict = ext.read_model(TestModel, 1)
        self.assertEquals({'int_field':7, 'str_field':'hello'}, field_dict)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
