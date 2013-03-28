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
        """ Create the power tables. """
        self.__cursor.execute("CREATE TABLE power_modules (id INTEGER PRIMARY KEY, " 
                              "name TEXT default '', address INTEGER, "
                              "input0 TEXT default '', input1 TEXT default '', "
                              "input2 TEXT default '', input3 TEXT default '', "
                              "input4 TEXT default '', input5 TEXT default '', "
                              "input6 TEXT default '', input7 TEXT default '', "
                              "sensor0 INT default 0, sensor1 INT default 0, "
                              "sensor2 INT default 0, sensor3 INT default 0, "
                              "sensor4 INT default 0, sensor5 INT default 0, "
                              "sensor6 INT default 0, sensor7 INT default 0 );")
        
        self.__cursor.execute("CREATE TABLE power_config (key TEXT PRIMARY KEY, " 
                              "config TEXT);")
        self.__cursor.execute("INSERT INTO power_config (key, config) VALUES "
                              "('times', '0,0,0,0,0,0,0,0,0,0,0,0,0,0');")

    def get_power_modules(self):
        """ Get a dict containing all power modules. The key of the dict is the id of the module,
        the value is a dict containing 'id', 'name', 'address', 'input0', 'input1', 'input2',
        'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', 'sensor1', 'sensor2',
        'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7'.
        """
        power_modules = {}
        for row in self.__cursor.execute("SELECT id, name, address, input0, input1, input2, "
                                         "input3, input4, input5, input6, input7, sensor0, " 
                                         "sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, "
                                         "sensor7 FROM power_modules;"):
            power_modules[row[0]] = { 'id': row[0], 'name': row[1], 'address': row[2],
                                      'input0': row[3], 'input1': row[4], 'input2': row[5],
                                      'input3':row[6], 'input4':row[7], 'input5': row[8],
                                      'input6':row[9], 'input7':row[10],
                                      'sensor0': row[11], 'sensor1': row[12], 'sensor2': row[13],
                                      'sensor3':row[14], 'sensor4':row[15], 'sensor5': row[16],
                                      'sensor6':row[17], 'sensor7':row[18] }
        return power_modules

    def get_address(self, id):
        """ Get the address of a module when the module id is provided. """
        for row in self.__cursor.execute("SELECT address FROM power_modules WHERE id=?;",
                                         (id,)):
            return row[0]

    def module_exists(self, address):
        """ Check if a module with a certain address exists. """
        for row in self.__cursor.execute("SELECT count(id) FROM power_modules WHERE address=?;",
                                         (address,)):
            return row[0] > 0

    def update_power_module(self, module):
        """ Update the name and names of the inputs of the power module.
        
        :param module: dicts with keys: 'id', 'name', 'input0', 'input1', 'input2', \
        'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', 'sensor1', 'sensor2', \
        'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7'.
        """
        self.__cursor.execute("UPDATE power_modules SET "
                              "name=?, input0=?, input1=?, input2=?, input3=?, "
                              "input4=?, input5=?, input6=?, input7=?, sensor0=?, sensor1=?, "
                              "sensor2=?, sensor3=?, sensor4=?, sensor5=?, sensor6=?, sensor7=? "
                              "WHERE id=?;",
                              (module['name'], module['input0'], module['input1'],
                               module['input2'], module['input3'], module['input4'],
                               module['input5'], module['input6'], module['input7'],
                               module['sensor0'], module['sensor1'], module['sensor2'], 
                               module['sensor3'], module['sensor4'], module['sensor5'], 
                               module['sensor6'], module['sensor7'],
                               module['id']))
        self.__connection.commit()

    def register_power_module(self, address):
        """ Register a new power module using an address. """
        self.__cursor.execute("INSERT INTO power_modules(address) VALUES (?);", (address,))
        self.__connection.commit()
    
    def readdress_power_module(self, old_address, new_address):
        """ Change the address of a power module. """
        self.__cursor.execute("UPDATE power_modules SET address=? WHERE address=?;",
                              (new_address, old_address))
        self.__connection.commit()
    
    def get_free_address(self):
        """ Get a free address for a power module. """
        max_address = 0
        for row in self.__cursor.execute("SELECT address FROM power_modules;"):
            max_address = max(max_address, row[0])
        return max_address + 1 if max_address < 255 else 1
    
    def get_time_configuration(self):
        """ Get the time configuration for the low and high periods.
        :returns: Array with 7 tuples (high-start, high-stop) for Monday-Sunday.
        """
        for row in self.__cursor.execute("SELECT config FROM power_config WHERE key='times';"):
            parts = row[0].split(",")
            return [ ( int(parts[0]),  int(parts[1]) ), ( int(parts[2]),  int(parts[3]) ),
                     ( int(parts[4]),  int(parts[5]) ), ( int(parts[6]),  int(parts[7]) ),
                     ( int(parts[8]),  int(parts[9]) ), ( int(parts[10]), int(parts[11]) ),
                     ( int(parts[12]), int(parts[13]) ) ]
    
    def set_time_configuration(self, configuration):
        """ Set the time configuration for low an high periods.
        :param configuration: Array with 7 tuples (high-start, high-stop) for Monday-Sunday.
        """
        if len(configuration) != 7:
            raise ValueError("Time configuration should contain 7 tuples")
        
        config = ",".join([ str(num) for tuple in configuration for num in tuple ])
        self.__cursor.execute("UPDATE power_config SET config=? WHERE key='times';", (config,))
    
    def close(self):
        """ Commit the changes and close the database connection. """
        self.__connection.commit()
        self.__connection.close()
