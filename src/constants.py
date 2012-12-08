'''
The constants modules contains static definitions for filenames.

Created on Sep 23, 2012

@author: fryckbos
'''

def get_config_file():
    """ Get the filename of the OpenMotics config file. This file is in ini format. """
    return "/opt/openmotics/etc/openmotics.conf"


def get_user_database_file():
    """ Get the filename of the user database file. This file is in sqlite format. """
    return "/opt/openmotics/etc/config.db"


def get_ssl_certificate_file():
    """ Get the filename of the ssl certificate. """
    return "/etc/openvpn/client.crt"

def get_ssl_private_key_file():
    """ Get the filename of the ssl private key. """
    return "/etc/openvpn/client.key"


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
    return [ "/usr/bin/python", "/opt/openmotics/python/update.py", str(version), str(md5) ]

def get_update_script():
    """ Get the bash script that runs the update after the tgz file is extracted. """
    return "/opt/openmotics/Updater/updater.sh"

