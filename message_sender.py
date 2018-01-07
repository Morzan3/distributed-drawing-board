from events import InnerNextHopBroken
import threading
import logging
import json
import helpers
logger = logging.getLogger(__name__)
# This is thread responsible for listening for predecessor


class MessageSender(threading.Thread):
    def __init__(self, event_queue, message_queue, connection):
        super(MessageSender, self).__init__()
        self.event_queue = event_queue
        self.message_queue = message_queue
        self.connection = connection
        self._stop_event = threading.Event()

    def stop(self):
        logging.info('Sending signal to stop predecessor_listener')
        self._stop_event.set()

    def run(self):
        logger.info('Thread sending message started')
        while not self._stop_event.is_set():
            (e) = self.message_queue.get()
            try:
                message = helpers.event_to_message(e)
                message_size = (len(message)).to_bytes(8, byteorder='big')
                self.connection.send(message_size)
                self.connection.send(message)
            except Exception:
                self.event_queue.put(InnerNextHopBroken())
                return
