'''
Tests for gateway_api module.

Created on Oct 25, 2012

@author: fryckbos
'''
import unittest

import master.master_api
from master.master_command import MasterCommandSpec, Field
import gateway_api

class MasterCommunicatorDummy:
    """ Dummy for the MasterCommunicator. """
    
    def register_consumer(self, consumer):
        pass

class GatewayApiTest(unittest.TestCase):
    """ Tests for :class`GatewayApi`. """

    def test_check_crc(self):
        """ Test the check crc method. """
        gateway = gateway_api.GatewayApi(MasterCommunicatorDummy())
        
        test_command = MasterCommandSpec("tt", 
                                         [ Field.byte('thermostat'), Field.padding(13) ],
                                         [ Field.byte('byte_field'), Field.svt('svt_field'), 
                                           Field.str('str_field', 16), Field.bytes('crc', 3) ])
        
        crc = 14 + (20 + 32) * 2
        for ch in 'test            ':
            crc += ord(ch)
        
        self.assertTrue(gateway.check_crc(test_command,
                          { 'byte_field' : 14,
                            'svt_field': master_api.Svt(master_api.Svt.TEMPERATURE, 20),
                            'str_field': 'test            ',
                            'crc': [ ord('C'), (crc / 256), (crc % 256) ] }))

        self.assertFalse(gateway.check_crc(test_command,
                          { 'byte_field' : 14,
                            'svt_field': master_api.Svt(master_api.Svt.TEMPERATURE, 20),
                            'str_field': 'test            ',
                            'crc': [ ord('C'), 0, 0 ] }))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
