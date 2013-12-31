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
