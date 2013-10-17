""" The vpn_service asks the OpenMotics cloud it a vpn tunnel should be opened. It start openvpn
if required. On each check the vpn_service sends some status information about the outputs and
thermostats to the cloud, to keep the status information in the cloud in sync. """

import requests
import time
import subprocess
import os

from threading import Thread
from ConfigParser import ConfigParser
from datetime import datetime

try:
    import json
except ImportError:
    import simplejson as json

import constants

from frontend.physical_frontend import PhysicalFrontend

REBOOT_TIMEOUT = 900

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

    DEFAULT_SLEEP_TIME = 30
    DEFAULT_SEND_REAL_TIME_DATA = False

    def __init__(self, url, physical_frontend, action_executor, sleep_time=DEFAULT_SLEEP_TIME,
                 send_real_time_data=DEFAULT_SEND_REAL_TIME_DATA):
        self.__url = url
        self.__physical_frontend = physical_frontend
        self.__action_executor = action_executor
        self.__last_connect = time.time()
        self.__sleep_time = sleep_time
        self.__send_real_time_data = send_real_time_data

    def should_open_vpn(self, extra_data):
        """ Check with the OpenMotics could if we should open a VPN """
        try:
            r = requests.post(self.__url, data={'extra_data' : json.dumps(extra_data)}, timeout=10.0, verify=True)
            data = json.loads(r.text)

            if 'sleep_time' in data:
                self.__sleep_time = data['sleep_time']

            if 'send_real_time_data' in data:
                self.__send_real_time_data = data['send_real_time_data']

            if 'actions' in data:
                self.__action_executor.execute_actions_in_background(data['actions'])

            self.__physical_frontend.set_led('cloud', True)
            self.__physical_frontend.toggle_led('alive')
            self.__last_connect = time.time()

            return data['open_vpn']
        except Exception as exception:
            print "Exception occured during check: ", exception
            self.__physical_frontend.set_led('cloud', False)
            self.__physical_frontend.set_led('alive', False)

            return True

    def get_sleep_time(self):
        """ Get the time to sleep between two cloud checks. """
        return self.__sleep_time

    def should_send_real_time_data(self):
        """ Whether we should send real time data to the cloud. """
        return self.__send_real_time_data

    def get_last_connect(self):
        """ Get the timestamp of the last connection with the cloud. """
        return self.__last_connect

class Gateway:
    """ Class to get the current status of the gateway. """

    def __init__(self, host="127.0.0.1"):
        self.__host = host
        self.__last_pulse_counters = None

    def do_call(self, uri):
        """ Do a call to the webservice, returns a dict parsed from the json returned by the
        webserver. """
        try:
            r = requests.get("http://" + self.__host + "/" + uri, timeout=15.0)
            return json.loads(r.text)
        except Exception as exception:
            print "Exception during getting output status: ", exception
            return None

    def get_enabled_outputs(self):
        """ Get the enabled outputs.

        :returns: a list of tuples containing the output number and dimmer value. None on error.
        """
        data = self.do_call("get_output_status?token=None")
        if data == None or data['success'] == False:
            return None
        else:
            ret = []
            for output in data['outputs']:
                if output["status"] == 1:
                    ret.append((output["id"], output["dimmer"]))
            return ret

    def get_thermostats(self):
        """ Fetch the setpoints for the enabled thermostats from the webservice.

        :returns: a dict with 'thermostats_on', 'automatic' and an array of dicts in 'status'
        with the following fields: 'id', 'act', 'csetp', 'output0', 'output1' and 'mode'.
        None on error.
        """
        data = self.do_call("get_thermostat_status?token=None")
        if data == None or data['success'] == False:
            return None
        else:
            ret = { 'thermostats_on' : data['thermostats_on'], 'automatic' : data['automatic'] }
            thermostats = []
            for thermostat in data['status']:
                to_add = {}
                for field in [ 'thermostat', 'act', 'csetp', 'mode', 'output0', 'output1',
                               'outside' ]:
                    to_add[field] = thermostat[field]
                thermostats.append(to_add)
            ret['status'] = thermostats
            return ret

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

    def get_real_time_power(self):
        """ Get the real time power measurements. """
        data = self.do_call("get_realtime_power?token=None")
        if data == None or data['success'] == False:
            return None
        else:
            del data['success']
            return data

    def get_total_energy(self):
        """ Get the total energy. """
        data = self.do_call("get_total_energy?token=None")
        if data == None or data['success'] == False:
            return None
        else:
            del data['success']
            return data

    def get_pulse_counter_status(self):
        """ Get the pulse counter values. """
        data = self.do_call("get_pulse_counter_status?token=None")
        if data == None or data['success'] == False:
            return None
        else:
            counters = data['counters']

            if self.__last_pulse_counters == None:
                ret = [ 0 for i in range(0, 8) ]
            else:
                ret = [ self.__counter_diff(counters[i], self.__last_pulse_counters[i])
                         for i in range(0, 8) ]

            self.__last_pulse_counters = counters
            return ret

    def __counter_diff(self, current, previous):
        """ Calculate the diff between two counter values. """
        diff = current - previous
        return diff if diff >= 0 else 65536 - previous + current

    def get_errors(self):
        """ Get the errors on the gateway. """
        data = self.do_call("get_errors?token=None")
        if data == None:
            return None
        else:
            if data['errors'] != None:
                master_errors = sum(map(lambda x: x[1], data['errors']))
            else:
                master_errors = 0

            return { 'master_errors': master_errors,
                     'master_last_success': data['master_last_success'],
                     'power_last_success': data['power_last_success'] }

    def get_local_ip_address(self):
        """ Get the local ip address. """
        try:
            lines = subprocess.check_output("ifconfig eth0", shell=True)
            return lines.split("\n")[1].strip().split(" ")[1].split(":")[1]
        except:
            return None


