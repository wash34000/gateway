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
Tests for the vpn service.

@author: fryckbos
"""

import time
import threading
import unittest
import os

from vpn_service import BufferingDataCollector

import constants
constants.get_buffer_file = lambda filename: "/tmp/%s.buffer" % filename

import time

def reset_time():
    time.time = lambda: 123456789.0

def advance_time():
    now = time.time()
    time.time = lambda: now + 1

reset_time()

def gen():
    accum = { 'i' : 0 }
    def get_data():
        accum['i'] = accum['i'] + 1
        return [ [i, i+1] for i in range(accum['i'], accum['i'] + 4)]
    return get_data

class BufferingDataCollectorTest(unittest.TestCase):
    """ Tests for BufferingDataCollector class """

    def setUp(self):
        """ Clear the buffer before each test. """
        path = constants.get_buffer_file(gen().__name__)
        if os.path.exists(path):
            os.remove(path)

    def test_get(self):
        """ Test direct data collection. """
        bdc = BufferingDataCollector(gen(), 1)
        reset_time()
        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [[123456789.0, [[1, 2], [2, 3], [3, 4], [4, 5]]]]},
            bdc.collect(''))
        bdc.data_sent_callback(True)
        advance_time()

        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [[123456790.0, [[2, 3], [3, 4], [4, 5], [5, 6]]]]},
            bdc.collect(''))
        bdc.data_sent_callback(True)

    def test_buffering(self):
        """ Test data collection with buffering. """
        bdc = BufferingDataCollector(gen(), 1)
        reset_time()
        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [[123456789.0, [[1, 2], [2, 3], [3, 4], [4, 5]]]]},
            bdc.collect(''))
        bdc.data_sent_callback(False)
        advance_time()

        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [
            [123456789.0, [[1, 2], [2, 3], [3, 4], [4, 5]]],
            [123456790.0, [[2, 3], [3, 4], [4, 5], [5, 6]]]]},
            bdc.collect(''))
        bdc.data_sent_callback(True)
        advance_time()

        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [[123456791.0, [[3, 4], [4, 5], [5, 6], [6, 7]]]]},
            bdc.collect(''))
        bdc.data_sent_callback(True)

    def test_on_disk_buffering(self):
        """ Test data collection with on-disk buffering. """
        get_data = gen()

        bdc = BufferingDataCollector(get_data, 1)
        reset_time()
        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [[123456789.0, [[1, 2], [2, 3], [3, 4], [4, 5]]]]},
            bdc.collect(''))
        bdc.data_sent_callback(False)
        advance_time()
        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [
            [123456789.0, [[1, 2], [2, 3], [3, 4], [4, 5]]],
            [123456790.0, [[2, 3], [3, 4], [4, 5], [5, 6]]]]},
            bdc.collect(''))
        bdc.data_sent_callback(False)
        advance_time()
        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [
            [123456789.0, [[1, 2], [2, 3], [3, 4], [4, 5]]],
            [123456790.0, [[2, 3], [3, 4], [4, 5], [5, 6]]],
            [123456791.0, [[3, 4], [4, 5], [5, 6], [6, 7]]]]},
            bdc.collect(''))
        bdc.data_sent_callback(False)
        advance_time()

        bdc2 = BufferingDataCollector(get_data, 1)
        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [
            [123456789.0, [[1, 2], [2, 3], [3, 4], [4, 5]]],
            [123456790.0, [[2, 3], [3, 4], [4, 5], [5, 6]]],
            [123456791.0, [[3, 4], [4, 5], [5, 6], [6, 7]]],
            [123456792.0, [[4, 5], [5, 6], [6, 7] ,[7, 8]]]]},
            bdc2.collect(''))
        bdc.data_sent_callback(True)
        advance_time()

        bdc3 = BufferingDataCollector(get_data, 1)
        self.assertEquals(
            {'timestamp' : time.time(),
            'values' : [[123456793.0, [[5, 6], [6, 7] ,[7, 8], [8, 9]]]]},
            bdc3.collect(''))
        bdc.data_sent_callback(True)

    def test_on_disk_limit(self):
        """ Test whether the on-disk file size limiting works. """
        reset_time()
        get_data = gen()

        bdc = BufferingDataCollector(get_data, 1)
        for i in range(0, 700000):
            bdc.collect('')
            bdc.data_sent_callback(False)
            advance_time()

        path = constants.get_buffer_file(get_data.__name__)

        self.assertTrue(os.stat(path).st_size < BufferingDataCollector.FILE_SIZE)
        
        f = open(path, 'r')
        line = f.readline()
        self.assertEquals('[123764780.0, [[307992, 307993], [307993, 307994], [307994, 307995], [307995, 307996]]]\n', line)
        f.close()


if __name__ == "__main__":
    unittest.main()
