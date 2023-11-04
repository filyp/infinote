import sys

import pynvim
from PySide6.QtWidgets import QApplication


class Config:
    autoshrink = True
    text_width = 300
    text_max_height = text_width * 1  # * 1.618
    initial_position = (500, 40)
    text_gap = 10
    starting_box_scale = 0.7
    # font sizes for each indent level
    font_sizes = [12, 12, 12, 12, 10, 10, 10, 10, 8, 8, 8, 8]

    # whether to change zoom level only on jumps to a neighbor text
    track_jumps_on_neighbor_moves = True

    # closer to 1 is slower
    scroll_speed = 1.0005
    # invert scroll direction
    scroll_invert = True

    # https://blog.depositphotos.com/15-cyberpunk-color-palettes-for-dystopian-designs.html
    dir_colors = ["#05d9e8", "#d9e805", "#2bbf52"]
    # TODO make this less than a double for stronger color hint:
    text_colors = ["#d7fcfe", "#fcfed7", "#def7e5"]  # double dir_color's HSL
    selection_colors = ["#036c72", "#6d7203", "#175e2b"]  # half dir_color's HSL

    non_persistent_dir_color = "#eb004a"
    non_persistent_text_color = "#ffd6e3"
    non_persistent_selection_color = "#750025"

    background_color = "#000000"

    leader_key = ","
    # supported single key codes, and single key codes preceded with leader key
    # (note: the order of modifiers murt be M-, A-, S-, C-)
    keys = {
        # hop to any text using leap plugin
        ",h": "hop",
        # when in bookmarks window, jump to location of bookmark under cursor
        ",b": "bookmark jump",
        # create a child of the current text box, down of it
        ",<Space>": "create child down",
        # create a child of the current text box, right of it
        ",.": "create child right",
        # move to the down child
        "<A-S-n>": "move down",
        "<A-S-e>": "move up",
        "<A-S-m>": "move left",
        "<A-S-i>": "move right",
        # custom C-o and C-i, because normal ones create unwanted buffers
        "<C-o>": "jump back",
        "<C-i>": "jump forward",
    }

    ########################
    _initial_distance = (initial_position[0] ** 2 + initial_position[1] ** 2) ** 0.5
