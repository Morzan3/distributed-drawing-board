from enum import Enum


class EventType(Enum):
    NEW_CLIENT_REQUEST = 1
    NEW_CLIENT_RESPONSE = 2
    NEW_PREDECESSOR_REQUEST = 3
    PREDECESSOR_MESSAGE = 4

class Event:
    def __init__(self):
        pass

class NewClientRequestEvent(Event):
    def __init__(self, connection, address):
        Event.__init__(self)
        self.connection = connection
        self.address = address
        self.event_type = EventType.NEW_CLIENT_REQUEST

class NewClientResponseEvent(Event):
    def __init__(self, next_hop, next_next_hop):
        Event.__init__(self)
        self.next_hop = next_hop
        self.next_next_hop = next_next_hop
        self.event_type = EventType.NEW_CLIENT_REQUEST


class NewPredecessorRequestEvent(Event):
    def __init__(self, data):
        Event.__init__(self, data)
        self.event_type = EventType.NEW_PREDECESSOR_REQUEST


class PredecessorMessageEvent(Event):
    def __init__(self, data):
        Event.__init__(self, data)
        self.event_type = EventType.PREDECESSOR_MESSAGE
