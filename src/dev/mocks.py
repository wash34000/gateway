from master.master_command import FieldType, SvtFieldType, ErrorListFieldType

class MasterCommunicatorMock:

    def __init__(self):
        pass

    def start(self):
        pass

    def enable_passthrough(self):
        pass

    def get_bytes_written(self):
        return 0

    def get_bytes_read(self):
        return 0

    def get_seconds_since_last_success(self):
        return 0

    def register_consumer(self, consumer):
        pass

    def do_basic_action(self, action_type, action_number):
        return { 'resp' : 'OK' }

    def do_command(self, cmd, fields=None, timeout=2):
        output = {}
        input_field_names = [ field.name for field in cmd.input_fields ]

        for field in cmd.output_fields:
            if field.name in input_field_names and fields is not None and field.name in fields:
                output[field.name] = fields[field.name]
            elif isinstance(field.field_type, FieldType):
                if field.field_type.python_type == int:
                    output[field.name] = 0
                elif field.field_type.python_type == str:
                    output[field.name] = '\x00' * field.field_type.length
            elif isinstance(field.field_type, SvtFieldType):
                output[field.name] = field.field_type.decode('\x00')
            elif isinstance(field.field_type, ErrorListFieldType):
                output[field.name] = field.field_type.decode('\x00')

        return output

    def send_passthrough_data(self, data):
        pass

    def get_passthrough_data(self):
        return ''

    def start_maintenance_mode(self):
        pass

    def send_maintenance_data(self, data):
        pass

    def get_maintenance_data(self):
        return ''

    def stop_maintenance_mode(self):
        pass

    def in_maintenance_mode(self):
        return False


class PowerCommunicatorMock:

    def __init__(self):
        pass

    def start(self):
        pass

    def get_bytes_written(self):
        return 0

    def get_bytes_read(self):
        return 0

    def get_seconds_since_last_success(self):
        return 0

    def do_command(self, address, cmd, *data):
        return {}

    def start_address_mode(self):
        pass

    def stop_address_mode(self):
        pass

    def in_address_mode(self):
        return False
