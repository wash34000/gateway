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
Tests for the passthrough module.

@author: fryckbos
"""

import unittest
import time

from master.master_communicator import MasterCommunicator
from master.passthrough import PassthroughService

from serial_tests import SerialMock, sout, sin

class PassthroughServiceTest(unittest.TestCase):
    """ Tests for :class`PassthroughService`. """

    def test_passthrough(self):
        """ Test the passthrough. """
        master_mock = SerialMock([
                        sout("data for the passthrough"), sin("response"),
                        sout("more data"), sin("more response")])

        passthrough_mock = SerialMock([
                        sin("data for the passthrough"), sout("response"),
                        sin("more data"), sout("more response")])

        master_communicator = MasterCommunicator(master_mock, init_master=False)
        master_communicator.start()

        passthrough = PassthroughService(master_communicator, passthrough_mock)
        passthrough.start()

        time.sleep(1)

        self.assertEquals(33, master_communicator.get_bytes_read())
        self.assertEquals(21, master_communicator.get_bytes_written())

        self.assertEquals(33, master_mock.bytes_read)
        self.assertEquals(21, master_mock.bytes_written)

        self.assertEquals(21, passthrough_mock.bytes_read)
        self.assertEquals(33, passthrough_mock.bytes_written)

        passthrough.stop()


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
