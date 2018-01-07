from enum import Enum


class EventType(Enum):
    NEW_CLIENT_RESPONSE = 2
    NEW_PREDECESSOR_REQUEST = 3
    PREDECESSOR_MESSAGE = 4
    DRAWING_INFORMATION = 5
    ENTERED_CRITICAL_SECTION = 6
    LEAVING_CRITICAL_SECTION = 7
    TOKEN_PASS = 8
    SET_NEW_NEXT_NEXT_HOP = 9
    TOKEN_RECEIVED_QUESTION = 10


class InnerEventType(Enum):
    DRAWING_INFORMATION = 100
    WANT_TO_ENTER_CRITICAL_SECTION = 101
    LEAVING_CRITICAL_SECTION = 102
    NEXT_HOP_BROKEN = 103
    NEW_CLIENT_REQUEST = 104


class Event:
    def __init__(self):
        pass

class InnerNewClientRequestEvent(Event):
    def __init__(self, connection, address):
        Event.__init__(self)
        self.data = {
            'connection': connection,
            'address': address
        }
        self.event_type = EventType.NEW_CLIENT_REQUEST

class NewClientResponseEvent(Event):
    def __init__(self, next_hop, next_next_hop, board_state):
        Event.__init__(self)
        self.data = {
            'next_hop': next_hop,
            'next_next_hop': next_next_hop,
            'board_state': board_state
        }
        self.event_type = EventType.NEW_CLIENT_RESPONSE


class NewPredecessorRequestEvent(Event):
    def __init__(self, data):
        Event.__init__(self)
        self.data = data
        self.event_type = EventType.NEW_PREDECESSOR_REQUEST


class PredecessorMessageEvent(Event):
    def __init__(self, data):
        Event.__init__(self)
        self.data = data
        self.event_type = EventType.PREDECESSOR_MESSAGE


class DrawingInformationEvent(Event):
    def __init__(self, client_uuid, timestamp, x, y, color, begin):
        Event.__init__(self)
        self.data = {
            'x': x,
            'y': y,
            'color': color,
            'begin': begin,
            'client_uuid': client_uuid,
            'timestamp': timestamp
        }
        self.event_type = EventType.DRAWING_INFORMATION

class EnteredCriticalSectionEvent(Event):
    def __init__(self, timestamp, client_uuid):
        Event.__init__(self)
        self.data = {
            'timestamp': timestamp,
            'client_uuid': client_uuid
        }
        self.event_type = EventType.ENTERED_CRITICAL_SECTION

class LeavingCriticalSectionEvent(Event):
    def __init__(self, timestamp, client_uuid):
        Event.__init__(self)
        self.data = {
            'timestamp': timestamp,
            'client_uuid': client_uuid
        }
        self.event_type = EventType.LEAVING_CRITICAL_SECTION

class TokenPassEvent(Event):
    def __init__(self, token):
        Event.__init__(self)
        self.data = {
            'token': token
        }
        self.event_type = EventType.TOKEN_PASS

# When a new client connects we want to send the information to the previous hop of the
# client we are connecting to that we are his new next next hop
class NewNextNextHop(Event):
    def __init__(self, new_address, destination_next_hop):
        Event.__init__(self)
        self.data = {
            'new_address': new_address,
            'destination_next_hop': destination_next_hop
        }
        self.event_type = EventType.SET_NEW_NEXT_NEXT_HOP


class TokenReceivedQuestionEvent(Event):
    def __init__(self, token):
        Event.__init__(self)
        self.data = {
            'token': token
        }

        self.event_type = EventType.TOKEN_RECEIVED_QUESTION


#####################################################################################
#                                  Inner events
#####################################################################################

class InnerNewClientRequestEvent(Event):
    def __init__(self, connection, address):
        Event.__init__(self)
        self.data = {
            'connection': connection,
            'address': address
        }
        self.event_type = InnerEventType.NEW_CLIENT_REQUEST

class InnerDrawingInformationEvent(Event):
    def __init__(self, timestamp, x, y, color, begin):
        Event.__init__(self)
        self.timestamp = timestamp
        self.data = {
            'x': x,
            'y': y,
            'color': color,
            'begin': begin,
            'timestamp': timestamp
        }
        self.event_type = InnerEventType.DRAWING_INFORMATION

class InnerWantToEnterCriticalSection(Event):
    def __init__(self):
        Event.__init__(self)
        self.event_type = InnerEventType.WANT_TO_ENTER_CRITICAL_SECTION

class InnerLeavingCriticalSection(Event):
    def __init__(self):
        Event.__init__(self)
        self.event_type = InnerEventType.LEAVING_CRITICAL_SECTION

class InnerNextHopBroken(Event):
    def __init__(self):
        Event.__init__(self)
        self.event_type = InnerEventType.NEXT_HOP_BROKEN
