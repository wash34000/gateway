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
    version = "1.0.0"
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
    version = "1.0.0"
    interfaces = [ ]
""")
            
            self.create_plugin("test2", """
from plugins.base import *

class P2(OMPluginBase):
    name = "P2"
    version = "1.0.0"
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
    
            def __init__(self, webservice, logger):
                OMPluginBase.__init__(self, webservice, logger)
    
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
        p1 = P1(None, None)
        
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
            pc.check_plugin(P1)
        except PluginException as e:
            self.assertEquals("attribute 'name' is missing from the plugin class", str(e))

        class P2(OMPluginBase):
            name = "malformed name"
        
        try:
            pc.check_plugin(P2)
        except PluginException as e:
            self.assertEquals("Plugin name 'malformed name' is malformed: can only contain letters, numbers and underscores.", str(e))

        class P2(OMPluginBase):
            name = "test_name123"
        
        try:
            pc.check_plugin(P2)
        except PluginException as e:
            self.assertEquals("attribute 'version' is missing from the plugin class", str(e))

        class P3(OMPluginBase):
            name = "test"
            version = "1.0.0"
        
        try:
            pc.check_plugin(P3)
        except PluginException as e:
            self.assertEquals("attribute 'interfaces' is missing from the plugin class", str(e))
        
        class P4(OMPluginBase):
            name = "test"
            version = "1.0.0"
            interfaces = []
        
        pc.check_plugin(P4)

        class P4(OMPluginBase):
            name = "test"
            version = "1.0.0"
            interfaces = [ ("webui", "1.0") ]
        
        try:
            pc.check_plugin(P4)
        except PluginException as e:
            self.assertEquals("Plugin 'test' has no method named 'html_index'", str(e))


from base import PluginConfigChecker, PluginException

full_descr = [
    { 'name' : 'hostname', 'type' : 'str',      'description': 'The hostname of the server.' },
    { 'name' : 'port',     'type' : 'int',      'description': 'Port on the server.' },
    { 'name' : 'use_auth', 'type' : 'bool',     'description': 'Use authentication while connecting.' },
    { 'name' : 'password', 'type' : 'password', 'description': 'Your secret password.' },
    { 'name' : 'enumtest', 'type' : 'enum',     'description': 'Test for enum', 'choices': [ 'First', 'Second' ] },
    
    { 'name' : 'outputs', 'type' : 'section', 'repeat' : True, 'min' : 1, 'content' : [
        { 'name' : 'output', 'type' : 'int' }
    ] },

    { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [
        { 'value': 'Facebook',  'content' : [ { 'name' : 'likes', 'type' : 'int' } ] },
        { 'value': 'Twitter',  'content' : [ { 'name' : 'followers', 'type' : 'int' } ] }
    ] }
]

