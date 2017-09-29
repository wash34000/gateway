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
Contains controller from reading and writing to the Master EEPROM.
"""

import inspect
import types

from master_api import eeprom_list, write_eeprom, activate_eeprom


class EepromController(object):
    """ The controller takes EepromModels and reads or writes them from and to an EepromFile. """

    def __init__(self, eeprom_file, eeprom_extension):
        """
        Constructor takes the eeprom_file (for reading and writes from the eeprom) and the
        eeprom_extension (for reading the extensions from sqlite).

        :type eeprom_file: master.eeprom_controller.EepromFile
        :type eeprom_extension: master.eeprom_extension.EepromExtension
        """
        self.__eeprom_file = eeprom_file
        self.__eeprom_extension = eeprom_extension

    def invalidate_cache(self):
        """ Invalidate the cache, this should happen when maintenance mode was used. """
        self.__eeprom_file.invalidate_cache()

    def read(self, eeprom_model, id=None, fields=None):
        """
        Create an instance of an EepromModel by reading it from the EepromFile. The id has to
        be specified if the model has an EepromId field.
        """
        eeprom_model.check_id(id)

        addresses = eeprom_model.get_addresses(id, fields)
        eeprom_data = self.__eeprom_file.read(addresses)

        field_dict = eeprom_model.from_eeprom_data(eeprom_data, id, fields)
        field_dict.update(self.__eeprom_extension.read_model(eeprom_model, id, fields))
        return eeprom_model(**field_dict)

    def read_batch(self, eeprom_model, ids, fields=None):
        """ Create a list of instances of an EepromModel by reading it from the EepromFile. """
        for id in ids:
            eeprom_model.check_id(id)

        addresses = []
        for id in ids:
            addresses.extend(eeprom_model.get_addresses(id, fields))

        eeprom_data = self.__eeprom_file.read(addresses)

        i = 0
        out = []

        for id in ids:
            length = len(eeprom_model.get_addresses(id, fields))
            field_dict = eeprom_model.from_eeprom_data(eeprom_data[i:i + length], id, fields)
            field_dict.update(self.__eeprom_extension.read_model(eeprom_model, id, fields))
            out.append(eeprom_model(**field_dict))
            i += length

        return out

    def read_all(self, eeprom_model, fields=None):
        """
        Create a list of instance of an EepromModel by reading all ids of that model from the
        EepromFile. Only applicable for EepromModels with an EepromId.
        """
        return self.read_batch(eeprom_model, range(self.get_max_id(eeprom_model)), fields)

    def write(self, eeprom_model):
        """
        Write a given EepromModel to the EepromFile.

        :type eeprom_model: master.eeprom_controller.EepromModel
        """
        return self.write_batch([eeprom_model])

    def write_batch(self, eeprom_models):
        """
        Write a list of EepromModel instances to the EepromFile.

        :type eeprom_models: list of master.eeprom_controller.EepromModel
        """
        # Write to the eeprom
        eeprom_data = []
        for eeprom_model in eeprom_models:
            eeprom_data.extend(eeprom_model.to_eeprom_data())

        if len(eeprom_data) > 0:
            self.__eeprom_file.write(eeprom_data)
            self.__eeprom_file.activate()

        # Write the extensions
        for eeprom_model in eeprom_models:
            self.__eeprom_extension.write_model(eeprom_model)

    def get_max_id(self, eeprom_model):
        """
        Get the maximum id for an eeprom_model.

        :type eeprom_model: master.eeprom_controller.EepromModel
        """
        if not eeprom_model.has_id():
            raise TypeError('EepromModel {0} does not contain an id'.format(eeprom_model.get_name()))
        else:
            eeprom_id = eeprom_model.__dict__[eeprom_model.get_id_field()]

            if not eeprom_id.has_address():
                return eeprom_id.get_max_id()
            else:
                address = eeprom_id.get_address()
                if address.length != 1:
                    raise TypeError('Length of max id address in EepromModel {0} is not 1'.format(eeprom_model.get_name()))

                eeprom_data = self.__eeprom_file.read([address])
                max_id = ord(eeprom_data[0].bytes[0])

                return max_id * eeprom_id.get_multiplier()


class EepromFile(object):
    """ Reads from and writes to the Master EEPROM. """

    BATCH_SIZE = 10

    def __init__(self, master_communicator):
        """
        Create an EepromFile.

        :param master_communicator: communicates with the master.
        :type master_communicator: master.master_communicator.MasterCommunicator
        """
        self.__master_communicator = master_communicator
        self.__bank_cache = {}

    def invalidate_cache(self):
        """ Invalidate the cache, this should happen when maintenance mode was used. """
        self.__bank_cache = {}

    def activate(self):
        """
        Activate a change in the Eeprom. The master will read the eeprom
        and adjust the current settings.
        """
        self.__master_communicator.do_command(activate_eeprom(), {'eep': 0})

    def read(self, addresses):
        """
        Read data from the Eeprom.

        :param addresses: the addresses to read.
        :type addresses: list of master.eeprom_controller.EepromAddress
        :returns: list of master.eeprom_controller.EepromData
        """
        bank_data = self.__read_banks({a.bank for a in addresses})
        return [EepromData(a, bank_data[a.bank][a.offset:a.offset + a.length]) for a in addresses]

    def __read_banks(self, banks):
        """
        Read a number of banks from the Eeprom.

        :param banks: a list of banks (integers).
        :returns: a dict mapping the bank to the data.
        """
        try:
            return_data = {}
            for bank in banks:
                if bank in self.__bank_cache:
                    data = self.__bank_cache[bank]
                else:
                    output = self.__master_communicator.do_command(eeprom_list(), {'bank': bank})
                    data = output['data']
                    self.__bank_cache[bank] = data
                return_data[bank] = data
            return return_data
        except Exception:
            # Failure reading, cache might be invalid
            self.invalidate_cache()
            raise

    def write(self, data):
        """
        Write data to the Eeprom.

        :param data: the data to write.
        :type data: list of master.eeprom_controller.EepromData
        """
        # Read the data in the banks that we are trying to write
        bank_data = self.__read_banks({d.address.bank for d in data})
        new_bank_data = bank_data.copy()

        for data_item in data:
            address = data_item.address
            data = new_bank_data[address.bank]
            new_bank_data[address.bank] = data[0:address.offset] + data_item.bytes + data[address.offset + address.length:]

        # Check what changed and write changes in batch
        try:
            for bank in bank_data.keys():
                old = bank_data[bank]
                new = new_bank_data[bank]

                i = 0
                while i < len(bank_data[bank]):
                    if old[i] != new[i]:
                        length = 1
                        j = 1
                        while j < EepromFile.BATCH_SIZE and i + j < len(old):
                            if old[i + j] != new[i + j]:
                                length = j + 1
                            j += 1

                        self.__write(bank, i, new[i:i + length])
                        i += EepromFile.BATCH_SIZE
                    else:
                        i += 1

                self.__bank_cache[bank] = new
        except Exception:
            # Failure reading, cache might be invalid
            self.invalidate_cache()
            raise

    def __write(self, bank, offset, to_write):
        """ Write a byte array to a specific location defined by the bank and the offset. """
        self.__master_communicator.do_command(
            write_eeprom(), {'bank': bank, 'address': offset, 'data': to_write}
        )


class EepromAddress(object):
    """ Represents an address in the Eeprom, has a bank, an offset and a length. """

    def __init__(self, bank, offset, length, shared=False, name=None):
        self.bank = bank
        self.offset = offset
        self.length = length
        self.shared = shared
        self.name = name

    def __eq__(self, other):
        return self.bank == other.bank \
               and self.offset == other.offset \
               and self.length == other.length

    def __hash__(self):
        return self.bank + self.offset * 256 + self.length * 256 * 256

    def __str__(self):
        return '(B{0} A{1} L{2})'.format(self.bank, self.offset, self.length)

    def __repr__(self):
        return self.__str__()


class EepromData(object):
    """ A piece of Eeprom data, has an address and the actual data. """

    def __init__(self, address, data):
        """
        :type address: master.eeprom_controller.EepromAddress
        :type data: basestring
        """
        if address.length != len(data):
            raise TypeError('Length in the address ({0}) does not match the number of bytes ({1})'.format(address.length, len(data)))

        self.address = address
        self.bytes = data

    def __str__(self):
        hex_data = ' '.join(['%3d' % ord(c) for c in self.bytes])
        readable = ''.join([c if 32 < ord(c) <= 126 else '.' for c in self.bytes])
        return '{0}: {1} | {2}'.format(self.address, hex_data, readable)

    def __repr__(self):
        return self.__str__()


class EepromModel(object):
    """
    The EepromModel provides a generic way to model data in the eeprom by creating a child
    class of EepromModel with an optional EepromId and EepromDataTypes as class fields.
    """

    def __init__(self, **kwargs):
        """ The arguments to the constructor are defined by the EepromDataType class fields. """
        fields = [x[0] for x in self.__class__.get_fields(include_id=True,
                                                          include_eeprom=True,
                                                          include_eext=True)]

        for (field, value) in kwargs.items():
            if field in fields:
                self.__dict__[field] = value
            else:
                raise TypeError('Field {0} is unknown for {1}'.format(field, self.__class__.__name__))

        id_field_name = self.__class__.get_id_field()
        if id_field_name is not None and id_field_name not in kwargs:
            raise TypeError('The id was missing for {0}'.format(self.__class__.__name__))

    def get_id(self):
        """ Create EepromData from the EepromModel. """
        id_field = self.__class__.get_id_field()
        return None if id_field is None else self.__dict__[id_field]

    @classmethod
    def get_fields(cls, include_id=False, include_eeprom=False, include_eext=False):
        """ Get the fields defined by an EepromModel child. """
        def include(field):
            if isinstance(field, EepromId) and include_id:
                return True
            elif (isinstance(field, EepromDataType) or isinstance(field, CompositeDataType)) and include_eeprom:
                return True
            elif isinstance(field, EextDataType) and include_eext:
                return True
            else:
                return False

        return inspect.getmembers(cls, include)

    @classmethod
    def get_field_dict(cls, include_id=False, include_eeprom=False, include_eext=False):
        """ Get a dict from the field name to the field type for each field defined by the
        EepromModel child.
        """
        class_field_dict = {}
        for (name, field_type) in cls.get_fields(include_id, include_eeprom, include_eext):
            class_field_dict[name] = field_type

        return class_field_dict

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
            raise TypeError('Found more than 1 EepromId for {0}'.format(cls.__name__))

    @classmethod
    def get_name(cls):
        """ Get the name of the EepromModel. """
        return cls.__name__

    @classmethod
    def check_id(cls, id):
        """ Check if the id is valid for this EepromModel. """
        has_id = cls.has_id()

        if id is None and has_id:
            raise TypeError('{0} has an id, but no id was given.'.format(cls.__name__))
        elif id is not None and not has_id:
            raise TypeError('{0} doesn\'t have an id, but id was given.'.format(cls.__name__))
        elif id is not None:
            id_type = inspect.getmembers(cls, lambda x: isinstance(x, EepromId))
            max_id = id_type[0][1].get_max_id()

            if id > max_id:
                raise TypeError('The maximum id for {0} is {1}, {2} was provided.'.format(cls.__name__, max_id, id))

    def to_dict(self):
        """ Create a model dict from the EepromModel. """
        out = dict()
        fields = self.__class__.get_fields(include_id=True, include_eeprom=True, include_eext=True)

        for (field_name, _) in fields:
            if field_name in self.__dict__:
                out[field_name] = self.__dict__[field_name]

        return out

    @classmethod
    def from_dict(cls, in_dict):
        """ Create an EepromModel from a dict. """
        return cls(**in_dict)

    def to_eeprom_data(self):
        """ Create EepromData from the EepromModel. """
        data = []
        id = self.get_id()

        for (field_name, field_type) in self.__class__.get_fields(include_eeprom=True):
            if field_name in self.__dict__ and field_type.is_writable():
                if isinstance(field_type, CompositeDataType):
                    data.extend(field_type.to_eeprom_data(self.__dict__[field_name], id))
                else:
                    address = field_type.get_address(id)
                    field_bytes = field_type.to_bytes(self.__dict__[field_name])
                    data.append(EepromData(address, field_bytes))

        return data

    @classmethod
    def from_eeprom_data(cls, data, id=None, fields=None):
        """ Create an EepromModel from EepromData. """
        cls.check_id(id)

        # Put the data in a dict by address
        data_dict = dict()
        for d in data:
            data_dict[d.address] = d

        field_dict = dict()

        if fields is None:
            # Add data for all fields.
            for (field_name, field_type) in cls.get_fields(include_eeprom=True):
                if isinstance(field_type, CompositeDataType):
                    field_dict[field_name] = field_type.from_data_dict(data_dict, id)
                else:
                    address = field_type.get_address(id)
                    field_bytes = data_dict[address].bytes
                    field_dict[field_name] = field_type.from_bytes(field_bytes)
        else:
            # Add data for given fields only.
            class_field_dict = cls.get_field_dict(include_eeprom=True)
            for field_name in fields:
                if field_name not in class_field_dict:
                    raise TypeError('Field {0} is unknown for {1}'.format(field_name, cls.__name__))
                else:
                    field_type = class_field_dict[field_name]
                    if isinstance(field_type, CompositeDataType):
                        field_dict[field_name] = field_type.from_data_dict(data_dict, id)
                    else:
                        address = field_type.get_address(id)
                        field_bytes = data_dict[address].bytes
                        field_dict[field_name] = field_type.from_bytes(field_bytes)

        if id is not None:
            field_dict[cls.get_id_field()] = id

        return field_dict

    @classmethod
    def get_addresses(cls, id=None, fields=None):
        """ Get the addresses used by this EepromModel. """
        cls.check_id(id)
        addresses = []

        if fields is None:
            # Add addresses for all fields.
            for (field, field_type) in cls.get_fields(include_eeprom=True):
                if isinstance(field_type, CompositeDataType):
                    addresses.extend(field_type.get_addresses(id, field))
                else:
                    addresses.append(field_type.get_address(id, field))

        else:
            # Add addresses for given fields only.
            class_field_dict = cls.get_field_dict(include_eeprom=True)

            for field in fields:
                if field not in class_field_dict:
                    raise TypeError('Field {0} is unknown for {1}'.format(field, cls.__name__))
                else:
                    field_type = class_field_dict[field]
                    if isinstance(field_type, CompositeDataType):
                        addresses.extend(field_type.get_addresses(id, field))
                    else:
                        addresses.append(field_type.get_address(id, field))

        return addresses


class EepromId(object):
    """ Represents an id in an EepromModel. """

    def __init__(self, amount_of_modules, address=None, multiplier=None):
        """ Constructor.

        @param amount_of_modules: The amount of modules
        @type amount_of_modules: Integer.
        @param address: the EepromAddress where the dynamic maximum for the id is located.
        @type address: EepromAddress.
        @param multiplier: if an address is provided, the multiplier can be used to multiply the
        value located at that address.
        @type multiplier: Integer.
        """
        self.__max_id = amount_of_modules - 1
        self.__address = address
        if multiplier is not None and self.__address is None:
            raise TypeError('A multiplier was specified without an address')
        else:
            self.__multiplier = multiplier if multiplier is not None else 1

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


class CompositeDataType(object):
    """ Defines a composite data type in an EepromModel, the composite structure contains multiple
    EepromDataTypes and defines a name for each child data type.
    """

    def __init__(self, eeprom_data_types, read_only=False):
        """Create a new composite data type using a list of tuples (name, EepromDataType). """
        self.__eeprom_data_types = eeprom_data_types
        self.__read_only = read_only

    def get_addresses(self, id=None, field_name=None):
        """ Get all EepromDataType addresses in the composite data type. """
        return [t[1].get_address(id, field_name) for t in self.__eeprom_data_types]

    def get_name(self):
        """ Get the name of the EepromDataType. To be implemented in the subclass. """
        return '[{0}]'.format(','.join(['{0}({1})'.format(t[0], t[1].get_name()) for t in self.__eeprom_data_types]))

    def from_data_dict(self, data_dict, id=None):
        """ Convert a data_dict (mapping from EepromAddress to EepromData) to a list of fields. """
        out = []

        for _, field_type in self.__eeprom_data_types:
            address = field_type.get_address(id)
            field_bytes = data_dict[address].bytes
            out.append(field_type.from_bytes(field_bytes))

        return out

    def to_eeprom_data(self, fields, id=None):
        """ Convert a list of field data to a list of EepromData objects. """
        if len(fields) != len(self.__eeprom_data_types):
            raise TypeError('The length of the composite data does not match the type: got {0} for {1}.'.format(fields, self.get_name()))

        out = []

        for i in range(len(fields)):
            field_type = self.__eeprom_data_types[i][1]
            address = field_type.get_address(id)
            field_bytes = field_type.to_bytes(fields[i])
            out.append(EepromData(address, field_bytes))

        return out

    def is_writable(self):
        """ Returns whether the CompositeDataType is writable. """
        return not self.__read_only


class EepromDataType(object):
    """ Defines a data type in an EepromModel, and provides functions to_bytes and from_bytes to
    convert this data type from and to a string of bytes.  Besides these functions, the data type
    also contains the address, or the address generator (in case the model has an id).
    """

    def __init__(self, addr_gen, read_only=False, shared=False):
        """
        Create an instance of an EepromDataType with an address or an address generator.
        The address is a tuple of (bank, offset).
        The address generator is a function that takes an id (integer).
        """
        self.__read_only = read_only
        self.__shared = shared
        self.__addr_tuple = None
        self.__addr_func = None

        if isinstance(addr_gen, types.TupleType):
            self.__addr_tuple = addr_gen
        elif isinstance(addr_gen, types.FunctionType):
            args = inspect.getargspec(addr_gen).args
            if len(args) == 1:
                self.__addr_func = addr_gen
            else:
                raise TypeError('addr_gen should be a function that takes an id and returns the same tuple.')
        else:
            raise TypeError('addr_gen should be a tuple (bank, address) or a function that takes an id and returns the same tuple.')

    def is_writable(self):
        """ Returns whether the EepromDataType is writable. """
        return not self.__read_only

    def check_writable(self):
        """ Raises a TypeError if the EepromDataType is not writable. """
        if self.__read_only:
            raise TypeError('EepromDataType is not writable')

    def get_address(self, id=None, field_name=None):
        """ Calculate the address for this data type. """
        length = self.get_length()

        if id is None:
            if self.__addr_tuple is not None:
                (bank, address) = self.__addr_tuple
            else:
                raise TypeError('EepromDataType expects an id')
        else:
            if self.__addr_func is not None:
                (bank, address) = self.__addr_func(id)
            else:
                raise TypeError('EepromDataType did not expect an id')

        return EepromAddress(bank, address, length, self.__shared, field_name)

    def get_name(self):
        """ Get the name of the EepromDataType. To be implemented in the subclass. """
        raise NotImplementedError()

    def from_bytes(self, data):
        """ Convert a string of bytes to the desired type. To be implemented in the subclass. """
        raise NotImplementedError()

    def to_bytes(self, field):
        """ Convert the field data to a string of bytes. To be implemented in the subclass. """
        raise NotImplementedError()

    def get_length(self):
        """ Get the length of the data type. """
        raise NotImplementedError()


def remove_tail(byte_str, delimiter='\xff'):
    """ Returns a new string where all instance of the delimiter at the end of the string are
    removed.
    """
    index = byte_str.rfind(delimiter)
    while index > 0:
        byte_str = byte_str[:index]
        index = byte_str.rfind(delimiter)

    if index == -1:
        return byte_str
    else:
        return byte_str[:index]


def append_tail(byte_str, length, delimiter='\xff'):
    """ Returns a new string with the given length by adding instances of the delimiter at the end
    of the string.
    """
    if len(byte_str) < length:
        return str(byte_str) + delimiter * ((length - len(byte_str)) / len(delimiter))
    else:
        return str(byte_str)


class EepromString(EepromDataType):
    """ A string with a given length. """

    def __init__(self, length, addr_gen, read_only=False, shared=False):
        EepromDataType.__init__(self, addr_gen, read_only, shared)
        self.__length = length

    def get_name(self):
        return 'String[{0}]'.format(self.__length)

    def from_bytes(self, data):
        return str(remove_tail(data))

    def to_bytes(self, field):
        self.check_writable()
        return append_tail(field, self.__length)

    def get_length(self):
        return self.__length


class EepromByte(EepromDataType):
    """ A byte. """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return 'Byte'

    def from_bytes(self, data):
        return ord(data[0])

    def to_bytes(self, field):
        self.check_writable()
        return str(chr(field))

    def get_length(self):
        return 1


class EepromWord(EepromDataType):
    """ A word (2 bytes, converted to an integer). """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return 'Word'

    def from_bytes(self, data):
        return ord(data[1]) * 256 + ord(data[0])

    def to_bytes(self, field):
        self.check_writable()
        return ''.join([chr(int(field) % 256), chr(int(field) / 256)])

    def get_length(self):
        return 2


class EepromTemp(EepromDataType):
    """ A temperature (1 byte, converted to a float). """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return 'Temp'

    def from_bytes(self, data):
        value = ord(data[0])
        if value == 255:
            return None
        return float(value) / 2 - 32

    def to_bytes(self, field):
        self.check_writable()
        if field is None:
            value = 255
        else:
            value = int((float(field) + 32) * 2)
            value = max(min(value, 255), 0)
        return str(chr(value))

    def get_length(self):
        return 1


class EepromSignedTemp(EepromDataType):
    """ A signed temperature (1 byte, converted to a float, from -7.5 to +7.5). """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return 'SignedTemp(-7.5 to 7.5 degrees)'

    def from_bytes(self, data):
        value = ord(data)
        if value == 255:
            return 0.0
        else:
            multiplier = 1 if value & 128 == 0 else -1
            return multiplier * float(value & 15) / 2.0

    def to_bytes(self, field):
        self.check_writable()
        if field < -7.5 or field > 7.5:
            raise ValueError('SignedTemp should be in [-7.5, 7.5], was {0}'.format(field))

        if field == 0.0:
            return str(chr(255))
        else:
            offset = 0 if field > 0 else 128
            value = int(abs(field) * 2)
            return str(chr(offset + value))

    def get_length(self):
        return 1


class EepromTime(EepromDataType):
    """ A time (1 byte, converted into string HH:MM). """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return 'Time'

    def from_bytes(self, data):
        value = ord(data[0])
        hours = value / 6
        minutes = (value % 6) * 10
        return "{0:02d}{1:02d}".format(hours, minutes)

    def to_bytes(self, field):
        self.check_writable()
        split = [int(x) for x in field.split(':')]
        if len(split) != 2:
            raise ValueError('Time is not in HH:MM format: {0}'.format(field))
        field = (split[0] * 6) + (split[1] / 10)
        return str(chr(field))

    def get_length(self):
        return 1


class EepromCSV(EepromDataType):
    """ A list of bytes with a given length (converted to a string of comma separated integers).
    """

    def __init__(self, length, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)
        self.__length = length

    def get_name(self):
        return 'CSV[{0}]'.format(self.__length)

    def from_bytes(self, data):
        return ','.join([str(ord(b)) for b in remove_tail(data, '\xff')])

    def to_bytes(self, field):
        self.check_writable()
        actions = '' if len(field) == 0 else ''.join([chr(int(x)) for x in field.split(",")])
        return append_tail(actions, self.__length, '\xff')

    def get_length(self):
        return self.__length


class EepromActions(EepromDataType):
    """
    A list of basic actions with a given length (2 bytes each, converted to a string of comma
    separated integers).
    """

    def __init__(self, length, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)
        self.__length = length

    def get_name(self):
        return 'Actions[{0}]'.format(self.__length)

    def from_bytes(self, data):
        return ','.join([str(ord(b)) for b in remove_tail(data, '\xff\xff')])

    def to_bytes(self, field):
        self.check_writable()
        actions = '' if len(field) == 0 else ''.join([chr(int(x)) for x in field.split(',')])
        return append_tail(actions, 2 * self.__length, '\xff\xff')

    def get_length(self):
        return 2 * self.__length


class EepromIBool(EepromDataType):
    """ A boolean that is encoded in a byte where value 255 is False and values < 255 are True. """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return 'Boolean'

    def from_bytes(self, data):
        return ord(data[0]) < 255

    def to_bytes(self, field):
        self.check_writable()
        value = 0 if field is True else 255
        return str(chr(value))

    def get_length(self):
        return 1


class EepromEnum(EepromDataType):
    """ A enum value that is encoded into a byte. """

    def __init__(self, addr_gen, enum_values, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)
        self.__enum_values = enum_values

    def get_name(self):
        return 'Enum'

    def from_bytes(self, data):
        index = ord(data[0])
        if index in self.__enum_values.keys():
            return self.__enum_values[index]
        return 'UNKNOWN'

    def to_bytes(self, field):
        self.check_writable()
        for key, value in self.__enum_values.iteritems():
            if field == value:
                return str(chr(key))
        return str(chr(255))

    def get_length(self):
        return 1


class EextDataType(object):
    """ Classes that are eeprom extensions should inherit from EextDataType. """

    def get_name(self):
        """ Get the name of the EextDataType. To be implemented in the subclass. """
        raise NotImplementedError()

    def is_writable(self):
        """ Always returns True, all EextDataTypes are writeable. """
        _ = self
        return True

    def default_value(self):
        """ Get the default value for this data type. To be implemented in the subclass. """
        raise NotImplementedError()

    def decode(self, value):
        """ Decode the database string value into the appropriate data type.
        To be implemented in the subclass. """
        raise NotImplementedError()

    def encode(self, value):
        """ Encode the data type into the database string value.
        To be implemented in the subclass. """
        raise NotImplementedError()


class EextByte(EextDataType):
    """ An byte field, stored in the eeprom extension database. """

    def __init__(self):
        pass

    def get_name(self):
        return 'Byte'

    def default_value(self):
        return 255

    def decode(self, value):
        return int(value)

    def encode(self, value):
        return str(value)


class EextString(EextDataType):
    """ An string field, stored in the eeprom extension database. """

    def __init__(self):
        pass

    def get_name(self):
        return 'String'

    def default_value(self):
        return ''

    def decode(self, value):
        return value

    def encode(self, value):
        return value


class EextBool(EextDataType):
    """ A Boolean field, stored in the eepro extension database. """

    def __init__(self):
        pass

    def get_name(self):
        return 'Boolean'

    def default_value(self):
        return False

    def decode(self, value):
        return bool(value)

    def encode(self, value):
        return str(value)
