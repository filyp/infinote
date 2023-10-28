import json
import os
import sys
from pathlib import Path
from time import sleep, time

import pynvim
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

from config import Config
from text_object import DraggableText

# TODO
# correct deletion of buffers
# can't drag spedial buffers
# jump back from bookmarks by :buffer 4.md
# backups
#
# tab in insert mode is caught by qt, so it doesn't get to nvim
# dumb fix is to use Ctrl-I
# for more granular control of bookmarks, each group would need to be a separate folder?
# but also separate nvim session, and I don't want that
# but maybe this option could be set https://github.com/MattesGroeger/vim-bookmarks#bookmarks-per-buffer
#
# saving - each buffer should get saved to a file
#  then we create bookmarks on them
#  and in case of failure, stuff isn't lost
#  and the storage format is nice, extensible and robust
#  filenames are just buffer numbers, .md extension, frontmatter with metadata
#  have bookmarks per layer folder
# when someone chooses a bookmark and jumps, we get the buffer number
#  from filename, and we set that buffer as current
#  then we go to the right line num
#  unfold if needed
#
# mid:
# when leaving an empty buffer, delete it
# ribbon for vim commands
# save web of transitions with timestamps
#
# low:
# polish chars seem to break stuff, because they throuw position out of range,
#     they are probably more chars than one
# custom wrappint, extending height
# native node dragging would maybe be more efficient (there are cases with big text where it lags)
# if stuff gets too heavy, move back to QTextBrowser, and just have some different color for insert cursor
# solve those weird glitches when moving text around
# dragging take correction for rescaling, keep mouse pos fixed on text pos
# unnamed buffers, created with piping something to vim, if they exist, they can fuck stuff up, binding gets incorrect


def translate_key_event_to_vim(event):
    special_keys = {
        32: "Space",
        16777219: "BS",
        16777216: "Esc",
        16777220: "CR",
        16777217: "Tab",
        16777232: "Home",
        16777233: "End",
        16777223: "Del",
        16777237: "Down",
        16777235: "Up",
        16777234: "Left",
        16777236: "Right",
        16777239: "PageDown",
        16777238: "PageUp",
    }
    key = event.key()
    if key in special_keys:
        text = special_keys[key]
    elif key < 0x110000:
        text = chr(key).lower()
    else:
        return

    mods = event.modifiers()
    # if ctrl
    if mods & Qt.ControlModifier:
        text = "C-" + text
    if mods & Qt.ShiftModifier:
        text = "S-" + text
    if mods & Qt.AltModifier:
        text = "A-" + text
    if mods & Qt.MetaModifier:
        text = "M-" + text
    # if mods & Qt.KeypadModifier:
    #     text = "W-" + text

    if mods or (key in special_keys):
        text = "<" + text + ">"

    return text


