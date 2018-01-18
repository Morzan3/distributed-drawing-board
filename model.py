import threading
import logging
import uuid
import events
import queue
import helpers
import socket
from config_wrapper import config
from critical_section_leaver import CriticalSectionLeaver
from painter import DrawingQueueEvent
from message_sender import MessageSender
from dummy_message_sender import DummyMessageSender
import json


logger = logging.getLogger(__name__)

class ModelThread(threading.Thread):
    def __init__(self, event_queue, paint_queue, time_offset, init_data=None, init_connection=None):
        super(ModelThread, self).__init__()

        # Queues
        self.event_queue = event_queue
        self.paint_queue = paint_queue

        #Event handling
        self.handlers = {}
        self.initialize_handlers()

        # Unique uuid identifying clients in the network
        self.uuid = uuid.uuid4().hex
        # Flag indicating weather we want to enter critical section when the token comes
        self.want_to_enter_critical_section = False
        # Information about critical section like the timestamp and client uuid which is in the section
        self.critical_section = None
        # Time offset between ntp server and local time
        self.time_offset = time_offset
        # Value of the last token we have received
        self.last_token = None

        # Initial board state
        self.board_state = [[0 for _ in range(config.getint('Tkinter', 'CanvasY'))] for _ in range(config.getint('Tkinter', 'CanvasX'))]

        # If we are the first client
        if not init_data:
            self.next_hop_info = None
            self.next_next_hop_info = None
            self.sending_queue = None
            self.message_sender = None
            self.predecessor = None
            self.last_token = 0
        else:
            self.next_hop_info = init_data['next_hop']
            if not init_data['next_next_hop']:
                # If there is no next_next_hop init data in the response we are the second client so we set
                # next next hop as our address
                self.next_next_hop_info = (helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port'))
            else:
                # If there are more thant two clients we set the value from the response
                self.next_next_hop_info = init_data['next_next_hop']

            # Address of our predecessor
            self.predecessor = init_connection.getsockname()

            # We initialize connection to our next hop and we start sending queue
            ip, port = init_data['next_hop']
            s = socket.create_connection((ip, port))
            self.sending_queue = queue.Queue(maxsize=0)
            self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
            self.message_sender.start()
            self.initialize_board(init_data['board_state'])

            # We signal that client has initialized properly
            init_connection.shutdown(1)
            init_connection.close()

        # We start a dummy message sender event which will create dummy messages to detect connection breaks
        self.dummy_message_sender = DummyMessageSender(self.event_queue, self.uuid)
        self.dummy_message_sender.start()


    def run(self):
        while True:
            (e) = self.event_queue.get()
            handler_function = self.handlers[type(e).__name__]
            handler_function(e)

    def initialize_board(self, board_state):
        for counter in range(len(board_state)):
            x, y = board_state[counter]
            try:
                self.board_state[x][y] = 1
            except IndexError:
                return
        self.paint_queue.put({'type': DrawingQueueEvent.DRAWING, 'data': (board_state, 1)})


    def initialize_handlers(self):
        # Inner Handlers
        self.handlers['InnerNewClientRequestEvent'] = self.handle_new_client_request
        self.handlers['InnerNewPredecessorRequestEvent'] = self.handle_new_predecessor_request_event
        self.handlers['InnerDrawingInformationEvent'] = self.handle_inner_draw_information_event
        self.handlers['InnerWantToEnterCriticalSection'] = self.inner_handle_want_to_enter_critical_section_event
        self.handlers['InnerLeavingCriticalSection'] = self.inner_leaving_critical_section_event
        self.handlers['InnerNextHopBroken'] = self.inner_next_hop_broken_event

        # Outter handlers
        self.handlers['DrawingInformationEvent'] = self.handle_drawing_information_event
        self.handlers['EnteredCriticalSectionEvent'] = self.handle_entering_critical_section
        self.handlers['LeavingCriticalSectionEvent'] = self.handle_leaving_critical_section
        self.handlers['TokenPassEvent'] = self.handle_token_pass_event
        self.handlers['NewNextNextHop'] = self.handle_new_next_next_hop_event
        self.handlers['TokenReceivedQuestionEvent'] = self.handle_token_received_question_event
        self.handlers['DummyMessageEvent'] = self.handle_dummy_message_event

    ############################################################################################
    #
    #                                      Inner Event handlers
    ############################################################################################
    def handle_inner_draw_information_event(self, event):
        def draw_points(event):
            color = event.data['color']
            points = event.data['points']
            try:
                for point in points:
                  x,y = point
                  self.board_state[x][y] = color
            except IndexError as e:
                print(e)
                return

            self.paint_queue.put({'type': DrawingQueueEvent.DRAWING, 'data': (points, color)})
            if (self.sending_queue):
                self.sending_queue.put(
                    events.DrawingInformationEvent(self.uuid, helpers.get_current_timestamp(), points, color))

        if not self.critical_section:
            draw_points(event)
        elif self.critical_section['timestamp'] > event.data['timestamp']:
            draw_points(event)
        elif self.critical_section['client_uuid'] == self.uuid:
            draw_points(event)
        elif self.critical_section['client_uuid'] != self.uuid:
            pass

    def inner_handle_want_to_enter_critical_section_event(self, _):
        self.want_to_enter_critical_section = True

    def inner_leaving_critical_section_event(self, _):
        self.critical_section = None
        self.paint_queue.put({"type": DrawingQueueEvent.BOARD_OPEN})
        if self.sending_queue:
            self.sending_queue.put(events.LeavingCriticalSectionEvent(helpers.get_current_timestamp(), self.uuid))
            self.sending_queue.put(events.TokenPassEvent(self.last_token))
        else:
            self.event_queue.put(events.LeavingCriticalSectionEvent(helpers.get_current_timestamp(), self.uuid))
            self.event_queue.put(events.TokenPassEvent(self.last_token))


    def inner_next_hop_broken_event(self, _):
        # If we detect that the next hop connection is down we want to:
        # 1.Try to reconnect to the client
        # 2.If reconnect fails we want to connect to our next next hop
        # 3.When we succesfully connect to our next next hop we want to send recovery token question
        #   in case that the dead client was holding the token the moment he died
        print("****"*100)
        ip, port = self.next_next_hop_info
        print(self.next_next_hop_info)
        # If we are the only client left we reset the data to the initial state
        if ip == helpers.get_self_ip_address():
            self.critical_section = None
            self.next_hop_info = None
            self.next_next_hop_info = None
            if self.message_sender:
                self.message_sender.stop()
            self.sending_queue = None
            self.message_sender = None
            self.predecessor = None
            self.last_token = 0
            self.paint_queue.put({'type': DrawingQueueEvent.BOARD_OPEN})
            return

        def connect_to_next_next_hop(self):
            ip, port = self.next_next_hop_info
            try:
                s = socket.create_connection((ip, port))
                self.sending_queue = queue.Queue(maxsize=0)
                self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
                self.message_sender.start()
                self.next_hop_info = self.next_next_hop_info
                # After we connect to a new client we have to check whether the dead client wasn't in posession
                # of token
                self.sending_queue.put(events.TokenReceivedQuestionEvent(self.last_token))
            except Exception as e:
                logger.error(e)

        ip, port = self.next_hop_info
        try:
            s = socket.create_connection((ip, port))
            self.sending_queue = queue.Queue(maxsize=0)
            self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
            self.message_sender.start()
        except ConnectionRefusedError as e:
            logger.error(e)
            connect_to_next_next_hop(self)

    ############################################################################################
    #
    #                                      Event handlers
    ############################################################################################
    def handle_new_client_request(self, event):
        # At first we want to receive information to properly connect as new predecessor after sending init_data
        message_size =  event.data['connection'].recv(8)
        message_size = int.from_bytes(message_size, byteorder='big')
        message = b''
        while len(message) < message_size:
            packet =  event.data['connection'].recv(message_size - len(message))
            if not packet:
                return None
            message += packet
        client_request = json.loads(message.decode('utf-8'))

        first_client = not self.next_hop_info
        # When we detect a new client connecting we want to;
        # 1.Send him the initial data over the connection we already established
        # 2.Connect to him as a predecessor

        # Gather the initial board state (only the coloured spots)
        marked_spots = [(x, y) for x in range(len(self.board_state)) for y in range(len(self.board_state[x])) if self.board_state[x][y]]

        # If we have next hop information we send it, if we do not have we are the first client so we send our
        # information as the first hop information
        next_hop = (helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port')) if first_client else self.next_hop_info
        # If we are the first client next next hop is None
        response = events.NewClientResponseEvent(next_hop, self.next_next_hop_info, marked_spots)
        message = helpers.event_to_message(response)
        message_size = (len(message)).to_bytes(8, byteorder='big')
        event.data['connection'].send(message_size)
        print(message)
        event.data['connection'].send(message)


        print("WAITING FOR SHUTDOWN")
        try:
            message = event.data['connection'].recv(8)
        except Exception as ex:
            print(ex)
            print(message)
            if message == b'':
                print("SHUUTDOWN")
                # Only case when we have a succesfull read of 0 bytes is when other socket shutdowns normally
                pass
            else:
                logger.error(ex)
                #Client did not initializ correctly so we abort the process
                return
        # If we are not the first client we have to update our next next hop to our previous next hop
        if not first_client:
            self.next_next_hop_info = self.next_hop_info
        else:
            # If we are the first client we update our next next hop info to self address
            self.next_next_hop_info = (
                helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port')
            )

        # We stop current message sender if it exists
        if self.message_sender:
            self.message_sender.stop()


        # We update our next hop info with the newest client request
        self.next_hop_info = client_request['data']['address']
        ip, port = self.next_hop_info
        # We establish a new connection and a new message sender
        connection = socket.create_connection((ip, port), 100)
        self.sending_queue = queue.Queue(maxsize=0)
        self.message_sender = MessageSender(self.event_queue, self.sending_queue, connection)
        self.message_sender.start()
        if first_client and self.last_token != None:
            # If we are the first client we start passing of the token
            self.sending_queue.put(events.TokenPassEvent(self.last_token))


    def handle_drawing_information_event(self, event):
        def draw_point(event):
            points = event.data['points']
            color = event.data['color']
            try:
                for point in points:
                  x,y = point
                  self.board_state[x][y] = color
            except IndexError:
                return

            self.paint_queue.put({'type': DrawingQueueEvent.DRAWING, 'data': (points, color)})
            if self.sending_queue:
                self.sending_queue.put(event)

        if event.data['client_uuid'] == self.uuid:
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
        # has a new next next hop address (which is our address) and our predecessor has new next next hop (which is
        # our next hop)
        self.predecessor = event.data['client_address']
        self_address = (helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port'))
        # Special case if we have only 2 nodes left
        if self.predecessor[0] == self.next_hop_info[0]:
            self.sending_queue.put(events.NewNextNextHop(self.predecessor, self_address))
            self.next_next_hop_info = (helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port'))
        else:
            # We send information to predecessor of our predecessor about his new next next hop address
            self.sending_queue.put(events.NewNextNextHop(self_address, self.predecessor))
            # We send information to our predecessor about his new next next hop
            self.sending_queue.put(events.NewNextNextHop(self.next_hop_info, self_address))

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

        if self.critical_section and self.critical_section['client_uuid'] == event.data['client_uuid']:
            self.paint_queue.put({'type': DrawingQueueEvent.BOARD_OPEN})
            self.critical_section = None

        self.sending_queue.put(event)

    def handle_token_pass_event(self, event):
        token = event.data['token'] + 1
        self.last_token = token

        if self.critical_section:
            # If we have received the token and the critical section exists we unvalidate critical secion info
            self.critical_section = None
            self.paint_queue.put({'type': DrawingQueueEvent.BOARD_OPEN})

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
            if self.sending_queue:
                self.sending_queue.put(events.TokenPassEvent(token))

    def handle_new_next_next_hop_event(self, event):
        # print('NEW next next HOP')
        post_destination_ip, _ = event.data['destination_next_hop']
        next_hop_ip, _ = self.next_hop_info

        # We are the recipient of the message
        if post_destination_ip == next_hop_ip:
            self.next_next_hop_info = event.data['new_address']
        else:
            # print("###"*80)
            self.sending_queue.put(event)

    def handle_token_received_question_event(self, event):
        # We check weather the last token we received is greater than
        # the token from the request
        # If it is, this means that the disconnected client was not in posession of the token when he disconnected
        # If it was we have to unvalidate critial secion information and send token further

        if self.last_token > event.data['token'] + 1:
            return
        else:
            self.critical_section = None
            self.paint_queue.put({'type': DrawingQueueEvent.BOARD_OPEN})
            token = event.data['token'] + 1 if event.data['token'] else self.last_token + 1
            self.sending_queue.put(events.TokenPassEvent(token))

    def handle_dummy_message_event(self, event):
        if self.uuid != event.data['uuid']:
            return
        else:
            if self.sending_queue:
                self.sending_queue.put(event)
