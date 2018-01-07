import threading
import logging
import json
from events import \
    EventType,\
    DrawingInformationEvent,\
    TokenPassEvent, \
    NewNextNextHop, \
    EnteredCriticalSectionEvent, \
    LeavingCriticalSectionEvent
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
                message_size = self.connection_data['connection'].recv(8)
                message_size = int.from_bytes(message_size, byteorder='big')
                message = self.connection_data['connection'].recv(message_size)
                parsed_message = (json.loads(message.decode('utf-8')))
                self.handle_message(parsed_message)
            except Exception as ex:
                if(message == b''):
                    # Only case when we have a succesfull read of 0 bytes is when other socket shutdowns normally
                    return
                print(message)
                raise ex

    def handle_message(self, parsed_message):
        message_type = EventType(parsed_message['type'])
        data = parsed_message['data']
        if message_type == EventType.DRAWING_INFORMATION:
            self.event_queue.put(
                DrawingInformationEvent(data['client_uuid'], data['timestamp'], data['x'], data['y'],
                                        data['color'], data['begin'])
            )
        elif message_type == EventType.TOKEN_PASS:
            self.event_queue.put(TokenPassEvent(data['token']))
        elif message_type == EventType.SET_NEW_NEXT_NEXT_HOP:
            self.event_queue.put(NewNextNextHop(data['new_address'], data['destination_next_hop']))
        elif message_type == EventType.ENTERED_CRITICAL_SECTION:
            self.event_queue.put(EnteredCriticalSectionEvent(data['timestamp'], data['client_uuid']))
        elif message_type == EventType.LEAVING_CRITICAL_SECTION:
            self.event_queue.put(LeavingCriticalSectionEvent(data['timestamp'], data['client_uuid']))
        else:
            raise Exception("Not implemented yet")