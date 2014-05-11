'''
The outputs module contains classes to track the current state of the outputs on
the master.

Created on Sep 22, 2012

@author: fryckbos
'''
import time

class OutputStatus(object):
    """ Contains a cached version of the current output of the controller. """

    def __init__(self, outputs, refresh_period=600):
        """ Create a status object using a list of outputs (can be None),
        and a refresh period: the refresh has to be invoked explicitly. """
        self.__outputs = outputs
        self.__refresh_period = refresh_period
        self.__last_refresh = time.time()

    def force_refresh(self):
        """ Force a refresh on the OuptutStatus. """
        self.__last_refresh = 0

    def should_refresh(self):
        """ Check whether the status should be refreshed. """
        return time.time() >= self.__last_refresh + self.__refresh_period

    def partial_update(self, on_outputs):
        """ Update the status of the outputs using a list of tuples containing the
        light id an the dimmer value of the lights that are on. """
        on_dict = {}
        for on_output in on_outputs:
            on_dict[on_output[0]] = on_output[1]

        for output in self.__outputs:
            if output['id'] in on_dict:
                output['status'] = 1
                output['dimmer'] = on_dict[output['id']]
            else:
                output['status'] = 0

    def full_update(self, outputs):
        """ Update the status of the outputs using a list of Outputs. """
        self.__outputs = outputs
        self.__last_refresh = time.time()

    def get_outputs(self):
        """ Return the list of Outputs. """
        return self.__outputs
