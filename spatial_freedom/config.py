import sys

import pynvim
from PySide6.QtWidgets import QApplication


class Config:
    autoshrink = True
    text_width = 300
    initial_position = (500, 40)
    font_size = 12
    leader_key = ","
    # FPS = 60

    # command keys after leader key
    #
    # hop to any text using leap plugin
    hop_key = "h"
    # when in bookmarks window, jump to location of bookmark under cursor
    bookmark_jump_key = "b"
