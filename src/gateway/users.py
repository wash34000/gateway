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
The users module contains the UserController class, which provides methods for creating
and authenticating users.
"""

import sqlite3
import hashlib
import uuid
import time
from random import randint


class UserController(object):
    """ The UserController provides methods for the creation and authentication of users. """

    def __init__(self, db_filename, config, token_timeout=3600):
        """ Constructor a new UserController.

        :param db_filename: filename of the sqlite database used to store the users and tokens.
        :param config: Contains the OpenMotics cloud username and password.
        :type config: A dict with keys 'username' and 'password'.
        :param token_timeout: the number of seconds a token is valid.
        """
        self.__config = config
        self.__connection = sqlite3.connect(db_filename,
                                            detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False,
                                            isolation_level=None)
        self.__cursor = self.__connection.cursor()
        self.__token_timeout = token_timeout
        self.__tokens = {}
        self.__check_tables()

        # Create the user for the cloud
        self.create_user(self.__config['username'].lower(), self.__config['password'], "admin", True)

    def __execute(self, *args, **kwargs):
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
        if 'users' not in tables:
            self.__execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, enabled INTEGER);")

    @staticmethod
    def __hash(password):
        """ Hash the password using sha1. """
        sha = hashlib.sha1()
        sha.update("OpenMotics")
        sha.update(password)
        return sha.hexdigest()

    def create_user(self, username, password, role, enabled):
        """ Create a new user using a username, password, role and enabled. The username is case
        insensitive.

        :param username: username for the newly created user.
        :param password: password for the newly created user.
        :param role: role for the newly created user.
        :param enabled: boolean, only enabled users can log into the system.
        """
        username = username.lower()

        self.__execute("INSERT OR REPLACE INTO users (username, password, role, enabled) VALUES (?, ?, ?, ?);",
                       (username, UserController.__hash(password), role, int(enabled)))

    def get_usernames(self):
        """ Get all usernames.

        :returns: a list of strings.
        """
        usernames = []
        for row in self.__execute("SELECT username FROM users;"):
            usernames.append(row[0])
        return usernames

    def remove_user(self, username):
        """ Remove a user.

        :param username: the name of the user to remove.
        """
        username = username.lower()

        if self.get_role(username) == "admin" and self.__get_num_admins() == 1:
            raise Exception("Cannot delete last admin account")
        else:
            self.__execute("DELETE FROM users WHERE username = ?;", (username,))

            to_remove = []
            for token in self.__tokens:
                if self.__tokens[token][0] == username:
                    to_remove.append(token)

            for token in to_remove:
                del self.__tokens[token]

    def __get_num_admins(self):
        """ Get the number of admin users in the system. """
        for row in self.__execute("SELECT count(*) FROM users WHERE role = ?", ("admin", )):
            return row[0]

        return 0

    def login(self, username, password, timeout=None):
        """ Login with a username and password, returns a token for this user.

        :returns: a token that identifies this user, None for invalid credentials.
        """
        username = username.lower()
        if timeout is not None:
            try:
                timeout = int(timeout)
                timeout = min(60 * 60 * 24 * 30, max(60 * 60, timeout))
            except ValueError:
                timeout = None
        if timeout is None:
            timeout = self.__token_timeout

        for _ in self.__execute("SELECT id FROM users WHERE username = ? AND password = ? AND enabled = ?;",
                                (username, UserController.__hash(password), 1)):
            return self.__gen_token(username, time.time() + timeout)

        return None

    def logout(self, token):
        """ Removes the token from the controller. """
        self.__tokens.pop(token, None)

    def get_role(self, username):
        """ Get the role for a certain user. Returns None is user was not found. """
        username = username.lower()

        for row in self.__execute("SELECT role FROM users WHERE username = ?;", (username,)):
            return row[0]

        return None

    def __gen_token(self, username, valid_until):
        """ Generate a token and insert it into the tokens dict. """
        ret = uuid.uuid4().hex
        self.__tokens[ret] = (username, valid_until)

        # Delete the expired tokens
        to_delete = []
        for token in self.__tokens:
            if self.__tokens[token][1] < time.time():
                to_delete.append(token)

        for token in to_delete:
            del self.__tokens[token]

        return ret

    def check_token(self, token):
        """ Returns True if the token is valid, False if the token is invalid. """
        if token is None or token not in self.__tokens:
            return False
        else:
            return self.__tokens[token][1] >= time.time()

    def close(self):
        """ Cose the database connection. """
        self.__connection.close()
