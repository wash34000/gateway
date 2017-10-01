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
        self.__connection = sqlite3.connect(db_filename,
                                            detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False,
                                            isolation_level=None)
        self.__cursor = self.__connection.cursor()
        if create_tables is True:
            self.__create_tables()

    def __create_tables(self):
        """ Create the extensions table. """
        with self.__lock:
            self.__cursor.execute("CREATE TABLE extensions (id INTEGER PRIMARY KEY, model TEXT, "
                                  "model_id INTEGER, field TEXT, value TEXT, "
                                  "UNIQUE(model, model_id, field) ON CONFLICT REPLACE);")

    def read_data(self, eeprom_model_name, model_id, field_name):
        model_id = 0 if model_id is None else model_id
        with self.__lock:
            for row in self.__cursor.execute("SELECT value FROM extensions WHERE "
                                             "model=? AND model_id=? AND field=?",
                                             (eeprom_model_name, model_id, field_name)):
                return row[0]
        return None

    def write_data(self, data):
        """
        :type data: list of tuple[basestring, int, basestring, basestring]
        """
        for data_entry in data:
            model_name, field_name, model_id, value = data_entry
            model_id = 0 if model_id is None else model_id
            with self.__lock:
                self.__cursor.execute("INSERT INTO extensions (model, model_id, field, value) "
                                      "VALUES (?, ?, ?, ?)",
                                      (model_name, model_id, field_name, value))

    def close(self):
        """ Commit the changes and close the database connection. """
        with self.__lock:
            self.__connection.commit()
            self.__connection.close()
