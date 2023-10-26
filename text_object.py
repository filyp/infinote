from time import sleep, time
import textwrap

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QFontMetrics,
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

from global_objects import nvim


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


class DraggableText(QGraphicsProxyWidget):
    def __init__(self, buffer_handle, scale=1.0):
        super().__init__()

        self.buffer = buffer_handle
        self.scale_ = scale
        self.setScale(scale)

        self.text_box = NonSelectableTextEdit()

        font = QFont("monospace", 12)
        self.text_box.setFont(font)
        self.text_box.setFixedWidth(300)
        self.text_box.setFixedHeight(QFontMetrics(font).height())
        # make bg black, create a pale grey border
        self.text_box.setStyleSheet(
            """
            background-color: black; color: white;
            border: 1px solid grey;
            """
        )

        self.setWidget(self.text_box)

    def zoom(self, zoom_factor, global_scale):
        # # pos = event.pos()   # this is unstable
        # pos = self.boundingRect().center()
        # self.setTransformOriginPoint(pos)

        self.scale_ *= zoom_factor
        self.reposition(global_scale)
        # todo? maybe defocus here too

    def mouseMoveEvent(self, event):
        # drag around
        movevent = event.screenPos() - event.lastScreenPos()
        self.moveBy(movevent.x(), movevent.y())

    def _yx_to_pos(self, y, x):
        # get the one number char position
        doc = self.text_box.document()
        return doc.findBlockByLineNumber(y - 1).position() + x

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

    def update_text(self):
        # set new text
        lines = self.buffer[:]
        self.set_lines(lines)

        # draw marks
        buf_num = self.buffer.number
        marks = nvim.api.buf_get_extmarks(
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

        # the rest if done only if this node's buffer is the current buffer
        if nvim.current.buffer != self.buffer:
            return

        mode = nvim.api.get_mode()["mode"]

        # set cursor
        curs_y, curs_x = nvim.current.window.cursor
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
            s = nvim.eval('getpos("v")')[1:3]
            e = nvim.eval('getpos(".")')[1:3]
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

        # set height
        height = self.text_box.document().size().height() 
        self.text_box.setFixedHeight(height + 2)

    def reposition(self, global_scale):
        self.setScale(self.scale_ * global_scale)
        