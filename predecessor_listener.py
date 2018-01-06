from events import PredecessorMessageEvent
import threading
import logging
logger = logging.getLogger(__name__)
# This is thread responsible for listening for predecessor


class PredecessorListener(threading.Thread):
    def __init__(self, event_queue, connection_data):
        super(PredecessorListener, self).__init__()
        self.event_queue = event_queue
        self.connection_data = connection_data
        self._stop_event = threading.Event()

    def stop(self):
        logging.info('Sending signal to stop predecessor_listener')
        self._stop_event.set()

    def run(self):
        logger.info('Server is listening for new messages from predecessor'.format(self.listening_port))
        while not self._stop_event.is_set():
            data = self.conenction_data.connection.recv(1024)
            if not self._stop_event:
                self.event_queue.put(PredecessorMessageEvent(data))
