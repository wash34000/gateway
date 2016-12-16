'''
Created on Feb 24, 2013

@author: fryckbos
'''
import time

class ThermostatStatus(object):
    """ Contains a cached version of the current thermostat status. """

    def __init__(self, thermostats, refresh_period=600):
        """ Create a status object using a dict (keys: 'cooling', 'heating') where each value is a
        list of thermostats (can be None), and a refresh period: the refresh has to be invoked
        explicitly. """
        self.__thermostats = thermostats
        self.__refresh_period = refresh_period
        self.__last_refresh = time.time()

    def force_refresh(self):
        """ Force a refresh on the ThermostatStatus. """
        self.__last_refresh = 0

    def should_refresh(self):
        """ Check whether the status should be refreshed. """
        return time.time() >= self.__last_refresh + self.__refresh_period

    def update(self, thermostats):
        """ Update the status of the thermostats using a dict (keys: 'cooling', 'heating') with as
        value a list of thermostats. """
        self.__thermostats = thermostats
        self.__last_refresh = time.time()

    def get_thermostats(self):
        """ Return the list of thermostats. """
        return self.__thermostats
