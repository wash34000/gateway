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
Contains the EepromModels.

@author: fryckbos
"""

from eeprom_controller import EepromModel, EepromAddress, EepromId, EepromString, \
                              EepromWord, EepromByte, EepromActions, EepromTemp, EepromTime, \
                              EepromCSV, CompositeDataType, EepromSignedTemp, EepromIBool, \
                              EepromEnum, EextByte, EextString


def page_per_module(module_size, start_bank, start_offset, field_size):
    """ Returns a function that takes an id and returns an address (bank, offset). The bank is
    calculated by adding the module id to the start_bank and the offset is calculated by adding the
    start_offset to the field_size times the id in the module (the offset id).
    """
    return per_module(module_size, lambda mid, iid: (start_bank+mid, start_offset+field_size*iid))


def per_module(module_size, func):
    """ Returns a function that takes an id and returns an address. The id is split into the a
    module id and offset id, these two iids are provided to func to calculate the address.

    @param func: function that takes two ids (module id, offset id) and returns an address.
    @returns: function that takes an id and returns an address (bank, offset).
    """
    return lambda id: func(id / module_size, id % module_size)


def gen_address(start_page, ids_per_page, extra_offset):
    """ Returns a function that takes an id and returns an address. The returned address starts at
    the given start_page, has a fixed number of ids_per_page. The extra_offset is added to the
    offset calculated using the ids_per_page.
    """
    page_offset = 256 / ids_per_page
    return lambda id: (start_page + (id / ids_per_page), (id % ids_per_page) * page_offset + extra_offset)


def get_led_functions():
    """ Get dict describing the enum for the CAN LED functions. """
    led_functions = {}
    for brightness in range(16):
        for function in [(0,'On'), (16,'Fast blink'), (32,'Medium blink'), (48,'Slow blink'), (64,'Swinging')]:
            for inverted in [(0, ''), (128, ' Inverted')]:
                led_functions[brightness + function[0] + inverted[0]] = "%s B%d%s" %(function[1], brightness + 1, inverted[1])
    return led_functions


class FloorConfiguration(EepromModel):
    """ Models a floor. A floor has a name. """
    id = EepromId(10)
    name = EextString()


class RoomConfiguration(EepromModel):
    """ Models a room. A room has a name and is located on a floor. """
    id = EepromId(100)
    name = EextString()
    floor = EextByte()


class OutputConfiguration(EepromModel):
    """ Models an output. The maximum number of inputs is 240 (30 modules), the actual number of
    outputs is 8 times the number of output modules (eeprom address 0, 2).
    """
    id = EepromId(240, address=EepromAddress(0, 2, 1), multiplier=8)
    module_type = EepromString(1, lambda id: (33 + id /8, 0), read_only=True)
    name = EepromString(16, page_per_module(8, 33, 20, 16))
    timer = EepromWord(page_per_module(8, 33, 4, 2))
    floor = EepromByte(page_per_module(8, 33, 157, 1))
    type = EepromByte(page_per_module(8, 33, 149, 1))
    can_led_1_id = EepromByte(gen_address(221, 32, 0))
    can_led_1_function = EepromEnum(gen_address(221, 32, 1), get_led_functions())
    can_led_2_id = EepromByte(gen_address(221, 32, 2))
    can_led_2_function = EepromEnum(gen_address(221, 32, 3), get_led_functions())
    can_led_3_id = EepromByte(gen_address(221, 32, 4))
    can_led_3_function = EepromEnum(gen_address(221, 32, 5), get_led_functions())
    can_led_4_id = EepromByte(gen_address(221, 32, 6))
    can_led_4_function = EepromEnum(gen_address(221, 32, 7), get_led_functions())
    room = EextByte()


class InputConfiguration(EepromModel):
    """ Models an input. The maximum number of inputs is 240 (30 modules), the actual number of
    inputs is 8 times the number of input modules (eeprom address 0, 1).
    """
    id = EepromId(240, address=EepromAddress(0, 1, 1), multiplier=8)
    module_type = EepromString(1, lambda id: (2 + id /8, 0), read_only=True)
    name = EepromString(8, per_module(8, lambda mid, iid: (115+(mid/4), 64*(mid % 4) + 8*iid)))
    action = EepromByte(page_per_module(8, 2, 4, 1))
    basic_actions = EepromActions(15, page_per_module(8, 2, 12, 30))
    invert = EepromByte(lambda id: (32, id))
    room = EextByte()
    can = EepromString(1, lambda id: (2 + id /8, 252), read_only=True)


class CanLedConfiguration(EepromModel):
    """ Models a CAN LED configuration. Each configuration defines the CAN LED that will be driven
    and the the function to drive the LED. The LED function will be activated when:
    the number of lights on is 0 (id = 0), the number of lights on is greater than 0 (id = 1), ...,
    the number of lights on is greater than 14 (id = 15), the number of outputs on is 0 (id = 16),
    ther number of outputs is greater than 0 (id = 17), the number of outputs on is greater than 14
    (id = 31). """
    id = EepromId(32)
    can_led_1_id = EepromByte(gen_address(229, 32, 0))
    can_led_1_function = EepromEnum(gen_address(229, 32, 1), get_led_functions())
    can_led_2_id = EepromByte(gen_address(229, 32, 2))
    can_led_2_function = EepromEnum(gen_address(229, 32, 3), get_led_functions())
    can_led_3_id = EepromByte(gen_address(229, 32, 4))
    can_led_3_function = EepromEnum(gen_address(229, 32, 5), get_led_functions())
    can_led_4_id = EepromByte(gen_address(229, 32, 6))
    can_led_4_function = EepromEnum(gen_address(229, 32, 7), get_led_functions())
    room = EextByte()


class ShutterConfiguration(EepromModel):
    """ Models a shutter. The maximum number of shutters is 120 (30 modules), the actual number of
    shutters is 4 times the number of shutter modules (eeprom address 0, 3).
    """
    id = EepromId(240, address=EepromAddress(0, 3, 1), multiplier=4)
    timer_up = EepromByte(page_per_module(4, 33, 177, 2))
    timer_down = EepromByte(page_per_module(4, 33, 178, 2))
    up_down_config = EepromByte(page_per_module(4, 33, 185, 1))
    name = EepromString(16, page_per_module(4, 33, 189, 16))
    group_1 = EepromByte(lambda id: (63, (id * 2) + 0))
    group_2 = EepromByte(lambda id: (63, (id * 2) + 1))
    room = EextByte()


class ShutterGroupConfiguration(EepromModel):
    """ Models a group of shutters. """
    id = EepromId(30)
    timer_up = EepromByte(lambda id: (64, (id * 2) + 0))
    timer_down = EepromByte(lambda id: (64, (id * 2) + 1))
    room = EextByte()


class ThermostatConfiguration(EepromModel):
    """ Models a thermostat. The maximum number of thermostats is 24. """
    id = EepromId(24)
    name = EepromString(16, lambda id: (187 + (id / 16), 16 * (id % 16)))
    setp0 = EepromTemp(lambda id: (142, 32+id))
    setp1 = EepromTemp(lambda id: (142, 64+id))
    setp2 = EepromTemp(lambda id: (142, 96+id))
    setp3 = EepromTemp(lambda id: (142, 128+id))
    setp4 = EepromTemp(lambda id: (142, 160+id))
    setp5 = EepromTemp(lambda id: (142, 192+id))
    sensor = EepromByte(lambda id: (144, 8+id))
    output0 = EepromByte(lambda id: (142, id))
    output1 = EepromByte(lambda id: (142, 224+id))
    pid_p = EepromByte(lambda id: (141, 4*id))
    pid_i = EepromByte(lambda id: (141, (4*id)+1))
    pid_d = EepromByte(lambda id: (141, (4*id)+2))
    pid_int = EepromByte(lambda id: (141, (4*id)+3))
    permanent_manual = EepromIBool(lambda id: (195, 32+id))
    auto_mon = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (198, id + 0))),
         ('start_d1', EepromTime(lambda id: (189, (4*id)+0))),
         ('stop_d1', EepromTime(lambda id: (189, (4*id)+1))),
         ('temp_d1', EepromTemp(lambda id: (196, id + 0))),
         ('start_d2', EepromTime(lambda id: (189, (4*id)+2))),
         ('stop_d2', EepromTime(lambda id: (189, (4*id)+3))),
         ('temp_d2', EepromTemp(lambda id: (197, id + 0)))
        ])
    auto_tue = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (198, id + 32))),
         ('start_d1', EepromTime(lambda id: (189, (4*id)+128))),
         ('stop_d1', EepromTime(lambda id: (189, (4*id)+129))),
         ('temp_d1', EepromTemp(lambda id: (196, id + 32))),
         ('start_d2', EepromTime(lambda id: (189, (4*id)+130))),
         ('stop_d2', EepromTime(lambda id: (189, (4*id)+131))),
         ('temp_d2', EepromTemp(lambda id: (197, id + 32)))
        ])
    auto_wed = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (198, id + 64))),
         ('start_d1', EepromTime(lambda id: (190, (4*id)+0))),
         ('stop_d1', EepromTime(lambda id: (190, (4*id)+1))),
         ('temp_d1', EepromTemp(lambda id: (196, id + 64))),
         ('start_d2', EepromTime(lambda id: (190, (4*id)+2))),
         ('stop_d2', EepromTime(lambda id: (190, (4*id)+3))),
         ('temp_d2', EepromTemp(lambda id: (197, id + 64)))
        ])
    auto_thu = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (198, id + 96))),
         ('start_d1', EepromTime(lambda id: (190, (4*id)+128))),
         ('stop_d1', EepromTime(lambda id: (190, (4*id)+129))),
         ('temp_d1', EepromTemp(lambda id: (196, id + 96))),
         ('start_d2', EepromTime(lambda id: (190, (4*id)+130))),
         ('stop_d2', EepromTime(lambda id: (190, (4*id)+131))),
         ('temp_d2', EepromTemp(lambda id: (197, id + 96)))
        ])
    auto_fri = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (198, id + 128))),
         ('start_d1', EepromTime(lambda id: (191, (4*id)+0))),
         ('stop_d1', EepromTime(lambda id: (191, (4*id)+1))),
         ('temp_d1', EepromTemp(lambda id: (196, id + 128))),
         ('start_d2', EepromTime(lambda id: (191, (4*id)+2))),
         ('stop_d2', EepromTime(lambda id: (191, (4*id)+3))),
         ('temp_d2', EepromTemp(lambda id: (197, id + 128)))
        ])
    auto_sat = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (198, id + 160))),
         ('start_d1', EepromTime(lambda id: (191, (4*id)+128))),
         ('stop_d1', EepromTime(lambda id: (191, (4*id)+129))),
         ('temp_d1', EepromTemp(lambda id: (196, id + 160))),
         ('start_d2', EepromTime(lambda id: (191, (4*id)+130))),
         ('stop_d2', EepromTime(lambda id: (191, (4*id)+131))),
         ('temp_d2', EepromTemp(lambda id: (197, id + 160)))
        ])
    auto_sun = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (198, id + 192))),
         ('start_d1', EepromTime(lambda id: (192, (4*id)+0))),
         ('stop_d1', EepromTime(lambda id: (192, (4*id)+1))),
         ('temp_d1', EepromTemp(lambda id: (196, id + 192))),
         ('start_d2', EepromTime(lambda id: (192, (4*id)+2))),
         ('stop_d2', EepromTime(lambda id: (192, (4*id)+3))),
         ('temp_d2', EepromTemp(lambda id: (197, id + 192)))
        ])
    room = EextByte()


class PumpGroupConfiguration(EepromModel):
    """ Models a pump group. The maximum number of pump groups is 8. """
    id = EepromId(8)
    outputs = EepromCSV(32, lambda id: (143, id * 32))
    room = EextByte()


class CoolingConfiguration(EepromModel):
    """ Models a thermostat in cooling mode. The maximum number of thermostats is 24. """
    id = EepromId(24)
    name = EepromString(16, lambda id: (204 + (id / 16), 16 * (id % 16)))
    setp0 = EepromTemp(lambda id: (201, 32+id))
    setp1 = EepromTemp(lambda id: (201, 64+id))
    setp2 = EepromTemp(lambda id: (201, 96+id))
    setp3 = EepromTemp(lambda id: (201, 128+id))
    setp4 = EepromTemp(lambda id: (201, 160+id))
    setp5 = EepromTemp(lambda id: (201, 192+id))
    sensor = EepromByte(lambda id: (203, 8+id))
    output0 = EepromByte(lambda id: (201, id))
    output1 = EepromByte(lambda id: (201, 224+id))
    pid_p = EepromByte(lambda id: (200, 4*id))
    pid_i = EepromByte(lambda id: (200, (4*id)+1))
    pid_d = EepromByte(lambda id: (200, (4*id)+2))
    pid_int = EepromByte(lambda id: (200, (4*id)+3))
    permanent_manual = EepromIBool(lambda id: (195, 64+id))
    auto_mon = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (212, id + 0))),
         ('start_d1', EepromTime(lambda id: (206, (4*id)+0))),
         ('stop_d1', EepromTime(lambda id: (206, (4*id)+1))),
         ('temp_d1', EepromTemp(lambda id: (210, id + 0))),
         ('start_d2', EepromTime(lambda id: (206, (4*id)+2))),
         ('stop_d2', EepromTime(lambda id: (206, (4*id)+3))),
         ('temp_d2', EepromTemp(lambda id: (211, id + 0)))
        ])
    auto_tue = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (212, id + 32))),
         ('start_d1', EepromTime(lambda id: (206, (4*id)+128))),
         ('stop_d1', EepromTime(lambda id: (206, (4*id)+129))),
         ('temp_d1', EepromTemp(lambda id: (210, id + 32))),
         ('start_d2', EepromTime(lambda id: (206, (4*id)+130))),
         ('stop_d2', EepromTime(lambda id: (206, (4*id)+131))),
         ('temp_d2', EepromTemp(lambda id: (211, id + 32)))
        ])
    auto_wed = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (212, id + 64))),
         ('start_d1', EepromTime(lambda id: (207, (4*id)+0))),
         ('stop_d1', EepromTime(lambda id: (207, (4*id)+1))),
         ('temp_d1', EepromTemp(lambda id: (210, id + 64))),
         ('start_d2', EepromTime(lambda id: (207, (4*id)+2))),
         ('stop_d2', EepromTime(lambda id: (207, (4*id)+3))),
         ('temp_d2', EepromTemp(lambda id: (211, id + 64)))
        ])
    auto_thu = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (212, id + 96))),
         ('start_d1', EepromTime(lambda id: (207, (4*id)+128))),
         ('stop_d1', EepromTime(lambda id: (207, (4*id)+129))),
         ('temp_d1', EepromTemp(lambda id: (210, id + 96))),
         ('start_d2', EepromTime(lambda id: (207, (4*id)+130))),
         ('stop_d2', EepromTime(lambda id: (207, (4*id)+131))),
         ('temp_d2', EepromTemp(lambda id: (211, id + 96)))
        ])
    auto_fri = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (212, id + 128))),
         ('start_d1', EepromTime(lambda id: (208, (4*id)+0))),
         ('stop_d1', EepromTime(lambda id: (208, (4*id)+1))),
         ('temp_d1', EepromTemp(lambda id: (210, id + 128))),
         ('start_d2', EepromTime(lambda id: (208, (4*id)+2))),
         ('stop_d2', EepromTime(lambda id: (208, (4*id)+3))),
         ('temp_d2', EepromTemp(lambda id: (211, id + 128)))
        ])
    auto_sat = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (212, id + 160))),
         ('start_d1', EepromTime(lambda id: (208, (4*id)+128))),
         ('stop_d1', EepromTime(lambda id: (208, (4*id)+129))),
         ('temp_d1', EepromTemp(lambda id: (210, id + 160))),
         ('start_d2', EepromTime(lambda id: (208, (4*id)+130))),
         ('stop_d2', EepromTime(lambda id: (208, (4*id)+131))),
         ('temp_d2', EepromTemp(lambda id: (211, id + 160)))
        ])
    auto_sun = CompositeDataType(
        [('temp_n', EepromTemp(lambda id: (212, id + 192))),
         ('start_d1', EepromTime(lambda id: (209, (4*id)+0))),
         ('stop_d1', EepromTime(lambda id: (209, (4*id)+1))),
         ('temp_d1', EepromTemp(lambda id: (210, id + 192))),
         ('start_d2', EepromTime(lambda id: (209, (4*id)+2))),
         ('stop_d2', EepromTime(lambda id: (209, (4*id)+3))),
         ('temp_d2', EepromTemp(lambda id: (211, id + 192)))
        ])
    room = EextByte()


class CoolingPumpGroupConfiguration(EepromModel):
    """ Models a pump group for cooling. The maximum number of pump groups is 8. """
    id = EepromId(8)
    outputs = EepromCSV(32, lambda id: (202, id * 32))
    room = EextByte()


class RTD10HeatingConfiguration(EepromModel):
    """ Configuration for RTD-10 when in heating mode. """
    id = EepromId(24)
    temp_setpoint_output = EepromByte(lambda id: (213, id))
    ventilation_speed_output = EepromByte(lambda id: (214, id))
    ventilation_speed_value = EepromByte(lambda id: (214, 24 + id))
    mode_output = EepromByte(lambda id: (215, id))
    mode_value = EepromByte(lambda id: (215, 24 + id))
    on_off_output = EepromByte(lambda id: (215, 100 + id))
    poke_angle_output = EepromByte(lambda id: (216, id))
    poke_angle_value = EepromByte(lambda id: (216, 24 + id))
    room = EextByte()


class RTD10CoolingConfiguration(EepromModel):
    """ Configuration for RTD-10 when in cooling mode. """
    id = EepromId(24)
    temp_setpoint_output = EepromByte(lambda id: (217, id))
    ventilation_speed_output = EepromByte(lambda id: (218, id))
    ventilation_speed_value = EepromByte(lambda id: (218, 24 + id))
    mode_output = EepromByte(lambda id: (219, id))
    mode_value = EepromByte(lambda id: (219, 24 + id))
    on_off_output = EepromByte(lambda id: (219, 100 + id))
    poke_angle_output = EepromByte(lambda id: (220, id))
    poke_angle_value = EepromByte(lambda id: (220, 24 + id))
    room = EextByte()


class GlobalRTD10Configuration(EepromModel):
    """ The global RTD-10 configuration. """
    output_value_heating_16 = EepromByte((213, 24))
    output_value_heating_16_5 = EepromByte((213, 25))
    output_value_heating_17 = EepromByte((213, 26))
    output_value_heating_17_5 = EepromByte((213, 27))
    output_value_heating_18 = EepromByte((213, 28))
    output_value_heating_18_5 = EepromByte((213, 29))
    output_value_heating_19 = EepromByte((213, 30))
    output_value_heating_19_5 = EepromByte((213, 31))
    output_value_heating_20 = EepromByte((213, 32))
    output_value_heating_20_5 = EepromByte((213, 33))
    output_value_heating_21 = EepromByte((213, 34))
    output_value_heating_21_5 = EepromByte((213, 35))
    output_value_heating_22 = EepromByte((213, 36))
    output_value_heating_22_5 = EepromByte((213, 37))
    output_value_heating_23 = EepromByte((213, 38))
    output_value_heating_23_5 = EepromByte((213, 39))
    output_value_heating_24 = EepromByte((213, 40))
    output_value_cooling_16 = EepromByte((217, 24))
    output_value_cooling_16_5 = EepromByte((217, 25))
    output_value_cooling_17 = EepromByte((217, 26))
    output_value_cooling_17_5 = EepromByte((217, 27))
    output_value_cooling_18 = EepromByte((217, 28))
    output_value_cooling_18_5 = EepromByte((217, 29))
    output_value_cooling_19 = EepromByte((217, 30))
    output_value_cooling_19_5 = EepromByte((217, 31))
    output_value_cooling_20 = EepromByte((217, 32))
    output_value_cooling_20_5 = EepromByte((217, 33))
    output_value_cooling_21 = EepromByte((217, 34))
    output_value_cooling_21_5 = EepromByte((217, 35))
    output_value_cooling_22 = EepromByte((217, 36))
    output_value_cooling_22_5 = EepromByte((217, 37))
    output_value_cooling_23 = EepromByte((217, 38))
    output_value_cooling_23_5 = EepromByte((217, 39))
    output_value_cooling_24 = EepromByte((217, 40))


class SensorConfiguration(EepromModel):
    """ Models a sensor. The maximum number of sensors is 32. """
    id = EepromId(32)
    name = EepromString(16, lambda id: (193 + (id / 16), (id % 16) * 16))
    offset = EepromSignedTemp(lambda id: (0, 60 + id))
    virtual = EepromIBool(lambda id: (195, id))
    room = EextByte()


class ThermostatSetpointConfiguration(EepromModel):
    """ Models the setpoints for all of the thermostats. """
    id = EepromId(24)
    automatic = EextBool()
    setpoint = EextByte()


class GroupActionConfiguration(EepromModel):
    """ Models a group action. The maximum number of inputs is 160. """
    id = EepromId(160)
    name = EepromString(16, lambda id: (158 + (id / 16), 16 * (id % 16)))
    actions = EepromActions(16, lambda id: (67 + (id / 8), 32 * (id % 8)))


class ScheduledActionConfiguration(EepromModel):
    """ Models the scheduled actions. The maximum number of scheduled actions is 102. """
    id = EepromId(102)
    hour = EepromByte(lambda id: (113 + (id / 51), 5 * (id % 51) + 0))
    minute = EepromByte(lambda id: (113 + (id / 51), 5 * (id % 51) + 1))
    day = EepromByte(lambda id: (113 + (id / 51), 5 * (id % 51) + 2))
    ## day's 8th byte -> one time or reschedule
    action = EepromActions(1, lambda id: (113 + (id / 51), 5 * (id % 51) + 3))
    ## 24:00 -> execute every minute, 24:05 -> execute every 5 minutes


class PulseCounterConfiguration(EepromModel):
    """ Models a pulse counter. The maximum number of pulse counters is 24. """
    id = EepromId(24)
    name = EepromString(16, lambda id: (98 + (id / 16), 16 * (id % 16)))
    input = EepromByte(lambda id: (0, 160+id))
    room = EextByte()


class StartupActionConfiguration(EepromModel):
    """ Models the startup actions, this contains 100 basic actions. """
    actions = EepromActions(100, (1, 0))


class DimmerConfiguration(EepromModel):
    """ Models the global dimmer configuration.  """
    min_dim_level = EepromByte((0, 5))
    dim_step = EepromByte((0, 6))
    dim_wait_cycle = EepromByte((0, 7))
    dim_memory = EepromByte((0, 9))


class GlobalThermostatConfiguration(EepromModel):
    """ The global thermostat configuration. """
    outside_sensor = EepromByte((0, 16))
    threshold_temp = EepromTemp((0, 17))
    pump_delay = EepromByte((0, 19))
    switch_to_heating_output_0 = EepromByte((199, 0))
    switch_to_heating_value_0 = EepromByte((199, 1))
    switch_to_heating_output_1 = EepromByte((199, 2))
    switch_to_heating_value_1 = EepromByte((199, 3))
    switch_to_heating_output_2 = EepromByte((199, 4))
    switch_to_heating_value_2 = EepromByte((199, 5))
    switch_to_heating_output_3 = EepromByte((199, 6))
    switch_to_heating_value_3 = EepromByte((199, 7))
    switch_to_cooling_output_0 = EepromByte((199, 8))
    switch_to_cooling_value_0 = EepromByte((199, 9))
    switch_to_cooling_output_1 = EepromByte((199, 10))
    switch_to_cooling_value_1 = EepromByte((199, 11))
    switch_to_cooling_output_2 = EepromByte((199, 12))
    switch_to_cooling_value_2 = EepromByte((199, 13))
    switch_to_cooling_output_3 = EepromByte((199, 14))
    switch_to_cooling_value_3 = EepromByte((199, 15))


class ModuleConfiguration(EepromModel):
    """ Models the global module configuration. """
    nr_input_modules = EepromByte((0, 1), read_only=True)
    nr_output_modules = EepromByte((0, 2), read_only=True)
    enable_thermostat_16 = EepromByte((0, 15))


class CliConfiguration(EepromModel):
    """ Models the cli configuration. These values are set by the OpenMotics daemon at startup. """
    auto_response = EepromByte((0, 11))
    auto_response_OL = EepromByte((0, 18))
    echo = EepromByte((0, 12))
    start_cli_api = EepromByte((0, 13))
    auto_init = EepromByte((0, 14))
