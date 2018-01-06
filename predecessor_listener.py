from events import PredecessorMessageEvent, DrawingInformationEvent
import threading
import logging
import json
from events import EventType, DrawingInformationEvent, TokenPassEvent
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
        logger.info('Server is listening for new messages from predecessor')
        while not self._stop_event.is_set():
            try:
                message = self.connection_data['connection'].recv(1024)
                parsed_message = (json.loads(message.decode('utf-8')))
                message_type = EventType(parsed_message['type'])
                data = parsed_message['data']
                if message_type == EventType.DRAWING_INFORMATION:
                    self.event_queue.put(
                        DrawingInformationEvent(data['client_uuid'], data['timestamp'], data['x'], data['y'],
                                                data['color'], data['begin'])
                    )
                elif message_type == EventType.TOKEN_PASS:
                    print("TOKEN PASSS")
                    self.event_queue.put(TokenPassEvent(data['token']))
            except Exception as e:
                print(e)
                print(message.decode('utf-8'))
                return

