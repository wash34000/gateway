# Copyright (C) 2018 OpenMotics BVBA
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
The pulses module contains the PulseCounterController.
"""

import sqlite3
import logging

import master.master_api as master_api
from master.eeprom_models import PulseCounterConfiguration

LOGGER = logging.getLogger('openmotics')
MASTER_PULSE_COUNTERS = 24


class PulseCounterController(object):
    """
    The PulseCounterController stores the configuation and values of the virtual pulse counters.
    It abstracts the master (id < 24) and virtual pulse counters (id >= 24).
    """

    def __init__(self, db_filename, master_communicator, eeprom_controller):
        """
        Constructs a new PulseCounterController.

        :param db_filename: filename of the sqlite database used to store the pulse counters.
        """
        self._connection = sqlite3.connect(db_filename,
                                           detect_types=sqlite3.PARSE_DECLTYPES,
                                           check_same_thread=False,
                                           isolation_level=None)
        self._cursor = self._connection.cursor()
        self._check_tables()

        self._master_communicator = master_communicator
        self._eeprom_controller = eeprom_controller
        self._counts = {}

    def _execute(self, *args, **kwargs):
        return self._cursor.execute(*args, **kwargs)

    def _check_tables(self):
        """
        Creates the table.
        """
        self._execute('CREATE TABLE IF NOT EXISTS pulse_counters ' 
                      '(id INTEGER PRIMARY KEY, name TEXT, room INTEGER, persistent INTEGER);')

    def set_pulse_counter_amount(self, amount):
        if amount < MASTER_PULSE_COUNTERS:
            raise ValueError('Amount should be {0} or more'.format(MASTER_PULSE_COUNTERS))

        # Create new pulse counters if required
        for i in xrange(24, amount):
            self._execute('INSERT INTO pulse_counters (id, name, room, persistent) ' 
                          'SELECT ?, "", 255, 0 ' 
                          'WHERE NOT EXISTS (SELECT 1 FROM pulse_counters WHERE id = ?);', (i, i))

        # Delete pulse counters with a higher id
        self._execute('DELETE FROM pulse_counters WHERE id >= ?;', (amount,))

    def get_pulse_counter_amount(self):
        for row in self._execute('SELECT max(id) FROM pulse_counters;'):
            max_id = row[0]
            return max_id + 1 if max_id is not None else 24

    def _check_id(self, pulse_counter_id, check_not_physical):
        if check_not_physical and pulse_counter_id < MASTER_PULSE_COUNTERS:
            raise ValueError('Cannot set pulse counter status for {0} (should be > {1})'.format(pulse_counter_id, MASTER_PULSE_COUNTERS - 1))

        if pulse_counter_id >= self.get_pulse_counter_amount():
            raise ValueError('Could not find pulse counter {0}'.format(pulse_counter_id))

    def set_pulse_counter_status(self, pulse_counter_id, value):
        self._check_id(pulse_counter_id, True)
        self._counts[pulse_counter_id] = value

    def get_pulse_counter_status(self):
        pulse_counter_status = self._get_master_pulse_counter_status()

        for row in self._execute('SELECT id FROM pulse_counters ORDER BY id ASC;'):
            pulse_counter_status.append(self._counts[row[0]])

        return pulse_counter_status

    def _get_master_pulse_counter_status(self):
        out_dict = self._master_communicator.do_command(master_api.pulse_list())
        return [out_dict['pv{0}'.format(i)] for i in xrange(0, MASTER_PULSE_COUNTERS)]

    @staticmethod
    def _row_to_config(row):
        return {'id': row[0], 'name': str(row[1]), 'input': -1, 'room': row[2], 'persistent': row[3] >= 1}

    def get_configuration(self, pulse_counter_id, fields=None):
        self._check_id(pulse_counter_id, False)

        if pulse_counter_id < MASTER_PULSE_COUNTERS:
            return dict(
                self._eeprom_controller.read(PulseCounterConfiguration, pulse_counter_id, fields).serialize(),
                persistent=False
            )
        else:
            for row in self._execute('SELECT id, name, room, persistent FROM pulse_counters WHERE id = ?;', (pulse_counter_id,)):
                return PulseCounterController._row_to_config(row)

    def get_configurations(self, fields=None):
        configs = [dict(o.serialize(), persistent=False)
                   for o in self._eeprom_controller.read_all(PulseCounterConfiguration, fields)]

        for row in self._execute('SELECT id, name, room, persistent FROM pulse_counters ORDER BY id ASC;'):
            configs.append(PulseCounterController._row_to_config(row))

        return configs

    def set_configuration(self, config):
        self._check_id(config['id'], False)

        if config['id'] < MASTER_PULSE_COUNTERS:
            if 'persistent' in config:
                del config['persistent']
            self._eeprom_controller.write(PulseCounterConfiguration.deserialize(config))
        else:
            if config['input'] != -1:
                raise ValueError('Virtual pulse counter {0} can only have input -1'.format(config['id']))
            else:
                persistent = ''
                values = (config['name'], config['room'], config['id'])
                if 'persistent' in config:
                    persistent = ', persistent = ?'
                    values = (config['name'], config['room'], 1 if config['persistent'] else 0, config['id'])
                self._execute('UPDATE pulse_counters SET name = ?, room = ?{0} WHERE id = ?;'.format(persistent), values)

    def set_configurations(self, config):
        for item in config:
            self.set_configuration(item)

    def get_persistence(self):
        configs = [True for _ in xrange(0, MASTER_PULSE_COUNTERS)]
        for row in self._execute('SELECT persistent FROM pulse_counters ORDER BY id ASC;'):
            configs.append(row[0] >= 1)
        return configs
