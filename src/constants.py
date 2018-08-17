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

@author: fryckbos
"""


def get_config_file():
    """ Get the filename of the OpenMotics config file. This file is in ini format. """
    return "/opt/openmotics/etc/openmotics.conf"


def get_config_database_file():
    """ Get the filename of the config database file. This file is in sqlite format. """
    return "/opt/openmotics/etc/config.db"


def get_power_database_file():
    """ Get the filename of the power database file. This file is in sqlite format. """
    return "/opt/openmotics/etc/power.db"


def get_scheduling_database_file():
    """ Get the filename of the scheduling database file. This file is in sqlite format. """
    return "/opt/openmotics/etc/sched.db"


def get_eeprom_extension_database_file():
    """ Get the filename of the EEPROM extension database file. This file is in sqlite format. """
    return "/opt/openmotics/etc/eeprom_ext.db"


def get_metrics_database_file():
    """ Get the filename of the metrics database file. This file is in sqlite format. """
    return "/opt/openmotics/etc/metrics.db"


def get_ssl_certificate_file():
    """ Get the filename of the ssl certificate. """
    return "/opt/openmotics/etc/https.crt"


def get_ssl_private_key_file():
    """ Get the filename of the ssl private key. """
    return "/opt/openmotics/etc/https.key"


def get_update_dir():
    """ Get the directory to store the temporary update data. """
    return "/opt/openmotics/update/"


def get_update_file():
    """ Get the filename of the tgz file that contains the update script and data. """
    return "/opt/openmotics/update/update.tgz"

def get_update_output_file():
    """ Get the filename for the output of the update command. """
    return "/opt/openmotics/etc/last_update.out"


def get_update_cmd(version, md5):
    """ Get the command to execute an update. Returns an array of arguments (string). """
    return ["/usr/bin/python", "/opt/openmotics/python/update.py", str(version), str(md5)]


def get_update_script():
    """ Get the bash script that runs the update after the tgz file is extracted. """
    return "/opt/openmotics/Updater/updater.sh"


def get_timezone_file():
    """ Get the path of the timezone file. """
    return "/opt/openmotics/etc/timezone"


def get_self_test_cmd():
    """ Get the path of the bash script that executes the self test. """
    return "/opt/openmotics/bin/self_test.sh"


def get_plugin_dir():
    """ Get the directory where plugin data is stored. """
    return "/opt/openmotics/python/plugins/"


def get_plugin_configfiles():
    """ Get the directory where plugin data is stored. """
    return "/opt/openmotics/etc/pi_*"