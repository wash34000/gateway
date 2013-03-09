'''
Created on Mar 2, 2013

@author: fryckbos
'''
import unittest
from datetime import datetime

from time_keeper import TimeKeeper

class PowerControllerDummy:
    
    def get_time_configuration(self):
        return [ (1,2), (2,3), (3,4), (4,5), (5,6), (6,7), (7,8) ]

class TimeKeeperTest(unittest.TestCase):
    """ Tests for TimeKeeper. """

    def test_is_day_time(self):
        """ Test for is_day_time. """
        tk = TimeKeeper(None, PowerControllerDummy(), 10)
        
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 4, 0, 0, 0))) # Monday 12AM
        self.assertTrue(tk.is_day_time(datetime(2013, 3, 4, 1, 0, 0))) # Monday 1AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 4, 2, 0, 0))) # Monday 2AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 4, 12, 0, 0))) # Monday 2AM
        
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 5, 0, 0, 0))) # Tuesday 12AM
        self.assertTrue(tk.is_day_time(datetime(2013, 3, 5, 2, 0, 0))) # Tuesday 1AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 5, 3, 0, 0))) # Tuesday 2AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 5, 12, 0, 0))) # Tuesday 2AM

        self.assertFalse(tk.is_day_time(datetime(2013, 3, 6, 0, 0, 0))) # Wednesday 12AM
        self.assertTrue(tk.is_day_time(datetime(2013, 3, 6, 3, 0, 0))) # Wednesday 1AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 6, 4, 0, 0))) # Wednesday 2AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 6, 12, 0, 0))) # Wednesday 2AM
        
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 7, 0, 0, 0))) # Thursday 12AM
        self.assertTrue(tk.is_day_time(datetime(2013, 3, 7, 4, 0, 0))) # Thursday 1AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 7, 5, 0, 0))) # Thursday 2AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 7, 12, 0, 0))) # Thursday 2AM
        
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 8, 0, 0, 0))) # Friday 12AM
        self.assertTrue(tk.is_day_time(datetime(2013, 3, 8, 5, 0, 0))) # Friday 1AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 8, 6, 0, 0))) # Friday 2AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 8, 12, 0, 0))) # Friday 2AM
        
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 9, 0, 0, 0))) # Saturday 12AM
        self.assertTrue(tk.is_day_time(datetime(2013, 3, 9, 6, 0, 0))) # Saturday 1AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 9, 7, 0, 0))) # Saturday 2AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 9, 12, 0, 0))) # Saturday 2AM
        
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 10, 0, 0, 0))) # Sunday 12AM
        self.assertTrue(tk.is_day_time(datetime(2013, 3, 10, 7, 0, 0))) # Sunday 1AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 10, 8, 0, 0))) # Sunday 2AM
        self.assertFalse(tk.is_day_time(datetime(2013, 3, 10, 12, 0, 0))) # Sunday 2AM

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
