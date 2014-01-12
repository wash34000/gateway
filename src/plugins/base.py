""" The OpenMotics plugin decorators, base class and controller. """
import logging
LOGGER = logging.getLogger("openmotics")

import pkgutil
import importlib
import inspect
import threading
import re

import cherrypy

def om_expose(method=None, auth=True):
    """ Decorator to expose a method of the plugin class through the
    webinterface. The url will be /plugins/<plugin-name>/<method>.

    Normally an authentication token is required to access the method.
    The token will be checked and removed automatically when using the
    following construction:

    @om_expose
    def method_to_expose(self, ...):
        ...

    It is possible to expose a method without authentication: no token
    will be required to access the method, this is done as follows:

    @om_expose(auth=False)
    def method_to_expose(self, ...):
        ...

    """
    def decorate(method):
        if auth:
            # The decorated method has 'token' parameter
            def _exposed(self, token, *args, **kwargs):
                self.webinterface.check_token(token)
                return method(self, *args, **kwargs)
        else:
            # The decorated method has no 'token' parameter.
            def _exposed(*args, **kwargs):
                return method(*args, **kwargs)
        
        _exposed.exposed = True
        _exposed.auth = auth
        _exposed.orig = method
        return _exposed

    if method:
        # Actual decorator: @om_expose
        return decorate(method)
    else:
        # Decorator factory: @om_expose(...)
        return decorate


def input_status(method):
    """ Decorator to indicate that the method should receive input status messages.
    The receiving method should accept one parameter, a tuple of (input, output).
    Each time an input is pressed, the method will be called.
    
    Important !This method should not block, as this will result in an unresponsive system.
    Please use a separate thread to perform complex actions on input status messages.
    """
    method.input_status = True
    return method


def output_status(method):
    """ Decorator to indicate that the method should receive output status messages.
    The receiving method should accept one parameter, a list of tuples (output, dimmer value).
    Each time an output status is changed, the method will be called.
    
    Important !This method should not block, as this will result in an unresponsive system.
    Please use a separate thread to perform complex actions on output status messages.
    """
    method.output_status = True
    return method


def background_task(method):
    """ Decorator to indicate that the method is a background task. A thread running this
    background task will be started on startup.
    """
    method.background_task = True
    return method


class OMPluginBase:
    """ Base class for an OpenMotics plugin. Every plugin package should contain a 
    module with the name 'main' that contains a class that extends this class.
    """
    def __init__(self, webinterface):
        """ The web interface is provided to the plugin to interface with the OpenMotics
        system. """
        self.webinterface = webinterface


class PluginException(Exception):
    """ Exception that is raised when there are errors in a plugin implementation. """
    pass


