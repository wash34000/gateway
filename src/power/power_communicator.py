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
Module to communicate with the power modules.

@author: fryckbos
"""

import logging
import traceback
import time
import Queue
import power.power_api as power_api
from threading import Thread, RLock
from serial_utils import printable, CommunicationTimedOutException
from power.power_command import crc7
from power.time_keeper import TimeKeeper

LOGGER = logging.getLogger("openmotics")


class PowerCommunicator(object):
    """ Uses a serial port to communicate with the power modules. """

    def __init__(self, serial, power_controller, verbose=False, time_keeper_period=60,
                 address_mode_timeout=300):
        """ Default constructor.

        :param serial: Serial port to communicate with
        :type serial: Instance of :class`RS485`
        :param verbose: Print all serial communication to stdout.
        :type verbose: boolean.
        """
        self.__serial = serial
        self.__serial_lock = RLock()
        self.__serial_bytes_written = 0
        self.__serial_bytes_read = 0
        self.__cid = 1

        self.__address_mode = False
        self.__address_mode_stop = False
        self.__address_thread = None
        self.__address_mode_timeout = address_mode_timeout
        self.__power_controller = power_controller

        self.__last_success = 0

        if time_keeper_period != 0:
            self.__time_keeper = TimeKeeper(self, power_controller, time_keeper_period)
        else:
            self.__time_keeper = None

        self.__verbose = verbose

    def start(self):
        """ Start the power communicator. """
        if self.__time_keeper is not None:
            self.__time_keeper.start()

    def get_bytes_written(self):
        """ Get the number of bytes written to the power modules. """
        return self.__serial_bytes_written

    def get_bytes_read(self):
        """ Get the number of bytes read from the power modules. """
        return self.__serial_bytes_read

    def get_seconds_since_last_success(self):
        """ Get the number of seconds since the last successful communication. """
        if self.__last_success == 0:
            return 0  # No communication - return 0 sec since last success
        else:
            return time.time() - self.__last_success

    def __get_cid(self):
        """ Get a communication id """
        (ret, self.__cid) = (self.__cid, (self.__cid % 255) + 1)
        return ret

    def __log(self, action, data):
        if data is not None:
            LOGGER.info("%.3f %s power: %s" % (time.time(), action, printable(data)))

    def __write_to_serial(self, data):
        """ Write data to the serial port.

        :param data: the data to write
        :type data: string
        """
        if self.__verbose:
            self.__log('writing to', data)
        self.__serial.write(data)
        self.__serial_bytes_written += len(data)

    def do_command(self, address, cmd, *data):
        """ Send a command over the serial port and block until an answer is received.
        If the power module does not respond within the timeout period, a
        CommunicationTimedOutException is raised.

        :param address: Address of the power module
        :type address: 2 bytes string
        :param cmd: the command to execute
        :type cmd: :class`PowerCommand`
        :param data: data for the command
        :raises: :class`CommunicationTimedOutException` if power module did not respond in time
        :raises: :class`InAddressModeException` if communicator is in address mode
        :returns: dict containing the output fields of the command
        """
        if self.__address_mode:
            raise InAddressModeException()

        def do_once(_address, _cmd, *_data):
            """ Send the command once. """
            cid = self.__get_cid()
            send_data = _cmd.create_input(_address, cid, *_data)
            self.__write_to_serial(send_data)

            if _address == power_api.BROADCAST_ADDRESS:
                return None  # No reply on broadcast messages !
            else:
                header = None
                response_data = None
                try:
                    tries = 0
                    while True:
                        # In this loop we might receive data that didn't match the expected header. This might happen
                        # if we for some reason had a timeout on the previous call, and we now read the response
                        # to that call. In this case, we just re-try (up to 3 times), as the correct data might be
                        # next in line.
                        header, response_data = self.__read_from_serial()
                        if not _cmd.check_header(header, _address, cid):
                            if _cmd.is_nack(header, _address, cid) and response_data == "\x02":
                                raise UnkownCommandException()
                            tries += 1
                            LOGGER.warning("Header did not match command ({0})".format(tries))
                            if tries == 3:
                                raise Exception("Header did not match command ({0})".format(tries))
                            else:
                                if not self.__verbose:
                                    self.__log('writing to', send_data)
                                    self.__log('reading header from', header)
                                    self.__log('reading data from', response_data)
                        else:
                            break
                except:
                    if not self.__verbose:
                        self.__log('writing to', send_data)
                        self.__log('reading header from', header)
                        self.__log('reading data from', response_data)
                    raise

                self.__last_success = time.time()
                return _cmd.read_output(response_data)

        with self.__serial_lock:
            try:
                return do_once(address, cmd, *data)
            except UnkownCommandException:
                # This happens when the module is stuck in the bootloader.
                LOGGER.error("Got UnkownCommandException")
                do_once(address, power_api.bootloader_jump_application())
                time.sleep(1)
                return self.do_command(address, cmd, *data)
            except CommunicationTimedOutException:
                # Communication timed out, try again.
                LOGGER.error("First communication timed out")
                return do_once(address, cmd, *data)
            except Exception as ex:
                LOGGER.exception("Unexpected error: {0}".format(ex))
                time.sleep(0.25)
                return do_once(address, cmd, *data)

    def start_address_mode(self):
        """ Start address mode.

        :raises: :class`InAddressModeException` if communicator is in maintenance mode.
        """
        if self.__address_mode:
            raise InAddressModeException()

        self.__address_mode = True
        self.__address_mode_stop = False

        with self.__serial_lock:
            self.__address_thread = Thread(target=self.__do_address_mode,
                                           name="PowerCommunicator address mode thread")
            self.__address_thread.daemon = True
            self.__address_thread.start()

    def __do_address_mode(self):
        """ This code is running in a thread when in address mode. """
        expire = time.time() + self.__address_mode_timeout
        address_mode = power_api.set_addressmode()
        want_an_address_8 = power_api.want_an_address(power_api.POWER_API_8_PORTS)
        want_an_address_12 = power_api.want_an_address(power_api.POWER_API_12_PORTS)
        set_address = power_api.set_address()

        # AGT start
        data = address_mode.create_input(power_api.BROADCAST_ADDRESS,
                                         self.__get_cid(),
                                         power_api.ADDRESS_MODE)
        self.__write_to_serial(data)

        # Wait for WAA and answer.
        while not self.__address_mode_stop and time.time() < expire:
            try:
                header, data = self.__read_from_serial()

                waa_8 = want_an_address_8.check_header_partial(header)
                waa_12 = want_an_address_12.check_header_partial(header)

                if not waa_8 and not waa_12:
                    LOGGER.warning("Received non WAA/WAD message in address mode")
                else:
                    (old_address, cid) = (ord(header[:2][1]), header[2:3])
                    # Ask power_controller for new address, and register it.
                    new_address = self.__power_controller.get_free_address()

                    if self.__power_controller.module_exists(old_address):
                        self.__power_controller.readdress_power_module(old_address, new_address)
                    else:
                        version = power_api.POWER_API_8_PORTS if waa_8 else power_api.POWER_API_12_PORTS

                        self.__power_controller.register_power_module(new_address, version)

                    # Send new address to power module
                    address_data = set_address.create_input(old_address, ord(cid), new_address)
                    self.__write_to_serial(address_data)

            except CommunicationTimedOutException:
                pass  # Didn't receive a command, no problem.
            except Exception as exception:
                traceback.print_exc()
                LOGGER.warning("Got exception in address mode: %s", exception)

        # AGT stop
        data = address_mode.create_input(power_api.BROADCAST_ADDRESS,
                                         self.__get_cid(),
                                         power_api.NORMAL_MODE)
        self.__write_to_serial(data)

        self.__address_mode = False
        self.__address_thread = None

    def stop_address_mode(self):
        """ Stop address mode. """
        if not self.__address_mode:
            raise Exception("Not in address mode !")

        self.__address_mode_stop = True
        self.__address_thread.join()

    def in_address_mode(self):
        """ Returns whether the PowerCommunicator is in address mode. """
        return self.__address_mode

    def __read_from_serial(self):
        """ Read a PowerCommand from the serial port. """
        phase = 0
        index = 0

        header = ""
        length = 0
        data = ""
        crc = 0

        command = ""
        error = False

        try:
            while phase < 8:
                byte = self.__serial.read_queue.get(True, 0.25)
                command += byte
                self.__serial_bytes_read += 1
                if phase == 0:  # Skip non 'R' bytes
                    if byte == 'R':
                        phase = 1
                    else:
                        phase = 0
                elif phase == 1:  # Expect 'T'
                    if byte == 'T':
                        phase = 2
                    else:
                        raise Exception("Unexpected character")
                elif phase == 2:  # Expect 'R'
                    if byte == 'R':
                        phase = 3
                        index = 0
                    else:
                        raise Exception("Unexpected character")
                elif phase == 3:  # Read the header fields
                    header += byte
                    index += 1
                    if index == 8:
                        length = ord(byte)
                        if length > 0:
                            phase = 4
                            index = 0
                        else:
                            phase = 5
                elif phase == 4:  # Read the data
                    data += byte
                    index += 1
                    if index == length:
                        phase = 5
                elif phase == 5:  # Read the CRC code
                    crc = ord(byte)
                    phase = 6
                elif phase == 6:  # Expect '\r'
                    if byte == '\r':
                        phase = 7
                    else:
                        raise Exception("Unexpected character")
                elif phase == 7:  # Expect '\n'
                    if byte == '\n':
                        phase = 8
                    else:
                        raise Exception("Unexpected character")
            if crc7(header + data) != crc:
                raise Exception("CRC doesn't match")
        except Queue.Empty:
            error = True
            raise CommunicationTimedOutException()
        except Exception:
            error = True
            raise
        finally:
            if self.__verbose or error is True:
                self.__log('reading from', command)

        return header, data


class InAddressModeException(Exception):
    """ Raised when the power communication is in address mode. """
    def __init__(self):
        Exception.__init__(self)


class UnkownCommandException(Exception):
    """ Raised when the power module responds with a NACK indicating an unkown command. """
    def __init__(self):
        Exception.__init__(self)
