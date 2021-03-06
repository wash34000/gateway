# Copyright (C) 2016 OpenMotics BVBA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
""" The OpenMotics plugin decorators, base class and controller. """

import time
import cherrypy
import copy
import inspect
import logging
import os
import re
import pkgutil
import threading
import traceback
from collections import deque
from datetime import datetime
from plugins.decorators import *  # Import for backwards compatibility
from gateway.webservice import params_parser

try:
    import json
except ImportError:
    import simplejson as json

LOGGER = logging.getLogger("openmotics")


class WebInterfaceWrapper(object):
    def __init__(self, webinterface, logger):
        self.__webinterface = webinterface
        self.__logger = logger
        self.__warned = False

    def __getattr__(self, attribute):
        if hasattr(self.__webinterface, attribute):
            func = getattr(self.__webinterface, attribute)
            if callable(func) and hasattr(func, 'plugin_exposed') and func.plugin_exposed is True:
                new_func = self.parameter_wrapper(func)
                setattr(self, attribute, new_func)
                return new_func
        raise AttributeError()

    def check_token(self, token):
        return self.__webinterface._user_controller.check_token(token)

    def warn(self):
        if self.__warned is False:
            self.__logger('[W] Deprecation warning:')
            self.__logger('[W] - Plugins should not pass \'token\' to API calls')
            self.__logger('[W] - Plugins should use keyword arguments for API calls')
            self.__warned = True

    def parameter_wrapper(self, func):
        spec = inspect.getargspec(func)
        args_length = len(spec.args) - 1  # Don't count `self`

        def wrapper(*args, **kwargs):
            # 1. Try to remove a possible "token" parameter, which is now deprecated
            args = list(args)
            if 'token' in kwargs:
                del kwargs['token']
                self.warn()
            elif len(args) > 0:
                self.warn()
                if len(args) + len(kwargs) > args_length or len(kwargs) == 0:
                    del args[0]
            # 2. Convert to kwargs, so it's possible to do parameter parsing
            for i in xrange(len(args)):
                kwargs[spec.args[i + 1]] = args[i]
            if func.check is not None:
                params_parser(kwargs, func.check)
            return func(**kwargs)
        return wrapper


class OMPluginBase(object):
    """ Base class for an OpenMotics plugin. Every plugin package should contain a
    module with the name 'main' that contains a class that extends this class.
    """
    def __init__(self, webinterface, logger):
        """ The web interface is provided to the plugin to interface with the OpenMotics
        system.

        :param webinterface: Reference the OpenMotics webinterface, this can be used to
        perform actions, fetch status data, etc.
        :param logger: Function that can be called with one parameter: message (String),
        the message will be appended to the plugin's log. This log can be fetched using
        the webinterface.
        """
        self.webinterface = webinterface
        self.logger = logger

    def __get_config_path(self):
        """ Get the path for the plugin configuration file based on the plugin name. """
        return '/opt/openmotics/etc/pi_%s.conf' % self.__class__.name

    def read_config(self, default_config=None):
        """ Read the configuration file for the plugin: the configuration file contains json
        string that will be converted to a python dict, if an error occurs, the default confi
        is returned. The PluginConfigChecker can be used to check if the configuration is valid,
        this has to be done explicitly in the Plugin class.
        """
        config_path = self.__get_config_path()

        if os.path.exists(config_path):
            config_file = open(config_path, 'r')
            config = config_file.read()
            config_file.close()

            try:
                return json.loads(config)
            except Exception as exception:
                LOGGER.error("Exception while getting config for plugin '%s': "
                             "%s", self.__class__.name, exception)

        return default_config

    def write_config(self, config):
        """ Write the plugin configuration to the configuration file: the config is a python dict
        that will be serialized to a json string.
        """
        config_file = open(self.__get_config_path(), 'w')
        config_file.write(json.dumps(config))
        config_file.close()


class PluginException(Exception):
    """ Exception that is raised when there are errors in a plugin implementation. """
    pass


