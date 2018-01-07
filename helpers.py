import time
import socket
import json
time_offset = None

def initialize_offset(offset):
    global time_offset
    time_offset=offset

def get_current_timestamp():
    epoch_time = int(time.time())
    return epoch_time + time_offset[0]

def get_self_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    s.close()
    return ip_address

def event_to_message(event):
    message = {'type': event.event_type.value, 'data': event.data}
    message_json = json.dumps(message)
    return message_json.encode('utf-8')