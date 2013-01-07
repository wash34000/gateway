""" The vpn_service asks the OpenMotics cloud it a vpn tunnel should be opened. It start openvpn
if required. On each check the vpn_service sends some status information about the outputs and 
thermostats to the cloud, to keep the status information in the cloud in sync. """

import urllib, urllib2
import time
import subprocess
import os

from ConfigParser import ConfigParser
from datetime import datetime

try:
    import json
except ImportError:
    import simplejson as json

import constants

from frontend.physical_frontend import PhysicalFrontend

REBOOT_TIMEOUT = 600

def reboot_gateway():
    """ Reboot the gateway. """
    subprocess.call('reboot', shell=True)


class VpnController:
    """ Contains methods to check the vpn status, start and stop the vpn. """
    
    vpnService = "openvpn.service"
    startCmd = "systemctl start " + vpnService
    stopCmd = "systemctl stop " + vpnService
    checkCmd = "systemctl is-active " + vpnService
    
    def __init__(self):
        pass
    
    def start_vpn(self):
        """ Start openvpn """
        return subprocess.call(VpnController.startCmd, shell=True) == 0
        
    def stop_vpn(self):
        """ Stop openvpn """
        return subprocess.call(VpnController.stopCmd, shell=True) == 0
    
    def check_vpn(self):
        """ Check if openvpn is running """
        return subprocess.call(VpnController.checkCmd, shell=True) == 0


class Cloud:
    """ Connects to the OpenMotics cloud to check if the vpn should be opened. """

    def __init__(self, url, physical_frontend):
        self.__url = url
        self.__physical_frontend = physical_frontend
        self.__last_connect = time.time()

    def should_open_vpn(self, extra_data):
        """ Check with the OpenMotics could if we should open a VPN """
        url_opener = urllib2.build_opener()
        try:
            handle = url_opener.open(self.__url, urllib.urlencode([("extra_data", extra_data)]),
                                     timeout=10.0)
            lines = ''.join(handle.readlines())
            handle.close()
            
            self.__physical_frontend.set_led('cloud', True)
            self.__physical_frontend.toggle_led('alive')
            self.__last_connect = time.time()
            
            return "true" in lines
        except Exception as exception:
            print "Exception occured during check: ", exception
            self.__physical_frontend.set_led('cloud', False)
            self.__physical_frontend.set_led('alive', False)
            
            return True
    
    def get_last_connect(self):
        """ Get the timestamp of the last connection with the cloud. """
        return self.__last_connect

class Gateway:
    """ Class to get the current status of the gateway. Outputs are fetched from the webservice on
    each call, fetching the thermostats is cached for one minute to reduce the load on the
    webservice. """
    
    def __init__(self, host="127.0.0.1"):
        self.__host = host 
        self.__last_thermostats_fetch = 0
        self.__last_thermostats_data = None

    def __do_call(self, uri):
        """ Do a call to the webservice, returns a dict parsed from the json returned by the
        webserver. """
        try:
            url = "https://" + self.__host + "/" + uri
            handler = urllib2.urlopen(url, timeout=60.0)
            return json.loads(handler.read())
        except Exception as exception:
            print "Exception during getting output status: ", exception
            return None
    
    def get_enabled_outputs(self):
        """ Get the enabled outputs.
        
        :returns: a list of tuples containing the output number and dimmer value. None on error.
        """
        data = self.__do_call("get_outputs?token=None")
        if data == None or data['success'] == False:
            return None
        else:
            ret = []
            for output in data['outputs']:
                if output["status"] == 1:
                    ret.append((output["output_nr"], output["dimmer"]))
            return ret
    
    def __fetch_thermostats(self):
        """ Fetch the setpoints for the enabled thermostats from the webservice.
        
        :returns: a dict with 'thermostats_on', 'automatic' and an array of dicts in 'thermostats'
        with the following fields: 'thermostat', 'act', 'csetp' and 'mode'. None on error.
        """
        data = self.__do_call("get_thermostats?token=None")
        if data == None or data['success'] == False:
            return None
        else:
            ret = { 'thermostats_on' : data['thermostats_on'], 'automatic' : data['automatic'] }
            thermostats = []
            for thermostat in data['thermostats']:
                to_add = {}
                for field in [ 'thermostat', 'act', 'csetp', 'mode', 'output0', 'output1',
                               'outside' ]:
                    to_add[field] = thermostat[field]
                thermostats.append(to_add)
            ret['thermostats'] = thermostats
            return ret

    def get_thermostats(self):
        """ Get the setpoints for the enabled thermostats, fetched from web interface
        once per minute.
        
        :returns: a dict with 'thermostats_on', 'automatic' and an array of dicts in 'thermostats'
        with the following fields: 'thermostat', 'act', 'csetp' and 'mode'. None on error.
        """
        now = time.time()
        if self.__last_thermostats_data == None or now >= self.__last_thermostats_fetch + 60:
            self.__last_thermostats_fetch = now
            self.__last_thermostats_data = self.__fetch_thermostats()
            return self.__last_thermostats_data
        else:
            return None

    def get_update_status(self):
        """ Get the status of an executing update. """
        update_status_file = '/opt/openmotics/update_status'
        if os.path.exists(update_status_file):
            f = open(update_status_file, 'r')
            status = f.read()
            f.close()
            os.remove(update_status_file)
            return status
        else:
            return None

def main():
    """ The main function contains the loop that check if the vpn should be opened every 2 seconds.
    Status data is sent when the vpn is checked. """
    
    physical_frontend = PhysicalFrontend()
    physical_frontend.set_led('vpn', True)
    
    # Get the configuration
    config = ConfigParser()
    config.read(constants.get_config_file())
    
    check_url = config.get('OpenMotics', 'vpn_check_url') % config.get('OpenMotics', 'uuid')

    vpn = VpnController()
    cloud = Cloud(check_url, physical_frontend)
    gateway = Gateway()

    # Loop: check vpn and open/close if needed
    while True:
        monitoring_data = {}
        monitoring_data['thermostats'] = gateway.get_thermostats()
        monitoring_data['outputs'] = gateway.get_enabled_outputs()
        
        update_status = gateway.get_update_status()
        if update_status != None:
            monitoring_data['update'] = update_status
        
        extra_data = json.dumps(monitoring_data)
    
        should_open = cloud.should_open_vpn(extra_data)
        
        if cloud.get_last_connect() < time.time() - REBOOT_TIMEOUT:
            ''' The cloud is not responding for a while, perhaps the BeagleBone network stack is 
            hanging, reboot the gateway to reset the BeagleBone. '''
            reboot_gateway()
        
        is_open = vpn.check_vpn()
        
        if should_open and not is_open:
            physical_frontend.set_led('vpn', True)
            print str(datetime.now()) + ": opening vpn"
            vpn.start_vpn()
        elif not should_open and is_open:
            physical_frontend.set_led('vpn', False)
            print str(datetime.now()) + ": closing vpn"
            vpn.stop_vpn()
            
        time.sleep(2)


if __name__ == '__main__':
    main()
