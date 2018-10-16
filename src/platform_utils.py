# Copyright (C) 2018 OpenMotics BVBA
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
The hardware_utils module contains various classes helping with Hardware and System abstraction
"""
import subprocess


class Hardware(object):
    """
    Abstracts the hardware related functions
    """

    class Led(object):
        POWER = 'POWER'
        STATUS = 'STATUS'
        ALIVE = 'ALIVE'
        CLOUD = 'CLOUD'
        VPN = 'VPN'
        COMM_1 = 'COMM_1'
        COMM_2 = 'COMM_2'

    class BoardType(object):
        BB = 'BB'
        BBB = 'BBB'
        BBGW = 'BBGW'

    BoardTypes = [BoardType.BB, BoardType.BBB, BoardType.BBGW]
    IOCTL_I2C_SLAVE = 0x0703

    @staticmethod
    def get_board_type():
        try:
            with open('/proc/device-tree/model', 'r') as mfh:
                board_type = mfh.read().strip('\x00').replace(' ', '_')
                if board_type in ['TI_AM335x_BeagleBone', 'TI_AM335x_BeagleBone_Black']:
                    return Hardware.BoardType.BBB
                if board_type in ['TI_AM335x_BeagleBone_Green_Wireless']:
                    return Hardware.BoardType.BBGW
        except IOError:
            pass
        with open('/proc/meminfo', 'r') as memfh:
            mem_total = memfh.readline()
            if '254228 kB' in mem_total:
                return Hardware.BoardType.BB
            if '510716 kB' in mem_total:
                return Hardware.BoardType.BBB
        return None  # Unknown

    @staticmethod
    def get_i2c_device():
        return '/dev/i2c-2' if Hardware.get_board_type() == Hardware.BoardType.BB else '/dev/i2c-1'

    @staticmethod
    def get_local_interface():
        board_type = Hardware.get_board_type()
        if board_type in [Hardware.BoardType.BB, Hardware.BoardType.BBB]:
            return 'eth0'
        elif board_type == Hardware.BoardType.BBGW:
            return 'wlan0'
        else:
            return 'lo'

    @staticmethod
    def get_i2c_led_config():
        if not Hardware.get_board_type() == Hardware.BoardType.BB:
            return {'COMM_1': 64,
                    'COMM_2': 128,
                    'VPN': 16,
                    'ALIVE': 1,
                    'CLOUD': 4}
        return {'COMM_1': 64,
                'COMM_2': 128,
                'VPN': 16,
                'CLOUD': 4}

    @staticmethod
    def get_gpio_led_config():
        if not Hardware.get_board_type() == Hardware.BoardType.BB:
            return {'POWER': 60,
                    'STATUS': 48}
        return {'POWER': 75,
                'STATUS': 60,
                'ALIVE': 49}

    @staticmethod
    def get_gpio_input():
        return 38 if Hardware.get_board_type() == Hardware.BoardType.BB else 26


class System(object):
    """
    Abstracts the system related functions
    """

    @staticmethod
    def _get_os():
        os = {}
        with open('/etc/os-release', 'r') as osfh:
            lines = osfh.readlines()
            for line in lines:
                k, v = line.strip().split('=')
                os[k] = v
        return os

    @staticmethod
    def get_ip_address():
        """ Get the local ip address. """
        interface = Hardware.get_local_interface()
        os = System._get_os()
        try:
            lines = subprocess.check_output('ifconfig {0}'.format(interface), shell=True)
            if os['ID'] == 'angstrom':
                return lines.split('\n')[1].strip().split(' ')[1].split(':')[1]
            elif os['ID'] == 'debian':
                return lines.split('\n')[1].strip().split(' ')[1]
            else:
                return None
        except Exception:
            return None

    @staticmethod
    def get_vpn_service():
        return 'openvpn.service' if System._get_os()['ID'] == 'angstrom' else 'openvpn-client@omcloud'

    @staticmethod
    def get_ssl_socket(sock, private_key_filename, certificate_filename):
        os = System._get_os()
        if os['ID'] == 'angstrom':
            from OpenSSL import SSL
            context = SSL.Context(SSL.SSLv23_METHOD)
            context.use_privatekey_file(private_key_filename)
            context.use_certificate_file(certificate_filename)
            return SSL.Connection(context, sock)
        import ssl
        return ssl.wrap_socket(sock,
                               keyfile=private_key_filename,
                               certfile=certificate_filename,
                               ssl_version=ssl.PROTOCOL_SSLv23,
                               do_handshake_on_connect=False,
                               suppress_ragged_eofs=False)

    @staticmethod
    def setup_cherrypy_ssl(https_server, private_key_filename, certificate_filename):
        os = System._get_os()
        if os['ID'] == 'angstrom':
            https_server.ssl_module = 'pyopenssl'
        else:
            import ssl
            https_server.ssl_module = 'builtin'
            https_server.ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        https_server.ssl_certificate = certificate_filename
        https_server.ssl_private_key = private_key_filename

    @staticmethod
    def get_syscall_exception():
        os = System._get_os()
        if os['ID'] == 'angstrom':
            from OpenSSL import SSL
            return SSL.SysCallError
        import ssl
        return ssl.SSLSyscallError

    @staticmethod
    def get_wantread_exception():
        os = System._get_os()
        if os['ID'] == 'angstrom':
            from OpenSSL import SSL
            return SSL.WantReadError
        import ssl
        return ssl.SSLWantReadError
