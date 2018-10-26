import inspect
import re
import traceback

from base import PluginException, OMPluginBase

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

    from interfaces import check_interfaces
    check_interfaces(plugin_class)


def get_special_methods(plugin_object, method_attribute):
    """ Get all methods of a plugin object that have the given attribute. """
    def __check(member):
        """ Check if a member is a method and has the given attribute. """
        return inspect.ismethod(member) and hasattr(member, method_attribute)

    return [m[1] for m in inspect.getmembers(plugin_object, predicate=__check)]
