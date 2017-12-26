import socket
from events import NewClientRequestEvent


class NewClientListener:
    def __init__(self, event_queue, listening_port):
        self.event_queue = event_queue
        self.listening_port = listening_port

    def listen_for_new_clients(self):
        listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listening_socket.bind(('localhost', self.listening_port))
        listening_socket.listen()
        print('Server is listening for new clients on port: {}'.format(self.listening_port))
        while True:
            connection, client_address = listening_socket.accept()
            new_connection_data = {connection: connection, client_address: client_address}
            self.event_queue.put(NewClientRequestEvent(new_connection_data))


def initialize_client_listener(event_queue, listening_port):
    new_client_listener = NewClientListener(event_queue, listening_port)
    new_client_listener.listen_for_new_clients()
