# Copyright (C) 2016 OpenMotics BVBA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
The vpn_service asks the OpenMotics cloud it a vpn tunnel should be opened. It start openvpn
if required. On each check the vpn_service sends some status information about the outputs and
thermostats to the cloud, to keep the status information in the cloud in sync.
"""

from platform_utils import System, Hardware
System.import_eggs()

import sys
import requests
import time
import subprocess
import os
import traceback
import constants
import threading

from ConfigParser import ConfigParser
from datetime import datetime
from bus.led_service import LedService
from gateway.config import ConfigurationController

try:
    import json
except ImportError:
    import simplejson as json

REBOOT_TIMEOUT = 900


class LOGGER(object):
    @staticmethod
    def log(line):
        sys.stdout.write('{0}\n'.format(line))
        sys.stdout.flush()


def reboot_gateway():
    """ Reboot the gateway. """
    subprocess.call('sync && reboot', shell=True)


class VpnController(object):
    """ Contains methods to check the vpn status, start and stop the vpn. """

    vpn_service = System.get_vpn_service()
    start_cmd = "systemctl start " + vpn_service + " > /dev/null"
    stop_cmd = "systemctl stop " + vpn_service + " > /dev/null"
    check_cmd = "systemctl is-active " + vpn_service + " > /dev/null"

    def __init__(self):
        pass

    @staticmethod
    def start_vpn():
        """ Start openvpn """
        return subprocess.call(VpnController.start_cmd, shell=True) == 0

    @staticmethod
    def stop_vpn():
        """ Stop openvpn """
        return subprocess.call(VpnController.stop_cmd, shell=True) == 0

    @staticmethod
    def check_vpn():
        """ Check if openvpn is running """
        return subprocess.call(VpnController.check_cmd, shell=True) == 0

    @staticmethod
    def vpn_connected():
        """ Checks if the VPN tunnel is connected """
        try:
            route = subprocess.check_output('ip r | grep tun | grep via || true', shell=True).strip()
            if not route:
                return False
            vpn_server = route.split(' ')[0]
            return ping(vpn_server)
        except Exception as ex:
            LOGGER.log('Exception occured during vpn connectivity test: {0}'.format(ex))
            return False


class Cloud(object):
    """ Connects to the OpenMotics cloud to check if the vpn should be opened. """

    DEFAULT_SLEEP_TIME = 30

    def __init__(self, url, led_service, config, sleep_time=DEFAULT_SLEEP_TIME):
        self.__url = url
        self.__led_service = led_service
        self.__last_connect = time.time()
        self.__sleep_time = sleep_time
        self.__config = config

    def should_open_vpn(self, extra_data):
        """ Check with the OpenMotics could if we should open a VPN """
        try:
            request = requests.post(self.__url, data={'extra_data': json.dumps(extra_data)},
                                    timeout=10.0, verify=True)
            data = json.loads(request.text)

            if 'sleep_time' in data:
                self.__sleep_time = data['sleep_time']
            else:
                self.__sleep_time = Cloud.DEFAULT_SLEEP_TIME

            if 'configuration' in data:
                for setting, value in data['configuration'].iteritems():
                    self.__config.set_setting(setting, value)

            self.__last_connect = time.time()
            self.__led_service.set_led(Hardware.Led.CLOUD, True)

            return data['open_vpn']
        except Exception as ex:
            LOGGER.log('Exception occured during check: {0}'.format(ex))
            self.__led_service.set_led(Hardware.Led.CLOUD, False)

            return True

    def get_sleep_time(self):
        """ Get the time to sleep between two cloud checks. """
        return self.__sleep_time

    def get_last_connect(self):
        """ Get the timestamp of the last connection with the cloud. """
        return self.__last_connect


class Gateway(object):
    """ Class to get the current status of the gateway. """

    def __init__(self, host="127.0.0.1"):
        self.__host = host
        self.__last_pulse_counters = None

    def do_call(self, uri):
        """ Do a call to the webservice, returns a dict parsed from the json returned by the
        webserver. """
        try:
            request = requests.get("http://" + self.__host + "/" + uri, timeout=15.0)
            return json.loads(request.text)
        except Exception as ex:
            LOGGER.log('Exception during Gateway call: {0}'.format(ex))
            return None

    def get_enabled_outputs(self):
        """ Get the enabled outputs.

        :returns: a list of tuples containing the output number and dimmer value. None on error.
        """
        data = self.do_call("get_output_status?token=None")
        if data is None or data['success'] is False:
            return None
        else:
            ret = []
            for output in data['status']:
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
        if data is None or data['success'] is False:
            return None
        else:
            ret = {'thermostats_on': data['thermostats_on'],
                   'automatic': data['automatic'],
                   'cooling': data['cooling']}
            thermostats = []
            for thermostat in data['status']:
                to_add = {}
                for field in ['id', 'act', 'csetp', 'mode', 'output0', 'output1', 'outside', 'airco']:
                    to_add[field] = thermostat[field]
                thermostats.append(to_add)
            ret['status'] = thermostats
            return ret

    def get_update_status(self):
        """ Get the status of an executing update. """
        _ = self  # Needs to be an instance method
        filename = '/opt/openmotics/update_status'
        if os.path.exists(filename):
            update_status_file = open(filename, 'r')
            status = update_status_file.read()
            update_status_file.close()
            if status.endswith('DONE\n'):
                os.remove(filename)
            return status
        else:
            return None

    def get_real_time_power(self):
        """ Get the real time power measurements. """
        data = self.do_call("get_realtime_power?token=None")
        if data is None or data['success'] is False:
            return None
        else:
            del data['success']
            return data

    def get_pulse_counter_diff(self):
        """ Get the pulse counter differences. """
        data = self.do_call("get_pulse_counter_status?token=None")
        if data is None or data['success'] is False:
            return None
        else:
            counters = data['counters']

            if self.__last_pulse_counters is None:
                ret = [0 for _ in xrange(0, 24)]
            else:
                ret = [Gateway.__counter_diff(counters[i], self.__last_pulse_counters[i])
                       for i in xrange(0, 24)]

            self.__last_pulse_counters = counters
            return ret

    @staticmethod
    def __counter_diff(current, previous):
        """ Calculate the diff between two counter values. """
        diff = current - previous
        return diff if diff >= 0 else 65536 - previous + current

    def get_errors(self):
        """ Get the errors on the gateway. """
        data = self.do_call("get_errors?token=None")
        if data is None:
            return None
        else:
            if data['errors'] is not None:
                master_errors = sum([error[1] for error in data['errors']])
            else:
                master_errors = 0

            return {'master_errors': master_errors,
                    'master_last_success': data['master_last_success'],
                    'power_last_success': data['power_last_success']}

    def get_local_ip_address(self):
        """ Get the local ip address. """
        _ = self  # Needs to be an instance method
        return System.get_ip_address()


class DataCollector(object):
    """ Defines a function to retrieve data, the period between two collections
    """

    def __init__(self, fct, period=0):
        """
        Create a collector with a function to call and a period.
        If the period is 0, the collector will be executed on each call.
        """
        self.__function = fct
        self.__period = period
        self.__last_collect = 0

    def __should_collect(self):
        """ Should we execute the collect ? """

        return self.__period == 0 or time.time() >= self.__last_collect + self.__period

    def collect(self):
        """ Execute the collect if required, return None otherwise. """
        try:
            if self.__should_collect():
                if self.__period != 0:
                    self.__last_collect = time.time()
                return self.__function()
            else:
                return None
        except Exception as ex:
            LOGGER.log('Error while collecting data: {0}'.format(ex))
            traceback.print_exc()
            return None


def ping(target, verbose=True):
    """ Check if the target can be pinged. Returns True if at least 1/4 pings was successful. """
    if target is None:
        return False

    if verbose is True:
        LOGGER.log("Testing ping to {0}".format(target))
    try:
        # Ping returns status code 0 if at least 1 ping is successful
        subprocess.check_output("ping -c 3 {0}".format(target), shell=True)
        return True
    except Exception as ex:
        LOGGER.log("Error during ping: {0}".format(ex))
        return False


def get_gateway():
    """ Get the default gateway. """
    try:
        return subprocess.check_output("ip r | grep '^default via' | awk '{ print $3; }'", shell=True)
    except Exception as ex:
        LOGGER.log("Error during get_gateway: {0}".format(ex))
        return None


def main():
    """
    The main function contains the loop that check if the vpn should be opened every 2 seconds.
    Status data is sent when the vpn is checked.
    """

    led_service = LedService()
    config_lock = threading.Lock()
    config_controller = ConfigurationController(constants.get_config_database_file(), config_lock)

    def set_vpn(_should_open):
        is_running = VpnController.check_vpn()
        if _should_open and not is_running:
            LOGGER.log(str(datetime.now()) + ": opening vpn")
            VpnController.start_vpn()
        elif not _should_open and is_running:
            LOGGER.log(str(datetime.now()) + ": closing vpn")
            VpnController.stop_vpn()
        is_running = VpnController.check_vpn()
        led_service.set_led(Hardware.Led.VPN, is_running and VpnController.vpn_connected())

    # Get the configuration
    config = ConfigParser()
    config.read(constants.get_config_file())
    check_url = config.get('OpenMotics', 'vpn_check_url') % config.get('OpenMotics', 'uuid')

    gateway = Gateway()
    cloud = Cloud(check_url, led_service, config_controller)

    collectors = {'thermostats': DataCollector(gateway.get_thermostats, 60),
                  'pulses': DataCollector(gateway.get_pulse_counter_diff, 60),
                  'outputs': DataCollector(gateway.get_enabled_outputs),
                  'power': DataCollector(gateway.get_real_time_power),
                  'update': DataCollector(gateway.get_update_status),
                  'errors': DataCollector(gateway.get_errors, 600),
                  'local_ip': DataCollector(gateway.get_local_ip_address, 1800)}

    iterations = 0

    previous_sleep_time = 0
    while True:
        try:
            # Check whether connection to the Cloud is enabled/disabled
            cloud_enabled = config_controller.get_setting('cloud_enabled')
            if cloud_enabled is False:
                set_vpn(False)
                led_service.set_led(Hardware.Led.CLOUD, False)
                led_service.set_led(Hardware.Led.VPN, False)
                time.sleep(30)
                continue

            vpn_data = {}

            # Collect data to be send to the Cloud
            for collector_name in collectors:
                collector = collectors[collector_name]
                data = collector.collect()
                if data is not None:
                    vpn_data[collector_name] = data

            # Send data to the cloud and see if the VPN should be opened
            should_open = cloud.should_open_vpn(vpn_data)

            if iterations > 20 and cloud.get_last_connect() < time.time() - REBOOT_TIMEOUT:
                # The cloud is not responding for a while.
                if not ping('cloud.openmotics.com') and not ping('8.8.8.8') and not ping(get_gateway()):
                    # Perhaps the BeagleBone network stack is hanging, reboot the gateway
                    # to reset the BeagleBone.
                    reboot_gateway()
            iterations += 1

            # Open or close the VPN
            set_vpn(should_open)

            # Getting some cleep
            sleep_time = cloud.get_sleep_time()
            if previous_sleep_time != sleep_time:
                LOGGER.log('Sleep time set to {0}s'.format(sleep_time))
                previous_sleep_time = sleep_time
            time.sleep(sleep_time)
        except Exception as ex:
            LOGGER.log("Error during vpn check loop: {0}".format(ex))


if __name__ == '__main__':
    LOGGER.log("Starting VPN service")
    main()
