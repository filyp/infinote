import sys
from pathlib import Path
from time import sleep, time

import pynvim
import yaml
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
    QTextBrowser,
)

from global_objects import Config, nvim
from text_object import DraggableText

# TODO
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
#
# low:
# polish chars seem to break stuff, because they throuw position out of range,
#     they are probably more chars than one
# custom wrappint, extending height
# native node dragging would maybe be more efficient (there are cases with big text where it lags)
# if stuff gets too heavy, move back to QTextBrowser, and just have some different color for insert cursor
# solve those weird glitches when moving text around
# dragging take correction for rescaling, keep mouse pos fixed on text pos


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
    # if mods & Qt.MetaModifier:
    #     text = "M-" + text
    # if mods & Qt.KeypadModifier:
    #     text = "W-" + text

    if mods or (key in special_keys):
        text = "<" + text + ">"

    return text


class GraphicView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(Qt.black))
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)
        self.setScene(QGraphicsScene())
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.global_scale = 1.0

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
        if not isinstance(item, DraggableText):
            self.create_text(event.screenPos() / self.global_scale)
        super().mousePressEvent(event)
        self.dummy.setFocus()

    def resizeEvent(self, event):
        self.scene().setSceneRect(0, 0, event.size().width(), event.size().height())
        super().resizeEvent(event)

    def create_text(self, pos, manual_scale=1.0):
        if isinstance(pos, (tuple, list)):
            pos = QPointF(*pos)
        num_of_texts = len(self.scene().items())
        if num_of_texts == len(nvim.buffers):
            # create new buffer
            nvim.command("new")
        text = DraggableText(nvim.current.buffer, self, pos, manual_scale)
        self.scene().addItem(text)
        self.update_texts()
        return text

    def keyPressEvent(self, event):
        text = translate_key_event_to_vim(event)
        if text is None:
            return
        nvim.input(text)
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

        if nvim.api.get_mode()["blocking"]:
            return

        # redraw
        for text in self.get_texts():
            text.update_text()
            text.reposition()
        
        # delete empty texts
        for text in self.get_texts():
            if text.buffer == nvim.current.buffer:
                continue
            if text.buffer[:] == [""]:
                self.scene().removeItem(text)
                del text

    def get_texts(self):
        for item in self.scene().items():
            if isinstance(item, DraggableText):
                yield item


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.view = GraphicView()
        self.setCentralWidget(self.view)
        self.showMaximized()
        # # not maximized, but 1000x1000
        # self.resize(1900, 1000)
        self.show()


def nvim_notification(method, args):
    return print("notification", method, args)


if __name__ == "__main__":
    savedir = Path(sys.argv[1])
    savedir.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    w = MainWindow()

    # make the cursor non-blinking
    app.setCursorFlashTime(0)

    # if there is at least one markdown file, open it
    # names must be integers
    files = [f for f in savedir.iterdir() if f.suffix == ".md" and f.stem.isnumeric()]
    if files:
        # load them into buffers
        for filename in files:
            full_text = filename.read_text()
            # parse frontmatter
            _, frontmatter, saved_buffer = full_text.split("---\n", 2)
            fm_dict = yaml.safe_load(frontmatter)
            # create text
            text = w.view.create_text(fm_dict["plane_pos"], fm_dict["manual_scale"])
            text.buffer[:] = saved_buffer.splitlines()
            text.update_text()
        # do some dummy vim action to make sure buffers are loaded
        # nvim.input("<Esc>")
        # w.view.update_texts()
    else:
        # create one text
        text = w.view.create_text(Config.initial_position)
        first_text_width = Config.text_width * text.get_scale()
        window_width = w.view.screen().size().width()
        # center it
        initial_x = Config.initial_position[0]
        w.view.global_scale = window_width / (initial_x * 2 + first_text_width)
        w.view.update_texts()

        print(first_text_width)
        print(window_width)
        print(w.view.global_scale)

    exit_code = app.exec()

    # save
    # backpup the dir to .[name]_backup
    backup = savedir.parent / f".{savedir.name}_backup"
    # if backup exists, delete it
    if backup.exists():
        for f in backup.iterdir():
            f.unlink()
        backup.rmdir()
    # move the savedir to backup
    savedir.rename(backup)
    # create a new savedir
    new_savedir = Path(sys.argv[1])
    new_savedir.mkdir(parents=True, exist_ok=True)
    # save each text
    for text in w.view.get_texts():
        text.save(new_savedir)

    sys.exit(exit_code)
