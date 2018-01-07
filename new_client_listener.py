import socket
from events import InnerNewClientRequestEvent
import threading
import logging
from config_wrapper import config

logger = logging.getLogger(__name__)

class NewClientListener(threading.Thread):
    def __init__(self, event_queue):
        super(NewClientListener, self).__init__()
        self.event_queue = event_queue
        self.listening_port = config.getint('NewClientListener', 'Port')
        self._stop_event = threading.Event()

    def stop(self):
        logger.info('Stopping new client listener')
        self._stop_event.set()

    def run(self):
        listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listening_socket.bind(('', self.listening_port))
        listening_socket.listen()
        logger.info('Server is listening for new clients on port: {}'.format(self.listening_port))
        while not self._stop_event.is_set():
            connection, client_address = listening_socket.accept()
            self.event_queue.put(InnerNewClientRequestEvent(connection, client_address))

        logger.info("New client listener stopped")
