'''
Contains the EepromModels.

Created on Sep 4, 2013

@author: fryckbos
'''
from eeprom_controller import EepromModel, EepromAddress, EepromId, EepromString, EepromWord, \
                              EepromByte,EepromActions, EepromTemp


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


class OutputConfiguration(EepromModel):
    """ Models an output. The maximum number of inputs is 240 (30 modules), the actual number of 
    outputs is 8 times the number of output modules (eeprom address 0, 1).
    """
    id = EepromId(160, address=EepromAddress(0, 1, 1), multiplier=8)
    name = EepromString(16, page_per_module(8, 33, 20, 16))
    timer = EepromWord(page_per_module(8, 33, 4, 2))
    floor = EepromByte(page_per_module(8, 33, 157, 1))
    type = EepromByte(page_per_module(8, 33, 149, 1))
    ## TODO Type of the output -> dimmer or light ?


class InputConfiguration(EepromModel):
    """ Models an input. The maximum number of inputs is 240 (30 modules), the actual number of 
    inputs is 8 times the number of input modules (eeprom address 0, 2).
    """
    id = EepromId(160, address=EepromAddress(0, 2, 1), multiplier=8)
    name = EepromString(8, per_module(8, lambda mid, iid: (115+(mid/4), 64*(mid % 4) + 8*iid)))
    action = EepromByte(page_per_module(8, 2, 4, 1))
    basic_actions = EepromActions(15, page_per_module(8, 2, 12, 30))


class ThermostatConfiguration(EepromModel):
    """ Models a thermostat. The maximum number of inputs is 24. """ 
    id = EepromId(24)
    setp0 = EepromTemp(lambda id: (142, 32+id))
    setp1 = EepromTemp(lambda id: (142, 64+id))
    setp2 = EepromTemp(lambda id: (142, 96+id))
    setp3 = EepromTemp(lambda id: (142, 128+id))
    setp4 = EepromTemp(lambda id: (142, 160+id))
    setp5 = EepromTemp(lambda id: (142, 192+id))
    sensor = EepromTemp(lambda id: (144, 8+id))
    output0 = EepromByte(lambda id: (142, id))
    output1 = EepromByte(lambda id: (142, 224+id))
    pid_p = EepromByte(lambda id: (141, 4*id))
    pid_i = EepromByte(lambda id: (141, (4*id)+1))
    pid_d = EepromByte(lambda id: (141, (4*id)+2))
    pid_int = EepromByte(lambda id: (141, (4*id)+3))
    ## TODO Add thermostat name

## TODO Add sensors

## TODO Add pump groups

class GroupActionConfiguration(EepromModel):
    """ Models a group action. The maximum number of inputs is 160. """
    id = EepromId(160)
    name = EepromString(16, lambda id: (158 + (id / 16), 16 * (id % 16)))
    actions = EepromActions(16, lambda id: (67 + (id / 8), 32 * (id % 8)))


class StartupActionConfiguration(EepromModel):
    """ Models the startup actions, this contains 100 basic actions. """
    actions = EepromActions(100, (1, 0))


class DimmerConfiguration(EepromModel):
    """ Models the global dimmer configuration.  """
    min_dim_level = EepromByte((0, 5))
    dim_step = EepromByte((0, 6))
    dim_wait_cycle = EepromByte((0, 7))
    dim_memory = EepromByte((0, 9))


class ModuleConfiguration(EepromModel):
    """ Models the global module configuration. """
    nr_input_modules = EepromByte((0, 1))
    nr_output_modules = EepromByte((0, 2))
    enable_thermostat_16 = EepromByte((0, 15))


class CliConfiguration(EepromModel):
    """ Models the cli configuration. These values are set by the OpenMotics daemon at startup. """
    auto_response = EepromByte((0, 11))
    auto_response_OL = EepromByte((0, 18))
    echo = EepromByte((0, 12))
    start_cli_api = EepromByte((0, 13))
    auto_init = EepromByte((0, 14))


class GlobalThermostatConfiguration(EepromModel):
    """ The global thermostat configuration. """
    outside_sensor = EepromByte((0, 16))
    threshold_temp = EepromTemp((0, 17))
    pump_delay = EepromByte((0, 19))
