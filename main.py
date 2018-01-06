import threading
import time
import json
import queue
from time_thread import TimeSynchronizer
from new_client_listener import NewClientListener
from new_predecessor_listener import NewPredecessorListener
from model import ModelThread

import logging
logger = logging.getLogger(__name__)

def connect_to_existing_client(connection):
    data = connection.recv(1024)
    print(json.loads(data.decode('utf-8')))
    # main queue holding network events
    main_queue = queue.Queue(maxsize=0)

    # Retrieving time from a ntp server thread
    time_offset = [0]
    time_synchronizer = TimeSynchronizer(time_offset)
    time_synchronizer.start()

    # Listening for a new client thread
    new_client_listener = NewClientListener(main_queue)
    new_client_listener.start()

    # Listening for a new predecessor thread
    new_predecessor_listener = NewPredecessorListener(main_queue)
    new_predecessor_listener.start()


def start_new_group():
    # main queue holding network events
    main_queue = queue.Queue(maxsize=0)

    # Retrieving time from a ntp server thread
    time_offset = [0]
    time_synchronizer = TimeSynchronizer(time_offset)
    time_synchronizer.start()

    # Listening for a new client thread
    new_client_listener = NewClientListener(main_queue)
    new_client_listener.start()

    # Listening for a new predecessor thread
    new_predecessor_listener = NewPredecessorListener(main_queue)
    new_predecessor_listener.start()

    model = ModelThread(main_queue)
    model.start()

