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
Contains the EEPROM extensions. This is used to store data that does not fit into the master. The
data is stored in a sqlite database on the gateways filesystem.
"""

import sqlite3
import os.path
from threading import Lock


class EepromExtension(object):
    """ Provides the interface for reading and writing EepromExtension objects to the sqlite
    database. """

    def __init__(self, db_filename):
        self.__lock = Lock()
        create_tables = not os.path.exists(db_filename)
        self.__connection = sqlite3.connect(db_filename, detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False, isolation_level=None)
        self.__cursor = self.__connection.cursor()
        if create_tables is True:
            self.__create_tables()

    def __create_tables(self):
        """ Create the extensions table. """
        with self.__lock:
            self.__cursor.execute("CREATE TABLE extensions (id INTEGER PRIMARY KEY, model TEXT, "
                                  "model_id INTEGER, field TEXT, value TEXT, "
                                  "UNIQUE(model, model_id, field) ON CONFLICT REPLACE);")

    def read_model(self, eeprom_model, model_id, fields=None):
        """ Read all eext data for the given eeprom model. Returns dict with all specified
        fields (if fields is None, all fields are returned).

        :param eeprom_model: EepromModel class.
        :param model_id: The id for the EepromModel.
        :param fields: List containing the fields to return.
        """
        eeprom_model_name = eeprom_model.get_name()

        field_dict = {}
        for (field_name, field_type) in eeprom_model.get_fields(include_eext=True):
            if fields is None or field_name in fields:
                field_value = self.read_extension_data(eeprom_model_name, model_id,
                                                       field_type, field_name)
                field_dict[field_name] = field_value

        return field_dict

    def read_extension_data(self, eeprom_model_name, model_id, field_type, field_name):
        """ Read data for a specific eext field. """
        model_id = 0 if model_id is None else model_id

        with self.__lock:
            for row in self.__cursor.execute("SELECT value FROM extensions WHERE "
                                             "model=? AND model_id=? AND field=?",
                                             (eeprom_model_name, model_id, field_name)):
                return field_type.decode(row[0])

        return field_type.default_value()

    def write_model(self, eeprom_model):
        """ Write all eext data for the given eeprom model.

        :param eeprom_model: an EepromModel instances.
        """
        model_id = eeprom_model.get_id()
        eeprom_model_name = eeprom_model.__class__.get_name()

        for (field_name, field_type) in eeprom_model.__class__.get_fields(include_eext=True):
            if field_name in eeprom_model.__dict__:
                self.write_extension_data(eeprom_model_name, model_id, field_type, field_name,
                                          eeprom_model.__dict__[field_name])

    def write_extension_data(self, eeprom_model_name, model_id, field_type, field_name, data):
        """ Write data for a specific eext field. """
        model_id = 0 if model_id is None else model_id
        value = field_type.encode(data)

        with self.__lock:
            self.__cursor.execute("INSERT INTO extensions (model, model_id, field, value) "
                                  "VALUES (?, ?, ?, ?)",
                                  (eeprom_model_name, model_id, field_name, value))

    def close(self):
        """ Commit the changes and close the database connection. """
        with self.__lock:
            self.__connection.commit()
            self.__connection.close()
