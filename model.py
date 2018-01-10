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
from dummy_message_sender import DummyMessageSender


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
            self.predecessor = None
            self.last_token = 0
        else:
            self.next_hop_info = init_data['next_hop']
            if not init_data['next_next_hop']:
                # If there is no next_next_hop init data in the response we are the second client so we set
                # next next hop as our address
                self.next_next_hop_info = (helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port'))
            else:
                self.next_next_hop_info = init_data['next_next_hop']

            self.predecessor = init_connection.getsockname()
            ip, port = init_data['next_hop']
            logger.info("Next hop info: {}".format(ip))
            # TODO change for ip address
            s = socket.create_connection((ip, config.getint('NewPredecessorListener', 'Port')))
            self.sending_queue = queue.Queue(maxsize=0)
            self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
            self.message_sender.start()
            self.initialize_board(init_data['board_state'])

            # We signal that client has initialized properly
            init_connection.shutdown(1)
            init_connection.close()

        # We start a dummy message sender event which will create cummy messages to detect connection break
        self.dummy_message_sender = DummyMessageSender(self.event_queue, helpers.get_self_ip_address())
        self.dummy_message_sender.start()


    def run(self):
        while not self._stop_event.is_set():
            (e) = self.event_queue.get()
            # if not (type(e).__name__ == 'DummyMessageEvent' or type(e).__name__ == 'TokenPassEvent'):
            #     print(e)
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
        self.handlers['TokenReceivedQuestionEvent'] = self.handle_token_received_question_event
        self.handlers['DummyMessageEvent'] = self.handle_dummy_message_event

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
        if self.sending_queue:
            self.sending_queue.put(events.LeavingCriticalSectionEvent(helpers.get_current_timestamp(), self.uuid))
            self.sending_queue.put(events.TokenPassEvent(self.last_token))
        else:
            self.event_queue.put(events.LeavingCriticalSectionEvent(helpers.get_current_timestamp(), self.uuid))
            self.event_queue.put(events.TokenPassEvent(self.last_token))


    def inner_next_hop_broken_event(self, event):
        # If we detect that the next hop connection is down we want to:
        # 1.Try to reconnect to the client
        # 2.If reconnect fails we want to connect to our next next hop
        # 3.When we succesfully connect to our next next hop we want to send recovery token question
        #   in case that the dead client was holding the token the moment he died

        ip, _ = self.next_next_hop_info
        # If we are the only client left we reset the data to the initial state
        print("!!!"*20)
        print(ip, helpers.get_self_ip_address())
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
                s = socket.create_connection((ip, config.getint('NewPredecessorListener', 'Port')))
                self.sending_queue = queue.Queue(maxsize=0)
                self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
                self.message_sender.start()
                self.next_hop_info = self.next_next_hop_info
                # TODO pamiętaj o tym
                # self.next_next_hop_info = None
                # After we connect to a new client we have to check whether the dead client wasn't in posession
                # of token
                self.sending_queue.put(events.TokenReceivedQuestionEvent(self.last_token))
            except Exception as e:
                print(e)

        ip, port = self.next_hop_info
        try:
            s = socket.create_connection((ip, port))
            self.sending_queue = queue.Queue(maxsize=0)
            self.message_sender = MessageSender(self.event_queue, self.sending_queue, s)
            self.message_sender.start()
        except ConnectionRefusedError as e:
            connect_to_next_next_hop(self)

    ############################################################################################
    #
    #                                      Event handlers
    ############################################################################################
    def handle_new_client_request(self, event):
        first_client = not self.next_hop_info
        # When we detect a new client connecting we want to;
        # 1.Send him the initial data over the connection we already established
        # 2.Connect to him as a predecessor

        # Gather the initial board state
        marked_spots = [(x, y) for x in range(len(self.board_state)) for y in range(len(self.board_state[x])) if self.board_state[x][y]]

        # If we have next hop information we send it, if we do not have we are the first client so we send our
        # information as the first hop information
        next_hop = (helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port')) if first_client else self.next_hop_info
        # If we are the first client next next hop is None
        response = events.NewClientResponseEvent(next_hop, self.next_next_hop_info, marked_spots)
        message = helpers.event_to_message(response)
        message_size = (len(message))
        print(message_size)
        message_size = message_size.to_bytes(8, byteorder='big')
        print(message_size)
        event.data['connection'].send(message_size)
        event.data['connection'].send(message)


        try:
            message = event.data['connection'].recv(8)
        except Exception as ex:
            if (message == b''):
                # Only case when we have a succesfull read of 0 bytes is when other socket shutdowns normally
                pass
            else:
                #Client did not initializ correctly so we abort the process
                return

        # If we are not the first client we have to update our next next hop to our previous next hop
        if not first_client:
            self.next_next_hop_info = self.next_hop_info
        else:
            self.next_next_hop_info = (
                helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port')
            )

        # Then we update our next hop info with the newest client request
        self.next_hop_info = event.data['address']


        # We stop current message sender if it exists
        if self.message_sender:
            self.message_sender.stop()

        ip, _ = self.next_hop_info
        logger.info("Establishing connection to: {} {}".format(ip, config.getint('NewPredecessorListener', 'Port')))
        # We establish a new connection and a new message sender
        print("Next hop info", self.next_hop_info)
        connection = socket.create_connection((ip, config.getint('NewPredecessorListener', 'Port')), 100)
        self.sending_queue = queue.Queue(maxsize=0)
        self.message_sender = MessageSender(self.event_queue, self.sending_queue, connection)
        self.message_sender.start()
        # for spot in marked_spots2:
        #   x, y = spot
        #   self.sending_queue.put(events.DrawingInformationEvent(self.uuid, helpers.get_current_timestamp(), x, y, 1, False))
        # If this is the first client we start the token pass
        if first_client:
            self.sending_queue.put(events.TokenPassEvent(self.last_token))


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
                self.sending_queue.put(event)

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
        # Special case if we have only 2 nodes left
        if self.predecessor[0] == self.next_hop_info[0]:
          self.sending_queue.put(events.NewNextNextHop(self.predecessor, self_address))
        else:
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
        # We are the recipient of the message
        # print(event.data)
        # print(self.next_hop_info)
        post_destination_ip, _ = event.data['destination_next_hop']
        next_hop_ip, _ = self.next_hop_info
        print("###"*40)
        print(post_destination_ip == next_hop_ip)
        print(event.data)
        # print(post_destination_ip, next_hop_ip)
        print(post_destination_ip == next_hop_ip)
        if post_destination_ip == next_hop_ip:
            self.next_next_hop_info = event.data['new_address']
            print(self.next_next_hop_info)
        else:
            self.sending_queue.put(event)

        # print(self.next_next_hop_info)

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
            self.sending_queue.put(events.TokenPassEvent(event.data['token'] + 1))

    def handle_dummy_message_event(self, event):
        if helpers.get_self_ip_address() != event.data['ip']:
            return
        else:
            if self.sending_queue:
                self.sending_queue.put(event)