class GraphicView(QGraphicsView):
    def __init__(self, nvim, parent=None):
        super().__init__(parent)
        self.nvim = nvim
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(Qt.black))
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)
        self.setScene(QGraphicsScene())
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.global_scale = 1.0
        self.last_file_num = 0

        # create a black background taking up all the space, to cover up glitches
        # it also serves as a dummy object that can grab focus,
        # so that the text boxes can be unfocused
        bg = QGraphicsRectItem()
        bg.setFlag(QGraphicsItem.ItemIsFocusable)
        bg.setBrush(QColor(Qt.black))
        bg.setPen(QColor(Qt.black))
        screen_size = self.screen().size()
        bg.setRect(0, 0, screen_size.width(), screen_size.height())
        self.scene().addItem(bg)
        self.dummy = bg

    def mousePressEvent(self, event):
        item = self.scene().itemAt(event.screenPos(), self.transform())
        if isinstance(item, DraggableText):
            # clicked on text, so make it current
            self.nvim.command(f"buffer {item.filenum}.md")
            self.update_texts()
        else:
            # clicked bg, so create a new text
            self.create_text(event.screenPos() / self.global_scale)
        super().mousePressEvent(event)
        self.dummy.setFocus()

    def resizeEvent(self, event):
        self.scene().setSceneRect(0, 0, event.size().width(), event.size().height())
        super().resizeEvent(event)

    def open_filenum(self, pos, manual_scale, filenum, buffer=None):
        if isinstance(pos, (tuple, list)):
            pos = QPointF(*pos)

        if buffer is None:
            # no buffer provided, so open the one with the given filenum
            num_of_texts = len(list(self.get_texts()))
            if num_of_texts == 0:
                self.nvim.command(f"edit {filenum}.md")
            elif num_of_texts == len(self.nvim.buffers):
                # create new file
                self.nvim.command(f"split {filenum}.md")
            buffer = self.nvim.current.buffer
        else:
            # buffer provided, so open it
            assert type(buffer) == pynvim.api.buffer.Buffer

        text = DraggableText(self.nvim, buffer, filenum, self, pos, manual_scale)
        self.scene().addItem(text)
        self.update_texts()
        return text

    def create_text(self, pos, manual_scale=1.0):
        num_of_texts = len(list(self.get_texts()))
        if num_of_texts == len(self.nvim.buffers) or num_of_texts == 0:
            self.last_file_num += 1
            return self.open_filenum(pos, manual_scale, self.last_file_num)

        # some buffer was created some other way than calling create_text,
        # so mark it to not be saved
        filenum = -1

        # get the unused buffer
        bound_buffers = [text.buffer for text in self.get_texts()]
        unbound_buf = None
        for buf in self.nvim.buffers:
            if buf not in bound_buffers:
                unbound_buf = buf
                print("unbound buffer found")
                break
        assert unbound_buf is not None, "no unused buffer found"

        return self.open_filenum(pos, manual_scale, filenum, unbound_buf)

    def keyPressEvent(self, event):
        text = translate_key_event_to_vim(event)
        if text is None:
            return
        self.nvim.input(text)
        self.update_texts()

        # super().keyPressEvent(event)

    def wheelEvent(self, event):
        zoom_factor = 1.0005 ** event.angleDelta().y()

        item = self.scene().itemAt(event.position(), self.transform())
        if isinstance(item, DraggableText):
            # zoom it
            item.manual_scale *= zoom_factor
            item.reposition()
        else:
            # zoom the whole view
            self.global_scale *= zoom_factor

            # reposition all texts
            for text in self.get_texts():
                text.reposition()

    def update_texts(self):
        # unfocus the text boxes - better would be to always have focus
        self.dummy.setFocus()

        # there are glitches when moving texts around
        # so redraw the background first (black)

        if self.nvim.api.get_mode()["blocking"]:
            return

        # redraw
        for text in self.get_texts():
            text.update_text()
            text.reposition()

        # delete empty texts
        for text in self.get_texts():
            if text.buffer == self.nvim.current.buffer:
                continue
            if text.buffer[:] == [""]:
                # TODO this does not delete!
                self.nvim.command(f"bdelete! {text.buffer.number}")
                self.scene().removeItem(text)
                del text

    def get_texts(self):
        for item in self.scene().items():
            if isinstance(item, DraggableText):
                yield item


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

    app = QApplication(sys.argv)
    w = MainWindow(nvim)

    # make the cursor non-blinking
    app.setCursorFlashTime(0)

    assert len(nvim.buffers) == 1, "we require nvim to start with one buffer"

    # if there is at least one markdown file, open it
    # names must be integers
    files = [f for f in savedir.iterdir() if f.suffix == ".md" and f.stem.isnumeric()]
    meta_path = Path("meta.json")
    if files and meta_path.exists():
        # load all
        meta = json.loads(meta_path.read_text())

        w.view.global_scale = meta["global_scale"]

        # load them into buffers
        for filename in files:
            full_text = filename.read_text()
            index = int(filename.stem)
            text_info = meta[str(index)]
            # create text
            text = w.view.open_filenum(
                text_info["plane_pos"], text_info["manual_scale"], index
            )
        # prepare the next file number
        max_filenum = max(int(f.stem) for f in files)
        w.view.last_file_num = max_filenum
    else:
        # create one text
        text = w.view.create_text(Config.initial_position)
        first_text_width = Config.text_width * text.get_scale()
        window_width = w.view.screen().size().width()
        # center it
        initial_x = Config.initial_position[0]
        w.view.global_scale = window_width / (initial_x * 2 + first_text_width)
        w.view.update_texts()

    exit_code = app.exec()

    # save
    # # backpup the dir to .[name]_backup
    # backup = savedir.parent / f".{savedir.name}_backup"
    # # if backup exists, delete it
    # if backup.exists():
    #     for f in backup.iterdir():
    #         f.unlink()
    #     backup.rmdir()
    # # move the savedir to backup
    # savedir.rename(backup)
    # # create a new savedir
    # new_savedir = Path(sys.argv[1])
    # new_savedir.mkdir(parents=True, exist_ok=True)

    # save each text
    for text in w.view.get_texts():
        text.save()

    # save metadata json
    meta = dict(global_scale=w.view.global_scale)
    for text in w.view.get_texts():
        if text.filenum < 0:
            # this buffer was not created by this program, so don't save it
            continue
        meta[text.filenum] = dict(
            plane_pos=tuple(text.plane_pos.toTuple()),
            manual_scale=text.manual_scale,
        )
    meta_path = Path("meta.json")
    meta_path.write_text(json.dumps(meta, indent=4))

    sys.exit(exit_code)
