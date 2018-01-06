import threading
import logging
import socket
import json
from config_wrapper import config
from events import NewClientResponseEvent, EventType


logger = logging.getLogger(__name__)

class ModelThread(threading.Thread):
    def __init__(self, event_queue, init_data = None):
        super(ModelThread, self).__init__()
        self.event_queue = event_queue
        self._stop_event = threading.Event()
        self.handlers = {}
        self.initialize_handlers()
        if not init_data:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            self.next_hop_info = (str(ip_address), config.getint('NewPredecessorListener', 'Port'))
            self.next_next_hop_info = None

    def stop(self):
        logger.info('Stopping model thread')
        self._stop_event.set()

    def initialize_handlers(self):
        self.handlers['NewClientRequestEvent'] = self.handle_new_client_request

    def handle_new_client_request(self, event):
        response = {'type': EventType.NEW_CLIENT_RESPONSE.value, 'next_hop': self.next_hop_info, 'next_next_hop': self.next_next_hop_info}
        response_json = json.dumps(response)
        event.connection.send(response_json.encode('utf-8'))

    def run(self):
        while not self._stop_event.is_set():
            (e) = self.event_queue.get()
            handler_function = self.handlers[type(e).__name__]
            handler_function(e)
