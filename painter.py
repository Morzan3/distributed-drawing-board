import tkinter as tk
import tkinter.font
import configparser
from config_wrapper import config
from threading import Thread
from queue import *
from events import InnerDrawingInformationEvent, InnerWantToEnterCriticalSection
import logging
import helpers
from enum import Enum

logger = logging.getLogger(__name__)

class DrawingQueueEvent(Enum):
    DRAWING = 1
    BOARD_CLOSED = 2
    BOARD_OPEN = 3
    BOARD_CONTROLLED = 4

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
          if self.x_pos is not None and self.y_pos is not None:
            points = self.line(self.x_pos, self.y_pos, event.x, event.y)
            self.master_queue.put(InnerDrawingInformationEvent(helpers.get_current_timestamp(), points, color))
          
          self.x_pos = event.x
          self.y_pos = event.y

    def __init__(self, paint_queue, master_queue):
        self.master = tkinter.Tk()
        self.critical_section_string = tk.StringVar()
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.paint_queue = paint_queue
        self.master_queue = master_queue
        self.drawing_area = tkinter.Canvas(self.master, bg='white', width=config.getint('Tkinter', 'CanvasX'), height=config.getint('Tkinter', 'CanvasY'))
        self.drawing_area.pack()
        self.drawing_button = tkinter.Button(self.master, text="Draw/Erase", command=self.change_drawing_color)
        self.drawing_button.pack(side=tkinter.LEFT, expand=tkinter.TRUE)
        self.drawing_button = tkinter.Button(self.master, text="Take board", command=self.want_to_enter_critial_section)
        self.drawing_button.pack(side=tkinter.RIGHT, expand=tkinter.TRUE)
        self.critical_section = tkinter.Label(self.master, textvariable=self.critical_section_string)
        self.critical_section.pack(side=tk.RIGHT, expand=tkinter.TRUE)
        self.drawing_area.bind("<Motion>", self.motion)
        self.drawing_area.bind("<ButtonPress-1>", self.left_but_down)
        self.drawing_area.bind("<ButtonRelease-1>", self.left_but_up)
        self.running = True
        self.drawing_color = 'black'
        self.critical_section_string.set('Board Open')

    def start_drawing(self):
        while self.running:
            self.make_mouse_events()
            while not self.paint_queue.empty():
                e = self.paint_queue.get()
                if e['type'] == DrawingQueueEvent.DRAWING:
                    points, color = e['data']
                    color = 'white' if color == 0 else 'black'


                    for point in points: 
                    # self.drawing_area.create_line(self.x_pos, self.y_pos, data['x'], data['y'], fill=color)
                      x, y = point
                      self.drawing_area.create_rectangle((x, y)*2, outline=color)
                elif e['type'] == DrawingQueueEvent.BOARD_CLOSED:
                    self.critical_section_string.set("Board closed")
                elif e['type'] == DrawingQueueEvent.BOARD_OPEN:
                    self.critical_section_string.set("Board open")
                elif e['type'] == DrawingQueueEvent.BOARD_CONTROLLED:
                    self.critical_section_string.set("Board yours")
                else:
                    raise Exception("Wrong event type")

    def make_mouse_events(self):
        if self.running:
            self.master.update_idletasks()
            self.master.update()

    def change_drawing_color(self):
        self.drawing_color = 'white' if self.drawing_color == 'black' else 'black'

    def on_closing(self):
        global running
        running = False

    def want_to_enter_critial_section(self):
        self.master_queue.put(InnerWantToEnterCriticalSection())


    def line(self, x0, y0, x1, y1):
      points_in_line = []
      dx = abs(x1 - x0)
      dy = abs(y1 - y0)
      x, y = x0, y0
      sx = -1 if x0 > x1 else 1
      sy = -1 if y0 > y1 else 1
      if dx > dy:
          err = dx / 2.0
          while x != x1:
              points_in_line.append((x, y))
              err -= dy
              if err < 0:
                  y += sy
                  err += dx
              x += sx
      else:
          err = dy / 2.0
          while y != y1:
              points_in_line.append((x, y))
              err -= dx
              if err < 0:
                  x += sx
                  err += dy
              y += sy
      points_in_line.append((x, y))
      return points_in_line