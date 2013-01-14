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
                              "name TEXT default '', uid TEXT, address TEXT UNIQUE, "
                              "input0 TEXT default '', input1 TEXT default '',"
                              "input2 TEXT default '', input3 TEXT default '',"
                              "input4 TEXT default '', input5 TEXT default '',"
                              "input6 TEXT default '', input7 TEXT default '');")

    def get_power_modules(self):
        """ Get a dict containing all power modules. The key of the dict is the id of the module,
        the value is a dict containing 'id', 'name', 'uid', 'address', 'input0', 'input1', 'input2',
        'input3', 'input4', 'input5', 'input6', 'input7'.
        """
        power_modules = {}
        for row in self.__cursor.execute("SELECT id, name, uid, address, input0, input1, input2,"
                                         "input3, input4, input5, input6, input7 "
                                         "FROM power_modules;"):
            power_modules[row[0]] = { 'id': row[0], 'name': row[1], 'uid': row[2],
                                      'address': row[3], 'input0': row[4], 'input1': row[5],
                                      'input2': row[6], 'input3':row[7], 'input4':row[8],
                                      'input5': row[9], 'input6':row[10], 'input7':row[11] }
        return power_modules

    def update_power_modules(self, modules):
        """ Update the name and names of the inputs of the power modules.
        
        :param modules: list of dicts with keys: 'id', 'name', 'input0', 'input1', 'input2', \
        'input3', 'input4', 'input5', 'input6', 'input7'.
        """
        for module in modules:
            self.__cursor.execute("UPDATE power_modules SET "
                                  "name=?, input0=?, input1=?, input2=?, input3=?, "
                                  "input4=?, input5=?, input6=?, input7=? "
                                  "WHERE id=?;",
                                  (module['name'], module['input0'], module['input1'],
                                   module['input2'], module['input3'], module['input4'],
                                   module['input5'], module['input6'], module['input7'],
                                   module['id']))

    def register_power_module(self, address):
        """ Register a new power module using an address. """
        self.__cursor.execute("INSERT INTO power_modules(address) VALUES (?);", (address,))
        self.__connection.commit()
        
    def get_free_address(self):
        """ Get a free address for a power module. """
        max_address = 0
        for row in self.__cursor.execute("SELECT address FROM power_modules;"):
            address_byte = ord(row[0][1])
            max_address = max(max_address, address_byte)
        return 'E' + chr(max_address + 1)
    
    def close(self):
        """ Commit the changes and close the database connection. """
        self.__connection.commit()
        self.__connection.close()
