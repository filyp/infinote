import re

from PySide6.QtGui import QColor, QFont

# main modifier used for the keybindings
mod = "C"
# mod = "A"  # move to alt if ctrl conflicts for you

# (note: the order of modifiers must be M-, A-, S-, C-)
qwerty_keys = {
    # move to neighbors
    f"<{mod}-j>": "move down",
    f"<{mod}-k>": "move up",
    f"<{mod}-h>": "move left",
    f"<{mod}-l>": "move right",
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
    # zooming
    f"<{mod}-j>": "zoom down",
    f"<{mod}-y>": "zoom up",
    # resizing box
    f"<{mod}-u>": "grow box",
    f"<{mod}-l>": "shrink box",
}


class Config:
    # if False, you will be kept in insert mode and so saved from vimming
    vim_mode = False
    # vim_mode = True
    # which keys to use for navigation and zooming
    keys = qwerty_keys
    # keys = colemak_keys

    # size params
    text_width = 340
    text_max_height = text_width  # * 1.618
    starting_box_scale = 0.9
    # how much smaller the child boxes are compared to their parent on their creation
    child_relative_scale = 0.85
    editor_width_ratio = 1 / 3  # part of screen width for the editor
    text_gap = 6

    # closer to 1 is slower (must be larger than 1)
    scroll_speed = 1.0005
    # invert scroll direction
    scroll_invert = False
    # speed of zooming left/right with keys (must be larger than 1)
    key_zoom_speed = 3
    # # whether to allow resizing text boxes with mouse wheel
    # scroll_can_resize_text = False

    initial_position = (500, 40)
    autoshrink = True
    # whether to change zoom level on jumps to a neighbor text
    track_jumps_on_neighbor_moves = False

    # https://blog.depositphotos.com/15-cyberpunk-color-palettes-for-dystopian-designs.html
    background_color = "#000000"
    border_brightness = 0.4
    text_brightness = 0.8
    selection_brightness = 0.23
    non_persistent_hue = 340
    sign_color = QColor.fromHsl(289, 100, 38)
    # lines matching this regex will be highlighted
    highlight_lines_regex = re.compile(r"^[\s-]*[!?]")

    # free keys: q, numbers, special chars
    # note: the order of modifiers must be M-, A-, S-, C-
    keys.update(
        {
            # Give birth to a child box
            f"<{mod}-g>": "create child",
            # Teleport to any text using leap plugin
            f"<{mod}-t>": "hop",
            # Focus view on the current text box
            f"<{mod}-f>": "focus on current text",
            # Summon GPT through vim-ai plugin
            f"<{mod}-s>": "summon gpt",
            # delete text
            "<C-w>": "delete text",
            # Detach child
            f"<{mod}-d>": "detach child",
            # when in bookmarks window, jump to location of bookmark under cursor
            f"<{mod}-b>": "bookmark jump",

            "<A-Left>": "jump back",
            "<A-Right>": "jump forward",

            # # toggle editor View
            # f"<{mod}-v>": "toggle editor",
            # # zoom in, pushing the current box to the Right
            # f"<{mod}-r>": "maximize on current text",
        }
    )

    # relevant for zooming and resizing with keys
    FPS = 180

    input_on_creation = "- "
    input_on_creation_aichat = """\
>>> user


>>> include
{files_to_include}"""

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
