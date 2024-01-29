import sys
from pathlib import Path

import pynvim
from PySide6.QtWidgets import QApplication, QMainWindow

from infinote.config import Config
from infinote.persistence import load_scene, save_scene
from infinote.view import GraphicView


class MainWindow(QMainWindow):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setCentralWidget(self.view)

        # self.resize(1900, 600)
        # self.showMaximized()  # this has small glitches when dragging or zooming
        self.showFullScreen()

        self.show()


def main():
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


if __name__ == "__main__":
    main()
