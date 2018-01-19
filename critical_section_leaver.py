import threading
import logging
import time
from events import InnerLeavingCriticalSection

# This is thread responsible for leaving the critical section after certain time.
class CriticalSectionLeaver(threading.Thread):
    def __init__(self, event_queue):
        super(CriticalSectionLeaver, self).__init__()
        self.event_queue = event_queue

    def run(self):
        time.sleep(5)
        self.event_queue.put(InnerLeavingCriticalSection())
        return
