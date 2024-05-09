import re

from PySide6.QtGui import QColor, QFont


# mod = "A"  # main modifier used for the keybindings
mod = "C"  # todo change back

# (note: the order of modifiers must be M-, A-, S-, C-)
qwerty_keys = {
    # move to neighbors
    f"<{mod}-j>": "move down",
    f"<{mod}-k>": "move up",
    f"<{mod}-h>": "move left",
    f"<{mod}-l>": "move right",
    # create a child of the current text box, down of it
    "<A-S-j>": "create child down",
    # create a child of the current text box, right of it
    "<A-S-l>": "create child right",
    # catch a child and insert it down
    "<M-A-j>": "catch child down",
    # catch a child and insert it right
    "<M-A-l>": "catch child right",
    # zooming
    f"<{mod}-y>": "zoom down",
    f"<{mod}-o>": "zoom up",
    # resizing box
    f"<{mod}-i>": "grow box",
    f"<{mod}-u>": "shrink box",
}
colemak_keys = {
    # move to neighbors
    f"<{mod}-n>": "move down",
    f"<{mod}-e>": "move up",
    f"<{mod}-m>": "move left",
    f"<{mod}-i>": "move right",
    # create a child of the current text box, down of it
    "<A-S-n>": "create child down",
    # create a child of the current text box, right of it
    "<A-S-i>": "create child right",
    # catch a child and insert it down
    "<M-A-n>": "catch child down",
    # catch a child and insert it right
    "<M-A-i>": "catch child right",
    # zooming
    f"<{mod}-j>": "zoom down",
    f"<{mod}-y>": "zoom up",
    # resizing box
    f"<{mod}-u>": "grow box",
    f"<{mod}-l>": "shrink box",
}


class Config:
    # if False, you will be kept in insert mode and so saved from vimming
    # todo change back
    # vim_mode = False
    vim_mode = True

    autoshrink = True
    text_width = 400
    text_max_height = text_width  # * 1.618
    initial_position = (500, 40)
    text_gap = 6
    starting_box_scale = 0.75

    # closer to 1 is slower (must be larger than 1)
    scroll_speed = 1.0005
    # invert scroll direction
    scroll_invert = False
    # speed of zooming left/right with keys (must be larger than 1)
    key_zoom_speed = 3
    # # whether to allow resizing text boxes with mouse wheel
    # scroll_can_resize_text = False
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
    editor_width_ratio = 1 / 3  # part of screen width for the editor
    sign_color = QColor.fromHsl(289, 100, 38)

    # note: in the future leader_key will probably be removed to simplify
    leader_key = ","
    # supported single key codes, and single key codes preceded with leader key
    # (note: the order of modifiers must be M-, A-, S-, C-)
    # keys that cannot be used: hjkl yuio men p
    keys = {
        "<C-w>": "delete text",
        # Teleport to any text using leap plugin
        f"<{mod}-t>": "hop",
        # Center view on the current text box
        f"<{mod}-c>": "center on current text",
        # zoom in, pushing the current box to the Right
        f"<{mod}-r>": "maximize on current text",
        # custom C-o andC-i, because normal ones create unwanted buffers
        # "<C-o>": "jump back",
        # "<C-i>": "jump forward",
        f"<{mod}-Left>": "jump back",
        f"<{mod}-Right>": "jump forward",
        # when in bookmarks window, jump to location of bookmark under cursor
        f"<{mod}-b>": "bookmark jump",
        # todo remove this option and this functionality?
        # # toggle editor View
        # f"<{mod}-v>": "toggle editor",
    }
    # todo change back
    # keys.update(qwerty_keys)
    keys.update(colemak_keys)

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
