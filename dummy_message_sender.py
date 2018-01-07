import threading
import logging
import json
from events import DummyMessageEvent
import time
logger = logging.getLogger(__name__)
# This is thread responsible for putting a special event

class DummyMessageSender(threading.Thread):
    def __init__(self, event_queue, uuid):
        super(DummyMessageSender, self).__init__()
        self.event_queue = event_queue
        self.uuid = uuid


    def run(self):
        while True:
            if self.event_queue.empty():
                self.event_queue.put(DummyMessageEvent(self.uuid))

