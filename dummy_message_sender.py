import threading
import logging
import time
from events import DummyMessageEvent
logger = logging.getLogger(__name__)
# Because we are relying on a TCP connection information when detecting failed connections
# we have to put dummy events to send so we can detect the fails all the time even if the data is not flowing
# through the network. This is the thread responsible for putting this dummy event if the queue is empty and sleeping
# for a while in order not to overflow the network.

class DummyMessageSender(threading.Thread):
    def __init__(self, event_queue, uuid):
        super(DummyMessageSender, self).__init__()
        self.event_queue = event_queue
        self.uuid = uuid

    def run(self):
        while True:
            if self.event_queue.empty():
                self.event_queue.put(DummyMessageEvent(self.uuid))
                time.sleep(0.2)
