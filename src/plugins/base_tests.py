'''
Tests for plugins.base.
Created on Dec 31, 2013

@author: fryckbos
'''
import unittest

import os
import shutil

import plugins
base_path = os.path.dirname(plugins.__file__)

class PluginControllerTest(unittest.TestCase):
    """ Tests for the PluginController. """
    
    def create_plugin(self, name, code):
        path = "%s/%s" % (base_path, name)
        os.makedirs(path)
        
        f = open("%s/main.py" % path, "w")
        f.write(code)
        f.close()
        
        f = open("%s/__init__.py" % path, "w")
        f.close()

    def destroy_plugin(self, name):
        path = "%s/%s" % (base_path, name)
        if os.path.exists(path):
            shutil.rmtree(path)

    def test_get_one_plugin(self):
        """ Test getting one plugin in the plugins package. """
        try:
            self.create_plugin("test", """
from plugins.base import *

class P1(OMPluginBase):
    name = "P1"
    version = "1.0"
    interfaces = [ ]
""")
            from base import PluginController
            
            pc = PluginController(None)
            ps = pc.get_plugins()
            self.assertEquals(1, len(ps))
            self.assertEquals("P1", ps[0].name)
        finally:
            self.destroy_plugin("test")

    def test_get_two_plugins(self):
        """ Test getting two plugins in the plugins package. """
        try:
            self.create_plugin("test1", """
from plugins.base import *

class P1(OMPluginBase):
    name = "P1"
    version = "1.0"
    interfaces = [ ]
""")
            
            self.create_plugin("test2", """
from plugins.base import *

class P2(OMPluginBase):
    name = "P2"
    version = "1.0"
    interfaces = [ ]
""")

            from base import PluginController
            
            pc = PluginController(None)
            ps = pc.get_plugins()
            self.assertEquals(2, len(ps))
            
            self.assertEquals("P2", ps[0].name)
            self.assertEquals("P1", ps[1].name)
        finally:
            self.destroy_plugin("test1")
            self.destroy_plugin("test2")


    def test_get_special_methods(self):
        """ Test getting special methods on a plugin. """
        from plugins.base import OMPluginBase, om_expose, input_status, output_status, background_task

        class P1(OMPluginBase):
            name = "P1"
            version = "0.1.0"
            interfaces = [ ("webui", "1.0") ]
    
            def __init__(self, webservice):
                OMPluginBase.__init__(self, webservice)
    
            @om_expose(auth=True)
            def html_index(self):
                pass
    
            @om_expose(auth=False)
            def get_log(self):
                pass
    
            @input_status
            def input(self, inpst):
                pass
    
            @output_status
            def output(self, os):
                pass
            
            @background_task
            def run(self):
                pass
        
        from base import PluginController
        
        pc = PluginController(None)
        p1 = P1(None)
        
        ins = pc._get_special_methods(p1, "input_status")
        self.assertEquals(1, len(ins))
        self.assertEquals("input", ins[0].__name__)
        
        outs = pc._get_special_methods(p1, "output_status")
        self.assertEquals(1, len(outs))
        self.assertEquals("output", outs[0].__name__)
        
        bts = pc._get_special_methods(p1, "background_task")
        self.assertEquals(1, len(bts))
        self.assertEquals("run", bts[0].__name__)
    
    def test_check_plugin(self):
        """ Test the exception that can occur when checking a plugin. """
        from plugins.base import OMPluginBase, PluginException, om_expose, input_status, output_status, background_task
        
        from base import PluginController
        pc = PluginController(None)

        class P1(OMPluginBase):
            pass

        try:
            pc._check_plugin(P1)
        except PluginException as e:
            self.assertEquals("attribute 'name' is missing from the plugin class", str(e))

        class P2(OMPluginBase):
            name = "malformed name"
        
        try:
            pc._check_plugin(P2)
        except PluginException as e:
            self.assertEquals("Plugin name 'malformed name' is malformed: can only contain letters, numbers and underscores.", str(e))

        class P2(OMPluginBase):
            name = "test_name123"
        
        try:
            pc._check_plugin(P2)
        except PluginException as e:
            self.assertEquals("attribute 'version' is missing from the plugin class", str(e))

        class P3(OMPluginBase):
            name = "test"
            version = "1.0.0"
        
        try:
            pc._check_plugin(P3)
        except PluginException as e:
            self.assertEquals("attribute 'interfaces' is missing from the plugin class", str(e))
        
        class P4(OMPluginBase):
            name = "test"
            version = "1.0.0"
            interfaces = []
        
        pc._check_plugin(P4)

        class P4(OMPluginBase):
            name = "test"
            version = "1.0.0"
            interfaces = [ ("webui", "1.0") ]
        
        try:
            pc._check_plugin(P4)
        except PluginException as e:
            self.assertEquals("Plugin 'test' has no method named 'html_index'", str(e))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()