class PluginController:
    """ The controller keeps track of all plugins in the system. """

    def __init__(self, webinterface):
        self.__webinterface = webinterface

        self.__plugins = self._gather_plugins()

        self.__input_status_receivers = []
        for plugin in self.__plugins:
            isrs = self._get_special_methods(plugin, 'input_status')
            for isr in isrs:
                self.__input_status_receivers.append((plugin.name, isr))

        self.__output_status_receivers = []
        for plugin in self.__plugins:
            osrs = self._get_special_methods(plugin, 'output_status')
            for osr in osrs:
                self.__output_status_receivers.append((plugin.name, osr))

    def _gather_plugins(self):
        """ Scan the plugins package for installed plugins in the form of subpackages. """
        import plugins
        objects = pkgutil.iter_modules(plugins.__path__) # (module_loader, name, ispkg)

        package_names = [ o[1] for o in objects if o[2] ] 

        plugin_descriptions = []
        for package_name in package_names:
            try:
                plugin_class = self._get_plugin_class(package_name)
                self._check_plugin(plugin_class)
                plugin_descriptions.append((package_name, plugin_class.name, plugin_class))
            except Exception as e:
                LOGGER.error("Could not load plugin in package '%s': %s" % (package_name, e))

        # Check for double plugins
        per_name = {}
        for description in plugin_descriptions:
            if description[1] not in per_name:
                per_name[description[1]] = [ description ]
            else:
                per_name[description[1]].append(description)
        
        # Remove plugins that are defined in multiple packages
        plugins = []
        for name in per_name:
            if len(per_name[name]) > 1:
                LOGGER.error("Plugin '%s' is not enabled, it was found in multiple packages : %s" %
                             (name, [ t[0] for t in per_name[name] ]))
            else:
                try:
                    plugin_class = per_name[name][0][2]
                    plugins.append(plugin_class(self.__webinterface))
                except Exception as e:
                    LOGGER.error("Exception while initializing plugin '%s': %s" % (name, e))

        return plugins

    def _get_plugin_class(self, package_name):
        """ Get the plugin class using the name of the plugin package. """
        plugin = __import__("plugins.%s" % package_name, globals(), locals(), [ 'main' ])
        plugin_class = None

        if not hasattr(plugin, 'main'):
            raise PluginException('Module main was not found in plugin %s' % package_name)

        for (_, obj) in inspect.getmembers(plugin.main):
            if inspect.isclass(obj) and issubclass(obj, OMPluginBase) and obj is not OMPluginBase:
                if plugin_class == None:
                    plugin_class = obj
                else:
                    raise PluginException('Found multiple OMPluginBase classes in %s.main' % package_name)

        if plugin_class != None:
            return plugin_class
        else:
            raise PluginException('OMPluginBase class not found in %s.main' % package_name)

    def _check_plugin(self, plugin_class):
        """ Check if the plugin class has name, version and interfaces attributes.
        Raises PluginException when the attributes are not present.
        """
        if not hasattr(plugin_class, 'name'):
            raise PluginException("attribute 'name' is missing from the plugin class")

        ## Check if valid plugin name
        if not re.match("^[a-zA-Z0-9_]+$", plugin_class.name):
            raise PluginException("Plugin name '%s' is malformed: can only contain letters, "
                                  "numbers and underscores." % plugin_class.name)

        if not hasattr(plugin_class, 'version'):
            raise PluginException("attribute 'version' is missing from the plugin class")

        if not hasattr(plugin_class, 'interfaces'):
            raise PluginException("attribute 'interfaces' is missing from the plugin class")
        
        from interfaces import check_interfaces
        check_interfaces(plugin_class)

    def _get_special_methods(self, plugin_object, method_attribute):
        """ Get all methods of a plugin object that have the given attribute. """
        def __check(member):
            return inspect.ismethod(member) and hasattr(member, method_attribute)

        return [ m[1] for m in inspect.getmembers(plugin_object, predicate=__check) ]

    def get_plugins(self):
        """ Get a list of all installed plugins. """
        return self.__plugins

    def start_background_tasks(self):
        """ Start all background tasks. """
        for plugin in self.__plugins:
            bts = self._get_special_methods(plugin, 'background_task')
            for bt in bts:
                thread = threading.Thread(target=bt)
                thread.name  = "Background thread for plugin '%s'" % plugin.name
                thread.daemon = True
                thread.start()

    def expose_plugins(self):
        """ Expose the plugins using cherrypy. """
        for plugin in self.__plugins:
            cherrypy.tree.mount(plugin, "/plugins/%s" % plugin.name)

    def process_input_status(self, input_status):
        """ Should be called when the input status changes, notifies all plugins. """
        for isr in self.__input_status_receivers:
            try:
                isr[1](input_status)
            except Exception as e:
                LOGGER.error("Exception while processing input status for plugin '%s': %s" % (isr[0], e))

    def process_output_status(self, output_status):
        """ Should be called when the output status changes, notifies all plugins. """
        for osr in self.__output_status_receivers:
            try:
                osr[1](output_status)
            except Exception as e:
                LOGGER.error("Exception while processing output status for plugin '%s': %s" % (osr[0], e))


