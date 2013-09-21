'''
Contains controller from reading and writing to the Master EEPROM.

Created on Sep 2, 2013

@author: fryckbos
'''
import inspect
import types

from master_api import eeprom_list, write_eeprom


class EepromController:
    """ The controller takes EepromModels and reads or writes them from and to an EepromFile. """
    
    def __init__(self, eeprom_file):
        """ Constructor takes the eeprom_file for reading and writes.
        
        :param eeprom_file: instance of EepromFile.
        """
        self.__eeprom_file = eeprom_file
    
    def read(self, eeprom_model, id=None):
        """ Create an instance of an EepromModel by reading it from the EepromFile. The id has to
        be specified if the model has an EepromId field.
        
        :param eeprom_model: EepromModel class 
        :param id: optional parameter (integer)
        """
        eeprom_model.check_id(id)
        
        addresses = eeprom_model.get_addresses(id)
        eeprom_data = self.__eeprom_file.read(addresses)
        
        return eeprom_model.from_eeprom_data(eeprom_data, id)
    
    def read_batch(self, eeprom_model, ids):
        """ Create a list of instances of an EepromModel by reading it from the EepromFile.
        
        :param eeprom_model: EepromModel class
        :param id: list of integers
        """
        for id in ids:
            eeprom_model.check_id(id)
        
        addresses = []
        for id in ids:
            addresses.extend(eeprom_model.get_addresses(id))
        
        eeprom_data = self.__eeprom_file.read(addresses)
        
        i = 0
        out = []
        
        for id in ids:
            length = len(eeprom_model.get_addresses(id))
            out.append(eeprom_model.from_eeprom_data(eeprom_data[i:i+length], id))
            i += length
        
        return out
    
    def read_all(self, eeprom_model):
        """ Create a list of instance of an EepromModel by reading all ids of that model from the
        EepromFile. Only applicable for EepromModels with an EepromId.
        
        :type eeprom_model: EepromModel class
        """
        return self.read_batch(eeprom_model, range(self.get_max_id(eeprom_model)))
    
    def write(self, eeprom_model):
        """ Write a given EepromModel to the EepromFile.
        
        :param eeprom_model: instance of EepromModel.
        """
        eeprom_data = eeprom_model.to_eeprom_data()
        self.__eeprom_file.write(eeprom_data)
    
    def write_batch(self, eeprom_models):
        """ Write a list of EepromModel instances to the EepromFile.
        
        :param eeprom_models: list of EepromModel instances.
        """
        eeprom_data = []
        for eeprom_model in eeprom_models:
            eeprom_data.extend(eeprom_model.to_eeprom_data())

        self.__eeprom_file.write(eeprom_data)
    
    def get_max_id(self, eeprom_model):
        """ Get the maximum id for an eeprom_model.
        
        :param eeprom_mode: instance of EepromModel.
        """
        if not eeprom_model.has_id():
            raise TypeError("EepromModel %s does not contain an id" % eeprom_model.get_name())
        else:
            eeprom_id = eeprom_model.__dict__[eeprom_model.get_id_field()]
            
            if not eeprom_id.has_address():
                return eeprom_id.get_max_id()
            else:
                address = eeprom_id.get_address()
                if address.length != 1:
                    raise TypeError("Length of max id address in EepromModel %s is not 1" % eeprom_model.get_name())
                
                eeprom_data = self.__eeprom_file.read([ address ])
                max_id = ord(eeprom_data[0].bytes[0])
                
                return max_id * eeprom_id.get_multiplier()    


