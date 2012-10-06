'''
Module to communicate with the master.

Created on Sep 10, 2012

@author: fryckbos
'''
import sys
import time
from threading import Thread, Lock
from Queue import Queue, Empty

import master_api
from master_command import printable

class MasterCommunicator:
    """ Uses a serial port to communicate with the master and updates the output state.
    Provides methods to send MasterCommands, Passthrough and Maintenance
    """
    
    def __init__(self, serial, verbose=True):
        """ Default constructor.
        
        :param serial: Serial port to communicate with 
        :type serial: Instance of :class`serial.Serial`
        """
        self.__verbose = verbose
        
        self.__serial = serial
        self.__serial_write_lock = Lock()
        self.__command_lock = Lock()
        self.__serial_bytes_written = 0
        self.__serial_bytes_read = 0
        
        self.__cid = 1
        
        self.__maintenance_mode = False
        self.__maintenance_queue = Queue()
        
        self.__consumers = []
        
        self.__passthrough_queue = Queue()
    
        self.__stop = False
        self.__read_thread = Thread(target=self.__read, name="MasterCommunicator read thread")
        self.__read_thread.daemon = True
    
    def __flush_serial_input(self):
        data = self.__serial.read(1)
        while len(data) > 0:
            data = self.__serial.read(1)
    
    def start(self):
        """ Start the MasterComunicator, this starts the background read thread. """
        self.__serial.timeout = 1
        self.__serial.write(" "*18 + "\r\n")
        self.__flush_serial_input()
        self.__serial.write("exit\r\n")
        self.__flush_serial_input()
        self.__serial.write(" "*10)
        self.__flush_serial_input()
        self.__serial.timeout = None
        
        self.__stop = False
        self.__read_thread.start()
    
    def get_bytes_written(self):
        """ Get the number of bytes written to the Master. """
        return self.__serial_bytes_written
    
    def get_bytes_read(self):
        """ Get the number of bytes read from the Master. """
        return self.__serial_bytes_read
    
    def __get_cid(self):
        """ Get a communication id """
        (ret, self.__cid) = (self.__cid, (self.__cid % 255) + 1)
        return ret

    def __write_to_serial(self, data):
        """ Write data to the serial port.
        
        :param data: the data to write
        :type data: string
        """
        with self.__serial_write_lock:
            if self.__verbose:
                print "%.3f writing to serial: %s" % (time.time(), printable(data))
            self.__serial.write(data)
            self.__serial_bytes_written += len(data)

    def register_consumer(self, consumer):
        """ Register a customer consumer with the communicator. An instance of :class`Consumer`
        will be removed when consumption is done. An instance of :class`BackgroundConsumer` stays
        active and is thus able to consume multiple messages.
        
        :param consumer: The consumer to register.
        :type consumer: Consumer or BackgroundConsumer.
        """
        self.__consumers.append(consumer)

    def do_command(self, cmd, fields=dict(), timeout=1):
        """ Send a command over the serial port and block until an answer is received.
        If the master does not respond within the timeout period, a CommunicationTimeOutException
        is raised
        
        :param cmd: specification of the command to execute
        :type cmd: :class`MasterCommand.MasterCommandSpec`
        :raises: :class`CommunicationTimeOutException` if master did not respond in time
        :raises: :class`InMaintenanceModeException` if master is in maintenance mode
        :returns: dict containing the output fields of the command
        """
        if self.__maintenance_mode:
            raise InMaintenanceModeException()
        
        cid = self.__get_cid()
        consumer = Consumer(cmd, cid)
        inp = cmd.create_input(cid, fields)
        
        with self.__command_lock:
            self.__consumers.append(consumer)
            self.__write_to_serial(inp)
            return consumer.get(timeout).fields
    
    def send_passthrough_data(self, data):
        """ Send raw data on the serial port. 
        
        :param data: string of bytes with raw command for the master.
        :raises: :class`InMaintenanceModeException` if master is in maintenance mode.
        """
        if self.__maintenance_mode:
            raise InMaintenanceModeException()
        
        self.__write_to_serial(data)
    
    def get_passthrough_data(self):
        """ Get data that wasn't consumed by do_command.
        Blocks if no data available or in maintenance mode.
        
        :returns: string containing unprocessed output
        """
        return self.__passthrough_queue.get()
    
    def start_maintenance_mode(self):
        """ Start maintenance mode.
        
        :raises: :class`InMaintenanceModeException` if master is in maintenance mode.
        """
        if self.__maintenance_mode:
            raise InMaintenanceModeException()
        
        self.__maintenance_mode = True
        
        self.send_maintenance_data(master_api.to_cli_mode().create_input(0))
    
    def send_maintenance_data(self, data):
        """ Send data to the master in maintenance mode.
        
        :param data: data to send to the master
        :type data: string
         """
        if not self.__maintenance_mode:
            raise Exception("Not in maintenance mode !")
        
        self.__write_to_serial(data)
    
    def get_maintenance_data(self):
        """ Get data from the master in maintenance mode.
        
        :returns: string containing unprocessed output
        """
        if not self.__maintenance_mode:
            raise Exception("Not in maintenance mode !")
        
        try:
            return self.__maintenance_queue.get(timeout=1)
        except Empty:
            return None
    
    def stop_maintenance_mode(self):
        """ Stop maintenance mode. """
        if not self.__maintenance_mode:
            raise Exception("Not in maintenance mode !")
        
        self.send_maintenance_data("exit\r\n")
        
        self.__maintenance_mode = False
    
    def in_maintenance_mode(self):
        """ Returns whether the MasterCommunicator is in maintenance mode. """
        return self.__maintenance_mode
    
    def __get_start_bytes(self):
        """ Create a dict that maps the start byte to a list of consumers. """
        start_bytes = {}
        for consumer in self.__consumers:
            start_byte = consumer.get_prefix()[0]
            if start_byte in start_bytes:
                start_bytes[start_byte].append(consumer)
            else:
                start_bytes[start_byte] = [ consumer ]
        return start_bytes
    
    def __read(self):
        """ Code for the background read thread: reads from the serial port, checks if
        consumers for incoming bytes, if not: put in pass through buffer.
        """
        def consumer_done(consumer):
            """ Callback for when consumer is done. ReadState does not access parent directly. """
            if isinstance(consumer, Consumer):
                self.__consumers.remove(consumer)
        
        class ReadState:
            """" The read state keeps track of the current consumer and the partial result
            for that consumer. """
            def __init__(self):
                self.current_consumer = None
                self.partial_result = None
            
            def should_resume(self):
                """ Checks whether we should resume consuming data with the current_consumer. """
                return self.current_consumer != None
            
            def should_find_consumer(self):
                """ Checks whether we should find a new consumer. """
                return self.current_consumer == None
            
            def set_consumer(self, consumer):
                """ Set a new consumer. """
                self.current_consumer = consumer
                self.partial_result = None
            
            def consume(self, data):
                """ Consume the bytes in data using the current_consumer, and return the bytes
                that were not used. """
                try:
                    (bytes_consumed, result, done) = \
                        read_state.current_consumer.consume(data, read_state.partial_result)
                except ValueError, value_error:
                    sys.stderr.write("Got ValueError: " + str(value_error))
                    return ""
                else:
                    if done:
                        consumer_done(self.current_consumer)
                        self.current_consumer.deliver(result)
                        
                        self.current_consumer = None
                        self.partial_result = None
                        
                        return data[bytes_consumed:]
                    else:
                        self.partial_result = result
                        return ""
        
        read_state = ReadState()
        data = ""
        
        while not self.__stop:
            data += self.__serial.read(1)
            num_bytes = self.__serial.inWaiting()
            if num_bytes > 0:
                data += self.__serial.read(num_bytes)
            if data != None and len(data) > 0:
                self.__serial_bytes_read += (1 + num_bytes)
                
                if self.__verbose:
                    print "%.3f read from serial: %s" % (time.time(), printable(data))
                
                if read_state.should_resume():
                    data = read_state.consume(data)
                
                # No else here: data might not be empty when current_consumer is done
                if read_state.should_find_consumer():
                    start_bytes = self.__get_start_bytes()
                    leftovers = "" # for unconsumed bytes; these will go to the passthrough.
                    
                    while len(data) > 0:
                        if data[0] in start_bytes:
                            # Prefixes are 3 bytes, make sure we have enough data to match 
                            if len(data) >= 3:
                                match = False
                                for consumer in start_bytes[data[0]]:
                                    if data[:3] == consumer.get_prefix():
                                        # Found matching consumer
                                        read_state.set_consumer(consumer)
                                        data = read_state.consume(data[3:]) # Strip off prefix
                                        # Consumers might have changed, update start_bytes
                                        start_bytes = self.__get_start_bytes()
                                        match = True
                                        break
                                if match:
                                    continue
                            else:
                                # All commands end with '\r\n', there are no prefixes that start
                                # with \r\n so the last bytes of a command will not get stuck
                                # waiting for the next serial.read()
                                break
                        
                        leftovers += data[0]
                        data = data[1:]
                    
                    if len(leftovers) > 0:
                        if not self.__maintenance_mode:
                            self.__passthrough_queue.put(leftovers)
                        else:
                            self.__maintenance_queue.put(leftovers)                    


