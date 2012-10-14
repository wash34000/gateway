'''
Tests for master_api module.

Created on Oct 13, 2012

@author: fryckbos
'''
import unittest

from master_api import Svt

class SvtTest(unittest.TestCase):
    """ Tests for :class`Svt`. """

    def test_temperature(self):
        """ Test the temperature type. """
        for temperature in range(-32, 95):
            self.assertEquals(temperature, int(Svt.temp(temperature).get_temperature()))
        
        self.assertEquals(chr(104), Svt.temp(20).get_byte())
    
    def test_time(self):
        """ Test the time type. """
        for hour in range(0, 24):
            for minute in range(0, 60, 10):
                time = "%02d:%02d" % (hour, minute)
                self.assertEquals(time, Svt.time(time).get_time())
        
        self.assertEquals("16:30", Svt.time("16:33").get_time())
        
        self.assertEquals(chr(99), Svt.time("16:30").get_byte())
    
    def test_raw(self):
        """ Test the raw type. """
        for value in range(0, 255):
            byte_value = chr(value)
            self.assertEquals(byte_value, Svt.from_byte(byte_value).get_byte())

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