class EepromFile:
    """ Reads from and writes to the Master EEPROM. """
    
    BATCH_SIZE = 10
    
    def __init__(self, master_communicator):
        """ Create an EepromFile.
        
        :param master_communicator: communicates with the master.
        :type master_communicator: instance of MasterCommunicator.
        """
        self.__master_communicator = master_communicator
    
    def read(self, addresses):
        """ Read data from the Eeprom.
        
        :param addresses: the addresses to read.
        :type addresses: list of EepromAddress instances.
        :returns: a list of EepromData instances (in the same order as the provided addresses).
        """
        bank_data = self.__read_banks(set([ a.bank for a in addresses ]))
        
        return [ EepromData(a, bank_data[a.bank][a.offset : a.offset + a.length]) 
                 for a in addresses ]
        
    def __read_banks(self, banks):
        """ Read a number of banks from the Eeprom.
        
        :param banks: a list of banks (integers).
        :returns: a dict mapping the bank to the data.
        """
        ret = dict()
        
        for bank in banks:
            output = self.__master_communicator.do_command(eeprom_list(), { "bank" : bank })
            ret[bank] = output['data']
        
        return ret
        
    
    def write(self, data):
        """ Write data to the Eeprom.
        
        :param data: the data to write.
        :type data: list of EepromData instances.
        """
        # Read the data in the banks that we are trying to write
        bank_data = self.__read_banks(set([ d.address.bank for d in data ]))
        new_bank_data = bank_data.copy()
        
        for d in data:
            self.__patch(new_bank_data, d)
        
        # Check what changed and write changes in batch
        for bank in bank_data.keys():
            old = bank_data[bank]
            new = new_bank_data[bank]
            
            i = 0
            while i < len(bank_data[bank]):
                if old[i] != new[i]:
                    length = 1
                    j = 1
                    while j < EepromFile.BATCH_SIZE:
                        if old[i+j] != new[i+j]:
                            length = j + 1
                        j += 1
                    
                    self.__write(bank, i, new[i:i+length])
                    i += EepromFile.BATCH_SIZE
                else:
                    i += 1
    
    def __patch(self, bank_data, eeprom_data):
        """ Patch a byte array with a eeprom_data.
        
        :param bank_data: dict with bank data, key = bank, data = bytes in the bank.
        :param eeprom_data: instance of EepromData.
        """
        a = eeprom_data.address
        d = bank_data[a.bank]
        bank_data[a.bank] = d[0:a.offset] + eeprom_data.bytes + d[a.offset+a.length:]
    
    def __write(self, bank, offset, to_write):
        """ Write a byte array to a specific location defined by the bank and the offset. """
        self.__master_communicator.do_command(
                write_eeprom(), { "bank" : bank, "address": offset, "data": to_write })


class EepromAddress:
    """ Represents an address in the Eeprom, has a bank, an offset and a length. """

    def __init__(self, bank, offset, length): 
        self.bank = bank
        self.offset = offset
        self.length = length

    def __eq__(self, other):
        return self.bank == other.bank and self.offset == other.offset and self.length == other.length

    def __hash__(self):
        return self.bank + self.offset * 256 + self.length * 256 * 256

    def __str__(self):
        return "(B%d A%d L%d)" % (self.bank, self.offset, self.length)

    def __repr__(self):
        return self.__str__()


class EepromData:
    """ A piece of Eeprom data, has an address and the actual data. """

    def __init__(self, address, bytes):
        if address.length != len(bytes):
            raise TypeError("Length in the address (%d) does not match the number of bytes (%d)" %
                            (address.length, len(bytes)))
        
        self.address = address
        self.bytes = bytes

    def __str__(self):
        hex = " ".join(['%3d' % ord(c) for c in self.bytes])
        readable = "".join([c if ord(c) > 32 and ord(c) <= 126 else '.' for c in self.bytes])
        return "%s : %s | %s" % (self.address, hex, readable)

    def __repr__(self):
        return self.__str__()


