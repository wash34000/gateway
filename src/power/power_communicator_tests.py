'''
Tests for PowerCommunicator module.

Created on Dec 29, 2012

@author: fryckbos
'''
import unittest
import os
import time
import logging

import power_api
from power_controller import PowerController
from power_communicator import PowerCommunicator, InAddressModeException

from serial_test import SerialMock, sin, sout
from serial_utils import CommunicationTimedOutException

class PowerCommunicatorTest(unittest.TestCase):
    """ Tests for PowerCommunicator class """

    FILE = "test.db"
    
    def setUp(self): #pylint: disable-msg=C0103
        """ Run before each test. """
        if os.path.exists(PowerCommunicatorTest.FILE):
            os.remove(PowerCommunicatorTest.FILE)
    
    def tearDown(self): #pylint: disable-msg=C0103
        """ Run after each test. """
        if os.path.exists(PowerCommunicatorTest.FILE):
            os.remove(PowerCommunicatorTest.FILE)

    def __get_communicator(self, serial_mock, time_keeper_period=0, address_mode_timeout=60):
        """ Get a PowerCommunicator. """
        return PowerCommunicator(serial_mock, PowerController(PowerCommunicatorTest.FILE), time_keeper_period=time_keeper_period, address_mode_timeout=address_mode_timeout)

    def test_do_command(self):
        """ Test for standard behavior PowerCommunicator.do_command. """
        action = power_api.get_voltage()
        
        serial_mock = SerialMock(
                        [ sin(action.create_input(1, 1)),
                        sout(action.create_output(1, 1, 49.5)) ])
        
        comm = self.__get_communicator(serial_mock)
        comm.start()
        
        output = comm.do_command(1, action)
        
        self.assertEquals((49.5, ), output)
 
        self.assertEquals(14, comm.get_bytes_written())
        self.assertEquals(18, comm.get_bytes_read())
    
    def test_do_command_timeout(self):
        """ Test for timeout in PowerCommunicator.do_command. """
        action = power_api.get_voltage()
        
        serial_mock = SerialMock([ sin(action.create_input(1, 1)), sout('') ])
        
        comm = self.__get_communicator(serial_mock)
        comm.start()
        
        try:
            comm.do_command(1, action)
            self.assertTrue(False)
        except CommunicationTimedOutException:
            pass
    
    def test_do_command_timeout_test_ongoing(self):
        """ Test if communication resumes after timeout. """
        action = power_api.get_voltage()
        
        serial_mock = SerialMock([ sin(action.create_input(1, 1)), sout(''),
                                   sin(action.create_input(1, 2)),
                                   sout(action.create_output(1, 2, 49.5)) ])
        
        comm = self.__get_communicator(serial_mock)
        comm.start()
        
        try:
            comm.do_command(1, action)
            self.assertTrue(False)
        except CommunicationTimedOutException:
            pass
        
        output = comm.do_command(1, action)
        self.assertEquals((49.5, ), output)
    
    def test_do_command_split_data(self):
        """ Test PowerCommunicator.do_command when the data is split over multiple reads. """
        action = power_api.get_voltage()
        out = action.create_output(1, 1, 49.5)
        
        serial_mock = SerialMock(
                        [ sin(action.create_input(1, 1)),
                        sout(out[:5]), sout(out[5:]) ])
        
        comm = self.__get_communicator(serial_mock)
        comm.start()
        
        output = comm.do_command(1, action)
        
        self.assertEquals((49.5, ), output)
    
    def test_wrong_response(self):
        """ Test PowerCommunicator.do_command when the power module returns a wrong response. """
        action_1 = power_api.get_voltage()
        action_2 = power_api.get_frequency()
        
        serial_mock = SerialMock([ sin(action_1.create_input(1, 1)),
                                   sout(action_2.create_output(3, 2, 49.5)) ])
        
        comm = self.__get_communicator(serial_mock)
        comm.start()
        
        try:
            comm.do_command(1, action_1)
            self.assertTrue(False)
        except Exception:
            pass
    
    def test_address_mode(self):
        """ Test the address mode. """
        serial_mock = SerialMock(
            [ sin(power_api.set_addressmode().create_input(power_api.BROADCAST_ADDRESS, 1, power_api.ADDRESS_MODE)),
              sout(power_api.want_an_address().create_input(0, 0)),
              sin(power_api.set_address().create_input(0, 0, 1)),
              sout(power_api.want_an_address().create_input(0, 0)),
              sin(power_api.set_address().create_input(0, 0, 2)),
              sout(''), ## Timeout read after 1 second
              sin(power_api.set_addressmode().create_input(power_api.BROADCAST_ADDRESS, 2, power_api.NORMAL_MODE))
            ], 1)
        
        comm = self.__get_communicator(serial_mock)
        comm.start()
        
        comm.start_address_mode()
        self.assertTrue(comm.in_address_mode())
        time.sleep(0.5)
        comm.stop_address_mode()
        
        self.assertFalse(comm.in_address_mode())
    
    def test_do_command_in_address_mode(self):
        """ Test the behavior of do_command in address mode."""
        action = power_api.get_voltage()
        
        serial_mock = SerialMock(
            [ sin(power_api.set_addressmode().create_input(power_api.BROADCAST_ADDRESS, 1, power_api.ADDRESS_MODE)),
              sout(''), ## Timeout read after 1 second
              sin(power_api.set_addressmode().create_input(power_api.BROADCAST_ADDRESS, 2, power_api.NORMAL_MODE)),
              sin(action.create_input(1, 3)),
              sout(action.create_output(1, 3, 49.5))
            ], 1)
        
        comm = self.__get_communicator(serial_mock)
        comm.start()
        
        comm.start_address_mode()
        
        try:
            comm.do_command(1, action)
            self.assertFalse(True)
        except InAddressModeException:
            pass
        
        comm.stop_address_mode()
        
        self.assertEquals((49.5, ), comm.do_command(1, action))
    
    def test_address_mode_timeout(self):
        """ Test address mode timeout. """
        action = power_api.get_voltage()
        
        serial_mock = SerialMock(
            [ sin(power_api.set_addressmode().create_input(power_api.BROADCAST_ADDRESS, 1, power_api.ADDRESS_MODE)),
              sout(''), ## Timeout read after 1 second
              sin(power_api.set_addressmode().create_input(power_api.BROADCAST_ADDRESS, 2, power_api.NORMAL_MODE)),
              sin(action.create_input(1, 3)),
              sout(action.create_output(1, 3, 49.5))
            ], 1)
        
        comm = self.__get_communicator(serial_mock, address_mode_timeout=1)
        comm.start()
        
        comm.start_address_mode()
        time.sleep(1.1)
        
        self.assertEquals((49.5, ), comm.do_command(1, action))        
    
    def test_timekeeper(self):
        """ Test the TimeKeeper. """
        action = power_api.get_voltage()
        
        serial_mock = SerialMock(
            [ sin(power_api.set_day_night().create_input(power_api.BROADCAST_ADDRESS, 1, power_api.NIGHT)),
              sin(action.create_input(1, 2)),
              sout(action.create_output(1, 2, 243))
            ], 1)
        
        comm = self.__get_communicator(serial_mock, 1)
        comm.start()
        
        time.sleep(1.5)
        
        self.assertEquals((243, ), comm.do_command(1, action))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    logger = logging.getLogger("openmotics")
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    
    unittest.main()
