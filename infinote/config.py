import sys

import pynvim
from PySide6.QtWidgets import QApplication


class Config:
    autoshrink = True
    text_width = 400
    text_max_height = 400 * 1.618
    initial_position = (500, 40)
    text_gap = 10
    starting_box_scale = 0.6
    # font sizes for each indent level
    font_sizes = [12, 12, 12, 12, 10, 10, 10, 10, 8, 8, 8, 8]

    leader_key = ","
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

    # closer to 1 is slower
    scroll_speed = 1.0005
    # invert scroll direction
    scroll_invert = True

    # FPS = 60