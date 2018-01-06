import tkinter as tk
import tkinter.font
import configparser
from config_wrapper import config
from threading import Thread
from queue import *
from events import InnerDrawingInformationEvent
import logging
import helpers

logger = logging.getLogger(__name__)

class Painter:
    # Tracks whether left mouse is down
    left_but = "up"

    # x and y positions for drawing with pencil
    x_pos, y_pos = None, None

    # Tracks x & y when the mouse is clicked and released
    x1_line_pt, y1_line_pt, x2_line_pt, y2_line_pt = None, None, None, None

    # ---------- CATCH MOUSE UP ----------

    def left_but_down(self, event=None):
        self.left_but = "down"
        self.begin_draw = True
        # Set x & y when mouse is clicked
        self.x1_line_pt = event.x
        self.y1_line_pt = event.y

    def left_but_up(self, event=None):
        self.left_but = "up"

        # Reset the line
        self.x_pos = None
        self.y_pos = None

        # Set x & y when mouse is released
        self.x2_line_pt = event.x
        self.y2_line_pt = event.y

    def motion(self, event=None):
        if event is not None and self.left_but == 'down':
            # Make sure x and y have a value
            # if self.x_pos is not None and self.y_pos is not None:
            color = 0 if self.drawing_color == 'white' else 1

            self.master_queue.put(InnerDrawingInformationEvent(helpers.get_current_timestamp(), event.x, event.y, color, self.begin_draw))
            self.begin_draw = False

    def __init__(self, paint_queue, master_queue):
        self.master = tkinter.Tk()
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.paint_queue = paint_queue
        self.master_queue = master_queue
        self.drawing_area = tkinter.Canvas(self.master, bg='white', width=config.getint('Tkinter', 'CanvasX'), height=config.getint('Tkinter', 'CanvasY'))
        self.drawing_area.pack()
        self.drawing_button = tkinter.Button(self.master, text="Draw/Erase", command=self.change_drawing_color)
        self.drawing_button.pack(side=tkinter.LEFT, expand=tkinter.TRUE)
        self.drawing_button = tkinter.Button(self.master, text="Take board")
        self.drawing_button.pack(side=tkinter.RIGHT, expand=tkinter.TRUE)
        self.drawing_area.bind("<Motion>", self.motion)
        self.drawing_area.bind("<ButtonPress-1>", self.left_but_down)
        self.drawing_area.bind("<ButtonRelease-1>", self.left_but_up)
        self.running = True
        self.drawing_color = 'black'
        self.begin_draw = False

    def start_drawing(self):
        while self.running:
            self.make_mouse_events()
            while not self.paint_queue.empty():
                (x, y, color, begin) = self.paint_queue.get()
                color = 'white' if color == 0 else 'black'
                if (not self.x_pos and not self.y_pos):
                    self.x_pos = x
                    self.y_pos = y

                if begin:
                    self.x_pos = x
                    self.y_pos = y

                # self.drawing_area.create_line(self.x_pos, self.y_pos, data['x'], data['y'], fill=color)
                self.drawing_area.create_rectangle((x, y)*2, )
                self.x_pos = x
                self.y_pos = y

    def make_mouse_events(self):
        if self.running:
            self.master.update_idletasks()
            self.master.update()

    def change_drawing_color(self):
        self.drawing_color = 'white' if self.drawing_color == 'black' else 'black'

    def on_closing(self):
        global running
        running = False
