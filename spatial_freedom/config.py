import sys

import pynvim
from PySide6.QtWidgets import QApplication


class Config:
    autoshrink = True
    text_width = 200
    initial_position = (500, 40)
    font_size = 7
    leader_key = ","
    # FPS = 60
    text_gap = 10

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
