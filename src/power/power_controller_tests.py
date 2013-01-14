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
        
        self.assertEquals({1: {'input2': u'', 'input3': u'', 'input0': u'', 'input1': u'',
                               'input6': u'', 'uid': None, 'input4': u'', 'input5': u'',
                               'address': u'E\x01', 'id': 1, 'input7': u'', 'name': u''}},
                          power_controller.get_power_modules())
        
        self.assertEquals("E\x02", power_controller.get_free_address())
        
        power_controller.register_power_module("E\x05")
        self.assertEquals({1: {'input2': u'', 'input3': u'', 'input0': u'', 'input1': u'',
                               'input6': u'', 'uid': None, 'input4': u'', 'input5': u'',
                               'address': u'E\x01', 'id': 1, 'input7': u'', 'name': u''},
                           2: {'input2': u'', 'input3': u'', 'input0': u'', 'input1': u'',
                               'input6': u'', 'uid': None, 'input4': u'', 'input5': u'',
                               'address': u'E\x05', 'id': 2, 'input7': u'', 'name': u''}},
                          power_controller.get_power_modules())
        
        self.assertEquals("E\x06", power_controller.get_free_address())

    def test_update(self):
        """ Test for updating the power module information. """
        power_controller = self.__get_controller()
        self.assertEquals({}, power_controller.get_power_modules())
        
        power_controller.register_power_module("E\x01")
        
        self.assertEquals({1: {'input2': u'', 'input3': u'', 'input0': u'', 'input1': u'',
                               'input6': u'', 'uid': None, 'input4': u'', 'input5': u'',
                               'address': u'E\x01', 'id': 1, 'input7': u'', 'name': u''}},
                          power_controller.get_power_modules())
        
        power_controller.update_power_modules([{'id':1, 'name':'module1', 'input0':'in0',
                                                'input1':'in1', 'input2':'in2', 'input3':'in3',
                                                'input4':'in4', 'input5':'in5', 'input6':'in6',
                                                'input7':'in7'}])        
        
        self.assertEquals({1: {'id': 1, 'uid': None, 'address': 'E\x01', 'name':'module1',
                               'input0':'in0', 'input1':'in1', 'input2':'in2', 'input3':'in3',
                               'input4':'in4', 'input5':'in5', 'input6':'in6', 'input7':'in7' } },
                          power_controller.get_power_modules())


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
