import sys

import pynvim
from PySide6.QtWidgets import QApplication

_colors = ["hsl(184, 96%, {}%)", "hsl(64, 96%, {}%)", "hsl(136, 96%, {}%)"]
_color_non_persistent = "hsl(341, 96%, {}%)"

colemak_keys = {
    # move to neighbors
    "<A-S-n>": "move down",
    "<A-S-e>": "move up",
    "<A-S-m>": "move left",
    "<A-S-i>": "move right",
    # create a child of the current text box, down of it
    "<A-n>": "create child down",
    # create a child of the current text box, right of it
    "<A-i>": "create child right",
    # catch a child and insert it down
    "<A-C-n>": "catch child down",
    # catch a child and insert it right
    "<A-C-i>": "catch child right",
    # zooming
    "<C-j>": "zoom down",
    "<C-y>": "zoom up",
    # resizing box
    "<C-l>": "grow box",
    "<C-u>": "shrink box",
}


class Config:
    autoshrink = True
    text_width = 300
    text_max_height = text_width * 1.618
    initial_position = (500, 40)
    text_gap = 6
    starting_box_scale = 0.7
    # font sizes for each indent level
    font_sizes = [12, 12, 12, 12, 10, 10, 10, 10, 8, 8, 8, 8]

    # whether to change zoom level only on jumps to a neighbor text
    track_jumps_on_neighbor_moves = False

    # closer to 1 is slower (must be larger than 1)
    scroll_speed = 1.0005
    # invert scroll direction
    scroll_invert = True
    # speed of zooming left/right with keys (must be larger than 1)
    key_zoom_speed = 3

    # https://blog.depositphotos.com/15-cyberpunk-color-palettes-for-dystopian-designs.html
    border_colors = [c.format(15) for c in _colors]
    text_colors = [c.format(80) for c in _colors]
    selection_colors = [c.format(23) for c in _colors]
    non_persistent_dir_color = _color_non_persistent.format(28)
    non_persistent_text_color = _color_non_persistent.format(80)
    non_persistent_selection_color = _color_non_persistent.format(23)
    background_color = "#000000"

    leader_key = ","
    # supported single key codes, and single key codes preceded with leader key
    # (note: the order of modifiers must be M-, A-, S-, C-)
    keys = {
        # hop to any text using leap plugin
        ",h": "hop",
        # when in bookmarks window, jump to location of bookmark under cursor
        ",b": "bookmark jump",
        # zoom on the current text box
        ",z": "zoom on current text",
        # custom C-o and C-i, because normal ones create unwanted buffers
        "<C-o>": "jump back",
        "<C-i>": "jump forward",
    }
    keys.update(colemak_keys)

    FPS = 120

    input_on_creation = "- "

    ########################
    _initial_distance = (initial_position[0] ** 2 + initial_position[1] ** 2) ** 0.5