class DataCollector:

    def __init__(self, function, period=0, real_time=False):
        """
        Create a collector with a function to call, a period and a boolean that indicates whether
        this collector is real time.

        If the period is 0, the collector will be executed on each call.
        """
        self.__function = function
        self.__period = period
        self.__real_time = real_time
        self.__last_collect = 0

    def is_real_time(self):
        """ Check if this is a real_time collector. """
        return self.__real_time

    def __should_collect(self):
        """ Should we execute the collect ? """
        return self.__period == 0 or time.time() >= self.__last_collect + self.__period

    def collect(self):
        """ Execute the collect if required, return None otherwise. """
        if self.__should_collect():
            if self.__period != 0:
                self.__last_collect = time.time()
            return self.__function()
        else:
            return None


class ActionExecutor:
    """ Executes actions received from the cloud. """

    def __init__(self, gateway):
        """ Use a Gateway instance to communicate with the gateway. """
        self.__gateway = gateway

    def execute_actions_in_background(self, actions):
        """ Execute a list of actions in the background. """
        def run():
            for action in actions:
                try:
                    self.execute(action)
                except Exception as e:
                    print "Error wile executing action '" + str(action) + "': " + str(e)

        thread = Thread(name="Action Executor", target=run)
        thread.daemon = True
        thread.start()

    def execute(self, action):
        """ Execute an action. """
        name = action.get('name', None)
        args = action.get('args', None)

        if name == 'set_output':
            self.__gateway.do_call("set_output?id=%s&on=%s&dimmer=%s&timer=%s&token=None" % \
                                   (args['id'], args['on'], args['dimmer'], args['timer']))

        elif name == 'set_all_lights_off':
            self.__gateway.do_call("set_all_lights_off?token=None")

        elif name == 'set_all_lights_floor_off':
            self.__gateway.do_call("set_all_lights_floor_off?floor=%s&token=None" % args['floor'])

        elif name == 'set_all_lights_floor_on':
            self.__gateway.do_call("set_all_lights_floor_on?floor=%s&token=None" % args['floor'])

        elif name == 'set_current_setpoint':
            self.__gateway.do_call("set_current_setpoint?thermostat=%s&temperature=%s&token=None" % \
                                   (args['thermostat'], args['temperature']))

        elif name == 'set_mode':
            self.__gateway.do_call("set_mode?on=%s&automatic=%s&setpoint=%s&token=None" % \
                                   (args['on'], args['automatic'], args['setpoint']))

        elif name == 'do_group_action':
            self.__gateway.do_call("do_group_action?group_action_id=%s&token=None" % \
                                   args['group_action_id'])

        else:
            raise Exception("Could not find action '%s'" % name)


def main():
    """ The main function contains the loop that check if the vpn should be opened every 2 seconds.
    Status data is sent when the vpn is checked. """

    physical_frontend = PhysicalFrontend()

    # Get the configuration
    config = ConfigParser()
    config.read(constants.get_config_file())

    check_url = config.get('OpenMotics', 'vpn_check_url') % config.get('OpenMotics', 'uuid')

    vpn = VpnController()
    physical_frontend.set_led('vpn', vpn.check_vpn())

    gateway = Gateway()
    cloud = Cloud(check_url, physical_frontend, ActionExecutor(gateway))

    collectors = { 'energy' : DataCollector(gateway.get_total_energy, 300),
                   'thermostats' : DataCollector(gateway.get_thermostats, 60),
                   'pulses' : DataCollector(gateway.get_pulse_counter_status, 60),
                   'outputs' : DataCollector(gateway.get_enabled_outputs, real_time=True),
                   'power' : DataCollector(gateway.get_real_time_power, real_time=True),
                   'update' : DataCollector(gateway.get_update_status),
                   'errors': DataCollector(gateway.get_errors, 600),
                   'local_ip' : DataCollector(gateway.get_local_ip_address, 1800) }

    iterations = 0

    # Loop: check vpn and open/close if needed
    while True:
        vpn_data = {}
        for collector_name in collectors:
            collector = collectors[collector_name]
            if cloud.should_send_real_time_data() or not collector.is_real_time():
                data = collector.collect()
                if data != None:
                    vpn_data[collector_name] = data

        should_open = cloud.should_open_vpn(vpn_data)

        if iterations > 20 and cloud.get_last_connect() < time.time() - REBOOT_TIMEOUT:
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

        print "Sleeping for %d" % cloud.get_sleep_time()
        time.sleep(cloud.get_sleep_time())

        iterations += 1


if __name__ == '__main__':
    main()
