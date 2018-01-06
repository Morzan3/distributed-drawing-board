import time
time_offset = None

def initialize_offset(offset):
    global time_offset
    time_offset=offset

def get_current_timestamp():
    epoch_time = int(time.time())
    return epoch_time + time_offset[0]