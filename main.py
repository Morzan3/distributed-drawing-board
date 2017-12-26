import threading
import time
from time_thread import calculate_ntp_offset
time_offset = [0]


ntp_offset_thread = threading.Thread(target=calculate_ntp_offset, args=(time_offset, ))
ntp_offset_thread.start()


while True:
    print(time_offset[0])
    time.sleep(5)