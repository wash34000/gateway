'''
Contains the definition of the Master Api.

Created on Sep 9, 2012

@author: fryckbos
'''
from master_command import MasterCommandSpec, Field, OutputFieldType

BA_LIGHT_OFF = 160
BA_LIGHT_ON = 161
BA_LIGHT_TOGGLE = 162
BA_ALL_LIGHTS_OFF = 163
BA_ALL_OUTPUTS_OFF = 164
BA_LIGHT_ON_DIMMER_MIN = 165
BA_LIGHT_ON_DIMMER_MAX = 166
BA_LIGHT_ON_DIMMER_PLUS_5 = 167
BA_LIGHTS_ON_DIMMER_MIN_5 = 168
BA_DIMMER_MIN = 169
BA_DIMMER_MAX = 170
BA_LIGHTS_OFF_FLOOR = 171
BA_LIGHTS_ON_FLOOR = 172
BA_LIGHTS_TOGGLE_FLOOR = 173
BA_LIGHT_ON_DIMMER_10 = 176
BA_LIGHT_ON_DIMMER_20 = 177
BA_LIGHT_ON_DIMMER_30 = 178
BA_LIGHT_ON_DIMMER_40 = 179
BA_LIGHT_ON_DIMMER_50 = 180
BA_LIGHT_ON_DIMMER_60 = 181
BA_LIGHT_ON_DIMMER_70 = 182
BA_LIGHT_ON_DIMMER_80 = 183
BA_LIGHT_ON_DIMMER_90 = 184
BA_LIGHT_TOGGLE_DIMMER_10 = 185
BA_LIGHT_TOGGLE_DIMMER_20 = 186
BA_LIGHT_TOGGLE_DIMMER_30 = 187
BA_LIGHT_TOGGLE_DIMMER_40 = 188
BA_LIGHT_TOGGLE_DIMMER_50 = 189
BA_LIGHT_TOGGLE_DIMMER_60 = 190
BA_LIGHT_TOGGLE_DIMMER_70 = 191
BA_LIGHT_TOGGLE_DIMMER_80 = 192
BA_LIGHT_TOGGLE_DIMMER_90 = 193
BA_LIGHT_TOGGLE_DIMMER_100 = 194
BA_LIGHT_ON_TIMER_150_OVERRULE = 195
BA_LIGHT_ON_TIMER_450_OVERRULE = 196
BA_LIGHT_ONT_TIMER_900_OVERRULE = 197
BA_LIGHT_ON_TIMER_1500_OVERRULE = 198
BA_LIGHT_ON_TIMER_2220_OVERRULE = 199
BA_LIGHT_ON_TIMER_3120_OVERRULE = 200
BA_LIGHT_ON_TIMER_150_NO_OVERRULE = 201
BA_LIGHT_ON_TIMER_450_NO_OVERRULE = 202
BA_LIGHT_ONT_TIMER_900_NO_OVERRULE = 203
BA_LIGHT_ON_TIMER_1500_NO_OVERRULE = 204
BA_LIGHT_ON_TIMER_2220_NO_OVERRULE = 205
BA_LIGHT_ON_TIMER_3120_NO_OVERRULE = 206

def basic_action():
    """ Basic actions. """
    return MasterCommandSpec("BA",
        [ Field.byte("action_type"), Field.byte("action_number"), Field.padding(11) ],
        [ Field.str("resp", 2), Field.padding(11), Field.lit("\r\n") ])

def reset():
    """ Reset the gateway, used for firmware updates. """
    return MasterCommandSpec("re", 
        [ Field.padding(13) ],
        [ Field.str("resp", 2), Field.padding(11), Field.lit("\r\n") ])

def status():
    """ Get the status of the gateway. """
    return MasterCommandSpec("ST", 
        [ Field.padding(13) ],
        [ Field.lit('\x00\x00'), Field.byte('hours'), Field.byte('minutes'), Field.byte('year'),
          Field.byte('month'), Field.byte('day'), Field.byte('weekday'), Field.byte('mode'),
          Field.byte('f1'), Field.byte('f2'), Field.byte('f3'), Field.byte('h'),
          Field.lit('\r\n') ])

def eeprom_list():
    """ List all bytes from a certain eeprom bank """
    return MasterCommandSpec("EL", 
        [ Field.byte("bank"), Field.padding(12) ],
        [ Field.byte("bank"), Field.str("data", 256) ])

def write_eeprom():
    """ Write data bytes to the addr in the specified eeprom bank """
    return MasterCommandSpec("WE", 
        [ Field.byte("bank"), Field.byte("address"), Field.varstr("data", 10) ],
        [ Field.byte("bank"), Field.byte("address"), Field.varstr("data", 10), Field.lit('\r\n') ])
    
def activate_eeprom():
    """ Activate eeprom after write """
    return MasterCommandSpec("AE", 
        [ Field.byte("eep"), Field.padding(12) ],
        [ Field.byte("eep"), Field.str("resp", 2), Field.padding(10), Field.lit('\r\n') ])

def number_of_io_modules():
    """ Read the number of input and output modules """
    return MasterCommandSpec("rn", 
        [ Field.padding(13) ],
        [ Field.byte("in"), Field.byte("out"), Field.padding(11), Field.lit('\r\n') ])

