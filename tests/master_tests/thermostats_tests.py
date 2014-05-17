'''
Created on Feb 24, 2013

@author: fryckbos
'''
import unittest
import time

from master.thermostats import ThermostatStatus

class ThermostatStatusTest(unittest.TestCase):
    """ Tests for ThermostatStatus. """

    def test_should_refresh(self):
        """ Test the should_refresh functionality. """
        status = ThermostatStatus([], 100)
        self.assertFalse(status.should_refresh())

        status.force_refresh()
        self.assertTrue(status.should_refresh())

        status = ThermostatStatus([], 0.001)
        time.sleep(0.01)
        self.assertTrue(status.should_refresh())


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