class CommunicationTimedOutException(Exception):
    """ An exception that is raised when the master did not respond in time. """
    def __init__(self):
        Exception.__init__(self)

class InMaintenanceModeException(Exception):
    """ An excpetion that is raised when the master is in maintenance mode. """
    def __init__(self):
        Exception.__init__(self)

class Consumer:
    """ A consumer is registered to the read thread before a command is issued.  If an output 
    matches the consumer, the output will unblock the get() caller. """
    
    def __init__(self, cmd, cid):
        self.cmd = cmd
        self.cid = cid
        self.__queue = Queue()
    
    def get_prefix(self):
        """ Get the prefix of the answer from the master. """
        return self.cmd.action + str(chr(self.cid))
    
    def consume(self, data, partial_result):
        """ Consume data. """
        return self.cmd.consume_output(data, partial_result)
    
    def get(self, timeout):
        """ Wait until the master replies or the timeout expires.
        
        :param timeout: timeout in seconds
        :raises: :class`CommunicationTimeOutException` if master did not respond in time
        :returns: dict containing the output fields of the command
        """
        try:
            return self.__queue.get(timeout=timeout)
        except Empty:
            raise CommunicationTimedOutException()
    
    def deliver(self, output):
        """ Deliver output to the thread waiting on get(). """
        self.__queue.put(output)


class BackgroundConsumer:
    """ A consumer that runs in the background. The BackgroundConsumer does not provide get()
    but does a callback to a function whenever a message was consumed. 
    """
    
    def __init__(self, cmd, cid, callback):
        """ Create a background consumer using a cmd, cid and callback.
        
        :param cmd: the MasterCommand to consume.
        :param cid: the communication id.
        :param callback: function to call when an instance was found.
        """ 
        self.cmd = cmd
        self.cid = cid
        self.callback = callback
    
    def get_prefix(self):
        """ Get the prefix of the answer from the master. """
        return self.cmd.action + str(chr(self.cid))
    
    def consume(self, data, partial_result):
        """ Consume data. """
        return self.cmd.consume_output(data, partial_result)
    
    def deliver(self, output):
        """ Deliver output to the thread waiting on get(). """
        self.callback(output)

