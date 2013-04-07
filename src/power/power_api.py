from power_command import PowerCommand

BROADCAST_ADDRESS = 255

NIGHT = 0
DAY = 1

NORMAL_MODE = 0
ADDRESS_MODE = 1

def get_general_status():
    """ Get the general status of a power module. """
    return PowerCommand('G', 'GST', '', 'H')

def get_time_on():
    """ Get the time the power module is on (in s) """
    return PowerCommand('G', 'TON', '', 'L')

def get_feed_status():
    """ Get the feed status of the power module (8x 0=low or 1=high) """
    return PowerCommand('G', 'FST', '', '8H')

def get_feed_counter():
    """ Get the feed counter of the power module """
    return PowerCommand('G', 'FCO', '', 'H')

def get_voltage():
    """ Get the voltage of a power module (in V)"""
    return PowerCommand('G', 'VOL', '', 'f')

def get_frequency():
    """ Get the frequency of a power module (in Hz)"""
    return PowerCommand('G', 'FRE', '', 'f')

def get_current():
    """ Get the current of a power module (8x in A)"""
    return PowerCommand('G', 'CUR', '', '8f')

def get_power():
    """ Get the power of a power module (8x in W)"""
    return PowerCommand('G', 'POW', '', '8f')

def get_normal_energy():
    """ Get the total energy measured by the power module (8x in Wh) """
    return PowerCommand('G', 'ENO', '', '8L')

def get_day_energy():
    """ Get the energy measured during the day by the power module (8x in Wh) """
    return PowerCommand('G', 'EDA', '', '8L')

def get_night_energy():
    """ Get the energy measured during the night by the power module (8x in Wh) """
    return PowerCommand('G', 'ENI', '', '8L')

def get_display_timeout():
    """ Get the timeout on the power module display (in min) """
    return PowerCommand('G', 'DTO', '', 'b')

def set_display_timeout():
    """ Set the timeout on the power module display (in min) """
    return PowerCommand('S', 'DTO', '', 'b')

def get_display_screen_menu():
    """ Get the index of the displayed menu on the power module display. """
    return PowerCommand('G', 'DSM', '', 'b')

def set_display_screen_menu():
    """ Set the index of the displayed menu on the power module display. """
    return PowerCommand('S', 'DSM', 'b', 'b')

def set_day_night():
    """ Set the power module in night (0) or day (1) mode. """
    return PowerCommand('S', 'SDN', 'b', 'b')

def set_addressmode():
    """ Set the address mode of the power module, 1 = address mode, 0 = normal mode"""
    return PowerCommand('S', 'AGT', 'b', 'b')

def want_an_address():
    """ The Want An Address command, send by the power modules in address mode. """
    return PowerCommand('S', 'WAA', '', '')

def set_address():
    """ Reply on want_an_address, setting a new address for the power module. """
    return PowerCommand('S', 'SAD', 'b', 'b')

def get_sensor_types():
    """ Get the sensor types used on the power modules (8x sensor type) """
    return PowerCommand('G', 'CSU', '', '8b')

def set_sensor_types():
    """ Set the sensor types used on the power modules (8x sensor type) """
    return PowerCommand('S', 'CSU', '8b', '')

def get_sensor_names():
    """ Get the names of the available sensor types. """
    return PowerCommand('G', 'CSN', '', '16s16s16s16s16s16s16s16s16s16s')

def set_voltage():
    """ Calibrate the voltage of the power module. """
    return PowerCommand('S', 'SVO', 'f', 'f')
