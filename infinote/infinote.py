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
# record some demo
# bookmarks can just be changed by swapping the .vim-bookmarks file
#    but this seems to require that nvim is inactive during swap, otherwise weird
#    stuff happens
# look into syncing with syncthing
#  or using attach nvim with tcp
#  everyone has their own folder
#  :set nomodifiable  -  prevent even editing the buffer
# for more granular control of bookmarks, each group would need to be a separate folder?
#  but also separate nvim session, and I don't want that
#  ? but maybe this option could be set https://github.com/MattesGroeger/vim-bookmarks#bookmarks-per-buffer
#
# mid:
# ? (have bookmarks per layer folder)
# if I even want to optimize, I shouldn't draw all the texts on each keypress
#  instead draw onl the changed, and redraw the rest is s was pressed
# save web of transitions with timestamps
# make ** text bold
# box shadows
#  https://stackoverflow.com/questions/13962228/how-do-i-add-a-box-shadow-to-an-element-in-qt
#  https://github.com/GvozdevLeonid/BoxShadow-in-PyQt-PySide

# low:
# polish chars seem to break stuff, because they throuw position out of range,
#     they are probably more chars than one
# highlight search
# if stuff gets too heavy, move back to QTextBrowser, and just have some different color for insert cursor?
#  for now, the bottleneck is communication with nvim
# solve those weird glitches when moving text around
#  they happen only when maximized
# unnamed buffers, created with piping something to vim, if they exist, they can fuck stuff up, binding gets incorrect
# for >100 lines texts, I still may not be able to jump there
#  https://github.com/ggandor/leap.nvim/issues/196
# potential redraw speed bottleneck are folds?
#     because deleting lines takes ~6ms each
#     instead, we could calculate in advance and only draw those necessary
#     but that complicates calculations of position - they need to be custom
#     so only do it if it feels slow, and double checked in profiler it really is folds
#   update: actually this may be false - folding is instant even for large folds
#
# note: custom C-o and C-i only jump between buffers, but not to correct lines


class MainWindow(QMainWindow):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setCentralWidget(self.view)

        # self.resize(1900, 600)
        # self.showMaximized()  # this has small glitches when dragging or zooming
        self.showFullScreen()

        self.show()


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

    app = QApplication(sys.argv)
    view = GraphicView(nvim, savedirs)
    w = MainWindow(view)

    # make the cursor non-blinking
    app.setCursorFlashTime(0)

    assert len(nvim.buffers) == 1, "we require nvim to start with one buffer"

    buf_handler = view.buf_handler
    # buf_handler.savedir_indexes = {savedir: i for i, savedir in enumerate(savedirs)}

    try:
        load_scene(view, savedirs)
    except AssertionError:
        # set the color of first text
        # create one text
        text = buf_handler.create_text(savedirs[0], Config.initial_position)
        first_text_width = (
            Config.text_width * text.get_plane_scale() * view.global_scale
        )
    view.global_scale = view.get_scale_centered_on_text(buf_handler.get_current_text())
    buf_handler.to_redraw.update(buf_handler.buf_num_to_text.keys())

    buf_handler.jumplist = [None, nvim.current.buffer.number]
    buf_handler.update_all_texts()

    exit_code = app.exec()
    save_scene(view, savedirs)
    sys.exit(exit_code)