def read_output():
    """ Read the information about an output """
    return MasterCommandSpec("ro", 
        [ Field.byte("output_nr"), Field.padding(12) ],
        [ Field.byte('output_nr'), Field.str('type', 1), Field.byte('light'), Field.int('timer'),
          Field.int('ctimer'), Field.byte('status'), Field.dimmer('dimmer'),
          Field.byte('controller_out'), Field.byte('max_power'), Field.byte('floor_level'),
          Field.str('menu_position', 3), Field.str('name', 16), Field.str('crc', 3),
          Field.lit('\r\n\r\n') ])

def read_input():
    """ Read the information about an input """
    return MasterCommandSpec("ri", 
        [ Field.byte("input_nr"), Field.padding(12) ],
        [ Field.byte('input_nr'), Field.byte('output_action'), Field.str('output_list', 30),
          Field.str('input_name', 8), Field.str('crc', 3), Field.lit('\r\n\r\n') ])

def temperature_list():
    """ Read the temperature thermostat sensor list for a series of 12 sensors """
    return MasterCommandSpec("TL", 
        [ Field.byte("series"), Field.padding(12) ],
        [ Field.byte("series"), Field.svt('tmp0'), Field.svt('tmp1'), Field.svt('tmp2'),
          Field.svt('tmp3'), Field.svt('tmp4'), Field.svt('tmp5'), Field.svt('tmp6'),
          Field.svt('tmp7'), Field.svt('tmp8'), Field.svt('tmp9'), Field.svt('tmp10'),
          Field.svt('tmp11'), Field.lit('\r\n') ])

def setpoint_list():
    """ Read the current setpoint of the thermostats in series of 12 """
    return MasterCommandSpec("SL", 
        [ Field.byte("series"), Field.padding(12) ],
        [ Field.byte("series"), Field.svt('tmp0'), Field.svt('tmp1'), Field.svt('tmp2'),
          Field.svt('tmp3'), Field.svt('tmp4'), Field.svt('tmp5'), Field.svt('tmp6'),
          Field.svt('tmp7'), Field.svt('tmp8'), Field.svt('tmp9'), Field.svt('tmp10'),
          Field.svt('tmp11'), Field.lit('\r\n') ])

def thermostat_mode():
    """ Read the current thermostat mode """
    return MasterCommandSpec("TM", 
        [ Field.padding(13) ],
        [ Field.byte('mode'), Field.padding(12), Field.lit('\r\n') ])

def read_setpoint():
    """ Read the programmed setpoint of a thermostat """
    return MasterCommandSpec("rs", 
        [ Field.byte('thermostat'), Field.padding(12) ],
        [ Field.byte('thermostat'), Field.svt('act'),  Field.svt('csetp'), Field.svt('psetp0'),
          Field.svt('psetp1'), Field.svt('psetp2'), Field.svt('psetp3'), Field.svt('psetp4'),
          Field.svt('psetp5'), Field.byte('sensor_nr'), Field.byte('output0_nr'), 
          Field.byte('output1_nr'), Field.byte('output0'), Field.byte('output1'),
          Field.svt('outside'), Field.byte('mode'), Field.str('name', 16), Field.byte('pid_p'),
          Field.byte('pid_i'), Field.byte('pid_d'), Field.byte('pid_ithresh'), 
          Field.svt('threshold_temp'), Field.byte('days'), Field.byte('hours'), 
          Field.byte('minutes'), Field.byte('mon_start_d1'), Field.byte('mon_stop_d1'),
          Field.byte('mon_start_d2'), Field.byte('mon_stop_d2'), Field.byte('tue_start_d1'),
          Field.byte('tue_stop_d1'), Field.byte('tue_start_d2'), Field.byte('tue_stop_d2'),
          Field.byte('wed_start_d1'), Field.byte('wed_stop_d1'), Field.byte('wed_start_d2'),
          Field.byte('wed_stop_d2'), Field.byte('thu_start_d1'), Field.byte('thu_stop_d1'),
          Field.byte('thu_start_d2'), Field.byte('thu_stop_d2'), Field.byte('fri_start_d1'),
          Field.byte('fri_stop_d1'), Field.byte('fri_start_d2'), Field.byte('fri_stop_d2'),
          Field.byte('sat_start_d1'), Field.byte('sat_stop_d1'), Field.byte('sat_start_d2'),
          Field.byte('sat_stop_d2'), Field.byte('sun_start_d1'), Field.byte('sun_stop_d1'),
          Field.byte('sun_start_d2'), Field.byte('sun_stop_d2'), Field.str('crc', 3),
          Field.lit('\r\n\r\n') ])        

def write_setpoint():
    """ Write a setpoints of a thermostats """
    return MasterCommandSpec("ws", 
        [ Field.byte("thermostat"), Field.byte("config"), Field.svt("temp"), Field.padding(10) ],
        [ Field.byte("thermostat"), Field.byte("config"), Field.svt("temp"), Field.padding(10),
          Field.lit('\r\n')])

def to_cli_mode():
    """ Go to CLI mode """
    return MasterCommandSpec("CM",
        [ Field.padding(13) ],
        None)

def output_list():
    """ The message sent by the master whenever the outputs change. """
    return MasterCommandSpec("OL",
        [],
        [Field("outputs", OutputFieldType()), Field.lit("\r\n\r\n")])
