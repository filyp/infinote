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
# gluing
#   gaps, scaled
#   don't rescale children
# custom wrappint, extending height
#
# mid:
# highlight search
# save web of transitions with timestamps
#
# ? backups
# ?:
# nicer sizing, tweak the width/position of boxes

# for more granular control of bookmarks, each group would need to be a separate folder?
# but also separate nvim session, and I don't want that
# ? but maybe this option could be set https://github.com/MattesGroeger/vim-bookmarks#bookmarks-per-buffer
#
# low:
# polish chars seem to break stuff, because they throuw position out of range,
#     they are probably more chars than one
# ? (have bookmarks per layer folder)
# native node dragging would maybe be more efficient (there are cases with big text where it lags)
# if stuff gets too heavy, move back to QTextBrowser, and just have some different color for insert cursor
# solve those weird glitches when moving text around
# dragging take correction for rescaling, keep mouse pos fixed on text pos
# unnamed buffers, created with piping something to vim, if they exist, they can fuck stuff up, binding gets incorrect
# for >100 lines texts, I still may not be able to jump there
#  https://github.com/ggandor/leap.nvim/issues/196
#


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

    try:
        load_scene(w.view, savedir)
    except AssertionError:
        # create one text
        text = w.view.create_text(Config.initial_position)
        first_text_width = (
            Config.text_width * text.get_plane_scale() * w.view.global_scale
        )
        window_width = w.view.screen().size().width()
        # center it
        initial_x = Config.initial_position[0]
        w.view.global_scale = window_width / (initial_x * 2 + first_text_width)
        w.view.update_texts()

    exit_code = app.exec()
    save_scene(w.view, savedir)
    sys.exit(exit_code)
