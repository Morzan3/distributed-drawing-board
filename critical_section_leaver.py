from events import PredecessorMessageEvent, DrawingInformationEvent
import threading
import logging
import json
from events import EventType, DrawingInformationEvent
import time
logger = logging.getLogger(__name__)
# This is thread responsible for listening for predecessor


class PredecessorListener(threading.Thread):
    def __init__(self, event_queue):
        super(PredecessorListener, self).__init__()
        self.event_queue = event_queue


    def run(self):
        time.sleep(20)
        self.event_queue.put

