import tkinter as tk
import tkinter.font
import configparser
from config_wrapper import config
from threading import Thread
from queue import *

drawing_queue = Queue()


class EventMaker:
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
            if self.x_pos is not None and self.y_pos is not None:
                event.widget.create_line(self.x_pos, self.y_pos, event.x, event.y, smooth=tkinter.TRUE)
                drawing_queue.put((event, self.x_pos, self.y_pos))  #

            self.x_pos = event.x
            self.y_pos = event.y
            print("x = " + str(event.x) + "\ty = " + str(event.y))

    def __init__(self, master):
        self.master = master
        self.drawing_area = tkinter.Canvas(self.master, bg='white', width=config.getint('Tkinter', 'CanvasX'), height=config.getint('Tkinter', 'CanvasY'))
        self.drawing_area.pack()
        self.drawing_button = tkinter.Button(self.master, text="Draw/Erase")
        self.drawing_button.pack(side=tkinter.LEFT, expand=tkinter.TRUE)
        self.drawing_button = tkinter.Button(self.master, text="Take board")
        self.drawing_button.pack(side=tkinter.RIGHT, expand=tkinter.TRUE)
        self.drawing_area.bind("<Motion>", self.motion)
        self.drawing_area.bind("<ButtonPress-1>", self.left_but_down)
        self.drawing_area.bind("<ButtonRelease-1>", self.left_but_up)

    def getrda(self):
        return self.drawing_area


running = True


def on_closing():
    global running
    running = False


def make_mouse_events(root: tkinter.Tk):
    if running:
        root.update_idletasks()
        root.update()


if __name__ == "__main__":
    root = tkinter.Tk()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    paint_app = EventMaker(root)
    drawing_area = paint_app.getrda()
    while running:
        make_mouse_events(root)
        while not drawing_queue.empty():
            (e) = drawing_queue.get()
            e.widget.create_line(e.x, e.y, e.x, e.y, smooth=tkinter.TRUE)
