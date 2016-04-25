'''
Contains the definition of the power modules Api.

@author: fryckbos
'''

from power.power_command import PowerCommand

BROADCAST_ADDRESS = 255

NIGHT = 0
DAY = 1

NORMAL_MODE = 0
ADDRESS_MODE = 1

POWER_API_8_PORTS = 8
POWER_API_12_PORTS = 12

NUM_PORTS = { POWER_API_8_PORTS : 8, POWER_API_12_PORTS : 12}

def get_general_status(version):
    """ Get the general status of a power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'GST', '', 'H')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'GST', '', 'B')
    else:
        raise ValueError("Unknown power api version")

def get_time_on(version):
    """ Get the time the power module is on (in s)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS or version == POWER_API_12_PORTS:
        return PowerCommand('G', 'TON', '', 'L')
    else:
        raise ValueError("Unknown power api version")

def get_feed_status(version):
    """ Get the feed status of the power module (12x 0=low or 1=high)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'FST', '', '8H')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'FST', '', '12I')
    else:
        raise ValueError("Unknown power api version")

def get_feed_counter(version):
    """ Get the feed counter of the power module
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS or version == POWER_API_12_PORTS:
        return PowerCommand('G', 'FCO', '', 'H')
    else:
        raise ValueError("Unknown power api version")

def get_voltage(version):
    """ Get the voltage of a power module (in V)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'VOL', '', 'f')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'VOL', '', '12f')
    else:
        raise ValueError("Unknown power api version")

def get_frequency(version):
    """ Get the frequency of a power module (in Hz)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'FRE', '', 'f')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'FRE', '', '12f')
    else:
        raise ValueError("Unknown power api version")

def get_current(version):
    """ Get the current of a power module (12x in A)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'CUR', '', '8f')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'CUR', '', '12f')
    else:
        raise ValueError("Unknown power api version")

def get_power(version):
    """ Get the power of a power module (12x in W)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'POW', '', '8f')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'POW', '', '12f')
    else:
        raise ValueError("Unknown power api version")

def get_normal_energy(version):
    """ Get the total energy measured by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'ENO', '', '8L')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'ENE', '', '12L')
    else:
        raise ValueError("Unknown power api version")

def get_day_energy(version):
    """ Get the energy measured during the day by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'EDA', '', '8L')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'EDA', '', '12L')
    else:
        raise ValueError("Unknown power api version")

def get_night_energy(version):
    """ Get the energy measured during the night by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'ENI', '', '8L')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('G', 'ENI', '', '12L')
    else:
        raise ValueError("Unknown power api version")

def set_day_night(version):
    """ Set the power module in night (0) or day (1) mode.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('S', 'SDN', '8b', '')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('S', 'SDN', '12b', '')
    else:
        raise ValueError("Unknown power api version")

def get_sensor_types(version):
    """ Get the sensor types used on the power modules (8x sensor type).
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('G', 'CSU', '', '8b')
    elif version == POWER_API_12_PORTS:
        raise ValueError("Getting sensor types is not applicable for the 12 port modules.")
    else:
        raise ValueError("Unknown power api version")

def set_sensor_types(version):
    """ Set the sensor types used on the power modules (8x sensor type).
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('S', 'CSU', '8b', '')
    elif version == POWER_API_12_PORTS:
        raise ValueError("Setting sensor types is not applicable for the 12 port modules.")
    else:
        raise ValueError("Unknown power api version")

def set_current_clamp_factor(version):
    """ Sets the current clamp factor.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        raise ValueError("Setting clamp factor is not applicable for the 8 port modules.")
    elif version == POWER_API_12_PORTS:
        return PowerCommand('S', 'CCF', '12f', '')
    else:
        raise ValueError('Unknown power api version')

def set_current_inverse(version):
    """ Sets the current inverse.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        raise ValueError("Setting current inverse is not applicable for the 8 port modules.")
    elif version == POWER_API_12_PORTS:
        return PowerCommand('S', 'SCI', '12b', '')
    else:
        raise ValueError('Unknown power api version')

## Below are the address mode functions.

def set_addressmode():
    """ Set the address mode of the power module, 1 = address mode, 0 = normal mode """
    return PowerCommand('S', 'AGT', 'b', '')

def want_an_address(version):
    """ The Want An Address command, send by the power modules in address mode. """
    if version == POWER_API_8_PORTS:
        return PowerCommand('S', 'WAA', '', '')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('S', 'WAD', '', '')
    else:
        raise ValueError('Unknown power api version')

def set_address():
    """ Reply on want_an_address, setting a new address for the power module. """
    return PowerCommand('S', 'SAD', 'b', '')

def set_voltage():
    """ Calibrate the voltage of the power module. """
    return PowerCommand('S', 'SVO', 'f', '')


## Below are the function to reset the kwh counters

def reset_normal_energy(version):
    """ Reset the total energy measured by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('S', 'ENE', '9B', '')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('S', 'ENE', 'B12L', '')
    else:
        raise ValueError("Unknown power api version")


def reset_day_energy(version):
    """ Reset the energy measured during the day by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('S', 'EDA', '9B', '')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('S', 'EDA', 'B12L', '')
    else:
        raise ValueError("Unknown power api version")

def reset_night_energy(version):
    """ Reset the energy measured during the night by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_API_8_PORTS:
        return PowerCommand('S', 'ENI', '9B', '')
    elif version == POWER_API_12_PORTS:
        return PowerCommand('S', 'ENI', 'B12L', '')
    else:
        raise ValueError("Unknown power api version")


## Below are the bootloader functions

def bootloader_goto():
    """ Go to bootloader and wait for a number of seconds (b parameter) """
    return PowerCommand('S', 'BGT', 'B', '')

def bootloader_read_id():
    """ Get the device id """
    return PowerCommand('G', 'BRI', '', '8B')

def bootloader_write_code():
    """ Write code """
    return PowerCommand('S', 'BWC', '195B', '')

def bootloader_write_configuration():
    """ Write configuration """
    return PowerCommand('S', 'BWF', '24B', '')

def bootloader_jump_application():
    """ Go from bootloader to applications """
    return PowerCommand('S', 'BJA', '', '')

def get_version():
    """ Get the current version of the power module firmware """
    return PowerCommand('G', 'FIV', '', '16s')
