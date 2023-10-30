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
# highlight bookmarks
# record some demo
# look into syncing with syncthing
#  or using attach nvim with tcp
#  everyone has their own folder
#  :set nomodifiable  -  prevent even editing the buffer
# for more granular control of bookmarks, each group would need to be a separate folder?
#  but also separate nvim session, and I don't want that
#  ? but maybe this option could be set https://github.com/MattesGroeger/vim-bookmarks#bookmarks-per-buffer
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
# filenums of non-persistent texts should be None, not -1
#
# note: custom C-o and C-i only jump between buffers, but not to correct lines


class MainWindow(QMainWindow):
    def __init__(self, nvim):
        super().__init__()
        self.view = GraphicView(nvim)
        self.setCentralWidget(self.view)
        # self.showMaximized()
        # # not maximized, but 1000x1000
        self.resize(1900, 600)
        self.show()


def nvim_notification(method, args):
    return print("notification", method, args)


if __name__ == "__main__":
    savedir = Path(sys.argv[1])
    savedir = savedir.absolute()
    savedir.mkdir(parents=True, exist_ok=True)

    # change working directory to savedir
    os.chdir(savedir)

    nvim = pynvim.attach(
        "child", argv=["/usr/bin/env", "nvim", "--embed", "--headless"]
    )
    # text that doesn't fit in window can't be jumped to with Leap (for now)
    nvim.ui_attach(80, 100, True)
    # nvim = pynvim.attach('socket', path='/tmp/nvim')

    app = QApplication(sys.argv)
    w = MainWindow(nvim)

    # make the cursor non-blinking
    app.setCursorFlashTime(0)

    assert len(nvim.buffers) == 1, "we require nvim to start with one buffer"

    buf_handler = w.view.buf_handler

    try:
        load_scene(w.view, savedir)
    except AssertionError:
        # create one text
        text = buf_handler.create_text(Config.initial_position)
        first_text_width = (
            Config.text_width * text.get_plane_scale() * w.view.global_scale
        )
        window_width = w.view.screen().size().width()
        # center it
        initial_x = Config.initial_position[0]
        w.view.global_scale = window_width / (initial_x * 2 + first_text_width)
        buf_handler.update_all_texts()
    buf_handler.jumplist = [nvim.current.buffer.number]

    exit_code = app.exec()
    save_scene(w.view, savedir)
    sys.exit(exit_code)
