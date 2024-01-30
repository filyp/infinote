import re

from PySide6.QtGui import QColor, QFont


# (note: the order of modifiers must be M-, A-, S-, C-)
qwerty_keys = {
    # move to neighbors
    "<A-j>": "move down",
    "<A-k>": "move up",
    "<A-h>": "move left",
    "<A-l>": "move right",
    # create a child of the current text box, down of it
    "<M-A-j>": "create child down",
    # create a child of the current text box, right of it
    "<M-A-l>": "create child right",
    # catch a child and insert it down
    "<A-S-j>": "catch child down",
    # catch a child and insert it right
    "<A-S-l>": "catch child right",
    # zooming
    "<A-y>": "zoom down",
    "<A-o>": "zoom up",
    # resizing box
    "<A-u>": "grow box",
    "<A-i>": "shrink box",
}
colemak_keys = {
    # move to neighbors
    "<A-n>": "move down",
    "<A-e>": "move up",
    "<A-m>": "move left",
    "<A-i>": "move right",
    # create a child of the current text box, down of it
    "<M-A-n>": "create child down",
    # create a child of the current text box, right of it
    "<M-A-i>": "create child right",
    # catch a child and insert it down
    "<A-S-n>": "catch child down",
    # catch a child and insert it right
    "<A-S-i>": "catch child right",
    # zooming
    "<A-j>": "zoom down",
    "<A-y>": "zoom up",
    # resizing box
    "<A-l>": "grow box",
    "<A-u>": "shrink box",
}


class Config:
    autoshrink = True
    text_width = 400
    text_max_height = text_width * 1.618
    initial_position = (500, 40)
    text_gap = 6
    starting_box_scale = 0.75

    # closer to 1 is slower (must be larger than 1)
    scroll_speed = 1.0005
    # invert scroll direction
    scroll_invert = False
    # speed of zooming left/right with keys (must be larger than 1)
    key_zoom_speed = 3
    # whether to allow resizing text boxes with mouse wheel
    scroll_can_resize_text = False
    # when jumping to neighbor, if no text is connected in chosen direction,
    # jump to closest disconnected text in that direction
    allow_disconnected_jumps = True

    # whether to change zoom level on jumps to a neighbor text
    track_jumps_on_neighbor_moves = False

    # https://blog.depositphotos.com/15-cyberpunk-color-palettes-for-dystopian-designs.html
    background_color = "#000000"
    border_brightness = "15%"
    text_brightness = "80%"
    selection_brightness = "23%"
    non_persistent_hue = 341
    sign_color = QColor.fromHsl(289, 100, 38)

    leader_key = ","
    # supported single key codes, and single key codes preceded with leader key
    # (note: the order of modifiers must be M-, A-, S-, C-)
    keys = {
        # hop to any text using leap plugin
        ",h": "hop",
        # when in bookmarks window, jump to location of bookmark under cursor
        ",b": "bookmark jump",
        # center view on the current text box
        ",c": "center on current text",
        # zoom in as much as possible, while keeping the current text box in view
        ",m": "maximize on current text",
        # custom C-o and C-i, because normal ones create unwanted buffers
        "<C-o>": "jump back",
        "<C-i>": "jump forward",
    }
    keys.update(qwerty_keys)

    # relevant for zooming and resizing with keys
    FPS = 180

    input_on_creation = "- "

    # font sizes for each indent level
    # font_sizes = [16] * 4 + [14] * 4 + [11] * 4
    # font_sizes = [15] * 4 + [14] * 4 + [11] * 4
    # font_sizes = [14] * 4 + [11] * 4 + [8] * 4
    font_sizes = [14] * 4 + [11] * 4 + [11] * 4
    # font_sizes = [11] * 4 + [8] * 4 + [6] * 4
    # some font sizes cause indent problems:
    # note that the problems also depent on the intended indent of that font
    # the combinations above are one of the very few that work well, so it's
    # recommended to just choose one of those
    # good values for first indent lvl: 16, 15, 14, 11
    # for the second indent level: 14, 11, 8, 6
    # for the third indent level: 14, 11, 8, 6, 5

    # when centering or maximizing on a text, this defines min gap left to win border
    min_gap_win_edge = 0.02

    ########################
    # don't tweak those - those are automatic calculations
    _initial_distance = (initial_position[0] ** 2 + initial_position[1] ** 2) ** 0.5

    fonts = [QFont("monospace", fs) for fs in font_sizes]