class PluginController(object):
    """ The controller keeps track of all plugins in the system. """

    def __init__(self, webinterface, config_controller):
        self.__webinterface = webinterface

        self.__stopped = False
        self.__logs = {}
        self.__plugins = self._gather_plugins()

        self.__input_status_receivers = []
        self.__output_status_receivers = []
        self.__shutter_status_receivers = []
        self.__event_receivers = []
        self.__metric_collectors = []
        self.__metric_receivers = []
        self.__metric_receiver_threads = {}
        self.__metrics_controller = None
        self.__config_controller = config_controller
        self.metric_receiver_queues = {}
        self.metric_intervals = []

        self.__receiver_mapping = {'input_status': self.__input_status_receivers,
                                   'output_status': self.__output_status_receivers,
                                   'shutter_status': self.__shutter_status_receivers,
                                   'receive_events': self.__event_receivers,
                                   'metric_data': self.__metric_collectors,
                                   'metric_receive': self.__metric_receivers}

        for plugin in self.__plugins:
            self.__add_receivers(plugin)
        self.__collector_runs = {}
        self.__metric_definitions = self.get_metric_definitions()

    def __add_receivers(self, plugin):
        """ Add the input and output receivers for a plugin. """
        for method_attribute, target in self.__receiver_mapping.iteritems():
            for method in PluginController._get_special_methods(plugin, method_attribute):
                target.append((plugin.name, method))
                if method_attribute == 'metric_receive':
                    metric_receive = method.metric_receive
                    self.metric_intervals.append(metric_receive)
            if method_attribute == 'metric_receive':
                self.metric_receiver_queues[plugin.name] = deque()
                thread = threading.Thread(target=self.__deliver_metrics, args=(plugin.name,))
                thread.setName('Metric delivery thread ({0})'.format(plugin.name))
                thread.daemon = True
                thread.start()
                self.__metric_receiver_threads[plugin.name] = thread

    def stop(self):
        self.__stopped = True

    def start_plugins(self):
        """ Start the background tasks for the plugins and expose them via the webinterface. """
        for plugin in self.__plugins:
            self.__start_plugin(plugin)

    def set_metrics_controller(self, metrics_controller):
        """ Sets the metrics controller """
        self.__metrics_controller = metrics_controller

    def __start_plugin(self, plugin):
        """ Start one plugin. """
        self.__start_background_tasks(plugin)
        self.__expose_plugin(plugin)

    def _gather_plugins(self):
        """ Scan the plugins package for installed plugins in the form of subpackages. """
        import plugins
        objects = pkgutil.iter_modules(plugins.__path__)  # (module_loader, name, ispkg)

        package_names = [o[1] for o in objects if o[2]]

        plugin_descriptions = []
        for package_name in package_names:
            try:
                plugin_class = PluginController.get_plugin_class(package_name)
                PluginController.check_plugin(plugin_class)
                plugin_descriptions.append((package_name, plugin_class.name, plugin_class))
            except Exception as exception:
                self.log(package_name, "Could not load plugin", exception)

        # Check for double plugins
        per_name = {}
        for description in plugin_descriptions:
            if description[1] not in per_name:
                per_name[description[1]] = [description]
            else:
                per_name[description[1]].append(description)

        # Remove plugins that are defined in multiple packages
        plugins = []
        for name in per_name:
            if len(per_name[name]) > 1:
                self.log(name, "Could not enable plugin",
                         "found in multiple pacakges: %s" % ([t[0] for t in per_name[name]],))
            else:
                try:
                    plugin_class = per_name[name][0][2]
                    logger = self.get_logger(name)
                    plugins.append(plugin_class(WebInterfaceWrapper(self.__webinterface, logger),
                                                logger))
                except Exception as exception:
                    self.log(name, "Could not initialize plugin", exception,
                             traceback.format_exc())

        return plugins

    @staticmethod
    def get_plugin_class(package_name):
        """ Get the plugin class using the name of the plugin package. """
        plugin = __import__(package_name, globals(), locals(), ['main'])
        plugin_class = None

        if not hasattr(plugin, 'main'):
            raise PluginException('Module main was not found in plugin %s' % package_name)

        for (_, obj) in inspect.getmembers(plugin.main):
            if inspect.isclass(obj) and issubclass(obj, OMPluginBase) and obj is not OMPluginBase:
                if plugin_class is None:
                    plugin_class = obj
                else:
                    raise PluginException('Found multiple OMPluginBase classes in %s.main' %
                                          package_name)

        if plugin_class is not None:
            return plugin_class
        else:
            raise PluginException('OMPluginBase class not found in %s.main' % package_name)

    @staticmethod
    def check_plugin(plugin_class):
        """ Check if the plugin class has name, version and interfaces attributes.
        Raises PluginException when the attributes are not present.
        """
        if not hasattr(plugin_class, 'name'):
            raise PluginException("attribute 'name' is missing from the plugin class")

        # Check if valid plugin name
        if not re.match(r"^[a-zA-Z0-9_]+$", plugin_class.name):
            raise PluginException("Plugin name '%s' is malformed: can only contain letters, "
                                  "numbers and underscores." % plugin_class.name)

        if not hasattr(plugin_class, 'version'):
            raise PluginException("attribute 'version' is missing from the plugin class")

        # Check if valid version (a.b.c)
        if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", plugin_class.version):
            raise PluginException("Plugin version '%s' is malformed: expected 'a.b.c' "
                                  "where a, b and c are numbers." % plugin_class.version)

        if not hasattr(plugin_class, 'interfaces'):
            raise PluginException("attribute 'interfaces' is missing from the plugin class")

        from plugins.interfaces import check_interfaces
        check_interfaces(plugin_class)

    @staticmethod
    def _get_special_methods(plugin_object, method_attribute):
        """ Get all methods of a plugin object that have the given attribute. """
        def __check(member):
            """ Check if a member is a method and has the given attribute. """
            return inspect.ismethod(member) and hasattr(member, method_attribute)

        return [m[1] for m in inspect.getmembers(plugin_object, predicate=__check)]

    def get_plugins(self):
        """ Get a list of all installed plugins. """
        return self.__plugins

    def __get_plugin(self, name):
        """ Get a plugin by name, None if it the plugin is not installed. """
        for plugin in self.__plugins:
            if plugin.name == name:
                return plugin

        return None

    def install_plugin(self, md5, package_data):
        """ Install a new plugin. """
        from tempfile import mkdtemp
        from shutil import rmtree
        from subprocess import call, check_output
        import hashlib

        # Check if the md5 sum matches the provided md5 sum
        hasher = hashlib.md5()
        hasher.update(package_data)
        calculated_md5 = hasher.hexdigest()

        if calculated_md5 != md5:
            raise Exception("The provided md5sum (%s) does not match the actual md5 of the "
                            "package data (%s)." % (md5, calculated_md5))

        tmp_dir = mkdtemp()
        try:
            # Extract the package_data
            tgz = open("%s/package.tgz" % tmp_dir, "wb")
            tgz.write(package_data)
            tgz.close()

            retcode = call("cd %s; mkdir new_package; tar xzf package.tgz -C new_package/" %
                           tmp_dir, shell=True)
            if retcode != 0:
                raise Exception("The package data (tgz format) could not be extracted.")

            # Create an __init__.py file, if it does not exist
            init_path = "%s/new_package/__init__.py" % tmp_dir
            if not os.path.exists(init_path):
                init_file = open(init_path, 'w')
                init_file.close()

            # Check if the package contains a valid plugin
            checker = open("%s/check.py" % tmp_dir, "w")
            checker.write("""import sys
sys.path.append('/opt/openmotics/python')
from platform_utils import System
System.import_eggs()

from plugins.base import PluginController, PluginException

try:
    p = PluginController.get_plugin_class('new_package')
    PluginController.check_plugin(p)
except Exception as exception:
    print "!! %s" % exception
else:
    print p.name
    print p.version
""")
            checker.close()

            checker_output = check_output("cd %s; python check.py" % tmp_dir, shell=True)
            if checker_output.startswith("!! "):
                raise Exception(checker_output[3:-1])

            # Get the name and version of the package
            checker_output = checker_output.split("\n")
            name = checker_output[0]
            version = checker_output[1]

            def parse_version(version_string):
                """ Parse the version from a string "x.y.z" to a tuple(x, y, z). """
                return tuple([int(x) for x in version_string.split(".")])

            # Check if a newer version of the package is already installed
            installed_plugin = self.__get_plugin(name)
            if installed_plugin is not None:
                if parse_version(version) <= parse_version(installed_plugin.version):
                    raise Exception("A newer version of plugins %s is already installed "
                                    "(current version = %s, to installed = %s)." %
                                    (name, installed_plugin.version, version))
                else:
                    # Remove the old version of the plugin
                    retcode = call("cd /opt/openmotics/python/plugins; rm -R %s" % name,
                                   shell=True)
                    if retcode != 0:
                        raise Exception("The old version of the plugin could not be removed.")

            # Check if the package directory exists, this can only be the case if a previous
            # install failed or if the plugin has gone corrupt: remove it !
            plugin_path = '/opt/openmotics/python/plugins/%s' % name
            if os.path.exists(plugin_path):
                rmtree(plugin_path)

            # Install the package
            retcode = call("cd %s; mv new_package %s" % (tmp_dir, plugin_path), shell=True)
            if retcode != 0:
                raise Exception("The package could not be installed.")

            # Initiate a reload of the OpenMotics daemon
            PluginController.__exit()

            return {'msg': 'Plugin successfully installed'}

        finally:
            rmtree(tmp_dir)

    @staticmethod
    def __exit():
        """ Exit the cherrypy server after 1 second. Lets the current request terminate. """
        threading.Timer(1, lambda: os._exit(0)).start()

    def remove_plugin(self, name):
        """ Remove a plugin, this removes the plugin package and configuration.
        It also calls the remove function on the plugin to cleanup other files written by the
        plugin. """
        from shutil import rmtree

        plugin = self.__get_plugin(name)

        # Check if the plugin in installed
        if plugin is None:
            raise Exception("Plugin '%s' is not installed." % name)

        # Execute the on_remove callbacks
        remove_callbacks = PluginController._get_special_methods(plugin, 'on_remove')
        for remove_callback in remove_callbacks:
            try:
                remove_callback()
            except Exception as exception:
                LOGGER.error("Exception while removing plugin '%s': %s", name, exception)

        # Remove the plugin package
        plugin_path = '/opt/openmotics/python/plugins/%s' % name
        try:
            rmtree(plugin_path)
        except Exception as exception:
            raise Exception("Error while removing package for plugin '%s': %s" % name, exception)

        # Remove the plugin configuration
        conf_file = '/opt/openmotics/etc/pi_%s.conf' % name
        if os.path.exists(conf_file):
            os.remove(conf_file)

        # Initiate a reload of the OpenMotics daemon
        PluginController.__exit()

        return {'msg': 'Plugin successfully removed'}

    def __start_background_tasks(self, plugin):
        """ Start all background tasks. """
        tasks = PluginController._get_special_methods(plugin, 'background_task')
        for task in tasks:
            thread = threading.Thread(target=self.__wrap_background_task, args=(plugin.name, task))
            thread.name = "Background thread for plugin '%s'" % plugin.name
            thread.daemon = True
            thread.start()

    def __wrap_background_task(self, plugin_name, target):
        """ Wrapper for a background task, an exception in the background task will be added to
        the plugin's log.
        """
        try:
            target()
        except Exception as exception:
            self.log(plugin_name, "Exception in background thread", exception,
                     traceback.format_exc())

    def __expose_plugin(self, plugin):
        """ Expose the plugins using cherrypy. """
        root_config = {'tools.sessions.on': False,
                       'tools.cors.on': self.__config_controller.get_setting('cors_enabled', False)}

        cherrypy.tree.mount(plugin,
                            '/plugins/{0}'.format(plugin.name),
                            {"/": root_config})

    def process_input_status(self, input_status_inst):
        """ Should be called when the input status changes, notifies all plugins. """
        for isr in self.__input_status_receivers:
            try:
                isr[1](input_status_inst)
            except Exception as exception:
                self.log(isr[0], "Exception while processing input status", exception,
                         traceback.format_exc())

    def process_output_status(self, output_status_inst):
        """ Should be called when the output status changes, notifies all plugins. """
        for osr in self.__output_status_receivers:
            try:
                osr[1](output_status_inst)
            except Exception as exception:
                self.log(osr[0], "Exception while processing output status", exception,
                         traceback.format_exc())

    def process_shutter_status(self, shutter_status_inst):
        """ Should be called when the shutter status changes, notifies all plugins. """
        for ssr in self.__shutter_status_receivers:
            try:
                ssr[1](shutter_status_inst)
            except Exception as exception:
                self.log(ssr[0], "Exception while processing shutter status", exception,
                         traceback.format_exc())

    def process_event(self, code):
        """ Should be called when an event is triggered, notifies all plugins. """
        for er in self.__event_receivers:
            try:
                er[1](code)
            except Exception as exception:
                self.log(er[0], "Exception while processing event", exception,
                         traceback.format_exc())

    def collect_metrics(self):
        """ Collects all metrics from all plugins """
        for mc in self.__metric_collectors:
            try:
                now = time.time()
                method = mc[1]
                interval = method.metric_data['interval']
                if self.__collector_runs.get(method, 0) < now - interval:
                    self.__collector_runs[method] = now
                    for metric in method():
                        if metric is None:
                            continue
                        metric = copy.deepcopy(metric)
                        metric['source'] = mc[0]
                        yield metric
            except Exception as exception:
                self.log(mc[0], "Exception while collecting metrics", exception,
                         traceback.format_exc())

    def distribute_metric(self, metric):
        """ Enqueues all metrics in a separate queue per plugin """
        delivery_count = 0
        for mr in self.__metric_receivers:
            try:
                method = mr[1]
                metadata = method.metric_receive
                sources = self.__metrics_controller.get_filter('source', metadata['source'])
                metric_types = self.__metrics_controller.get_filter('metric_type', metadata['metric_type'])
                if metric['source'] in sources and metric['type'] in metric_types:
                    self.metric_receiver_queues[mr[0]].appendleft(metric)
                    delivery_count += 1
            except Exception as exception:
                self.log(mr[0], "Exception while distributing metrics", exception, traceback.format_exc())
        return delivery_count

    def __deliver_metrics(self, plugin):
        """ Delivers enqueued metrics to plugin listener(s) """
        # Yield all metrics in the Queue
        while self.__stopped is False:
            try:
                data = self.metric_receiver_queues[plugin].pop()
                for mr in self.__metric_receivers:
                    if mr[0] != plugin:
                        continue
                    try:
                        mr[1](data)
                    except Exception as exception:
                        self.log(mr[0], "Exception while delivering metrics", exception, traceback.format_exc())
            except IndexError:
                time.sleep(0.1)

    def get_metric_definitions(self):
        """ Loads all metric definitions of all plugins """
        from plugins.interfaces import has_interface
        definitions = {}
        for plugin in self.__plugins:
            try:
                if has_interface(plugin, "metrics", "1.0"):
                    for definition in plugin.metric_definitions:
                        definition = copy.deepcopy(definition)
                        if plugin.name not in definitions:
                            definitions[plugin.name] = []
                        definitions[plugin.name].append(definition)
            except Exception as exception:
                self.log(plugin.name, "Exception while collecting metric definitions", exception,
                         traceback.format_exc())
        return definitions

    def log(self, plugin, msg, exception, stacktrace=None):
        """ Append an exception to the log for the plugins. This log can be retrieved
        using get_logs. """
        if plugin not in self.__logs:
            self.__logs[plugin] = []

        LOGGER.error("Plugin %s: %s (%s)", plugin, msg, exception)
        if stacktrace is None:
            self.__logs[plugin].append("%s - %s: %s" % (datetime.now(), msg, exception))
        else:
            self.__logs[plugin].append("%s - %s: %s\n%s" % (datetime.now(), msg, exception, stacktrace))
        if len(self.__logs[plugin]) > 100:
            self.__logs[plugin].pop(0)

    def get_logger(self, plugin_name):
        """ Get a logger for a plugin. """
        if plugin_name not in self.__logs:
            self.__logs[plugin_name] = []

        def log(msg):
            """ Log function for the given plugin."""
            self.__logs[plugin_name].append("%s - %s" % (datetime.now(), msg))
            if len(self.__logs[plugin_name]) > 100:
                self.__logs[plugin_name].pop(0)

        return log

    def get_logs(self):
        """ Get the logs for all plugins. Returns a dict where the keys are the plugin
        names and the value is a string. """
        return dict((plugin, '\n'.join(entries)) for plugin, entries in self.__logs.iteritems())


