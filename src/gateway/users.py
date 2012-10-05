'''
The users module contains the UserController class, which provides methods for creating
and authenticating users.

Created on Sep 16, 2012

@author: fryckbos
'''

import sqlite3
import hashlib
import uuid
import time
import os.path

class UserController:
    """ The UserController provides methods for the creation and authentication of users. """

    def __init__(self, db_filename, config, token_timeout = 3600):
        """ Constructor a new UserController.
        
        :param db_filename: filename of the sqlite database used to store the users and tokens.
        :param config: Contains the OpenMotics cloud username and password.
        :type config: A dict with keys 'username' and 'password'.
        :param token_timeout: the number of seconds a token is valid.
        """
        self.__config = config
        new_database = not os.path.exists(db_filename)
        self.__connection = sqlite3.connect(db_filename, detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False, isolation_level=None)
        self.__cursor = self.__connection.cursor()
        self.__token_timeout = token_timeout
        if new_database:
            self.__create_tables()
    
    def __create_tables(self):
        """ Create the users and tokens table,
        populate the users table with the OpenMotics cloud credentials.
        """
        self.__cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, "
                              "password TEXT, role TEXT, enabled INTEGER, last_login INTEGER);")
        self.__cursor.execute("CREATE TABLE tokens (id INTEGER PRIMARY KEY, user_id INTEGER, "
                              "token TEXT, valid_until INTEGER);")
        # Create the user for the cloud
        self.create_user(self.__config['username'], self.__config['password'], "admin", True)

    def __hash(self, password):
        """ Hash the password using sha1. """
        sha = hashlib.sha1()
        sha.update("OpenMotics")
        sha.update(password)
        return sha.hexdigest()
    
    def create_user(self, username, password, role, enabled):
        """ Create a new user using a username, password, role and enabled.
        
        :param username: username for the newly created user.
        :param password: password for the newly created user.
        :param role: role for the newly created user.
        :param enabled: boolean, only enabled users can log into the system.
        """
        self.__cursor.execute("INSERT INTO users (username, password, role, enabled) "
                              "VALUES (?, ?, ?, ?);",
                              (username, self.__hash(password), role, int(enabled)))
    
    def login(self, username, password):
        """ Login with a username and password, returns a token for this user.
        
        :returns: a token that identifies this user, None for invalid credentials.
        """
        for row in self.__cursor.execute("SELECT id FROM users WHERE username = ? AND "
                                         "password = ? AND enabled = ?;",
                                         (username, self.__hash(password), 1)):
            token = self.__gen_token(row[0], int(time.time() + self.__token_timeout))
            self.__cursor.execute("UPDATE users SET last_login = ? "
                                  "WHERE username = ?;", (int(time.time()), username))
            return token
        
        return None
    
    def get_role(self, username):
        """ Get the role for a certain user. Returns None is user was not found. """
        for row in self.__cursor.execute("SELECT role FROM users WHERE username = ?;",
                                         (username,)):
            return row[0]
        
        return None
    
    def __gen_token(self, user_id, valid_until):
        """ Generate a token and insert it into the database. """
        token = uuid.uuid4().hex
        self.__cursor.execute("INSERT INTO tokens (user_id, token, valid_until) "
                              "VALUES (?, ?, ?);", (user_id, token, valid_until))
        self.__cursor.execute("DELETE FROM tokens WHERE valid_until < ?;",
                              (int(time.time()),))
        return token
    
    def check_token(self, token):
        """ Returns True if the token is valid, False if the token is invalid. """
        for _ in self.__cursor.execute("SELECT * FROM tokens WHERE token = ? AND valid_until > ?;",
                                       (token, int(time.time()))):
            return True
        else:
            return False
    
    def close(self):
        """ Commit the changes and close the database connection. """
        self.__connection.commit()
        self.__connection.close()
