import pynvim
from config import Config
from key_handling import KeyHandler
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
    QStatusBar,
    QTextBrowser,
)
from text_object import DraggableText


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
        self.key_handler = KeyHandler(nvim)

        # note: this bg may be unnecessary (dummy object is necessary though)
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

        # create a status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("")
        # place it at the top and display
        self.status_bar.setGeometry(0, 0, screen_size.width(), 20)
        # make it black
        self.status_bar.setStyleSheet("QStatusBar{background-color: black;}")
        self.scene().addWidget(self.status_bar)

    # event handling methods

    def mousePressEvent(self, event):
        item = self.scene().itemAt(event.screenPos(), self.transform())
        if isinstance(item, DraggableText):
            # clicked on text, so make it current
            self.nvim.command(f"buffer {item.buffer.number}")
            self.update_texts()
        else:
            # clicked bg, so create a new text
            self.create_text(event.screenPos() / self.global_scale)
        super().mousePressEvent(event)
        self.dummy.setFocus()

    def resizeEvent(self, event):
        self.scene().setSceneRect(0, 0, event.size().width(), event.size().height())
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        self.key_handler.handle_key_event(event)
        self.update_texts()
        command_line = self.key_handler.get_command_line()
        self.status_bar.showMessage(command_line)
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

    # buffers handling methods

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
                # print("unbound buffer found")
                break
        assert unbound_buf is not None, "no unused buffer found"

        return self.open_filenum(pos, manual_scale, filenum, unbound_buf)

    def update_texts(self):
        # unfocus the text boxes - better would be to always have focus
        self.dummy.setFocus()

        # there are glitches when moving texts around
        # so redraw the background first (black)
        # TODO this does not work

        if self.nvim.api.get_mode()["blocking"]:
            return

        # redraw
        for text in self.get_texts():
            text.update_text()
            text.reposition()

        # delete empty texts
        for text in self.get_texts():
            if text.buffer == self.nvim.current.buffer:
                # current buffer can be empty
                continue
            if text.buffer[:] == [""] or not text.buffer[:]:
                if text.filenum >= 0:
                    self.nvim.command(f"call delete('{text.filenum}.md')")
                self.nvim.command(f"bwipeout! {text.buffer.number}")
                self.scene().removeItem(text)
                del text

        # get the cmd line
        # cmdline = self.nvim.command_output("echo getcmdline()")
        # cmdline = self.nvim.command_output("set statusline?")
        # cmdline = self.nvim.api.get_mode()
        # print(f"'{cmdline=}'")

    def get_texts(self):
        for item in self.scene().items():
            if isinstance(item, DraggableText):
                yield item