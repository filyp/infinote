import sys

import pynvim
from PySide6.QtWidgets import QApplication


class Config:
    autoshrink = True
    text_width = 300
    initial_position = (500, 40)
    # font sizes for each indent level
    font_sizes = [12, 12, 12, 12, 10, 10, 10, 10, 8, 8, 8, 8]
    leader_key = ","
    # FPS = 60
    text_gap = 10
    starting_box_scale = 0.9

    # command keys after leader key
    #
    # hop to any text using leap plugin
    hop_key = "h"
    # when in bookmarks window, jump to location of bookmark under cursor
    bookmark_jump_key = "b"
    # create a child of the current text box, down of it
    create_child_down_key = "/"
    # create a child of the current text box, right of it
    create_child_right_key = "o"
