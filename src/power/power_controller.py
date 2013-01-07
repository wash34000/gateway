'''
The power controller module contains the PowerController class, which keeps track of the registered
power modules and their address.
'''

import sqlite3
import os.path

class PowerController:
    """ The PowerController keeps track of the registered power modules. """

    def __init__(self, db_filename):
        """ Constructor a new PowerController.
        
        :param db_filename: filename of the sqlite database.
        """
        new_database = not os.path.exists(db_filename)
        self.__connection = sqlite3.connect(db_filename, detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False, isolation_level=None)
        self.__cursor = self.__connection.cursor()
        if new_database:
            self.__create_tables()
    
    def __create_tables(self):
        """ Create the power module table. """
        self.__cursor.execute("CREATE TABLE power_modules (id INTEGER PRIMARY KEY, " 
                              "name TEXT, address TEXT UNIQUE);")

    def get_power_modules(self):
        """ Get a dict containing all power modules. The key of the dict is the id of the module,
        the value is a dict containing 'id' and 'address'.
        """
        power_modules = {}
        for row in self.__cursor.execute("SELECT id, address FROM power_modules;"):
            power_modules[row[0]] = { 'id': row[0], 'address': row[1] }
        return power_modules

    def register_power_module(self, address):
        """ Register a new power module using an address. """
        self.__cursor.execute("INSERT INTO power_modules(address) VALUES (?);", (address,))
        self.__connection.commit()
        
    def get_free_address(self):
        """ Get a free address for a power module. """
        max_address = 0
        for power_module in self.get_power_modules().values():
            address_byte = ord(power_module['address'][1])
            max_address = max(max_address, address_byte)
        return 'E' + chr(max_address + 1)
    
    def close(self):
        """ Commit the changes and close the database connection. """
        self.__connection.commit()
        self.__connection.close()
