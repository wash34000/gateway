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
"""
The power controller module contains the PowerController class, which keeps track of the registered
power modules and their address.
"""

import sqlite3
import os.path
from threading import Lock

from power_api import POWER_API_8_PORTS, POWER_API_12_PORTS, NUM_PORTS


class PowerController(object):
    """ The PowerController keeps track of the registered power modules. """

    def __init__(self, db_filename):
        """ Constructor a new PowerController.

        :param db_filename: filename of the sqlite database.
        """

        self._schema = {'name': "TEXT default ''",
                        'address': "INTEGER",
                        'version': "INTEGER"}
        self._schema.update(dict([('input%d' % i, "TEXT default ''") for i in xrange(12)]))
        self._schema.update(dict([('sensor%d' % i, "INT default 0") for i in xrange(12)]))
        self._schema.update(dict([('times%d' % i, "TEXT") for i in xrange(12)]))
        self._schema.update(dict([('inverted%d' % i, "INT default 0") for i in xrange(12)]))

        new_database = not os.path.exists(db_filename)
        self.__connection = sqlite3.connect(db_filename, detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False, isolation_level=None)
        self.__cursor = self.__connection.cursor()
        self.__lock = Lock()

        if new_database:
            self.__create_tables()
        self.__update_schema_if_needed()  # Adds the fields required for the 12-port power modules.

    @staticmethod
    def _generate_fields(amount):
        fields = []
        fields += ['input%d' % i for i in xrange(amount)]
        fields += ['sensor%d' % i for i in xrange(amount)]
        fields += ['times%d' % i for i in xrange(amount)]
        fields += ['inverted%d' % i for i in xrange(amount)]
        return fields

    def __create_tables(self):
        """ Create the power tables. """
        with self.__lock:
            self.__cursor.execute("CREATE TABLE power_modules (id INTEGER PRIMARY KEY, %s);"
                                  % ", ".join(['%s %s' % (key, value) for key, value in self._schema.iteritems()]))
            self.__connection.commit()

    def __update_schema_if_needed(self):
        """ Upadtes the power_modules table schema from the 8-port power module version to the
        12-port power module version. The __create_tables above generates the 12-port version, so
        the update is only performed for legacy users that still have the old schema. """
        with self.__lock:
            changed = False
            fields = []
            for row in self.__cursor.execute("PRAGMA table_info('power_modules');"):
                fields.append(row[1])
            for field, default in self._schema.iteritems():
                if field not in fields:
                    self.__cursor.execute("ALTER TABLE power_modules ADD COLUMN %s %s;"
                                          % (field, default))
                    changed = True
            if changed is True:
                self.__connection.commit()

    def get_power_modules(self):
        """ Get a dict containing all power modules. The key of the dict is the id of the module,
        the value is a dict depends on the version of the power module. All versions contain 'id',
        'name', 'address', 'version', 'input0', 'input1', 'input2', 'input3', 'input4', 'input5',
        'input6', 'input7', 'times0', 'times1', 'times2', 'times3', 'times4', 'times5', 'times6',
        'times7'. For the 8-port power it also contains 'sensor0', 'sensor1', 'sensor2', 'sensor3',
        'sensor4', 'sensor5', 'sensor6', 'sensor7'. For the 12-port power module also contains
        'input8', 'input9', 'input10', 'input11', 'times8', 'times9', 'times10', 'times11'.
        """
        power_modules = {}
        fields = {}
        for version in [POWER_API_8_PORTS, POWER_API_12_PORTS]:
            amount = NUM_PORTS[version]
            fields[version] = ['id', 'name', 'address', 'version'] + PowerController._generate_fields(amount)
        with self.__lock:
            for row in self.__cursor.execute("SELECT %s FROM power_modules;" % ", ".join(fields[POWER_API_12_PORTS])):
                version = row[3]
                if version not in [POWER_API_8_PORTS, POWER_API_12_PORTS]:
                    raise ValueError("Unknown power api version")
                power_modules[row[0]] = dict([(field, row[fields[POWER_API_12_PORTS].index(field)])
                                              for field in fields[version]])
            return power_modules

    def get_address(self, id):
        """ Get the address of a module when the module id is provided. """
        with self.__lock:
            for row in self.__cursor.execute("SELECT address FROM power_modules WHERE id=?;",
                                             (id,)):
                return row[0]

    def get_version(self, id):
        """ Get the version of a module when the module id is provided. """
        with self.__lock:
            for row in self.__cursor.execute("SELECT version FROM power_modules WHERE id=?;",
                                             (id,)):
                return row[0]

    def module_exists(self, address):
        """ Check if a module with a certain address exists. """
        with self.__lock:
            for row in self.__cursor.execute("SELECT count(id) FROM power_modules WHERE address=?;",
                                             (address,)):
                return row[0] > 0

    def update_power_module(self, module):
        """ Update the name and names of the inputs of the power module.

        :param module: dict depending on the version of the power module. All versions contain 'id',
        'name', 'input0', 'input1', 'input2', 'input3', 'input4', 'input5', 'input6', 'input7',
        'times0', 'times1', 'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        For the 8-port power it also contains 'sensor0', 'sensor1', 'sensor2', 'sensor3',
        'sensor4', 'sensor5', 'sensor6', 'sensor7'. For the 12-port power module also contains
        'input8', 'input9', 'input10', 'input11', 'times8', 'times9', 'times10', 'times11'.
        """
        version = self.get_version(module['id'])
        if version not in [POWER_API_8_PORTS, POWER_API_12_PORTS]:
            raise ValueError("Unknown power api version")
        amount = NUM_PORTS[version]
        fields = ['name'] + PowerController._generate_fields(amount)
        with self.__lock:
            self.__cursor.execute("UPDATE power_modules SET %s WHERE id=?" %
                                  ", ".join(["%s=?" % field for field in fields]),
                                  tuple([module[field] for field in fields] + [module['id']]))
            self.__connection.commit()

    def register_power_module(self, address, version):
        """ Register a new power module using an address. """
        with self.__lock:
            self.__cursor.execute("INSERT INTO power_modules(address, version) VALUES (?, ?);",
                                  (address, version))
            self.__connection.commit()

    def readdress_power_module(self, old_address, new_address):
        """ Change the address of a power module. """
        with self.__lock:
            self.__cursor.execute("UPDATE power_modules SET address=? WHERE address=?;",
                                  (new_address, old_address))
            self.__connection.commit()

    def get_free_address(self):
        """ Get a free address for a power module. """
        max_address = 0
        with self.__lock:
            for row in self.__cursor.execute("SELECT address FROM power_modules;"):
                max_address = max(max_address, row[0])
            return max_address + 1 if max_address < 255 else 1

    def close(self):
        """ Commit the changes and close the database connection. """
        self.__connection.commit()
        self.__connection.close()
