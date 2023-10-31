import time
from pathlib import Path

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
    def __init__(self, nvim, savedirs, parent=None):
        super().__init__(parent)
        self.nvim = nvim
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(Config.background_color))
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)
        self.setScene(QGraphicsScene())
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.global_scale = 1.0
        self.key_handler = KeyHandler(nvim, self)
        self.buf_handler = BufferHandler(nvim, self)
        self.savedirs = savedirs
        self.current_folder = savedirs[0]

        # note: this bg may be unnecessary (dummy object is necessary though)
        # create a background taking up all the space, to cover up glitches
        # it also serves as a dummy object that can grab focus,
        # so that the text boxes can be unfocused
        bg = QGraphicsRectItem()
        bg.setFlag(QGraphicsItem.ItemIsFocusable)
        color = Config.background_color
        bg.setBrush(QColor(color))
        bg.setPen(QColor(color))
        screen_size = self.screen().size()
        bg.setRect(0, 0, screen_size.width(), screen_size.height())
        self.scene().addItem(bg)
        self.dummy = bg

        # create a status bar
        self.status_bar = QStatusBar()
        # place it at the top and display
        self.status_bar.setGeometry(0, 0, screen_size.width(), 20)
        self.status_bar.setStyleSheet("QStatusBar{background-color: " + color + ";}")
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

            # pin the click position, in case of dragging
            click_pos = event.screenPos() / self.global_scale
            item.pin_pos = (click_pos - item.plane_pos) / item.get_plane_scale()
        else:
            # clicked bg, so create a new text
            self.buf_handler.create_text(
                self.current_folder, event.screenPos() / self.global_scale
            )
            self.buf_handler.update_all_texts()

        super().mousePressEvent(event)
        self.dummy.setFocus()
        self._render_status_bar()

    def keyPressEvent(self, event):
        self._message = []
        self.key_handler.handle_key_event(event)
        self.buf_handler.update_all_texts()
        self._render_status_bar()

    def wheelEvent(self, event):
        direction = -1 if Config.scroll_invert else 1
        zoom_factor = 1.0005 ** (event.angleDelta().y() * direction)

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

    def get_state(self):
        return dict(
            global_scale=self.global_scale,
            current_folder=self.current_folder.as_posix(),
            current_file=Path(self.nvim.current.buffer.name)
            .relative_to(Path.cwd())
            .as_posix(),
        )

    def jump_to_neighbor(self, old, new):
        if new is None:
            return
        buf_num = new.buffer.number
        self.buf_handler.jump_to_buffer(buf_num)

    def track_jump(self, old, new):
        # update global scale to track the movement

        old_pos = old.plane_pos
        old_dist = (old_pos.x() ** 2 + old_pos.y() ** 2) ** 0.5
        new_pos = new.plane_pos
        new_dist = (new_pos.x() ** 2 + new_pos.y() ** 2) ** 0.5

        self.global_scale *= old_dist / new_dist
