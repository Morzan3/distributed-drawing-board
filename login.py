import sys
import tkinter as tk
import tkinter.font
import socket
from tkinter import messagebox
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

from main import connect_to_existing_client, start_new_group
import config_wrapper



if len(sys.argv) > 1 and sys.argv[1] == '0':
    config_wrapper.initialize(0)
else:
    config_wrapper.initialize(1)



# Section only for testing purpose
if len(sys.argv) > 1 and sys.argv[1] == '0':
    start_new_group()
else:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', config_wrapper.config.getint('NewClientConnector', 'Port')))
    connect_to_existing_client(s)

class LoginPanel(tk.Frame):
    def __init__(self, parent=None):
        self.parent = parent
        self.parent.title("Connect")
        self.parent.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.ip_address = tk.StringVar()
        self.ip_address.set('localhost')
        self.make_widgets()

    def make_widgets(self):
        self.top_frame = tk.Frame(root)
        self.top_frame.pack(side=tkinter.TOP)

        self.bottom_frame = tk.Frame(root)
        self.bottom_frame.pack(side=tkinter.BOTTOM)

        self.IP_label = tk.Label(self.top_frame, text="Ip address")
        self.IP_label.pack(side=tk.LEFT)

        self.IP_entry = tk.Entry(self.top_frame, bd=5, textvariable=self.ip_address)
        self.IP_entry.pack(side=tk.RIGHT)

        self.join_button = tk.Button(self.bottom_frame, text="Join", command=self.print_ip)
        self.join_button.pack(side=tk.LEFT, expand=tk.TRUE, fill=tk.X)

        self.start_new = tk.Button(self.bottom_frame, text="Start new group", command=self.start_new_group)
        self.start_new.pack(side=tk.RIGHT, expand=tk.TRUE, fill=tk.X)
        self.parent.mainloop()

    def on_closing(self):
        exit()

    def print_ip(self):
        if self.ip_address.get() == '':
            logger.info('Connecting to existing client')
            connect_to_existing_client()
            self.parent.destroy()
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect((self.ip_address.get(), config_wrapper.config.getint('NewClientConnector', 'Port')))
                connect_to_existing_client(s)
                self.parent.destroy()
            except Exception as e:
                logger.error(e)
                tk.messagebox.showinfo("ERROR", "No server listening on this address")

    def start_new_group(self):
        start_new_group()
        self.parent.destroy()


# if __name__ == "__main__":
    # root = tk.Tk()
    # root.eval('tk::PlaceWindow %s center' % root.winfo_pathname(root.winfo_id()))
    # panel = LoginPanel(root)