class PluginConfigChecker(object):
    """ The standard configuration controller for plugins enables the plugin creator to easily
    implement the 'config' plugin interface. By specifying a configuration description, the
    PluginConfigController is able to verify if a configuration dict matches this description.
    The description is a list of dicts, each dict contains the 'name', 'type' and optionally
    'description' and 'i18n' keys.

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
    'repeat' is true. The 'content' key should provide a configuration description like specified
    above.

    An example of a description:
    [
      {'name' : 'hostname', 'type' : 'str',      'description': 'The hostname of the server.', 'i18n': 'hostname'},
      {'name' : 'port',     'type' : 'int',      'description': 'Port on the server.',         'i18n': 'port'},
      {'name' : 'use_auth', 'type' : 'bool',     'description': 'Use authentication while connecting.'},
      {'name' : 'password', 'type' : 'password', 'description': 'Your secret password.' },
      {'name' : 'enumtest', 'type' : 'enum',     'description': 'Test for enum',
       'choices': [ 'First', 'Second' ] },

      {'name' : 'outputs', 'type' : 'section', 'repeat' : true, 'min' : 1,
       'content' : [{'name' : 'output', 'type' : 'int'}]
      },

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
        """ Checks if a plugin configuration description is valid. """
        if not isinstance(description, list):
            raise PluginException("The configuration description is not a list")
        else:
            for item in description:
                if 'name' not in item:
                    raise PluginException("The configuration item '%s' does not contain a 'name' key." % item)
                if not isinstance(item['name'], basestring):
                    raise PluginException("The key 'name' of configuration item '%s' is not a string." % item)

                if 'type' not in item:
                    raise PluginException("The configuration item '%s' does not contain a 'type' key." % item)
                if not isinstance(item['type'], basestring):
                    raise PluginException("The key 'type' of configuration item '%s' is not a string." % item)

                if 'description' in item and not isinstance(item['description'], basestring):
                    raise PluginException("The key 'description' of configuration item '%s' is not a string." % item)

                if 'i18n' in item and not isinstance(item['i18n'], basestring):
                    raise PluginException("The key 'i18n' of configuration item '%s' is not a string." % item)

                if item['type'] == 'enum':
                    PluginConfigChecker._check_enum(item)
                elif item['type'] == 'section':
                    self._check_section(item)
                elif item['type'] == 'nested_enum':
                    self._check_nested_enum(item)
                elif item['type'] not in ['str', 'int', 'bool', 'password']:
                    raise PluginException("Configuration item '%s' contains unknown type '%s'." % (item, item['type']))

    @staticmethod
    def _check_enum(item):
        """ Check an enum configuration description. """
        if 'choices' not in item:
            raise PluginException(
                    "The configuration item '%s' does not contain a 'choices' key." % item)

        if not isinstance(item['choices'], list):
            raise PluginException(
                    "The key 'choices' of configuration item '%s' is not a list." % item)

        for choice in item['choices']:
            if not isinstance(choice, basestring):
                raise PluginException("An element of the 'choices' list of configuration item"
                                      " '%s' is not a string." % item)

    def _check_section(self, item):
        """ Check an section configuration description. """
        if 'repeat' in item and not isinstance(item['repeat'], bool):
            raise PluginException(
                    "The key 'repeat' of configuration item '%s' is not a bool." % item)

        if ('repeat' not in item or item['repeat'] is False) and 'min' in item:
            raise PluginException("The configuration item '%s' does contains a 'min' key but "
                                  "is not repeatable." % item)

        if 'min' in item and not isinstance(item['min'], int):
            raise PluginException("The key 'min' of configuration item '%s' is not an int." % item)

        if 'content' not in item:
            raise PluginException("The configuration item '%s' does not contain a 'content' key."
                                  % item)

        try:
            self._check_description(item['content'])
        except PluginException as exception:
            raise PluginException("Exception in 'content': %s" % exception)

    def _check_nested_enum(self, item):
        """ Check a nested enum configuration description. """
        if 'choices' not in item:
            raise PluginException("The configuration item '%s' does not contain a "
                                  "'choices' key." % item)

        if not isinstance(item['choices'], list):
            raise PluginException(
                    "The key 'choices' of configuration item '%s' is not a list." % item)

        for choice in item['choices']:
            if not isinstance(choice, dict):
                raise PluginException("An element of the 'choices' list of configuration item '%s'"
                                      " is not a dict." % item)

            if 'value' not in choice:
                raise PluginException("The choices dict '%s' of item '%s' does not contain a "
                                      "'value' key." % (choice, item['name']))

            if not isinstance(choice['value'], str):
                raise PluginException("The 'value' key of choices dict '%s' of item '%s' is not "
                                      "a string." % (choice, item['name']))

            if 'content' not in choice:
                raise PluginException("The choices dict '%s' of item '%s' does not contain "
                                      "a 'content' key." % (choice, item['name']))

            try:
                self._check_description(choice['content'])
            except PluginException as exception:
                raise PluginException("Exception in 'choices' - 'content': %s" % exception)

    def check_config(self, config):
        """ Check if a config is valid for the description.
        Raises a PluginException if the config is not valid.
        """
        self._check_config(config, self.__description)

    def _check_config(self, config, description):
        """ Check if a config is valid for this description.
        Raises a PluginException if the config is not valid.
        """
        if not isinstance(config, dict):
            raise PluginException("The config '%s' is not a dict" % config)

        for item in description:
            name = item['name']
            if name not in config:
                raise PluginException("The config does not contain key '%s'" % name)

            if item['type'] == 'str':
                if not isinstance(config[name], basestring):
                    raise PluginException("Config '%s': '%s' is not a string" %
                                          (name, config[name]))
            elif item['type'] == 'int':
                if not isinstance(config[name], int):
                    raise PluginException("Config '%s': '%s' is not an int" % (name, config[name]))
            elif item['type'] == 'bool':
                if not isinstance(config[name], bool):
                    raise PluginException("Config '%s': '%s' is not a bool" % (name, config[name]))
            elif item['type'] == 'password':
                if not isinstance(config[name], basestring):
                    raise PluginException("Config '%s': '%s' is not a str" % (name, config[name]))
            elif item['type'] == 'enum':
                if config[name] not in item['choices']:
                    raise PluginException("Config '%s': '%s' is not in the choices '%s'" %
                                          (name, config[name], item['choices']))
            elif item['type'] == 'section':
                if not isinstance(config[name], list):
                    raise PluginException("Config '%s': '%s' is not a list" % (name, config[name]))

                for config_section in config[name]:
                    try:
                        self._check_config(config_section, item['content'])
                    except PluginException as exception:
                        raise PluginException("Exception in section list: %s" % exception)
            elif item['type'] == 'nested_enum':
                if not isinstance(config[name], list) or len(config[name]) != 2:
                    raise PluginException("Config '%s': '%s' is not a list of length 2" %
                                          (name, config[name]))

                choices = [c['value'] for c in item['choices']]
                try:
                    i = choices.index(config[name][0])
                except ValueError:
                    raise PluginException("Config '%s': '%s' is not in the choices '%s'" %
                                          (name, config[name], choices))
                else:
                    try:
                        self._check_config(config[name][1], item['choices'][i]['content'])
                    except PluginException as exception:
                        raise PluginException("Exception in nested_enum dict: %s" % exception)
