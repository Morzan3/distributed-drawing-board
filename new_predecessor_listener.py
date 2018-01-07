import socket
from events import NewPredecessorRequestEvent
from predecessor_listener import PredecessorListener
import threading
import logging
from config_wrapper import config

logger = logging.getLogger(__name__)

# This is thread responsible for listening for a new predecessor connections (not messages itself).
# It is responsible for creating a new predecessor connection or shutting down old one and creating a new one


class NewPredecessorListener(threading.Thread):
    def __init__(self, event_queue, init_data=None):
        super(NewPredecessorListener, self).__init__()
        self.event_queue = event_queue
        self.listening_port = config.getint('NewPredecessorListener', 'Port')
        self.predecessor_data = None
        self.predecessor_listening_thread = None
        self._stop_event = threading.Event()
        self.init_data = init_data

    def stop(self):
        logging.info('Sending signal to stop new predecessor_listener')
        self._stop_event.set()

    def run(self):
        listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listening_socket.bind(('localhost', self.listening_port))
        listening_socket.listen()
        logger.info("'Server is listening for new predecessors on port {}".format(self.listening_port))
        while not self._stop_event.is_set():
            connection, client_address = listening_socket.accept()
            logger.info("New Predecessor connected")
            if self.predecessor_listening_thread:
                self.predecessor_listening_thread.stop()
            self.predecessor_data = {'connection': connection, 'client_address': client_address}
            self.event_queue.put(NewPredecessorRequestEvent(self.predecessor_data))
            self.predecessor_listening_thread = PredecessorListener(self.event_queue, self.predecessor_data)
            self.predecessor_listening_thread.start()

        logger.info('New predecessor_listener stopped listening')