class PluginConfigCheckerTest(unittest.TestCase):
    """ Tests for the PluginConfigChecker. """

    def test_constructor(self):
        """ Test for the constructor. """
        PluginConfigChecker(full_descr)

    def test_constructor_error(self):
        """ Test with an invalid data type """
        try:
            PluginConfigChecker({ 'test' : 123 })
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('list' in str(e))
        
        try:
            PluginConfigChecker([ { 'test' : 123 } ])
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('name' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 123 } ])
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('name' in str(e) and 'string' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'test' } ])
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('type' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'test', 'type' : 123 } ])
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('type' in str(e) and 'string' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'test', 'type' : 'something_else' } ])
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('type' in str(e) and 'something_else' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'test', 'type' : 'str', 'description': [] } ])
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('description' in str(e) and 'string' in str(e))
        
    def test_constructor_str(self):
        """ Test for the constructor for str. """
        PluginConfigChecker([ { 'name' : 'hostname', 'type' : 'str', 'description': 'The hostname of the server.' } ])
        PluginConfigChecker([ { 'name' : 'hostname', 'type' : 'str' } ])
        
        try:
            PluginConfigChecker([ { 'type' : 'str' } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('name' in str(e))

    def test_constructor_int(self):
        """ Test for the constructor for int. """
        PluginConfigChecker([ { 'name' : 'port', 'type' : 'int', 'description': 'Port on the server.' } ])
        PluginConfigChecker([ { 'name' : 'port', 'type' : 'int' } ])
        
        try:
            PluginConfigChecker([ { 'type' : 'int' } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('name' in str(e))

    def test_constructor_bool(self):
        """ Test for the constructor for bool. """
        PluginConfigChecker([ { 'name' : 'use_auth', 'type' : 'bool', 'description': 'Use authentication while connecting.' } ])
        PluginConfigChecker([ { 'name' : 'use_auth', 'type' : 'bool' } ])
        
        try:
            PluginConfigChecker([ { 'type' : 'bool' } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('name' in str(e))

    def test_constructor_password(self):
        """ Test for the constructor for bool. """
        PluginConfigChecker([ { 'name' : 'password', 'type' : 'password', 'description': 'A password.' } ])
        PluginConfigChecker([ { 'name' : 'password', 'type' : 'password' } ])
        
        try:
            PluginConfigChecker([ { 'type' : 'password' } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('name' in str(e))

    def test_constructor_enum(self):
        """ Test for the constructor for enum. """
        PluginConfigChecker([ { 'name' : 'enumtest', 'type' : 'enum', 'description': 'Test for enum', 'choices': [ 'First', 'Second' ] } ])
        PluginConfigChecker([ { 'name' : 'enumtest', 'type' : 'enum', 'choices': [ 'First', 'Second' ] } ])
        
        try:
            PluginConfigChecker([ { 'name' : 'enumtest', 'type' : 'enum', 'choices': 'First' } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e) and 'list' in str(e))
    
    def test_constructor_section(self):
        """ Test for the constructor for section. """
        PluginConfigChecker([ { 'name' : 'outputs', 'type' : 'section', 'repeat' : True, 'min' : 1,
                                'content' : [ { 'name' : 'output', 'type' : 'int' } ] } ])
        
        PluginConfigChecker([ { 'name' : 'outputs', 'type' : 'section', 'repeat' : False,
                                'content' : [ { 'name' : 'output', 'type' : 'int' } ] } ])
        
        PluginConfigChecker([ { 'name' : 'outputs', 'type' : 'section',
                                'content' : [ { 'name' : 'output', 'type' : 'int' } ] } ])
        
        try:
            PluginConfigChecker([ { 'name' : 'outputs', 'type' : 'section', 'repeat' : 'hello',
                                    'content' : [ { 'name' : 'output', 'type' : 'int' } ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('repeat' in str(e) and 'bool' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'outputs', 'type' : 'section', 'min' : 1,
                                    'content' : [ { 'name' : 'output', 'type' : 'int' } ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('min' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'outputs', 'type' : 'section',
                                    'content' : 'error' } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('content' in str(e) and 'list' in str(e))

        try:
            PluginConfigChecker([ { 'name' : 'outputs', 'type' : 'section',
                                    'content' : [ { 'name' : 123 } ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('content' in str(e) and 'name' in str(e) and 'string' in str(e))
    
    def test_constructor_nested_enum(self):
        """ Test for constructor for nested enum. """
        PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [
                                { 'value': 'Facebook',  'content' : [ { 'name' : 'likes', 'type' : 'int' } ] },
                                { 'value': 'Twitter',  'content' : [ { 'name' : 'followers', 'type' : 'int' } ] }
                            ] } ])
        
        try:
            PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : 'test' } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e) and 'list' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [ 'test' ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e) and 'dict' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [ { } ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e) and 'value' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [ { 'value' : 123 } ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e) and 'value' in str(e) and 'string' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [ { 'value' : 'test' } ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e) and 'content' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [ { 'value' : 'test', 'content' : 'test' } ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e) and 'content' in str(e) and 'list' in str(e))
        
        try:
            PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [ { 'value' : 'test', 'content' : [ { }] } ] } ])
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e) and 'content' in str(e) and 'name' in str(e))
    
    def test_check_config_error(self):
        """ Test check_config with an invalid data type """
        pcc = PluginConfigChecker([ { 'name' : 'hostname', 'type' : 'str' } ])
        
        try:
            pcc.check_config('string')
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('dict' in str(e))
        
        try:
            pcc.check_config({ })
            self.fail("Expected PluginException")
        except PluginException as e:
            self.assertTrue('hostname' in str(e))
        
    def test_check_config_str(self):
        """ Test check_config for str. """
        pcc = PluginConfigChecker([ { 'name' : 'hostname', 'type' : 'str' } ])
        pcc.check_config({ 'hostname' : 'cloud.openmotics.com' })
        
        try:
            pcc.check_config({ 'hostname' : 123 })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('str' in str(e))

    def test_check_config_int(self):
        """ Test check_config for int. """
        pcc = PluginConfigChecker([ { 'name' : 'port', 'type' : 'int' } ])
        pcc.check_config({ 'port' : 123 })
        
        try:
            pcc.check_config({ 'port' : "123" })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('int' in str(e))

    def test_check_config_bool(self):
        """ Test check_config for bool. """
        pcc = PluginConfigChecker([ { 'name' : 'use_auth', 'type' : 'bool' } ])
        pcc.check_config({ 'use_auth' : True })
        
        try:
            pcc.check_config({ 'use_auth' : 234543 })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('bool' in str(e))

    def test_check_config_password(self):
        """ Test check_config for bool. """
        pcc = PluginConfigChecker([ { 'name' : 'password', 'type' : 'password' } ])
        pcc.check_config({ 'password' : 'test' })
        
        try:
            pcc.check_config({ 'password' : 123 })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('str' in str(e))
    
    def test_check_config_section(self):
        """ Test check_config for section. """
        pcc = PluginConfigChecker([ { 'name' : 'outputs', 'type' : 'section', 'repeat' : True, 'min' : 1,
                                      'content' : [ { 'name' : 'output', 'type' : 'int' } ] } ])
        
        pcc.check_config({ 'outputs' : [ ] })
        pcc.check_config({ 'outputs' : [ { 'output' : 2 } ] })
        pcc.check_config({ 'outputs' : [ { 'output' : 2 }, { 'output' : 4 } ] })
        
        try:
            pcc.check_config({ 'outputs' : 'test' })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('list' in str(e))
        
        try:
            pcc.check_config({ 'outputs' : [ { 'test' : 123 }] })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('section' in str(e) and 'output' in str(e))
    
    def test_check_config_nested_enum(self):
        """ Test check_config for nested_enum. """
        pcc = PluginConfigChecker([ { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [
                                        { 'value': 'Facebook',  'content' : [ { 'name' : 'likes', 'type' : 'int' } ] },
                                        { 'value': 'Twitter',  'content' : [ { 'name' : 'followers', 'type' : 'int' } ] }
                                    ] } ])
        
        pcc.check_config({ 'network' : [ 'Twitter' , { 'followers' : 3 } ] })
        pcc.check_config({ 'network' : [ 'Facebook' , { 'likes' : 3 } ] })
        
        try:
            pcc.check_config({ 'network' : 'test' })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('list' in str(e))
        
        try:
            pcc.check_config({ 'network' : [] })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('list' in str(e) and '2' in str(e))
            
        try:
            pcc.check_config({ 'network' : [ 'something else', {} ] })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('choices' in str(e))
        
        try:
            pcc.check_config({ 'network' : [ 'Twitter', {} ] })
            self.fail('Excepted exception')
        except PluginException as e:
            self.assertTrue('nested_enum dict' in str(e) and 'followers' in str(e))
    
    def test_simple(self):
        pcc = PluginConfigChecker([
            { 'name' : 'log_inputs',  'type' : 'bool', 'description': 'Log the input data.'  },
            { 'name' : 'log_outputs', 'type' : 'bool', 'description': 'Log the output data.' }
        ])
        
        print pcc.check_config({ 'log_inputs' : True, 'log_outputs' : False })
        
        print "Hello !"
        
    
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()