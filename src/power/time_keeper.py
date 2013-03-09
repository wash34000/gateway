'''
Created on Mar 2, 2013

@author: fryckbos
'''
import time
import traceback
from datetime import datetime
from threading import Thread

import power_api

class TimeKeeper:
    """ The TimeKeeper keeps track of time and sets the day or night mode on the power modules. """

    def __init__(self, power_communicator, power_controller, period):
        self.__power_communicator = power_communicator
        self.__power_controller = power_controller
        self.__period = period
        
        self.__in_day_mode = None # First time None, thereafter True or False
        
        self.__thread = None
        self.__stop = False
    
    def start(self):
        """ Start the background thread of the TimeKeeper. """
        if self.__thread == None:
            self.__stop = False
            self.__thread = Thread(target=self.__run, name="TimeKeeper thread")
            self.__thread.daemon = True
            self.__thread.start()
        else:
            raise Exception("TimeKeeper thread already running.")
    
    def stop(self):
        """ Stop the background thread in the TimeKeeper. """
        if self.__thread != None:
            self.__stop = True
        else:
            raise Exception("TimeKeeper thread not running.")
    
    def __run(self):
        """ Code for the background thread. """
        while not self.__stop:
            date = datetime.now()
            if self.is_day_time(date):
                self.__set_day_mode()
            else:
                self.__set_night_mode()
            
            time.sleep(self.__period)
            
        self.__thread = None
    
    def is_day_time(self, date):
        """ Check if a date is in day time. """
        day_of_week = date.weekday() # 0 = Monday, 6 = Sunday
        hour_of_day = date.hour
    
        times = self.__power_controller.get_time_configuration()
        start = times[day_of_week][0]
        stop = times[day_of_week][1]
    
        return hour_of_day >= start and hour_of_day < stop

    def __set_day_mode(self):
        """ Set the power modules in day mode. """
        try:
            if self.__in_day_mode == None or self.__in_day_mode == False:
                self.__power_communicator.do_command(power_api.BROADCAST_ADDRESS,
                                                     power_api.set_day_night(), power_api.DAY)
                self.__in_day_mode = True
        except:
            ## Got an exception, we'll just try again later
            print "Exception while setting day mode for power modules."
            traceback.print_exc()
    
    def __set_night_mode(self):
        """ Set the power modules in night mode. """
        try:
            if self.__in_day_mode == None or self.__in_day_mode == True:
                self.__power_communicator.do_command(power_api.BROADCAST_ADDRESS,
                                                     power_api.set_day_night(), power_api.NIGHT)
                self.__in_day_mode = False
        except:
            ## Got an exception, we'll just try again later
            print "Exception while setting night mode for power modules."
            traceback.print_exc()
