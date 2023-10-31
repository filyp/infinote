import json
import os
import sys
from pathlib import Path
from time import sleep, time

import pynvim
from config import Config
from persistence import load_scene, save_scene
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
    QTextBrowser,
)
from text_object import DraggableText
from view import GraphicView

# TODO
# save current text to meta
# optimize update_all_texts
#  maybe the checks of buffer change can be made faster, by asking for some last change timestamp (even better if it also containt extmark changes)
# neighbor move commands
#  make the scale track it
# record some demo
# look into syncing with syncthing
#  or using attach nvim with tcp
#  everyone has their own folder
#  :set nomodifiable  -  prevent even editing the buffer
# for more granular control of bookmarks, each group would need to be a separate folder?
#  but also separate nvim session, and I don't want that
#  ? but maybe this option could be set https://github.com/MattesGroeger/vim-bookmarks#bookmarks-per-buffer
# highlight bookmarks
# make ** text bold
#
# mid:
# if I even want to optimize, I shouldn't draw all the texts on each keypress
#  instead draw onl the changed, and redraw the rest is s was pressed
# highlight search
# save web of transitions with timestamps

# low:
# polish chars seem to break stuff, because they throuw position out of range,
#     they are probably more chars than one
# ? (have bookmarks per layer folder)
# if stuff gets too heavy, move back to QTextBrowser, and just have some different color for insert cursor?
# dragging take correction for rescaling, keep mouse pos fixed on text pos
# solve those weird glitches when moving text around
# unnamed buffers, created with piping something to vim, if they exist, they can fuck stuff up, binding gets incorrect
# for >100 lines texts, I still may not be able to jump there
#  https://github.com/ggandor/leap.nvim/issues/196
#
# note: custom C-o and C-i only jump between buffers, but not to correct lines


class MainWindow(QMainWindow):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setCentralWidget(self.view)
        self.showMaximized()
        # # not maximized, but 1000x1000
        # self.resize(1900, 600)
        self.show()


# def nvim_notification(method, args):
#     return print("notification", method, args)


if __name__ == "__main__":
    savedirs = [Path(pathname) for pathname in sys.argv[1:]]
    for savedir in savedirs:
        savedir.mkdir(parents=True, exist_ok=True)

    nvim = pynvim.attach(
        "child", argv=["/usr/bin/env", "nvim", "--embed", "--headless"]
    )
    # text that doesn't fit in window can't be jumped to with Leap (for now)
    nvim.ui_attach(80, 100, True)
    # nvim = pynvim.attach('socket', path='/tmp/nvim')  # there's no speedup to this

    # nvim.subscribe('nvim_buf_lines_event')
    # nvim.run_loop(notification_cb=nvim_notification, request_cb=None)

    app = QApplication(sys.argv)
    view = GraphicView(nvim, savedirs)
    w = MainWindow(view)

    # make the cursor non-blinking
    app.setCursorFlashTime(0)

    assert len(nvim.buffers) == 1, "we require nvim to start with one buffer"

    buf_handler = view.buf_handler
    buf_handler.savedir_indexes = {savedir: i for i, savedir in enumerate(savedirs)}

    try:
        load_scene(view, savedirs)
    except AssertionError:
        # create one text
        text = buf_handler.create_text(savedirs[0], Config.initial_position)
        first_text_width = (
            Config.text_width * text.get_plane_scale() * view.global_scale
        )
        window_width = view.screen().size().width()
        # center it
        initial_x = Config.initial_position[0]
        view.global_scale = window_width / (initial_x * 2 + first_text_width)
    buf_handler.jumplist = [nvim.current.buffer.number]
    buf_handler.update_all_texts()

    exit_code = app.exec()
    save_scene(view, savedirs)
    sys.exit(exit_code)
