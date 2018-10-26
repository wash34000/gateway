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
""" The OpenMotics plugin controller. """

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

try:
    import json
except ImportError:
    import simplejson as json

from runner import PluginRunner

LOGGER = logging.getLogger("openmotics")


class PluginController(object):
    """ The controller keeps track of all plugins in the system. """

    def __init__(self, webinterface, config_controller, runtime_path='/opt/openmotics/plugin_runtime'):
        self.__webinterface = webinterface
        self.__config_controller = config_controller
        self.__runtime_path = runtime_path

        self.__stopped = False
        self.__logs = {}
        self.__runnners = self.__init_runners()

        self.__metrics_controller = None

    def stop(self):
        for runner in self.__runners:
            runner.stop()
        self.__stopped = True

    def start_plugins(self):
        """ Start the background tasks for the plugins and expose them via the webinterface. """
        for runner in self.__runners:
            runner.start()
            self.__expose(runner)

    def __expose(self, runner):
        """ Expose the runner using cherrypy. """
        root_config = {'tools.sessions.on': False,
                       'tools.cors.on': self.__config_controller.get_setting('cors_enabled', False)}

        cherrypy.tree.mount(runner.get_webservice(),
                            '/plugins/{0}'.format(runner.name),
                            {"/": root_config})

    def set_metrics_controller(self, metrics_controller):
        """ Sets the metrics controller """
        self.__metrics_controller = metrics_controller

    def __init_runners(self):
        """ Scan the plugins package for installed plugins in the form of subpackages. """
        import plugins
        objects = pkgutil.iter_modules(plugins.__path__)  # (module_loader, name, ispkg)

        package_names = [o[1] for o in objects if o[2]]

        runners = []
        for package_name in package_names:
            try:
                logger = self.get_logger(package_name)
                plugin_path = os.path.join(self.__get_plugin_root(), package_name)
                runner = PluginRunner(self.__runtime_path, plugin_path, logger)
                runner.start()
                runners.append(runner)
            except Exception as exception:
                self.log(package_name, "Could not load plugin", exception)

        # Check for double plugins
        per_name = {}
        for runner in runners:
            if runner.name not in per_name:
                per_name[runner.name] = [runner]
            else:
                per_name[runner.name].append(runner)

        # Remove plugins that are defined in multiple packages
        filtered = []
        for name in per_name:
            if len(per_name[name]) != 1:
                self.log(name, "Could not enable plugin",
                         "found in multiple pacakges: %s" % ([r.plugin_path for r in per_name[name]],))
                for runner in per_name[name]:
                    runner.stop()
            else:
                filtered.append(per_name[name][0])

        return filtered

    def __get_plugin_root(self):
        import plugins
        return os.path.abspath(os.path.dirname(inspect.getfile(plugins)))

    def get_plugins(self):
        """ Get a list of all installed plugins. """
        return self.__runners

    def __get_plugin(self, name):
        """ Get a plugin by name, None if it the plugin is not installed. """
        for runner in self.__runners:
            if runner.name == name:
                return runner

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
            logger = self.get_logger("new_package")
            runner = PluginRunner(self.__runtime_path, "%s/new_package" % tmp_dir, logger)
            runner.start()
            runner.stop()
            (name, version) = (runner.name, runner.version)

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
        try:
            plugin.remove_callback()
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

    def process_input_status(self, input_status_inst):
        """ Should be called when the input status changes, notifies all plugins. """
        for runner in self.__runners:
            runner.process_input_status(input_status_inst)

    def process_output_status(self, output_status_inst):
        """ Should be called when the output status changes, notifies all plugins. """
        for runner in self.__runners:
            runner.process_output_status(output_status_inst)

    def process_shutter_status(self, shutter_status_inst):
        """ Should be called when the shutter status changes, notifies all plugins. """
        for runner in self.__runners:
            runner.process_shutter_status(shutter_status_inst)

    def process_event(self, code):
        """ Should be called when an event is triggered, notifies all plugins. """
        for runner in self.__runners:
            runner.process_event(code)

    def collect_metrics(self):
        """ Collects all metrics from all plugins """
        for runner in self.__runners:
            for metric in runner.collect_metrics():
                if metric is None:
                    continue
                else:
                    yield metric

    def distribute_metric(self, metric):
        """ Enqueues all metrics in a separate queue per plugin """
        delivery_count = 0
        for runner in self.__runners:
            for receiver in runner.get_metric_receivers():
                try:
                    sources = self.__metrics_controller.get_filter('source', receiver['source'])
                    metric_types = self.__metrics_controller.get_filter('metric_type', receiver['metric_type'])
                    if metric['source'] in sources and metric['type'] in metric_types:
                        runner.distribute_metric(receiver['name'], metric):
                        delivery_count += 1
                except Exception as exception:
                    self.log(mr[0], "Exception while distributing metrics", exception, traceback.format_exc())
        return delivery_count

    def get_metric_definitions(self):
        """ Loads all metric definitions of all plugins """
        definitions = {}

        for runner in self.__runners:
            definitions[runner.name] = runner.get_metric_definitions()

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
