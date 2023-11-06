import time

from buffer_handling import BufferHandler
from config import Config
from key_handler import KeyHandler
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QStatusBar,
    QTextBrowser,
)
from text_object import DraggableText


class GraphicView(QGraphicsView):
    def __init__(self, nvim, savedirs, parent=None):
        super().__init__(parent)
        self.nvim = nvim
        self.savedirs = savedirs
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
        self.current_folder = savedirs[0]
        self.timer = None
        self._timer_last_update = None

        # dummy object so that the text boxes can be unfocused
        dummy = QGraphicsRectItem()
        dummy.setFlag(QGraphicsItem.ItemIsFocusable)
        self.scene().addItem(dummy)
        self.dummy = dummy

        # create a status bar
        screen_size = self.screen().size()
        self.status_bar = QStatusBar()
        # place it at the top and display
        self.status_bar.setGeometry(0, 0, screen_size.width(), 20)
        color = Config.background_color
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
            item = self.buf_handler.create_text(
                self.current_folder, event.screenPos() / self.global_scale
            )
            self.buf_handler.update_all_texts()

        super().mousePressEvent(event)
        item.setFocus()
        self._render_status_bar()

    def keyPressEvent(self, event):
        self._message = []
        self.key_handler.handle_key_event(event)
        self.buf_handler.update_all_texts()
        self._render_status_bar()

    def wheelEvent(self, event):
        direction = -1 if Config.scroll_invert else 1
        zoom_factor = Config.scroll_speed ** (event.angleDelta().y() * direction)

        item = self.scene().itemAt(event.position(), self.transform())
        if isinstance(item, DraggableText):
            # zoom it
            item.manual_scale *= zoom_factor
            item.reposition()
        else:
            # zoom the whole view
            self.global_scale *= zoom_factor

            # reposition all texts
            for text in self.buf_handler.get_root_texts():
                text.reposition()

    def msg(self, msg):
        self._message.append(msg)

    def jump_to_neighbor(self, direction: str):
        current_text = self.buf_handler.get_current_text()
        match direction:
            case "down":
                new = current_text.child_down
            case "right":
                new = current_text.child_right
            case "up" | "left":
                new = current_text.parent
        if new is None:
            return

        buf_num = new.buffer.number
        self.buf_handler.jump_to_buffer(buf_num)

        if Config.track_jumps_on_neighbor_moves:
            self.track_jump(current_text, new)

    def track_jump(self, old, new):
        # update global scale to track the movement

        old_pos = old.plane_pos
        old_dist = (old_pos.x() ** 2 + old_pos.y() ** 2) ** 0.5
        new_pos = new.plane_pos
        new_dist = (new_pos.x() ** 2 + new_pos.y() ** 2) ** 0.5

        self.global_scale *= old_dist / new_dist

    def zoom_on_current_text(self):
        text = self.buf_handler.get_current_text()
        x = text.plane_pos.x()
        y = text.plane_pos.y()

        window_width = self.screen().size().width()
        center_scale = window_width / (x * 2 + text.get_plane_width())

        window_height = self.screen().size().height()
        height_scale = window_height / (y + text.get_plane_height()) * 0.9

        self.global_scale = min(center_scale, height_scale)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return

        if self.timer is not None:
            self.timer.stop()
            self.timer = None
            self._timer_last_update = None

    def zoom(self, sign):
        if self._timer_last_update is None:
            # timer just starting
            self._timer_last_update = time.time()
            return
        new_time = time.time()
        time_diff = new_time - self._timer_last_update
        self._timer_last_update = new_time

        self.global_scale *= Config.key_zoom_speed ** (time_diff * sign)

        # reposition all texts
        for text in self.buf_handler.get_root_texts():
            text.reposition()

    def resize(self, sign):
        if self._timer_last_update is None:
            # timer just starting
            self._timer_last_update = time.time()
            return
        new_time = time.time()
        time_diff = new_time - self._timer_last_update
        self._timer_last_update = new_time

        # resize current text box
        text = self.buf_handler.get_current_text()
        text.manual_scale *= Config.key_zoom_speed ** (time_diff * sign)
        text.reposition()
