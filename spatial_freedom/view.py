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
        self.key_handler = KeyHandler(nvim, self)
        self.last_chosen_text = None
        self._buffer_to_text = {}

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
        # place it at the top and display
        self.status_bar.setGeometry(0, 0, screen_size.width(), 20)
        # make it black
        self.status_bar.setStyleSheet("QStatusBar{background-color: black;}")
        self.message = []
        self.scene().addWidget(self.status_bar)

    def _render_status_bar(self):
        if not self.nvim.api.get_mode()["blocking"]:
            num_unbound_buffers = len(self.nvim.buffers) - len(self._buffer_to_text)
            if num_unbound_buffers > 0:
                self.message.append(f"{num_unbound_buffers} unbound buffer exists")

        command_line = self.key_handler.get_command_line()
        if command_line:
            self.message = [command_line] + self.message

        msg_string = " | ".join(self.message)
        self.status_bar.showMessage(msg_string)

    # event handling methods
    # note: there's one more possible event: mouseMoveEvent, but it's handled by texts

    def resizeEvent(self, event):
        self.scene().setSceneRect(0, 0, event.size().width(), event.size().height())
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        self.message = []
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
        self._render_status_bar()

    def keyPressEvent(self, event):
        self.message = []
        self.key_handler.handle_key_event(event)
        self.update_texts()
        self._render_status_bar()

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

    # buffer handling methods

    def open_filenum(self, pos, manual_scale, filenum, buffer=None):
        if isinstance(pos, (tuple, list)):
            pos = QPointF(*pos)

        if buffer is None:
            # no buffer provided, so open the one with the given filenum
            num_of_texts = len(self._buffer_to_text)
            if num_of_texts == 0:
                self.nvim.command(f"edit {filenum}.md")
            elif num_of_texts == len(self.nvim.buffers):
                # create new file
                self.nvim.command(f"tabnew {filenum}.md")
            buffer = self.nvim.current.buffer
        else:
            # buffer provided, so open it
            assert type(buffer) == pynvim.api.buffer.Buffer

        text = DraggableText(self.nvim, buffer, filenum, self, pos, manual_scale)
        self.scene().addItem(text)
        self._buffer_to_text[buffer] = text
        self.update_texts()
        return text

    def create_text(self, pos, manual_scale=1.0):
        num_of_texts = len(self._buffer_to_text)
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
                # detach
                text.detach_parent()
                text.detach_children()
                del text

        # if hidden buffer focused, focus on the last chosen text
        if self.nvim.current.buffer not in self._buffer_to_text:
            self.nvim.command(f"buffer {self.last_chosen_text.buffer.number}")

        # redraw
        for text in self.get_texts():
            text.update_text()
            text.reposition()

    def get_texts(self):
        yield from self._buffer_to_text.values()

    def _get_current_text(self):
        return self._buffer_to_text.get(self.nvim.current.buffer)

    def create_child(self, side):
        current_text = self._get_current_text()

        if current_text.filenum < 0:
            # it's not a persistent buffer, so it shouldn't have children
            self.message.append("can't create children for non-persistent buffers")
            return

        if side == "right":
            if current_text.child_right is not None:
                self.message.append("right child already exists")
                return
            child = self.create_text((0, 0))
            current_text.child_right = child
        elif side == "down":
            if current_text.child_down is not None:
                self.message.append("down child already exists")
                return
            child = self.create_text((0, 0))
            current_text.child_down = child
        else:
            raise ValueError("side must be 'right' or 'down'")

        child.parent = current_text
        current_text.reposition()
