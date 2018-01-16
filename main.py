import threading
import time
import json
import queue
from time_thread import TimeSynchronizer
from new_client_listener import NewClientListener
from new_predecessor_listener import NewPredecessorListener
from model import ModelThread
from painter import Painter
import helpers
from config_wrapper import config
import events

import logging
logger = logging.getLogger(__name__)

def connect_to_existing_client(connection):
    # main queue holding network events
    main_queue = queue.Queue(maxsize=0)
    paint_queue = queue.Queue(maxsize=0)

    # Retrieving time from a ntp server thread
    time_offset = [0]
    helpers.initialize_offset(time_offset)
    time_synchronizer = TimeSynchronizer(time_offset)
    time_synchronizer.start()

    # Listening for a new client thread
    new_client_listener = NewClientListener(main_queue)
    new_client_listener.start()

    # Listening for a new predecessor thread
    new_predecessor_listener = NewPredecessorListener(main_queue)
    new_predecessor_listener.start()

    # We send the client request containing our data so anothe rclient could connect as a predecessor
    new_client_request = events.NewClientRequestEvent((helpers.get_self_ip_address(), config.getint('NewPredecessorListener', 'Port')))
    message = helpers.event_to_message(new_client_request)
    message_size = (len(message)).to_bytes(8, byteorder='big')
    connection.send(message_size)
    connection.send(message)

    # After we send the request we are waiting for the response with init_data
    message_size = connection.recv(8)
    message_size = int.from_bytes(message_size, byteorder='big')
    data = b''
    while len(data) < message_size:
        packet = connection.recv(message_size - len(data))
        if not packet:
            return None
        data += packet

    init_data = (json.loads(data.decode('utf-8')))['data']
    model = ModelThread(main_queue, paint_queue, time_offset, init_data, connection)
    model.start()

    painter = Painter(paint_queue, main_queue)
    painter.start_drawing()


def start_new_group():
    # main queue holding network events
    main_queue = queue.Queue(maxsize=0)
    paint_queue = queue.Queue(maxsize=0)

    # Retrieving time from a ntp server thread
    time_offset = [0]
    helpers.initialize_offset(time_offset)
    time_synchronizer = TimeSynchronizer(time_offset)
    time_synchronizer.start()

    # Listening for a new client thread
    new_client_listener = NewClientListener(main_queue)
    new_client_listener.start()

    # Listening for a new predecessor thread
    new_predecessor_listener = NewPredecessorListener(main_queue)
    new_predecessor_listener.start()

    model = ModelThread(main_queue, paint_queue, time_offset)
    model.start()

    painter = Painter(paint_queue, main_queue)
    painter.start_drawing()

