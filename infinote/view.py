import pynvim
from buffer_handling import BufferHandler
from config import Config
from key_handler import KeyHandler
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
        self.key_handler = KeyHandler(nvim, self)
        self.buf_handler = BufferHandler(nvim, self)

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
        self._message = []
        self.scene().addWidget(self.status_bar)

    def _render_status_bar(self):
        if not self.nvim.api.get_mode()["blocking"]:
            num_unbound_buffers = self.buf_handler.get_num_unbound_buffers()
            if num_unbound_buffers > 0:
                self.msg(f"{num_unbound_buffers} unbound buffer exists")

        command_line = self.key_handler.get_command_line()
        if command_line:
            self._message = [command_line] + self._message

        msg_string = " | ".join(self._message)
        self.status_bar.showMessage(msg_string)

    # event handling methods
    # note: there's one more possible event: mouseMoveEvent, but it's handled by texts

    def resizeEvent(self, event):
        self.scene().setSceneRect(0, 0, event.size().width(), event.size().height())
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        self._message = []
        item = self.scene().itemAt(event.screenPos(), self.transform())
        if isinstance(item, DraggableText):
            # clicked on text, so make it current
            self.buf_handler.jump_to_buffer(item.buffer.number)
            self.buf_handler.update_all_texts()
        else:
            # clicked bg, so create a new text
            self.buf_handler.create_text(event.screenPos() / self.global_scale)

        super().mousePressEvent(event)
        self.dummy.setFocus()
        self._render_status_bar()

    def keyPressEvent(self, event):
        self._message = []
        self.key_handler.handle_key_event(event)
        self.buf_handler.update_all_texts()
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
            for text in self.buf_handler.get_texts():
                text.reposition()

    def msg(self, msg):
        self._message.append(msg)
