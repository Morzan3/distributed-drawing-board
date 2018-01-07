import threading
import logging
import json
from events import InnerLeavingCriticalSection
import time
logger = logging.getLogger(__name__)
# This is thread responsible for putting a special event

class CriticalSectionLeaver(threading.Thread):
    def __init__(self, event_queue):
        super(CriticalSectionLeaver, self).__init__()
        self.event_queue = event_queue


    def run(self):
        time.sleep(5)
        self.event_queue.put(InnerLeavingCriticalSection())
        return

