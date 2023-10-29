import textwrap
from time import sleep, time

from config import Config
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
    QTextBrowser,
    QTextEdit,
)


class NonSelectableTextEdit(QTextEdit):
    def mousePressEvent(self, event):
        # Skip the mouse press event to prevent it from being handled by QTextBrowser
        event.ignore()

    def mouseMoveEvent(self, event):
        # Skip the mouse move event to prevent it from being handled by QTextBrowser
        event.ignore()

    def mouseReleaseEvent(self, event):
        # Skip the mouse release event to prevent it from being handled by QTextBrowser
        event.ignore()

    def keyPressEvent(self, event):
        event.ignore()


class DraggableText(QGraphicsProxyWidget):
    def __init__(self, nvim, buffer_handle, filenum, view, plane_pos, manual_scale=1.0):
        super().__init__()

        self.autoshrink = Config.autoshrink

        # note that num doesn't need to be the same as buffer_handle.number
        self.nvim = nvim
        self.buffer = buffer_handle
        self.filenum = filenum
        self.view = view
        self.plane_pos = plane_pos
        self.manual_scale = manual_scale
        self.setScale(manual_scale)
        self.child_down = None
        self.child_right = None
        self.parent = None
        self._last_height = 0

        self.text_box = NonSelectableTextEdit()

        font = QFont("monospace", Config.font_size)
        self.text_box.setFont(font)
        self.text_box.setFixedWidth(Config.text_width)

        # make bg black, create a pale grey border
        # if filenum<0, it's non-persistent buffer, so mark it's border yellow
        style = f"""
            background-color: black; color: white;
            border: 1px solid {'#555' if self.filenum >= 0 else '#cc0'};
        """
        self.text_box.setStyleSheet(style)

        self.setWidget(self.text_box)
        self.update_text()

    def mouseMoveEvent(self, event):
        # drag around
        movevent = event.screenPos() - event.lastScreenPos()
        self.plane_pos += movevent / self.view.global_scale
        self.reposition()
        self.view.dummy.setFocus()

        self.detach_parent()

    def _yx_to_pos(self, y, x):
        # get the one number char position
        doc = self.text_box.document()
        return doc.findBlockByLineNumber(y - 1).position() + x

    def detach_parent(self):
        # detach from parent
        if self.parent is not None:
            if self.parent.child_down == self:
                self.parent.child_down = None
            elif self.parent.child_right == self:
                self.parent.child_right = None
            self.parent = None

    def detach_children(self):
        if self.child_down is not None:
            self.child_down.parent = None
            self.child_down = None
        if self.child_right is not None:
            self.child_right.parent = None
            self.child_right = None

    def highlight(self, color_style, start, end):
        color_format = QTextCharFormat()
        color_format.setBackground(QColor(color_style))

        start_pos = self._yx_to_pos(start[0], start[1] - 1)
        end_pos = self._yx_to_pos(end[0], end[1])

        cursor = self.text_box.textCursor()
        cursor.setPosition(start_pos, QTextCursor.MoveAnchor)
        cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(color_format)

    def set_lines(self, lines):
        wrapped_lines = []
        for line in lines:
            if line == "":
                # add space so that cursor can be displayed there
                wrapped_lines.append(" ")
                continue
            # # add a non-breaking space at both ends
            # line = '\xa0' + line + '\xa0'
            # wrapped_line = textwrap.fill(
            #     line, width=20, subsequent_indent=" ", replace_whitespace=False
            # )
            # wrapped_line = wrapped_line.replace('\xa0', ' ')
            # TODO
            # this is tricky, because all the marks and curson also need to be wrapped
            # I'd need a second "highlight layer" where non-space chars are some
            # placeholder like "x", and colors are some other letters
            #
            # leave it for now, it's too buggy and only would be worth it if I were
            # to do some funky stuff with text size shrink on indents

            # for now just
            wrapped_line = line
            wrapped_lines.append(wrapped_line)
        new_text = "\n".join(wrapped_lines)
        self.text_box.setText(new_text)

    def get_plane_scale(self):
        if self.autoshrink:
            # euclidean magniture of plane_pos
            distance = (self.plane_pos.x() ** 2 + self.plane_pos.y() ** 2) ** 0.5
            distance_scale = distance / Config.initial_position[0]
            return self.manual_scale * distance_scale
        else:
            return self.manual_scale

    def reposition(self):
        global_scale = self.view.global_scale
        self.setScale(self.get_plane_scale() * global_scale)
        self.setPos(self.plane_pos * global_scale)

        self.place_down_children()
        self.place_right_children()

    def update_text(self):
        # set new text
        lines = self.buffer[:]
        self.set_lines(lines)

        # draw marks
        buf_num = self.buffer.number
        marks = self.nvim.api.buf_get_extmarks(
            buf_num, -1, (0, 0), (-1, -1), {"details": True}
        )
        positions = []
        for _, y, x, details in marks:
            virt_text = details["virt_text"]
            assert len(virt_text) == 1, virt_text
            char, type_ = virt_text[0]
            if type_ == "Cursor":
                continue
            # TODO later relax this
            assert type_ == "LeapLabelPrimary", marks
            # put that char into text
            lines[y] = lines[y][:x] + char + lines[y][x + 1 :]
            positions.append((y, x))
        self.set_lines(lines)
        # highlight the chars
        for y, x in positions:
            self.highlight("orange", (y + 1, x + 1), (y + 1, x + 1))

        # set height
        height = self.text_box.document().size().height()
        self.text_box.setFixedHeight(height + 2)

        # place children
        if height != self._last_height:
            self._last_height = height
            self.place_down_children()

        ###################################################################
        # the rest if done only if this node's buffer is the current buffer
        if self.nvim.current.buffer != self.buffer:
            return

        mode = self.nvim.api.get_mode()["mode"]

        # set cursor
        curs_y, curs_x = self.nvim.current.window.cursor
        pos = self._yx_to_pos(curs_y, curs_x)
        # get focus so that cursor is displayed
        cursor = self.text_box.textCursor()
        if mode == "n":
            cursor.setPosition(pos, QTextCursor.MoveAnchor)
            cursor.setPosition(pos + 1, QTextCursor.KeepAnchor)
        elif mode == "i":
            self.text_box.setFocus()
            cursor.setPosition(pos)
        self.text_box.setTextCursor(cursor)

        # set selection
        if mode == "v" or mode == "V" or mode == "\x16":
            s = self.nvim.eval('getpos("v")')[1:3]
            e = self.nvim.eval('getpos(".")')[1:3]
            # if end before start, swap
            if s[0] > e[0] or (s[0] == e[0] and s[1] > e[1]):
                s, e = e, s
        if mode == "v":
            self.highlight("gray", s, e)
        elif mode == "V":
            # extend selection to full line
            s[1] = 1
            e[1] = len(self.buffer[e[0] - 1])
            self.highlight("gray", s, e)
        elif mode == "\x16":
            # visual block selection
            x_start = min(s[1], e[1])
            x_end = max(s[1], e[1])
            for y in range(s[0], e[0] + 1):
                self.highlight("gray", (y, x_start), (y, x_end))

    def place_down_children(self):
        if self.child_down is not None:
            height = self.get_plane_scale() * self.text_box.document().size().height()
            gap = Config.text_gap * self.get_plane_scale()
            self.child_down.plane_pos = self.plane_pos + QPointF(0, height + gap)
            self.child_down.reposition()

    def place_right_children(self):
        if self.child_right is not None:
            width = self.get_plane_scale() * self.text_box.document().size().width()
            gap = Config.text_gap * self.get_plane_scale()
            self.child_right.plane_pos = self.plane_pos + QPointF(width + gap, 0)
            self.child_right.reposition()

    def save(self):
        if self.filenum < 0:
            # this buffer was not created by this program, so don't save it
            return
        # set this buffer as current
        self.nvim.api.set_current_buf(self.buffer.number)
        # save it
        self.nvim.command("w")
