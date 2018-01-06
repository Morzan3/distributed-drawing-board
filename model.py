import threading
import logging
import socket
import uuid
from config_wrapper import config
from events import NewClientResponseEvent, EventType, DrawingInformationEvent, EnteredCriticalSectionEvent, LeavingCriticalSectionEvent, TokenPassEvent
import queue
import time
import helpers
from message_sender import MessageSender


logger = logging.getLogger(__name__)

class ModelThread(threading.Thread):
    def __init__(self, event_queue, paint_queue, time_offset, init_data=None):
        super(ModelThread, self).__init__()

        # Queues
        self.event_queue = event_queue
        self.paint_queue = paint_queue
        self._stop_event = threading.Event()
        self.board_state = [[0 for x in range(config.getint('Tkinter', 'CanvasX'))] for x in range(config.getint('Tkinter', 'CanvasY'))]

        #Event handling
        self.handlers = {}
        self.initialize_handlers()


        self.uuid = uuid.uuid4().hex
        self.want_to_enter_critical_section = False
        self.critical_section = None
        self.time_offset = time_offset

        if not init_data:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            self.next_hop_info = (ip_address, config.getint('NewPredecessorListener', 'Port'))
            self.next_next_hop_info = None
            self.sending_queue = None
            self.message_sender = None
            self.token = 0

        else:
            self.next_hop_info = init_data['next_hop']
            self.next_next_hop_info = init_data['next_next_hop']
            ip, port = init_data['next_hop']

            # TODO change for ip address
            s = socket.create_connection(('localhost', port))
            self.sending_queue = queue.Queue(maxsize=0)
            self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
            self.message_sender.start()
            self.initialize_board(init_data['board_state'])


    def run(self):
        while not self._stop_event.is_set():
            (e) = self.event_queue.get()
            handler_function = self.handlers[type(e).__name__]
            handler_function(e)

    def stop(self):
        logger.info('Stopping model thread')
        self._stop_event.set()


    def initialize_board(self, board_state):
        for counter in range(len(board_state)):
            x, y = board_state[counter]
            begin = True if counter == 0 else False
            self.paint_queue.put((x, y, 1, begin))

    def initialize_handlers(self):
        # Inner Handlers
        self.handlers['InnerDrawingInformationEvent'] = self.handle_inner_draw_information_event
        self.handlers['WantToEnterCriticalSection'] = self.inner_handle_want_to_enter_critical_section_event
        self.handlers['InnerLeavingCriticalSection'] = self.inner_leaving_critical_section_event
        self.handlers['InnerNextHopBroken'] = self.inner_next_hop_broken_event

        # Outter handlers
        self.handlers['NewClientRequestEvent'] = self.handle_new_client_request
        self.handlers['DrawingInformationEvent'] = self.handle_drawing_information_event
        self.handlers['NewPredecessorRequestEvent'] = self.handle_new_predecessor_request_event
        self.handlers['PredecessorMessageEvent'] = self.handle_predecessor_message_event
        self.handlers['EnteringCriticalSection'] = self.handle_entering_critical_section
        self.handlers['TokenPassEvent'] = self.handle_token_pass_event

    ############################################################################################
    #
    #                                      Inner Event handlers
    ############################################################################################
    def handle_inner_draw_information_event(self, event):
        def draw_point(event):
            x = event.data['x']
            y = event.data['y']
            color = event.data['color']
            begin = event.data['begin']
            try:
                self.board_state[x][y] = color
            except IndexError:
                return

            self.board_state[x][y] = color
            self.paint_queue.put((x, y, color, begin))
            if (self.sending_queue):
                self.sending_queue.put(
                    DrawingInformationEvent(self.uuid, helpers.get_current_timestamp(), x, y, color, begin))

        if not self.critical_section:
            draw_point(event)
        elif self.critical_section['timestamp'] > event.data['timestamp']:
            draw_point(event)
        elif self.critical_section['client_uuid'] == self.uuid:
            draw_point(event)
        elif self.critical_section['client_uuid'] != event.data['client_uuid']:
            pass

    def inner_handle_want_to_enter_critical_section_event(self):
        self.want_to_enter_critical_section = True

    def inner_leaving_critical_section_event(self):
        self.critical_section = None
        self.message_sender.put(LeavingCriticalSectionEvent(helpers.get_current_timestamp(), self.uuid))


    def inner_next_hop_broken_event(self, event):
        pass

    ############################################################################################
    #
    #                                      Event handlers
    ############################################################################################
    def handle_new_client_request(self, event):
        self.sending_queue = queue.Queue(maxsize=0)
        self.message_sender = MessageSender(self.event_queue, self.sending_queue, event.data['connection'])
        self.message_sender.start()
        marked_spots = []
        for x in range(len(self.board_state)):
            for y in range(len(self.board_state)):
                if self.board_state[x][y] == 1:
                    marked_spots.append((x, y))
        response = NewClientResponseEvent(self.next_hop_info, self.next_next_hop_info, marked_spots)
        self.sending_queue.put(response)
        # self.sending_queue.put(TokenPassEvent(self.token))


    def handle_drawing_information_event(self, event):
        def draw_point(event):
            x = event.data['x']
            y = event.data['y']
            color = event.data['color']
            begin = event.data['begin']
            client_uuid = event.data['client_uuid']
            timestamp = event.data['timestamp']
            try:
                self.board_state[x][y] = color
            except IndexError:
                return

            self.board_state[x][y] = color
            self.paint_queue.put((x, y, color, begin))
            if (self.sending_queue):
                self.sending_queue.put(DrawingInformationEvent(client_uuid, timestamp, x, y, color, begin))


        if (event.data['client_uuid'] == self.uuid):
            return
        if not self.critical_section:
            draw_point(event)
        elif self.critical_section['timestamp'] > event.data['timestamp']:
            draw_point(event)
        elif self.critical_section['client_uuid'] == event.data['client_uuid']:
            draw_point(event)
        elif self.critical_section['client_uuid'] != event.data['client_uuid']:
            pass


    def handle_new_predecessor_request_event(self, event):
        # raise Exception("Not implemented")
        pass

    def handle_predecessor_message_event(self, event):
        raise Exception("Not implemented")

    def handle_entering_critical_section(self, event):
        data = event.data
        if (data['client_uuid']) == self.uuid:
            return
        self.critical_section = {
            'timestamp': data['timestamp'],
            'client_uuid': data['client_uuid']
        }

        self.sending_queue.put(event)

    def handle_leaving_critical_section(self, event):
        data = event.data
        if (data['client_uuid']) == self.uuid:
            return

        if self.critical_section['client_uuid'] == event.data['client_uuid']:
            self.critical_section = None

        self.sending_queue.put(event)

    def handle_token_pass_event(self, event):
        print('passing the token', event.data)
        if (self.want_to_enter_critical_section):
            timestamp = helpers.get_current_timestamp()
            self.critical_section = {
                'timestamp': timestamp,
                'client_uuid': self.uuid
            }
            self.sending_queue.put(EnteredCriticalSectionEvent(timestamp, self.uuid))
        else:
            token = event.data['token'] + 1
            self.sending_queue.put(TokenPassEvent(token))