class PluginConfigChecker:
    """ The standard configuration controller for plugins enables the plugin creator to easily
    implement the 'config' plugin interface. By specifying a configuration description, the
    PluginConfigController is able to verify if a configuration dict matches this description.
    The description is a list of dicts, each dict contains the 'name', 'type' and optionally
    'description' keys.
    
    These are the basic types: 'str', 'int', 'bool', 'password', these types don't have additional
    keys. For the 'enum' type the user specifies the possible values in a list of strings in the
    'choices' key.
    
    The complex types 'section' and 'nested_enum' allow the creation of lists and conditional
    elements.
    
    A 'nested_enum' allows the user to create a subsection of which the content depends on the
    choosen enum value. The 'choices' key should contain a list of dicts with two keys: 'value',
    the value of the enum and 'content', a configuration description like specified here.
    
    A 'section' allows the user to create a subsection or a list of subsections (when the 'repeat'
    key is present and true, a minimum number of subsections ('min' key) can be provided when
    'repeat' is true. The 'content' key should provide a configuration description like specified above.
    
    An example of a description:
    [
        { 'name' : 'hostname', 'type' : 'str',      'description': 'The hostname of the server.' },
        { 'name' : 'port',     'type' : 'int',      'description': 'Port on the server.' },
        { 'name' : 'use_auth', 'type' : 'bool',     'description': 'Use authentication while connecting.' },
        { 'name' : 'password', 'type' : 'password', 'description': 'Your secret password.' },
        { 'name' : 'enumtest', 'type' : 'enum',     'description': 'Test for enum', 'choices': [ 'First', 'Second' ] },
    
        { 'name' : 'outputs', 'type' : 'section', 'repeat' : true, 'min' : 1, 'content' : [
            { 'name' : 'output', 'type' : 'int' }
        ] },

        { 'name' : 'network',  'type' : 'nested_enum', 'choices' : [
            { 'value': 'Facebook',  'content' : [ { 'name' : 'likes', 'type' : 'int' } ] },
            { 'value': 'Twitter',  'content' : [ { 'name' : 'followers', 'type' : 'int' } ] }
        ] }
    ]
    """
    def __init__(self, description):
        """
        Creates a PluginConfigChecker using a description. If the description is not valid,
        a PluginException will be thrown.
        """
        self._check_description(description)
        self.__description = description

    def _check_description(self, description):
        if not isinstance(config, list):
            raise PluginException("The configuration description is not a list")
        else:
            for item in description:
                if 'name' not in item:
                    raise PluginException("The configuration item '%s' does not contain a 'name' key." % item)
                if not isinstance(item['name'], str):
                    raise PluginException("The key 'name' of configuration item '%s' is not a string." % item)

                if 'type' not in item:
                    raise PluginException("The configuration item '%s' does not contain a 'type' key." % item)
                if not isinstance(item['type'], str):
                    raise PluginException("The key 'type' of configuration item '%s' is not a string." % item)

                if 'description' in item and not isinstance(item['description'], str):
                    raise PluginException("The key 'description' of configuration item '%s' is not a string." % item)

                if item['type'] == 'enum':
                    self._check_enum(item)
                elif item['type'] == 'section':
                    self._check_section(item)
                elif item['type'] == 'nested_enum':
                    self._check_nested_enum(item)
                elif item['type'] not in [ 'str', 'int', 'bool', 'password' ]:
                    raise PluginException("Configuration item '%s' contains unknown type '%s'." % (item, item['type']))

    def _check_enum(self, item):
        if 'choices' not in item:
            raise PluginException("The configuration item '%s' does not contain a 'choices' key." % item)
        
        if not isinstance(item['choices'], list):
            raise PluginException("The key 'choices' of configuration item '%s' is not a list." % item)
        
        for choice in item['choices']:
            if not isinstance(choice, str):
                raise PluginException("An element of the 'choices' list of configuration item '%s' is not a string." % item)

    def _check_section(self, item):
        if 'repeat' in item and not isinstance(item['repeat'], bool):
            raise PluginException("The key 'repeat' of configuration item '%s' is not a bool." % item)
        
        if ('repeat' not in item or item['repeat'] == False) and 'min' in item:
            raise PluginException("The configuration item '%s' does contains a 'min' key but is not repeatable." % item)
        
        if 'min' in item and not isinstance(item['min'], int):
            raise PluginException("The key 'min' of configuration item '%s' is not an int." % item)
        
        if 'content' not in item:
            raise PluginException("The configuration item '%s' does not contain a 'content' key." % item)
        
        self._check_description(item['content'])

    def _check_nested_enum(self, item):
        if 'choices' not in item:
            raise PluginException("The configuration item '%s' does not contain a 'choices' key." % item)
        
        if not isinstance(item['choices'], list):
            raise PluginException("The key 'choices' of configuration item '%s' is not a list." % item)
        
        for choice in item['choices']:
            if not isinstance(choice, dict):
                raise PluginException("An element of the 'choices' list of configuration item '%s' is not a dict." % item)

            if 'value' not in choice:
                raise PluginException("The choices dict '%s' of item '%s' does not contain a 'value' key." % (choice, item['name']))
            
            if not isinstance(choice['value'], str):
                raise PluginException("The 'value' key of choices dict '%s' of item '%s' is not a string." % (choice, item['name']))
            
            if 'content' not in choice:
                raise PluginException("The choices dict '%s' of item '%s' does not contain a 'content' key." % (choice, item['name']))
            
            self._check_description(choice['content'])

    def check_config(self, config):
        """ Check if a config is valid for the description. Raises a PluginException if the config is not valid. """
        self._check_config(config, self._description)

    def _check_config(self, config, description):
        """ Check if a config is valid for this description. Raises a PluginException if the config is not valid. """
        if not isinstance(config, dict):
            raise PluginException("The config '%s' is not a dict" % config)
        
        for item in description:
            name = item['name']
            if name not in config:
                raise PluginException("The config does not contain key '%s'" % name)
            
            if item['type'] == 'str':
                if not isinstance(config[name], str):
                    raise PluginException("Config '%s': '%s' is not a string" % (name, config[name]))
            elif item['type'] == 'int':
                if not isinstance(config[name], int):
                    raise PluginException("Config '%s': '%s' is not an int" % (name, config[name]))
            elif item['type'] == 'bool':
                if not isinstance(config[name], bool):
                    raise PluginException("Config '%s': '%s' is not a bool" % (name, config[name]))
            elif item['type'] == 'password':
                if not isinstance(config[name], str):
                    raise PluginException("Config '%s': '%s' is not a str" % (name, config[name]))
            elif item['type'] == 'enum':
                if config[name] not in item['choices']:
                     raise PluginException("Config '%s': '%s' is not in the choices '%s'" % (name, config[name], item['choices']))
            elif item['type'] == 'section':
                if not isinstance(config[name], list):
                    raise PluginException("Config '%s': '%s' is not a list" % (name, config[name]))
                
                for config_section in config[name]:
                    self._check_config(config_section, item['content'])
            elif item['type'] == 'nested_enum':
                if not isinstance(config[name], list) or len(config[name]) != 2:
                    raise PluginException("Config '%s': '%s' is not a list of length 2" % (name, config[name]))
                
                choices = [ c['value'] for c in item['choices']]
                try:
                    i = choices.index(config[name][0])
                except ValueError:
                    raise PluginException("Config '%s': '%s' is not in the choices '%s'" % (name, config[name], choices))
                else:
                    self._check_config(config[name][1], item['choices'][i]['content'])
