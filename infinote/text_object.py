import textwrap
import time
from pathlib import Path

from config import Config
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QGraphicsProxyWidget, QTextEdit


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
    def __init__(self, nvim, buffer_handle, filename, view, plane_pos, manual_scale):
        super().__init__()

        self.autoshrink = Config.autoshrink

        # note that num doesn't need to be the same as buffer_handle.number
        self.nvim = nvim
        self.buffer = buffer_handle
        self.filename = filename
        self.view = view
        self.plane_pos = plane_pos
        self.manual_scale = manual_scale
        self.setScale(manual_scale)
        self.child_down = None
        self.child_right = None
        self.parent = None
        self.pin_pos = None

        self._last_height = 0
        self._last_changedtick = 0
        self._last_lines = []

        self.text_box = NonSelectableTextEdit()
        self.text_box.setFixedWidth(Config.text_width)

        if filename is None:
            # it's non-persistent buffer, so mark its border yellow
            dir_color = Config.non_persistent_dir_color
            text_color = Config.non_persistent_text_color
            self.selection_color = Config.non_persistent_selection_color
        else:
            savedir = Path(filename).parent
            savedir_index = self.view.buf_handler.savedir_indexes[savedir]
            savedir_index %= len(Config.dir_colors)
            dir_color = Config.dir_colors[savedir_index]
            text_color = Config.text_colors[savedir_index]
            self.selection_color = Config.selection_colors[savedir_index]
        style = f"""
            QTextEdit {{
                background-color: {Config.background_color};
                border: 1px solid {dir_color};
                color: {text_color};
                selection-background-color: {text_color};
            }}
            QScrollBar:vertical {{
                width: 15px;
                background: {Config.background_color};
            }}
            QScrollBar::handle:vertical {{
                background-color: {self.selection_color};
            }}
        """
        # box-shadow: 0px 0px 5px 0px {dir_color};
        self.text_box.setStyleSheet(style)

        doc = self.text_box.document()
        doc.setIndentWidth(1)

        self.setWidget(self.text_box)

    # position related functions:

    def mouseMoveEvent(self, event):
        # drag around
        mouse_end = QPointF(event.screenPos() / self.view.global_scale)
        displacement = self.get_plane_scale() * self.pin_pos
        self.plane_pos = mouse_end - displacement

        self.reposition()
        self.view.dummy.setFocus()

        self.detach_parent()

    def get_plane_scale(self):
        if self.autoshrink:
            # euclidean magniture of plane_pos
            distance = (self.plane_pos.x() ** 2 + self.plane_pos.y() ** 2) ** 0.5
            distance_scale = distance / Config._initial_distance
            return self.manual_scale * distance_scale
        else:
            return self.manual_scale

    def reposition(self):
        global_scale = self.view.global_scale
        self.setScale(self.get_plane_scale() * global_scale)
        self.setPos(self.plane_pos * global_scale)

        self.place_down_children()
        self.place_right_children()

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

    # text related functions:

    def save(self):
        if self.filename is None:
            # this buffer was not created by this program, so don't save it
            return

        # take the actual filename from the buffer
        buf_filename = self.buffer.name
        # make it relative to Path.cwd()
        buf_filename = Path(buf_filename).relative_to(Path.cwd()).as_posix()
        # make sure the actual filename is the same as given one
        assert buf_filename == self.filename, (buf_filename, self.filename)

        # set this buffer as current
        self.nvim.api.set_current_buf(self.buffer.number)
        # save it
        self.nvim.command("w")

    def highlight(self, color_style, start, end):
        color_format = QTextCharFormat()
        color_format.setBackground(QColor(color_style))

        start_pos = self._yx_to_pos(start[0], start[1] - 1)
        end_pos = self._yx_to_pos(end[0], end[1])

        cursor = self.text_box.textCursor()
        cursor.setPosition(start_pos, QTextCursor.MoveAnchor)
        cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(color_format)

    def _get_blocks(self):
        doc = self.text_box.document()
        block = doc.begin()
        while block.isValid():
            yield block
            block = block.next()

    def _format_displayed_lines(self):
        # set the fancy formatting, with nice indents and decreasing font sizes
        cursor = self.text_box.textCursor()
        block_format = QTextBlockFormat()
        for block in self._get_blocks():
            line = block.text()
            cursor.setPosition(block.position(), QTextCursor.MoveAnchor)
            cursor.setPosition(block.position() + len(line), QTextCursor.KeepAnchor)

            real_indent = len(line) - len(line.lstrip())
            if line == " ":
                # indent was added artificially, (not strictly true, but it's ok)
                real_indent = 0

            if real_indent < len(Config.font_sizes):
                font_size = Config.font_sizes[real_indent]
            else:
                font_size = Config.font_sizes[-1]

            font = QFont("monospace", font_size)
            font_format = QTextCharFormat()
            font_format.setFont(font)
            cursor.setCharFormat(font_format)

            indent_width = QFontMetrics(font).horizontalAdvance(" " * (2 + real_indent))
            block_format.setIndent(indent_width)
            block_format.setTextIndent(-indent_width)
            cursor.setBlockFormat(block_format)

            self.text_box.setTextCursor(cursor)

    def update_text(self, get_marks):
        lines = self.buffer[:]

        # maybeTODO optimization:
        # only during leaps all of the texts will be redrawn, so that can
        # become really slow - otherwise it's ok
        #  then I could go back to additionally checking if extmark changed

        # add space to empty lines so that cursor can be displayed there
        for i, line in enumerate(lines):
            if line == "":
                lines[i] = " "

        # set marks text (mainly for the leap plugin)
        if get_marks:
            marks = self.nvim.api.buf_get_extmarks(
                self.buffer.number, -1, (0, 0), (-1, -1), {"details": True}
            )
        else:
            marks = []
        mark_positions = []
        for _, y, x, details in marks:
            virt_text = details["virt_text"]
            assert len(virt_text) == 1, virt_text
            char, type_ = virt_text[0]
            if type_ == "Cursor":
                continue
            # maybeTODO later relax this?
            assert type_ == "LeapLabelPrimary" or type_ == "LeapLabelSecondary", marks
            # put that char into text
            lines[y] = lines[y][:x] + char + lines[y][x + 1 :]
            mark_positions.append((y, x))

        # set new text
        new_text = "\n".join(lines)
        self.text_box.setText(new_text)

        self._format_displayed_lines()

        # highlight the chars
        for y, x in mark_positions:
            self.highlight("brown", (y + 1, x + 1), (y + 1, x + 1))

        # clear cursor
        cursor = self.text_box.textCursor()
        cursor.setPosition(0)
        self.text_box.setTextCursor(cursor)

        # set height
        height = self.text_box.document().size().height() + 2
        height = min(height, Config.text_max_height)
        self.text_box.setFixedHeight(height)
        # for some weird reason, we need to set height twice,
        # for the nonpersistent buffers to update correctly
        height = self.text_box.document().size().height() + 2
        height = min(height, Config.text_max_height)
        self.text_box.setFixedHeight(height)

        # place children
        if height != self._last_height:
            self._last_height = height
            self.place_down_children()

    def update_current_text(self, mode_info):
        # this function if called only if this node's buffer is the current buffer

        mode = mode_info["mode"]

        # set selection
        if mode == "v" or mode == "V" or mode == "\x16":
            s = self.nvim.eval('getpos("v")')[1:3]
            e = self.nvim.eval('getpos(".")')[1:3]
            # if end before start, swap
            if s[0] > e[0] or (s[0] == e[0] and s[1] > e[1]):
                s, e = e, s
        if mode == "v":
            self.highlight(self.selection_color, s, e)
        elif mode == "V":
            # extend selection to full line
            s[1] = 1
            e[1] = len(self.buffer[e[0] - 1])
            self.highlight(self.selection_color, s, e)
        elif mode == "\x16":
            # visual block selection
            x_start = min(s[1], e[1])
            x_end = max(s[1], e[1])
            for y in range(s[0], e[0] + 1):
                self.highlight(self.selection_color, (y, x_start), (y, x_end))

        # set cursor
        curs_y, curs_x = self.nvim.current.window.cursor
        pos = self._yx_to_pos(curs_y, curs_x)
        cursor = self.text_box.textCursor()
        if mode == "n":
            cursor.setPosition(pos, QTextCursor.MoveAnchor)
            cursor.setPosition(pos + 1, QTextCursor.KeepAnchor)
        elif mode == "i":
            # get focus so that cursor is displayed
            self.text_box.setFocus()
            cursor.setPosition(pos)
        else:
            # set the cursor pos anyway, so that in visual widget scrolls to it
            cursor.setPosition(pos)
        self.text_box.setTextCursor(cursor)