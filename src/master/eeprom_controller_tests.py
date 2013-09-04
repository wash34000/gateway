'''
Tests for the eeprom_controller module.
Created on Sep 2, 2013

@author: fryckbos
'''
import unittest

from eeprom_controller import EepromController, EepromFile, EepromModel, EepromId, EepromString, EepromByte, EepromWord


class Model1(EepromModel):
    """ Used in the tests. """
    id = EepromId(10)
    name = EepromString(100, lambda id: (1, 2 + id))


class Model2(EepromModel):
    """ Used in the tests. """
    name = EepromString(100, (3, 4))


class Model3(EepromModel):
    """ Used in the tests. """
    name = EepromString(10, (3, 4))
    link = EepromByte((3, 14))
    out = EepromWord((3, 15))


class EepromControllerTest(unittest.TestCase):
    """ Tests for EepromController. """

    def test_read(self):
        pass ## TODO Write test here

    def test_write(self):
        pass ## TODO Write test here


class EepromFileTest(unittest.TestCase):
    """ Tests for EepromFile. """

    def test_read(self):
        pass ## TODO Write test here

    def test_write(self):
        pass ## TODO Write test here


class EepromModelTest(unittest.TestCase):
    """ Tests for EepromModel. """
    
    def test_get_fields(self):
        """ Test get_fields. """
        fields = Model1.get_fields()
        
        self.assertEquals(1, len(fields))
        self.assertEquals("name", fields[0][0])
        
        fields = Model1.get_fields(include_id=True)
        
        self.assertEquals(2, len(fields))
        self.assertEquals("id", fields[0][0])
        self.assertEquals("name", fields[1][0])
        
    def test_has_id(self):
        """ Test has_id. """
        self.assertTrue(Model1.has_id())
        self.assertFalse(Model2.has_id())
    
    def test_get_name(self):
        """ Test get_name. """
        self.assertEquals("Model1", Model1.get_name())
        self.assertEquals("Model2", Model2.get_name())
    
    def test_check_id(self):
        """ Test check_id. """
        Model1.check_id(0) ## Should just work
        
        try:
            Model1.check_id(100)
            self.fail("Expected TypeError")
        except TypeError as e:
            self.assertTrue("maximum" in str(e))
        
        try:
            Model1.check_id(None)
            self.fail("Expected TypeError")
        except TypeError as e:
            self.assertTrue("id" in str(e))
            
        Model2.check_id(None) ## Should just work    
        
        try:
            Model2.check_id(0)
            self.fail("Expected TypeError")
        except TypeError as e:
            self.assertTrue("id" in str(e))
        
    def test_to_dict(self):
        """ Test to_dict. """
        self.assertEquals({'id':1, 'name':'test'}, Model1(id=1, name="test").to_dict())
        self.assertEquals({'name':'hello world'}, Model2(name="hello world").to_dict())
    
    def test_from_dict(self):
        """ Test from_dict. """
        model1 = Model1.from_dict({'id':1, 'name':'test'})
        self.assertEquals(1, model1.id)
        self.assertEquals('test', model1.name)
        
        model2 = Model2.from_dict({'name':'test'})
        self.assertEquals('test', model2.name)
    
    def test_to_eeprom_data(self):
        """ Test to_eeprom_data. """
        model1 = Model1(id=1, name="test")
        data = model1.to_eeprom_data()
        
        self.assertEquals(1, len(data))
        self.assertEquals(1, data[0].address.bank)
        self.assertEquals(3, data[0].address.offset)
        self.assertEquals(100, data[0].address.length)
        self.assertEquals("test" + "\xff" * 96, data[0].bytes)
        
        model2 = Model2(name="test")
        data = model2.to_eeprom_data()
        
        self.assertEquals(1, len(data))
        self.assertEquals(3, data[0].address.bank)
        self.assertEquals(4, data[0].address.offset)
        self.assertEquals(100, data[0].address.length)
        self.assertEquals("test" + "\xff" * 96, data[0].bytes)
        
        model3 = Model3(name="test", link=123, out=456)
        data = model3.to_eeprom_data()
        
        self.assertEquals(3, len(data))
        
        self.assertEquals(3, data[0].address.bank)
        self.assertEquals(14, data[0].address.offset)
        self.assertEquals(1, data[0].address.length)
        self.assertEquals(str(chr(123)), data[0].bytes)
        
        self.assertEquals(3, data[1].address.bank)
        self.assertEquals(4, data[1].address.offset)
        self.assertEquals(10, data[1].address.length)
        self.assertEquals("test" + "\xff" * 6, data[1].bytes)
        
        self.assertEquals(3, data[2].address.bank)
        self.assertEquals(15, data[2].address.offset)
        self.assertEquals(2, data[2].address.length)
        self.assertEquals(str(chr(1) + chr(200)), data[2].bytes)
        
    
    def test_from_eeprom_data(self):
        """ Test from_eeprom_data. """
        pass ## TODO Write test here
    
    def test_get_addresses(self):
        """ Test get_addresses. """
        try:
            Model1.get_addresses(None)
            self.fail("Expected TypeError.")
        except TypeError as e:
            self.assertTrue("id" in str(e))
        
        addresses = Model1.get_addresses(1)
        
        self.assertEquals(1, len(addresses))
        self.assertEquals(1, addresses[0].bank)
        self.assertEquals(3, addresses[0].offset)
        self.assertEquals(100, addresses[0].length)
        
        addresses = Model2.get_addresses()
        
        self.assertEquals(1, len(addresses))
        self.assertEquals(3, addresses[0].bank)
        self.assertEquals(4, addresses[0].offset)
        self.assertEquals(100, addresses[0].length)
        
        addresses = Model3.get_addresses()
        
        self.assertEquals(3, len(addresses))
        
        self.assertEquals(3, addresses[0].bank)
        self.assertEquals(14, addresses[0].offset)
        self.assertEquals(1, addresses[0].length)
        
        self.assertEquals(3, addresses[1].bank)
        self.assertEquals(4, addresses[1].offset)
        self.assertEquals(10, addresses[1].length)
        
        self.assertEquals(3, addresses[2].bank)
        self.assertEquals(15, addresses[2].offset)
        self.assertEquals(2, addresses[2].length)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()