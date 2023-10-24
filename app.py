import tkinter as tk
from threading import Thread
from time import sleep, time

from data_structure import Node
from global_objects import nodes, nvim, root
from key_handling import key_translate

# todo:
# custom wrappint, extending height
# saving
# scrolling
# resizing of widgets when i scroll on them
# to be general, draw highlights, by highlighting per line


class MouseHandler:
    def __init__(self):
        self.is_dragging = False
        self.clicked_widget = None
        self.dragging_start = None
        self.widget_start_pos = None

    def bind_to_widget(self, widget):
        widget.bind("<B1-Motion>", self.on_node_drag)
        widget.bind("<Button-4>", self.on_node_scroll)
        widget.bind("<Button-5>", self.on_node_scroll)
        # for Windows:
        # widget.bind("<MouseWheel>", self.on_node_scroll)

    def on_click(self, event):
        self.clicked_widget = event.widget
        self.dragging_start = (event.x_root, event.y_root)
        self.widget_start_pos = (event.widget.winfo_x(), event.widget.winfo_y())

    def on_node_drag(self, event):
        self.is_dragging = True

        if type(self.clicked_widget) == tk.Text:
            # move text widget
            new_x = self.widget_start_pos[0] + event.x_root - self.dragging_start[0]
            new_y = self.widget_start_pos[1] + event.y_root - self.dragging_start[1]
            self.clicked_widget.place(x=new_x, y=new_y)

        return "break"

    def on_release(self, event):
        if not self.is_dragging:
            # print("Clicked at ", event.x, event.y)
            node = Node(x=event.x, y=event.y)
            self.bind_to_widget(node.text_widget)
            nodes.append(node)
        self.is_dragging = False

    def on_node_scroll(self, event):
        widget = event.widget
        if event.num == 4:
            # enlarge
            pass
        elif event.num == 5:
            # shrink
            pass


def handle_keys(event):
    key = key_translate(event)
    match key:
        case None:
            return
        case "<C-n>":
            nvim.command("bn")
        case "<C-e>":
            nvim.command("bp")
        case _:
            nvim.input(key)


root.bind("<KeyPress>", handle_keys)

mouse_handler = MouseHandler()
root.bind("<ButtonPress-1>", mouse_handler.on_click)
root.bind("<ButtonRelease-1>", mouse_handler.on_release)


# on window close, just gracefully stop the main loop
stop = False
root.protocol("WM_DELETE_WINDOW", lambda: globals().update({"stop": True}))

# create first text field
node = Node(x=50, y=50, create_new_buffer=False)
mouse_handler.bind_to_widget(node.text_widget)
nodes.append(node)


nodes[0].buffer[:] = ["hello", "world", "this", "is", "a", "test", "buffer"]


while not stop:
    root.update_idletasks()
    root.update()

    root.focus_set()  # unfocus text widgets, so they don't catch keypresses
    # print(nvim.api.list_bufs())
    # print(nvim.current.buffer)

    sleep(0.016)

    if nvim.api.get_mode()["blocking"]:
        continue

    for node in nodes:
        node.update(nvim)