class EepromModel:
    """ The EepromModel provides a generic way to model data in the eeprom by creating a child
    class of EepromModel with an optional EepromId and EepromDataTypes as class fields.
    """

    def __init__(self, **kwargs):
        """ The arguments to the constructor are defined by the EepromDataType class fields. """
        fields = map(lambda x: x[0], self.__class__.get_fields(include_id=True))

        for (field, value) in kwargs.items():
            if field in fields:
                self.__dict__[field] = value
                fields.remove(field)
            else:
                raise TypeError("Field %s is unknown for %s" % (field, self.__class__.__name__))

        if len(fields) > 0:
            fields = ",".join(fields)
            raise TypeError("Fields %s were not present for %s" % (fields, self.__class__.__name__))

    @classmethod
    def get_fields(cls, include_id=False):
        """ Get the fields defined by an EepromModel child. """
        return inspect.getmembers(cls, lambda x: isinstance(x, EepromDataType) or (include_id and isinstance(x, EepromId)))

    @classmethod
    def get_id_field(cls):
        """ Get the name of the EepromId field. None if not included. """
        if cls.has_id():
            ids = inspect.getmembers(cls, lambda x: isinstance(x, EepromId))
            return ids[0][0]
        else:
            return None

    @classmethod
    def has_id(cls):
        """ Check if the EepromModel has an id. """
        ids = inspect.getmembers(cls, lambda x: isinstance(x, EepromId))
        if len(ids) == 0:
            return False
        elif len(ids) == 1:
            return True
        else:
            raise TypeError("Found more than 1 EepromId for %s" % cls.__name__)

    @classmethod
    def get_name(cls):
        """ Get the name of the EepromModel. """
        return cls.__name__

    @classmethod
    def check_id(cls, id):
        """ Check if the id is valid for this EepromModel. """
        has_id = cls.has_id()

        if id is None and has_id:
            raise TypeError("%s has an id, but no id was given." % cls.__name__)
        elif id is not None and not has_id:
            raise TypeError("%s doesn't have an id, but id was given." % cls.__name__)
        elif id is not None:
            id_type = inspect.getmembers(cls, lambda x: isinstance(x, EepromId))
            max_id = id_type[0][1].get_max_id()

            if id > max_id:
                raise TypeError("The maximum id for %s is %d, %d was provided." % (cls.__name__, max_id, id))

    def to_dict(self):
        """ Create a model dict from the EepromModel. """
        out = dict()

        for (field_name, _) in self.__class__.get_fields(include_id=True):
            out[field_name] = self.__dict__[field_name]

        return out

    @classmethod
    def from_dict(cls, in_dict):
        """ Create an EepromModel from a dict. """
        fields = dict()

        for (field_name, _) in cls.get_fields(include_id=True):
            fields[field_name] = in_dict[field_name]

        return cls(**fields)

    def to_eeprom_data(self):
        """ Create EepromData from the EepromModel. """
        data = []

        id_field = self.__class__.get_id_field()
        id = None if id_field is None else self.__dict__[id_field]

        for (field_name, field_type) in self.__class__.get_fields():
            address = field_type.get_address(id)
            bytes = field_type.to_bytes(self.__dict__[field_name])

            data.append(EepromData(address, bytes))

        return data

    @classmethod
    def from_eeprom_data(cls, data, id=None):
        """ Create an EepromModel from EepromData. """
        cls.check_id(id)

        # Put the data in a dict by address
        data_dict = dict()
        for d in data:
            data_dict[d.address] = d

        fields = dict()

        for (field_name, field_type) in cls.get_fields():
            address = field_type.get_address(id)
            bytes = data_dict[address].bytes
            fields[field_name] = field_type.from_bytes(bytes)

        if id is not None:
            fields[cls.get_id_field()] = id

        return cls(**fields)

    @classmethod
    def get_addresses(cls, id=None):
        """ Get the addresses used by this EepromModel. """
        cls.check_id(id)

        addresses = []

        for (_, field_type) in cls.get_fields():
            addresses.append(field_type.get_address(id))

        return addresses

class EepromId:
    """ Represents an id in an EepromModel. """

    def __init__(self, max_id, address=None, multiplier=None):
        """ Constructor.
        
        @param max_id: the static maximum for the id.
        @type max_id: Integer.
        @param address: the EepromAddress where the dynamic maximum for the id is located.
        @type address: EepromAddress.
        @param multiplier: if an address is provided, the multiplier can be used to multiply the
        value located at that address.
        @type multiplier: Integer.
        """
        self.__max_id = max_id
        self.__address = address
        if multiplier is not None and self.__address is None:
            raise TypeError("A multiplier was specified without an address")
        else:
            self.__multiplier = multiplier if multiplier != None else 1
    
    def get_max_id(self):
        """ Get the static maximum id. """
        return self.__max_id
    
    def has_address(self):
        """ Check if the EepromId has a dynamic maximum. """
        return self.__address is not None
    
    def get_address(self):
        """ Get the EepromAddress. """
        return self.__address
    
    def get_multiplier(self):
        """ Return the multiplier for the Eeprom value (at the defined EepromAddress). """
        return self.__multiplier


