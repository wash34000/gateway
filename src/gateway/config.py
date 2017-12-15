# Copyright (C) 2017 OpenMotics BVBA
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
Configuration controller
"""

import time
import sqlite3
import logging
from random import randint
try:
    import json
except ImportError:
    import simplejson as json

LOGGER = logging.getLogger("openmotics")


class ConfigurationController(object):

    def __init__(self, db_filename, lock):
        """
        Constructs a new ConfigController.

        :param db_filename: filename of the sqlite database used to store the configuration
        :param lock: DB lock
        """
        self.__lock = lock
        self.__connection = sqlite3.connect(db_filename,
                                            detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False,
                                            isolation_level=None)
        self.__cursor = self.__connection.cursor()
        self.__check_tables()

    def __execute(self, *args, **kwargs):
        with self.__lock:
            try:
                return self.__cursor.execute(*args, **kwargs)
            except sqlite3.OperationalError:
                time.sleep(randint(1, 20) / 10.0)
                return self.__cursor.execute(*args, **kwargs)

    def __check_tables(self):
        """
        Creates tables and execute migrations
        """
        tables = [table[0] for table in self.__execute("SELECT name FROM sqlite_master WHERE type='table';")]
        if 'settings' not in tables:
            self.__execute("CREATE TABLE settings (id INTEGER PRIMARY KEY, setting TEXT UNIQUE, data TEXT);")
        for setting, default_setting in {'cloud_enabled': True,
                                         'cloud_endpoint': 'cloud.openmotics.com',
                                         'cloud_endpoint_metrics': 'portal/metrics/',
                                         'cloud_metrics_types': ['energy', 'counter'],
                                         'cloud_metrics_enabled|energy': True,
                                         'cloud_metrics_enabled|counter': True,
                                         'cloud_metrics_batch_size': 50,
                                         'cloud_metrics_min_interval': 300,
                                         'cors_enabled': False}.iteritems():
            if self.get_setting(setting) is None:
                self.set_setting(setting, default_setting)

    def get_setting(self, setting, fallback=None):
        for setting in self.__execute("SELECT data FROM settings WHERE setting=?", (setting.lower(),)):
            return json.loads(setting[0])
        return fallback

    def set_setting(self, setting, value):
        self.__execute("INSERT OR REPLACE INTO settings (setting, data) VALUES (?, ?);",
                       (setting.lower(), json.dumps(value)))

    def close(self):
        """ Close the database connection. """
        self.__connection.close()
