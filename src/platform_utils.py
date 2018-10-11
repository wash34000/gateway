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
""""
The constants modules contains static definitions for filenames.

@author: saelbrec
"""

from enum import Enum

import sys
import subprocess

class LOGGER(object):
    @staticmethod
    def log(line):
        sys.stdout.write('{0}\n'.format(line))
        sys.stdout.flush()


class boardtype(Enum):
    """
    Board type Enum
    Make sure UNKNOWN is listed as last one
    """
    BB = 'TI_AM335x_BeagleBone'
    BBB = 'TI_AM335x_BeagleBone_Black'
    BBGW = 'TI_AM335x_BeagleBone_Green_Wireless'
    U = 'UNKNOWN'


class hardware(object):
    """
    Abstracts the hardware related functions
    """
    @staticmethod
    def get_gpios():
        gpios = {"GPIO_INPUT_BUTTON_GW": 38,     # Pin for the input button on the separate gateway module (deprecated)
                 "GPIO_INPUT_BUTTON_GW_M": 26,   # Pin for the input button on the gateway/master module (current)
                 "ETH_LEFT_BB": 60,
                 "ETH_RIGHT_BB": 49,
                 "ETH_STATUS_BBB": 48,
                 "POWER_BBB": 60,
                 "HOME": 75}
        return gpios

    @staticmethod
    def get_board_type():
        try:
            with open("/proc/device-tree/model", "r") as mfh:
                boardname = mfh.read().strip('\x00').replace(" ", "_")
        except IOError, e:
            if e.errno == errno.ENOENT:
                boardname = 'UNKNOWN'

        for t in boardType:
            if t.value == boardname:
                break
            else:
                continue
        return t


    @staticmethod
    def get_meminfo():
        with open("/proc/meminfo", "r") as memfh:
            mem_total = memfh.readline()
        return mem_total

    @staticmethod
    def is_beagle_bone_black():
        board_type = hardware.get_board_type()

        if board_type in (boardType.BB, boardType.BBB):
            return True
        else:
            return False

    @staticmethod
    def get_i2c_device():
        i2c_device = '/dev/i2c-1' if hardware.is_beagle_bone_black() else '/dev/i2c-2'
        return i2c_device


    @staticmethod
    def get_local_interface():
        board_name = hardware.get_board_type()
        if board_name in ("TI_AM335x_BeagleBone", "TI_AM335x_BeagleBone_Black"):
            return 'eth0'
        elif board_name() in ("TI_AM335x_BeagleBone_Green_Wireless"):
            return 'wlan0'
        else:
            return 'lo'


class system(object):
    """
    Abstracts the system related functions
    """
    @staticmethod
    def get_os():
        os = dict()
        with open("/etc/os-release", "r") as osfh:
            lines = osfh.readlines()
            for line in lines:
                k,v = line.strip().split("=")
                os[k] = v
        return os


    @staticmethod
    def get_ip_address():
        """ Get the local ip address. """
        interface = hardware.get_local_interface()
        os = system.get_os()
        try:
            lines = subprocess.check_output("ifconfig {0}".format(interface), shell=True)
            if os["ID"] == "angstrom":
                return lines.split("\n")[1].strip().split(" ")[1].split(":")[1]
            elif os["ID"] == "debian":
                return lines.split("\n")[1].strip().split(" ")[1]
            else:
                return None
        except Exception:
            return None


