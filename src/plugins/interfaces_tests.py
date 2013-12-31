'''
Tests for plugins.interfaces.
Created on Dec 30, 2013

@author: fryckbos
'''
import unittest

from base import *
from interfaces import *

class CheckInterfacesTest(unittest.TestCase):
    """ Tests for check_interfaces. """
    
    def test_no_interfaces(self):
        """ Test a plugin without interfaces. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = []
        
        check_interfaces(P1) ## Should not raise exceptions

    def test_wrong_interface_format(self):
        """ Test a plugin with the wrong interface format. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = "interface1"
        
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("The interfaces attribute on plugin 'P1' is not a list.", str(e))
        
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ "interface1" ]
            
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Interface 'interface1' on plugin 'P1' is not a tuple of (name, version).", str(e))
    
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("interface1") ]
            
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Interface 'interface1' on plugin 'P1' is not a tuple of (name, version).", str(e))
    
    def test_interface_not_found(self):
        """ Test a plugin with an interface that is not known. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("myinterface", "2.0") ]
        
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Interface 'myinterface' with version '2.0' was not found.", str(e))

    def test_missing_method_interface(self):
        """ Test a plugin with a missing method. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("webui", "1.0") ]
        
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Plugin 'P1' has no method named 'html_index'", str(e))

    def test_not_a_method(self):
        """ Test where a name of an interface method is used for something else. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("webui", "1.0") ]
            html_index = "hello"
        
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Plugin 'P1' has no method named 'html_index'", str(e))

    def test_not_exposed_interface(self):
        """ Test a non-exposed method on a plugin. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("webui", "1.0") ]
            
            def html_index(self):
                return "hello"
        
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Plugin 'P1' does not expose method 'html_index'", str(e))

    def test_wrong_authentication_interface(self):
        """ Test a plugin with wrong authentication on a method. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("webui", "1.0") ]
            
            @om_expose(auth=False)
            def html_index(self):
                return "hello"
        
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Plugin 'P1': authentication for method 'html_index' does not match the interface authentication (True required).", str(e))

    def test_wrong_arguments(self):
        """ Test a plugin with wrong arguments to a method. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("config", "1.0") ]
            
            @om_expose(auth=True)
            def get_config_description(self):
                pass
            
            @om_expose(auth=True)
            def get_config(self):
                pass
            
            @om_expose(auth=True)
            def set_config(self, test):
                pass
        
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Plugin 'P1': the arguments for method 'set_config': ['test'] do not match the interface arguments: ['config'].", str(e))
    
    def test_missing_self(self):
        """ Test a plugin that is missing 'self' for a method. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("webui", "1.0") ]
            
            @om_expose(auth=True)
            def html_index():
                pass
            
        try:
            check_interfaces(P1)
        except PluginException as e:
            self.assertEquals("Method 'html_index' on plugin 'P1' lacks 'self' as first argument.", str(e))
    
    def test_ok(self):
        """ Test an interface check that succeeds. """
        class P1(OMPluginBase):
            name = "P1"
            version = "1.0"
            interfaces = [ ("config", "1.0"), ("webui", "1.0") ]
            
            @om_expose(auth=True)
            def get_config_description(self):
                pass
            
            @om_expose(auth=True)
            def get_config(self):
                pass
            
            @om_expose(auth=True)
            def set_config(self, config):
                pass
            
            @om_expose(auth=True)
            def html_index(self):
                pass
        
        check_interfaces(P1)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()