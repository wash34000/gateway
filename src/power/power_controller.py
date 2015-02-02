'''
The power controller module contains the PowerController class, which keeps track of the registered
power modules and their address.
'''

import sqlite3
import os.path

from power_api import POWER_API_8_PORTS, POWER_API_12_PORTS

class PowerController(object):
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
                              "name TEXT default '', address INTEGER, version INTEGER,"
                              "input0 TEXT default '', input1 TEXT default '', "
                              "input2 TEXT default '', input3 TEXT default '', "
                              "input4 TEXT default '', input5 TEXT default '', "
                              "input6 TEXT default '', input7 TEXT default '', "
                              "input8 TEXT default '', input9 TEXT default '', "
                              "input10 TEXT default '', input11 TEXT default '', "
                              "sensor0 INT default 0, sensor1 INT default 0, "
                              "sensor2 INT default 0, sensor3 INT default 0, "
                              "sensor4 INT default 0, sensor5 INT default 0, "
                              "sensor6 INT default 0, sensor7 INT default 0, "
                              "times0 TEXT, times1 TEXT, times2 TEXT, times3 TEXT, "
                              "times4 TEXT, times5 TEXT, times6 TEXT, times7 TEXT, "
                              "times8 TEXT, times9 TEXT, times10 TEXT, times11 TEXT );")

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
        for row in self.__cursor.execute("SELECT id, name, address, version, input0, input1, "
                                         "input2, input3, input4, input5, input6, input7, input8 ,"
                                         "input9, input10, input11, sensor0, sensor1, sensor2, "
                                         "sensor3, sensor4, sensor5, sensor6, sensor7, times0, "
                                         "times1, times2, times3, times4, times5, times6, times7, "
                                         "times8, times9, times10, times11 FROM power_modules;"):
            version = row[3]
            if version == POWER_API_8_PORTS:
                power_modules[row[0]] = {'id': row[0], 'name': row[1], 'address': row[2],
                                     "version": row[3], 'input0': row[4], 'input1': row[5],
                                     'input2': row[6], 'input3':row[7], 'input4':row[8],
                                     'input5': row[9], 'input6':row[10], 'input7':row[11],
                                     'sensor0': row[16], 'sensor1': row[17], 'sensor2': row[18],
                                     'sensor3': row[19], 'sensor4': row[20], 'sensor5': row[21],
                                     'sensor6': row[22], 'sensor7': row[23], 'times0': row[24],
                                     'times1': row[25], 'times2': row[26], 'times3': row[27],
                                     'times4': row[28], 'times5': row[29], 'times6': row[30],
                                     'times7': row[31] }

            elif version == POWER_API_12_PORTS:
                power_modules[row[0]] = {'id': row[0], 'name': row[1], 'address': row[2],
                                     "version": row[3], 'input0': row[4], 'input1': row[5],
                                     'input2': row[6], 'input3':row[7], 'input4':row[8],
                                     'input5': row[9], 'input6':row[10], 'input7':row[11],
                                     'input8': row[12], 'input9': row[13], 'input10': row[14],
                                     'input11': row[15], 'times0': row[24], 'times1': row[25],
                                     'times2': row[26], 'times3': row[27], 'times4': row[28],
                                     'times5': row[29], 'times6': row[30], 'times7': row[31],
                                     'times8': row[32], 'times9': row[33], 'times10': row[34],
                                     'times11': row[35]}
            else:
                raise ValueError("Unknown power api version")

        return power_modules

    def get_address(self, id):
        """ Get the address of a module when the module id is provided. """
        for row in self.__cursor.execute("SELECT address FROM power_modules WHERE id=?;",
                                         (id,)):
            return row[0]

    def get_version(self, id):
        """ Get the version of a module when the module id is provided. """
        for row in self.__cursor.execute("SELECT version FROM power_modules WHERE id=?;",
                                         (id,)):
            return row[0]

    def module_exists(self, address):
        """ Check if a module with a certain address exists. """
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
        if version == POWER_API_8_PORTS:
            self.__cursor.execute("UPDATE power_modules SET "
                      "name=?, input0=?, input1=?, input2=?, input3=?, "
                      "input4=?, input5=?, input6=?, input7=?, sensor0=?, sensor1=?, "
                      "sensor2=?, sensor3=?, sensor4=?, sensor5=?, sensor6=?, sensor7=?, "
                      "times0=?, times1=?, times2=?, times3=?, times4=?, times5=?, "
                      "times6=?, times7=? WHERE id=?;",
                      (module['name'], module['input0'], module['input1'],
                       module['input2'], module['input3'], module['input4'],
                       module['input5'], module['input6'], module['input7'],
                       module['sensor0'], module['sensor1'], module['sensor2'],
                       module['sensor3'], module['sensor4'], module['sensor5'],
                       module['sensor6'], module['sensor7'], module['times0'],
                       module['times1'], module['times2'], module['times3'],
                       module['times4'], module['times5'], module['times6'],
                       module['times7'], module['id']))
        elif version == POWER_API_12_PORTS:
            self.__cursor.execute("UPDATE power_modules SET "
                      "name=?, input0=?, input1=?, input2=?, input3=?, input4=?, input5=?, "
                      "input6=?, input7=?, input8=?, input9=?, input10=?, input11=?, times0=?, "
                      "times1=?, times2=?, times3=?, times4=?, times5=?, times6=?, times7=?, "
                      "times8=?, times9=?, times10=?, times11=? WHERE id=?;",
                      (module['name'],
                       module['input0'], module['input1'], module['input2'], module['input3'],
                       module['input4'], module['input5'], module['input6'], module['input7'],
                       module['input8'], module['input9'], module['input10'],module['input11'],
                       module['times0'], module['times1'], module['times2'], module['times3'],
                       module['times4'], module['times5'], module['times6'], module['times7'], 
                       module['times8'], module['times9'], module['times10'], module['times11'],
                       module['id']))
        else:
            raise ValueError("Unknown power api version")

        self.__connection.commit()

    def register_power_module(self, address, version):
        """ Register a new power module using an address. """
        self.__cursor.execute("INSERT INTO power_modules(address, version) VALUES (?, ?);",
                              (address, version))
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

    def close(self):
        """ Commit the changes and close the database connection. """
        self.__connection.commit()
        self.__connection.close()
