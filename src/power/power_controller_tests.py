'''
Tests for the power controller module.

Created on Dec 29, 2012

@author: fryckbos
'''
import unittest
import os

from power_controller import PowerController

class PowerControllerTest(unittest.TestCase):
    """ Tests for PowerController. """

    FILE = "test.db"
    
    def setUp(self): #pylint: disable-msg=C0103
        """ Run before each test. """
        if os.path.exists(PowerControllerTest.FILE):
            os.remove(PowerControllerTest.FILE)
    
    def tearDown(self): #pylint: disable-msg=C0103
        """ Run after each test. """
        if os.path.exists(PowerControllerTest.FILE):
            os.remove(PowerControllerTest.FILE)

    def __get_controller(self):
        """ Get a PowerController using FILE. """
        return PowerController(PowerControllerTest.FILE)

    def test_empty(self):
        """ Test an empty database. """
        power_controller = self.__get_controller()
        self.assertEquals({}, power_controller.get_power_modules())
        self.assertEquals("E\x01", power_controller.get_free_address())
        
        power_controller.register_power_module("E\x01")
        self.assertEquals({ 1 : { "id" : 1, "address" : "E\x01" } } ,
                          power_controller.get_power_modules())
        
        self.assertEquals("E\x02", power_controller.get_free_address())
        
        power_controller.register_power_module("E\x05")
        self.assertEquals({ 1 : { "id" : 1, "address" : "E\x01" },
                            2 : { "id" : 2, "address" : "E\x05" } },
                          power_controller.get_power_modules())
        
        self.assertEquals("E\x06", power_controller.get_free_address())


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
