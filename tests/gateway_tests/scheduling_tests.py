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
Tests for the scheduling module.
"""
import os
import unittest
import time
import fakesleep
from threading import Lock, Semaphore

from gateway.webservice import WebInterface
from gateway.scheduling import SchedulingController


class GatewayApi(object):
    RETURN_DATA = {}

    def get_timezone(self):
        _ = self
        return 'Europe/Brussels'

    def do_group_action(self, group_action_id):
        _ = self
        GatewayApi.RETURN_DATA['do_group_action'] = group_action_id

    def do_basic_action(self, action_type, action_number):
        _ = self
        GatewayApi.RETURN_DATA['do_basic_action'] = (action_type, action_number)


class SchedulingControllerTest(unittest.TestCase):
    FILE = "test.db"

    @classmethod
    def setUpClass(cls):
        fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        fakesleep.monkey_restore()

    def setUp(self):
        GatewayApi.RETURN_DATA = {}
        if os.path.exists(SchedulingControllerTest.FILE):
            os.remove(SchedulingControllerTest.FILE)

    def tearDown(self):
        GatewayApi.RETURN_DATA = {}
        if os.path.exists(SchedulingControllerTest.FILE):
            os.remove(SchedulingControllerTest.FILE)

    def _get_controller(self):
        gateway_api = GatewayApi()
        controller = SchedulingController(SchedulingControllerTest.FILE, Lock(), gateway_api)
        controller.set_webinterface(WebInterface(None, gateway_api, None, None, None, controller))
        return controller

    def test_base_validation(self):
        controller = self._get_controller()
        with self.assertRaises(RuntimeError):
            # Must have a name
            controller._validate(None, None, None, None, None, None, None)
        with self.assertRaises(RuntimeError):
            # Unaccepted type
            controller._validate('test', time.time(), 'FOO', None, None, None, None)
        with self.assertRaises(RuntimeError):
            # Duration too short
            controller._validate('test', time.time(), 'GROUP_ACTION', None, None, 10, None)
        with self.assertRaises(RuntimeError):
            # End when not repeating
            controller._validate('test', time.time(), 'GROUP_ACTION', None, None, None, 1)
        with self.assertRaises(RuntimeError):
            # Invalid repeat string
            controller._validate('test', time.time(), 'GROUP_ACTION', None, 'foo', None, None)

    def test_group_action(self):
        start = time.time()
        semaphore = Semaphore(0)
        controller = self._get_controller()
        controller.set_unittest_semaphore(semaphore)
        # New controller is empty
        self.assertEquals(len(controller.schedules), 0)
        with self.assertRaises(RuntimeError) as ctx:
            # Doesn't support duration
            controller.add_schedule('group_action', start + 120, 'GROUP_ACTION', None, None, 1000, None)
        self.assertEquals(ctx.exception.message, 'A schedule of type GROUP_ACTION does not have a duration. It is a one-time trigger')
        with self.assertRaises(RuntimeError) as ctx:
            # Incorrect argument
            controller.add_schedule('group_action', start + 120, 'GROUP_ACTION', 'foo', None, None, None)
        self.assertEquals(ctx.exception.message, 'The arguments of a GROUP_ACTION schedule must be an integer, representing the Group Action to be executed')
        controller.add_schedule('group_action', start + 120, 'GROUP_ACTION', 1, None, None, None)
        self.assertEquals(len(controller.schedules), 1)
        self.assertEquals(controller.schedules[0].name, 'group_action')
        self.assertEquals(controller.schedules[0].status, 'ACTIVE')
        controller.start()
        semaphore.acquire()
        self.assertEquals(GatewayApi.RETURN_DATA['do_group_action'], 1)
        self.assertEquals(len(controller.schedules), 1)
        self.assertEquals(controller.schedules[0].name, 'group_action')
        self.assertEquals(controller.schedules[0].status, 'COMPLETED')
        controller.stop()

    def test_basic_action(self):
        start = time.time()
        semaphore = Semaphore(0)
        controller = self._get_controller()
        controller.set_unittest_semaphore(semaphore)
        self.assertEquals(len(controller.schedules), 0)
        with self.assertRaises(RuntimeError) as ctx:
            # Doesn't support duration
            controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', None, None, 1000, None)
        self.assertEquals(ctx.exception.message, 'A schedule of type BASIC_ACTION does not have a duration. It is a one-time trigger')
        invalid_arguments_error = 'The arguments of a BASIC_ACTION schedule must be of type dict with arguments `action_type` and `action_number`'
        with self.assertRaises(RuntimeError) as ctx:
            # Incorrect argument
            controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', 'foo', None, None, None)
        self.assertEquals(ctx.exception.message, invalid_arguments_error)
        with self.assertRaises(RuntimeError) as ctx:
            # Incorrect argument
            controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', {'action_type': 1}, None, None, None)
        self.assertEquals(ctx.exception.message, invalid_arguments_error)
        controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', {'action_type': 1, 'action_number': 2}, None, None, None)
        self.assertEquals(len(controller.schedules), 1)
        self.assertEquals(controller.schedules[0].name, 'basic_action')
        self.assertEquals(controller.schedules[0].status, 'ACTIVE')
        controller.start()
        semaphore.acquire()
        self.assertEquals(GatewayApi.RETURN_DATA['do_basic_action'], (1, 2))
        self.assertEquals(len(controller.schedules), 1)
        self.assertEquals(controller.schedules[0].name, 'basic_action')
        self.assertEquals(controller.schedules[0].status, 'COMPLETED')
        controller.stop()

    def test_local_api(self):
        start = time.time()
        semaphore = Semaphore(0)
        controller = self._get_controller()
        controller.set_unittest_semaphore(semaphore)
        self.assertEquals(len(controller.schedules), 0)
        with self.assertRaises(RuntimeError) as ctx:
            # Doesn't support duration
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', None, None, 1000, None)
        self.assertEquals(ctx.exception.message, 'A schedule of type LOCAL_API does not have a duration. It is a one-time trigger')
        invalid_arguments_error = 'The arguments of a LOCAL_API schedule must be of type dict with arguments `name` and `parameters`'
        with self.assertRaises(RuntimeError) as ctx:
            # Incorrect argument
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', 'foo', None, None, None)
        self.assertEquals(ctx.exception.message, invalid_arguments_error)
        with self.assertRaises(RuntimeError) as ctx:
            # Incorrect argument
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', {'name': 1}, None, None, None)
        self.assertEquals(ctx.exception.message, invalid_arguments_error)
        with self.assertRaises(RuntimeError) as ctx:
            # Not a valid call
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', {'name': 'foo', 'parameters': {}}, None, None, None)
        self.assertEquals(ctx.exception.message, 'The arguments of a LOCAL_API schedule must specify a valid and (plugin_)exposed call')
        with self.assertRaises(Exception) as ctx:
            # Not a valid call
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', {'name': 'do_basic_action',
                                                                            'parameters': {'action_type': 'foo', 'action_number': 4}}, None, None, None)
        self.assertEquals(ctx.exception.message, 'invalid literal for int() with base 10: \'foo\'')
        controller.add_schedule('local_api', start + 120, 'LOCAL_API', {'name': 'do_basic_action',
                                                                        'parameters': {'action_type': 3, 'action_number': 4}}, None, None, None)
        self.assertEquals(len(controller.schedules), 1)
        self.assertEquals(controller.schedules[0].name, 'local_api')
        self.assertEquals(controller.schedules[0].status, 'ACTIVE')
        controller.start()
        semaphore.acquire()
        self.assertEquals(GatewayApi.RETURN_DATA['do_basic_action'], (3, 4))
        self.assertEquals(len(controller.schedules), 1)
        self.assertEquals(controller.schedules[0].name, 'local_api')
        self.assertEquals(controller.schedules[0].status, 'COMPLETED')
        controller.stop()

    def test_two_actions(self):
        start = time.time()
        controller = self._get_controller()
        controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', {'action_type': 1, 'action_number': 2}, None, None, None)
        controller.add_schedule('group_action', start + 120, 'GROUP_ACTION', 1, None, None, None)
        self.assertEquals(len(controller.schedules), 2)
        self.assertEquals(sorted(s.name for s in controller.schedules), ['basic_action', 'group_action'])
        for s in controller.schedules:
            if s.name == 'group_action':
                controller.remove_schedule(s.id)
        self.assertEquals(len(controller.schedules), 1)
        self.assertEquals(controller.schedules[0].name, 'basic_action')


if __name__ == "__main__":
    unittest.main()
