'''
Tests for MasterCommunicator module.

Created on Sep 10, 2012

@author: fryckbos
'''
import unittest
import threading

from master_communicator import MasterCommunicator, CommunicationTimedOutException
from master_communicator import InMaintenanceModeException, BackgroundConsumer
import master_api

from serial_mock import SerialMock, sin, sout

class MasterCommunicatorTest(unittest.TestCase):
    """ Tests for MasterCommunicator class """

    def test_do_command(self):
        """ Test for standard behavior MasterCommunicator.do_command. """
        action = master_api.basic_action()
        in_fields = { "action_type": 1, "action_number": 2 }
        out_fields = {"resp": "OK" }
        
        serial_mock = SerialMock(
                        [ sin(action.create_input(1, in_fields)),
                        sout(action.create_output(1, out_fields)) ])
        
        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        output = comm.do_command(action, in_fields)
        self.assertEquals("OK", output["resp"])

    def test_do_command_timeout(self):
        """ Test for timeout in MasterCommunicator.do_command. """
        action = master_api.basic_action()
        in_fields = { "action_type": 1, "action_number": 2 }
        
        serial_mock = SerialMock([ sin(action.create_input(1, in_fields)) ])
        
        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        try:
            comm.do_command(action, in_fields)
            self.assertTrue(False)
        except CommunicationTimedOutException:
            pass
    
    def test_do_command_passthrough(self):
        """ Test for the do_command with passthrough data. """
        action = master_api.basic_action()
        in_fields = { "action_type": 1, "action_number": 2 }
        out_fields = {"resp": "OK" }
        
        serial_mock = SerialMock(
                        [ sin(action.create_input(1, in_fields)),
                          sout("hello" + action.create_output(1, out_fields)),
                          sin(action.create_input(2, in_fields)), 
                          sout(action.create_output(2, out_fields) + "world"),
                          sin(action.create_input(3, in_fields)), 
                          sout("hello" + action.create_output(3, out_fields) + " world"),
                          sin(action.create_input(4, in_fields)), 
                          sout("hello"), sout(action.create_output(4, out_fields)) ])
        
        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("hello", comm.get_passthrough_data())
        
        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("world", comm.get_passthrough_data())
        
        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("hello world", comm.get_passthrough_data())
        
        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("hello", comm.get_passthrough_data())
    
    def test_do_command_split_data(self):
        """ Test MasterCommunicator.do_command when the data is split over multiple reads. """
        action = master_api.basic_action()
        in_fields = { "action_type": 1, "action_number": 2 }
        out_fields = {"resp": "OK" }
        
        sequence = []
        for i in range(1, 18):
            sequence.append(sin(action.create_input(i, in_fields)))
            output_bytes = action.create_output(i, out_fields)
            sequence.append(sout(output_bytes[:i]))
            sequence.append(sout(output_bytes[i:]))
        
        serial_mock = SerialMock(sequence)

        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        for i in range(1, 18):
            self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
    
    def test_send_passthrough_data(self):
        """ Test the passthrough if no other communications are going on. """
        pt_input = "data from passthrough"
        pt_output = "got it !"
        serial_mock = SerialMock([ sin(pt_input), sout(pt_output) ] )
        
        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        comm.send_passthrough_data(pt_input)
        self.assertEquals(pt_output, comm.get_passthrough_data())
    
    def test_passhthrough_output(self):
        """ Test the passthrough output if no other communications are going on. """
        serial_mock = SerialMock([ sout("passthrough"), sout(" my "), sout("data") ] )
        
        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        self.assertEquals("passthrough", comm.get_passthrough_data())
        self.assertEquals(" my ", comm.get_passthrough_data())
        self.assertEquals("data", comm.get_passthrough_data())
    
    def test_maintenance_mode(self):
        """ Test the maintenance mode. """
        serial_mock = SerialMock([ sin(master_api.to_cli_mode().create_input(0)),
                                   sout("OK"), sin("error list\r\n"), sout("the list\n"),
                                   sin(" "*18 + "\r\n\nexit\r\n") ])
        
        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        comm.start_maintenance_mode()
        
        try:
            comm.send_passthrough_data("test")
            self.assertTrue(False)
        except InMaintenanceModeException:
            pass
        
        try:
            comm.do_command(None, None)
            self.assertTrue(False)
        except InMaintenanceModeException:
            pass
        
        self.assertEquals("OK", comm.get_maintenance_data())
        comm.send_maintenance_data("error list\r\n")
        self.assertEquals("the list\n", comm.get_maintenance_data())
        comm.stop_maintenance_mode()
    
    def test_maintenance_passthrough(self):
        """ Test the behavior of passthrough in maintenance mode. """
        serial_mock = SerialMock([
                        sout("For passthrough"), sin(master_api.to_cli_mode().create_input(0)),
                        sout("OK"), sin("error list\r\n"), sout("the list\n"),
                        sin(" "*18 + "\r\n\nexit\r\n"), sout("Passthrough again") ])
        
        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        def passthrough_thread():
            """ Background thread that reads the passthrough data. """
            self.assertEquals("For passthrough", comm.get_passthrough_data())
            self.assertEquals("Passthrough again", comm.get_passthrough_data())
        
        thread = threading.Thread(target=passthrough_thread)
        thread.start()
        
        comm.start_maintenance_mode()
        self.assertEquals("OK", comm.get_maintenance_data())
        comm.send_maintenance_data("error list\r\n")
        self.assertEquals("the list\n", comm.get_maintenance_data())
        comm.stop_maintenance_mode()
        
        thread.join()

    def test_background_consumer(self):
        """ Test the background consumer mechanism. """
        action = master_api.basic_action()
        in_fields = { "action_type": 1, "action_number": 2 }
        out_fields = {"resp": "OK" }
        
        serial_mock = SerialMock([
                        sout("OL\x00\x01\x03\x04\r\n\r\n"), sin(action.create_input(1, in_fields)),
                        sout("junkOL\x00\x02\x03\x04\x05\x06\r\n\r\n here"),
                        sout(action.create_output(1, out_fields)) ])
        
        comm = MasterCommunicator(serial_mock)

        got_output = { "phase" : 1 }
        
        def callback(output):
            """ Callback that check if the correct result was returned for OL. """
            if got_output["phase"] == 1:
                self.assertEquals([ (3, 4) ], output["outputs"])
                got_output["phase"] = 2
            elif got_output["phase"] == 2:
                self.assertEquals([ (3, 4), (5, 6) ], output["outputs"])
                got_output["phase"] = 3
        
        comm.register_consumer(BackgroundConsumer(master_api.output_list(), 0, callback))
        comm.start()
        
        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals(3, got_output["phase"])
        self.assertEquals("junk here", comm.get_passthrough_data())
        
    def test_bytes_counter(self):
        """ Test the number of bytes written and read from the serial port. """
        action = master_api.basic_action()
        in_fields = { "action_type": 1, "action_number": 2 }
        out_fields = {"resp": "OK" }
        
        serial_mock = SerialMock(
                        [ sin(action.create_input(1, in_fields)),
                          sout("hello"),
                          sout(action.create_output(1, out_fields)) ])
                          
        comm = MasterCommunicator(serial_mock)
        comm.start()
        
        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("hello", comm.get_passthrough_data())
        
        self.assertEquals(21, comm.get_bytes_written())
        self.assertEquals(5 + 18, comm.get_bytes_read())
        

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()