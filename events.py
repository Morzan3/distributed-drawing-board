from enum import Enum


class NewClientEventType(Enum):
    NEW_CLIENT_REQUEST = 1


class NewClientEvent:
    def __init__(self, data):
        self.data = data


class NewClientRequestEvent(NewClientEvent):
    def __init__(self, data):
        NewClientEvent.__init__(data)
        self.event_type = NewClientEventType.NEW_CLIENT_REQUEST
