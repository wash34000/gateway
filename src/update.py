""" The update modules provides the update functionality. """

import sys
import hashlib
import traceback
import subprocess

from ConfigParser import ConfigParser

from constants import get_config_file, get_update_script, get_update_output_file, get_update_file

def md5(filename):
    """ Generate the md5 sum of a file.
    
    :param filename: the name of the file to hash.
    :returns: md5sum
    """
    md5_hash = hashlib.md5()
    with open(filename,'rb') as file_to_hash:
        for chunk in iter(lambda: file_to_hash.read(128 * md5_hash.block_size), ''): 
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def update(version, md5_server):
    """ Execute the actual update: extract the archive and execute the bash update script.
    
    :param version: the new version (after the update).
    :param md5_sum: the md5 sum provided by the server.
    """
    update_file = get_update_file()

    md5_client = md5(update_file)
    if md5_server != md5_client:
        raise Exception("MD5 of client (" + str(md5_client) + ") and server (" + str(md5_server) +
                        ") don't match")
    
    extract = subprocess.Popen("cd `dirname " + update_file + "`; tar xzf " + update_file + " 2>&1",
                               stdout=subprocess.PIPE, shell=True)
    ret = extract.wait()
    output = extract.stdout.read()
    
    if ret != 0:
        raise Exception("Extraction failed: " + output)
    
    update_script = subprocess.Popen(get_update_script() + " `dirname " + update_file + "` 2>&1",
                              stdout=subprocess.PIPE, shell=True)
    ret = update_script.wait()
    output = update_script.stdout.read()

    cleanup = subprocess.Popen("rm -Rf `dirname " + update_file + "`/*", shell=True)
    cleanup.wait()

    if ret != 0:
        raise Exception("Error during update (ret=" + str(ret) + ") : " + output)
    else:
        config = ConfigParser()
        config.read(get_config_file())
        config.set('OpenMotics', 'version', version)
        with open(get_config_file(), 'wb') as configfile:
            config.write(configfile)


def main():
    """ The main function. """
    if len(sys.argv) != 3:
        print "Usage: python " + __file__ + " version md5sum"
        sys.exit(1)
    else:
        (version, md5_sum) = (sys.argv[1], sys.argv[2])
        error = None

        try:
            update(version, md5_sum)
        except:
            error = traceback.format_exc()
        finally:
            update_output_file = open(get_update_output_file(), "w")
            update_output_file.write(version + "\n")
            if error != None:
                update_output_file.write("Update failed " + traceback.format_exc())
            update_output_file.close()


if __name__ == "__main__":
    main()
