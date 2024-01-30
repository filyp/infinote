import os
import sys
from pathlib import Path

import pynvim
from PySide6.QtWidgets import QApplication, QMainWindow

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
    assert len(sys.argv) == 2, "usage: infinote <savedir>"
    group_dir = Path(sys.argv[1]).resolve()
    workspace_dir = group_dir.parent
    # change working directory to the workspace directory
    # so that nvim can find the bookmark file
    
    workspace_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(workspace_dir)

    nvim = pynvim.attach(
        "child", argv=["/usr/bin/env", "nvim", "--embed", "--headless"]
    )
    # text that doesn't fit in window can't be jumped to with Leap (for now)
    nvim.ui_attach(80, 100, True)
    # nvim = pynvim.attach('socket', path='/tmp/nvim')  # there's no speedup to this

    app = QApplication(sys.argv)
    view = GraphicView(nvim, group_dir)
    buf_handler = view.buf_handler
    w = MainWindow(view)

    # make the cursor non-blinking
    app.setCursorFlashTime(0)

    assert len(nvim.buffers) == 1, "we require nvim to start with one buffer"

    load_scene(buf_handler, group_dir)
    view.global_scale = view.get_scale_centered_on_text(buf_handler.get_current_text())
    buf_handler.to_redraw.update(buf_handler.buf_num_to_text.keys())

    buf_handler.jumplist = [None, nvim.current.buffer.number]
    buf_handler.update_all_texts()

    exit_code = app.exec()
    save_scene(buf_handler, nvim, group_dir)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