class EepromDataType:
    """ Defines a data type in an EepromModel, and provides functions to_bytes and from_bytes to
    convert this data type from and to a string of bytes.  Besides these functions, the data type
    also contains the address, or the address generator (in case the model has an id).
    """

    def __init__(self, addr_gen):
        """ Create an instance of an EepromDataType with an address or an address generator. 
        The address is a tuple of (bank, offset).
        The address generator is a function that takes an id (integer).
        """
        self.__addr_tuple = None
        self.__addr_func = None

        if isinstance(addr_gen, types.TupleType):
            self.__addr_tuple = addr_gen
        elif isinstance(addr_gen, types.FunctionType):
            args = inspect.getargspec(addr_gen).args
            if len(args) == 1:
                self.__addr_func = addr_gen
            else:
                raise TypeError("addr_gen should be a function that takes an id and returns the same tuple.")
        else:
            raise TypeError("addr_gen should be a tuple (bank, address) or a function that takes an id and returns the same tuple.")

    def get_address(self, id=None):
        """ Calculate the address for this data type. """
        length = self.get_length()

        if id is None:
            if self.__addr_tuple is not None:
                (bank, address) = self.__addr_tuple
            else:
                raise TypeError("EepromDataType expects an id")
        else:
            if self.__addr_func is not None:
                (bank, address) = self.__addr_func(id)
            else:
                raise TypeError("EepromDataType did not expect an id")

        return EepromAddress(bank, address, length)

    def get_name(self):
        """ Get the name of the EepromDataType. To be implemented in the subclass. """
        raise NotImplementedError()

    def from_bytes(self, bytes):
        """ Convert a string of bytes to the desired type. To be implemented in the subclass. """
        raise NotImplementedError()

    def to_bytes(self, field):
        """ Convert the field data to a string of bytes. To be implemented in the subclass. """
        raise NotImplementedError()

    def get_length(self):
        """ Get the length of the data type. """
        raise NotImplementedError()


def removeTail(byte_str, delimiter='\xff'):
    index = byte_str.rfind(delimiter)
    while index > 0:
        byte_str = byte_str[:index]
        index = byte_str.rfind(delimiter)

    if index == -1:
        return byte_str
    else:
        return byte_str[:index]


def appendTail(byte_str, length, delimiter='\xff'):
    if len(byte_str) < length:
        return str(byte_str) + delimiter * ((length - len(byte_str)) / len(delimiter))
    else:
        return str(byte_str)


class EepromString(EepromDataType):
    """ A string with a given length. """

    def __init__(self, length, addr_gen):
        EepromDataType.__init__(self, addr_gen)
        self.__length = length

    def get_name(self):
        return "String(%d)" % self.__length

    def from_bytes(self, bytes):
        return str(removeTail(bytes))

    def to_bytes(self, field):
        return appendTail(field, self.__length)

    def get_length(self):
        return self.__length


class EepromByte(EepromDataType):
    """ A byte. """

    def __init__(self, addr_gen):
        EepromDataType.__init__(self, addr_gen)

    def get_name(self):
        return "Byte"

    def from_bytes(self, bytes):
        return ord(bytes[0])

    def to_bytes(self, field):
        return str(chr(field))

    def get_length(self):
        return 1


class EepromWord(EepromDataType):
    """ A word (2 bytes, converted to an integer). """

    def __init__(self, addr_gen):
        EepromDataType.__init__(self, addr_gen)

    def get_name(self):
        return "Word"

    def from_bytes(self, bytes):
        return ord(bytes[0]) * 256 + ord(bytes[1])

    def to_bytes(self, field):
        return "".join([chr(int(field) / 256), chr(int(field) % 256)])

    def get_length(self):
        return 2


class EepromTemp(EepromDataType):
    """ A temperature (1 byte, converted to a float). """

    def __init__(self, addr_gen):
        EepromDataType.__init__(self, addr_gen)

    def get_name(self):
        return "Temp"

    def from_bytes(self, bytes):
        return float(ord(bytes[0])) / 2 - 32

    def to_bytes(self, field):
        return str(chr(int((float(field) + 32) * 2)))

    def get_length(self):
        return 1


class EepromActions(EepromDataType):
    """ A list of basic actions with a given length (2 bytes each, converted to a string of comma
    separated integers).
    """

    def __init__(self, length, addr_gen):
        EepromDataType.__init__(self, addr_gen)
        self.__length = length

    def get_name(self):
        return "Actions(%d)" % self.__length

    def from_bytes(self, bytes):
        return ",".join(map(lambda b: str(ord(b)), removeTail(bytes, '\xff\xff')))

    def to_bytes(self, field):
        actions = "" if len(field) == 0 else "".join(map(lambda x: chr(int(x)), field.split(",")))
        return appendTail(actions, 2 * self.__length, '\xff\xff')

    def get_length(self):
        return 2 * self.__length

