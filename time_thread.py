import time
import ntplib
import threading

class TimeSynchronizer(threading.Thread):
    def __init__(self, time_offset):
        super(TimeSynchronizer, self).__init__()
        self.ntp_client = ntplib.NTPClient()
        self.time_offset = time_offset
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                response = self.ntp_client.request('europe.pool.ntp.org', version=3)
                self.time_offset[0] = response.offset
                time.sleep(5)
            except Exception:
                pass
