'''
Gives the watchdog a push every 10 seconds.

Created on Oct 24, 2012

@author: fryckbos
'''
import time

def main():
    while True:
        watchdog = open('/dev/watchdog', 'w')
        watchdog.write("OM")
        watchdog.close()
        
        time.sleep(10)
    
    
if __name__ == '__main__':
    main()
