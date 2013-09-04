'''
Contains the EepromModels.

Created on Sep 4, 2013

@author: fryckbos
'''
from eeprom_controller import EepromModel, EepromId, EepromString, EepromWord, EepromByte,\
                              EepromActions, EepromTemp


def page_per_module(module_size, start_page, start_address, field_size):
    return per_module(module_size, lambda mid, iid: (start_page+mid, start_address+field_size*iid))


def per_module(module_size, func):
    return lambda id: func(id / module_size, id % module_size)


class Output(EepromModel):
    id = EepromId(240)
    name = EepromString(16, page_per_module(8, 33, 20, 16))
    timer = EepromWord(page_per_module(8, 33, 4, 2))
    floor = EepromByte(page_per_module(8, 33, 157, 1))
    type = EepromByte(page_per_module(8, 33, 149, 1))


class Input(EepromModel):
    id = EepromId(240)
    name = EepromString(8, per_module(8, lambda mid, iid: (115+(mid/4), 64*(mid % 4) + 8*iid)))
    action = EepromByte(page_per_module(8, 2, 4, 1))
    basic_actions = EepromActions(15, page_per_module(8, 2, 12, 30))


class Thermostat(EepromModel):
    id = EepromId(24)
    setp0 = EepromTemp(lambda id: (142, 32+id))
    setp1 = EepromTemp(lambda id: (142, 64+id))
    setp2 = EepromTemp(lambda id: (142, 96+id))
    setp3 = EepromTemp(lambda id: (142, 128+id))
    setp4 = EepromTemp(lambda id: (142, 160+id))
    setp5 = EepromTemp(lambda id: (142, 192+id))
    sensor = EepromTemp(lambda id: (144, 8+id))
    output1 = EepromByte(lambda id: (142, id))
    output2 = EepromByte(lambda id: (142, 224+id))
    pid_p = EepromByte(lambda id: (141, 4*id))
    pid_i = EepromByte(lambda id: (141, (4*id)+1))
    pid_d = EepromByte(lambda id: (141, (4*id)+2))
    pid_int = EepromByte(lambda id: (141, (4*id)+3))


class GroupAction(EepromModel):
    id = EepromId(160)
    name = EepromString(16, lambda id: (158 + (id / 16), 16 * (id % 16)))
    actions = EepromActions(16, lambda id: (67 + (id / 8), 32 * (id % 8)))


class StartupActions(EepromModel):
    actions = EepromActions(100, (1, 0))


class DimmerConfiguration(EepromModel):
    min_dim_level = EepromByte((0, 5))
    dim_step = EepromByte((0, 6))
    dim_wait_cycle = EepromByte((0, 7))
    dim_memory = EepromByte((0, 9))


class ModuleConfiguration(EepromModel):
    nr_input_modules = EepromByte((0, 1))
    nr_output_modules = EepromByte((0, 2))
    enable_thermostat_16 = EepromByte((0, 15))


class CliConfiguration(EepromModel):
    auto_response = EepromByte((0, 11))
    auto_response_OL = EepromByte((0, 18))
    echo = EepromByte((0, 12))
    start_cli_api = EepromByte((0, 13))
    auto_init = EepromByte((0, 14))


class ThermostatConfiguration(EepromModel):
    outside_sensor = EepromByte((0, 16))
    threshold_temp = EepromTemp((0, 17))
    pump_delay = EepromByte((0, 19))

