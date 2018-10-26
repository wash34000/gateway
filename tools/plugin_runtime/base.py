import os

from decorators import *  # Import for backwards compatibility

class PluginException(Exception):
    """ Exception that is raised when there are errors in a plugin implementation. """
    pass


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
