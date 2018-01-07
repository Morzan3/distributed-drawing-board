import threading
import logging
import socket
import uuid
from config_wrapper import config
import events
import queue
import time
import helpers
import socket
from critical_section_leaver import CriticalSectionLeaver
from painter import DrawingQueueEvent
from message_sender import MessageSender


logger = logging.getLogger(__name__)

class ModelThread(threading.Thread):
    def __init__(self, event_queue, paint_queue, time_offset, init_data=None, init_connection=None):
        super(ModelThread, self).__init__()

        # Queues
        self.event_queue = event_queue
        self.paint_queue = paint_queue
        self._stop_event = threading.Event()
        self.board_state = [[0 for _ in range(config.getint('Tkinter', 'CanvasX'))] for _ in range(config.getint('Tkinter', 'CanvasY'))]

        #Event handling
        self.handlers = {}
        self.initialize_handlers()


        self.uuid = uuid.uuid4().hex
        self.want_to_enter_critical_section = False
        self.critical_section = None
        self.time_offset = time_offset
        self.last_token = None

        if not init_data:
            self.next_hop_info = None
            self.next_next_hop_info = None
            self.sending_queue = None
            self.message_sender = None
            self.token = 0
            self.predecessor = None

        else:
            self.next_hop_info = init_data['next_hop']
            self.next_next_hop_info = init_data['next_next_hop']
            self.predecessor = init_connection.getsockname()
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
            self.paint_queue.put({'type': DrawingQueueEvent.DRAWING, 'data': (x, y, 1, begin)})

    def initialize_handlers(self):
        # Inner Handlers
        self.handlers['InnerNewClientRequestEvent'] = self.handle_new_client_request
        self.handlers['InnerDrawingInformationEvent'] = self.handle_inner_draw_information_event
        self.handlers['InnerWantToEnterCriticalSection'] = self.inner_handle_want_to_enter_critical_section_event
        self.handlers['InnerLeavingCriticalSection'] = self.inner_leaving_critical_section_event
        self.handlers['InnerNextHopBroken'] = self.inner_next_hop_broken_event

        # Outter handlers
        self.handlers['DrawingInformationEvent'] = self.handle_drawing_information_event
        self.handlers['NewPredecessorRequestEvent'] = self.handle_new_predecessor_request_event
        self.handlers['PredecessorMessageEvent'] = self.handle_predecessor_message_event
        self.handlers['EnteredCriticalSectionEvent'] = self.handle_entering_critical_section
        self.handlers['LeavingCriticalSectionEvent'] = self.handle_leaving_critical_section
        self.handlers['TokenPassEvent'] = self.handle_token_pass_event
        self.handlers['NewNextNextHop'] = self.handle_new_next_next_hop_event

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
            self.paint_queue.put({'type': DrawingQueueEvent.DRAWING, 'data': (x, y, color, begin)})
            if (self.sending_queue):
                self.sending_queue.put(
                    events.DrawingInformationEvent(self.uuid, helpers.get_current_timestamp(), x, y, color, begin))

        print(self.critical_section, event.data)
        if not self.critical_section:
            draw_point(event)
        elif self.critical_section['timestamp'] > event.data['timestamp']:
            draw_point(event)
        elif self.critical_section['client_uuid'] == self.uuid:
            draw_point(event)
        elif self.critical_section['client_uuid'] != self.uuid:
            pass

    def inner_handle_want_to_enter_critical_section_event(self, _):
        self.want_to_enter_critical_section = True

    def inner_leaving_critical_section_event(self, _):
        self.critical_section = None
        self.paint_queue.put({"type": DrawingQueueEvent.BOARD_OPEN})
        self.sending_queue.put(events.LeavingCriticalSectionEvent(helpers.get_current_timestamp(), self.uuid))
        self.sending_queue.put(events.TokenPassEvent(self.last_token))


    def inner_next_hop_broken_event(self, event):
        # If we detect that the next hop connection is down we want to:
        # 1.Try to reconnect to the client
        # 2.If reconnect fails we want to connect to our next next hop
        # 3.When we succesfully connect to our next next hop we want to send recovery token question
        #   in case that the dead client was holding the token the moment he died


        def connect_to_next_next_hop():
            ip, port = self.next_next_hop_info
            try:
                s = socket.create_connection(('localhost', port))
                self.sending_queue = queue.Queue(maxsize=0)
                self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
                self.message_sender.start()
                self.next_hop_info = self.next_next_hop_info
                # After we connect to a new client we have to check whether the dead client wasn't in posession
                # of token
                self.sending_queue.put(events.TokenReceivedQuestionEvent(self.token))
            except Exception as e:
                print(e)

        ip, port = self.next_hop_info
        try:
            s = socket.create_connection(('localhost', port))
            self.sending_queue = queue.Queue(maxsize=0)
            self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
            self.message_sender.start()
        except ConnectionRefusedError as e:
            connect_to_next_next_hop()

    ############################################################################################
    #
    #                                      Event handlers
    ############################################################################################
    def handle_new_client_request(self, event):
        # When we detect a new client connecting we want to;
        # 1.Send him the initial data over the connection we already established
        # 2.Connect to him as a predecessor

        # Gather the initial board state
        marked_spots = [(x, y) for x in range(len(self.board_state)) for y in range(len(self.board_state[x])) if self.board_state[x][y]]

        next_hop = self.next_hop_info if self.next_next_hop_info else (helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port'))

        if self.next_hop_info:
            self.next_next_hop_info = self.next_hop_info

        self.next_hop_info = event.data['address']

        response = events.NewClientResponseEvent(next_hop, self.next_next_hop_info, marked_spots)

        message = helpers.event_to_message(response)
        event.data['connection'].send(message)

        # If we do not have a nex_next hop info this means we are the first client so we set out next next hope as our addres
        if not self.next_next_hop_info:
            self.next_next_hop_info = (
            helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port'))

        # In the final application all client will be listening for new clients and new predecessors on the same port
        # for testing purposes the ports must be different
        # TODO uncomment in final application
        # s = socket.create_connection(('localhost', config.getint('NewPredecessorListener', 'Port')))
        self.sending_queue = queue.Queue(maxsize=0)
        connection = socket.create_connection(('localhost', config.getint('NewPredecessorConnector', 'Port')), 50)
        self.message_sender = MessageSender(self.event_queue, self.sending_queue, connection)
        self.message_sender.start()
        self.sending_queue.put(events.TokenPassEvent(self.token))


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
            self.paint_queue.put({'type': DrawingQueueEvent.DRAWING, 'data': (x, y, color, begin)})
            if (self.sending_queue):
                self.sending_queue.put(events.DrawingInformationEvent(client_uuid, timestamp, x, y, color, begin))


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
        # The moment we have a new predecessor this means that the client before our predecessor
        # has a new next next hop address (which is our address)
        self.predecessor = event.data['client_address']
        self_address = (helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port'))
        self.sending_queue.put(events.NewNextNextHop(self_address, self.predecessor))

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
        self.paint_queue.put({'type': DrawingQueueEvent.BOARD_CLOSED})
        self.sending_queue.put(event)

    def handle_leaving_critical_section(self, event):
        data = event.data
        if (data['client_uuid']) == self.uuid:
            return

        if self.critical_section['client_uuid'] == event.data['client_uuid']:
            self.paint_queue.put({'type': DrawingQueueEvent.BOARD_OPEN})
            self.critical_section = None

        self.sending_queue.put(event)

    def handle_token_pass_event(self, event):
        token = event.data['token'] + 1
        self.last_token = token
        if self.want_to_enter_critical_section:
            timestamp = helpers.get_current_timestamp()
            self.critical_section = {
                'timestamp': timestamp,
                'client_uuid': self.uuid
            }
            leave_critical_section_deamon = CriticalSectionLeaver(self.event_queue)
            leave_critical_section_deamon.start()
            self.want_to_enter_critical_section = False
            self.paint_queue.put({'type': DrawingQueueEvent.BOARD_CONTROLLED})
            self.sending_queue.put(events.EnteredCriticalSectionEvent(timestamp, self.uuid))
        else:
            self.sending_queue.put(events.TokenPassEvent(token))

    def handle_new_next_next_hop_event(self, event):
        pass
        # We are the recipient of the message
        # if self.next_hop_info == event.data['destination_next_hop']:
        #     self.next_next_hop_info = event.data['new_address']
        # else:
        #     self.sending_queue.put(event)