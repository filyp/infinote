from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QGraphicsProxyWidget, QTextBrowser, QTextEdit

from infinote.config import Config


def is_buf_empty(buf):
    if len(buf) > 1:
        return False
    only_line = buf[0]
    if only_line.strip() == "":
        return True
    return False


# class NonSelectableTextEdit(QTextBrowser):
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
        self.folds = []
        self.sign_lines = []
        self._height = 0
        self.cursor_pos = 0

        self.text_box = NonSelectableTextEdit()
        self.text_box.setFixedWidth(Config.text_width)

        # get folds for potential future fold drawing
        assert self.buffer == nvim.current.buffer
        self.folds = nvim.eval("GetAllFolds()")

        signs = nvim.eval("sign_getplaced()")
        self._set_sign_lines(signs)

        # optionally, send some input on creation
        if is_buf_empty(self.buffer) and Config.input_on_creation:
            nvim.command("startinsert")
            nvim.input(Config.input_on_creation)

        if filename is None:
            # it's non-persistent buffer, so mark its border yellow
            hue = Config.non_persistent_hue
        else:
            savedir = Path(filename).parent
            hue = self.view.buf_handler.savedir_hues[savedir]
        style = f"""
            QTextEdit {{
                background-color: {Config.background_color};
                border: 1px solid hsl({hue}, 96%, {Config.border_brightness});
                color: hsl({hue}, 96%, {Config.text_brightness});
            }}
            QScrollBar:vertical {{
                width: 15px;
                background: {Config.background_color};
            }}
            QScrollBar::handle:vertical {{
                background-color: hsl({hue}, 96%, {Config.border_brightness});
            }}
        """
        self.text_box.setStyleSheet(style)

        self.text_color = QColor()
        self.text_color.setHsl(hue, 96, int(Config.text_brightness[:-1]))
        self.selection_color = QColor()
        self.selection_color.setHsl(hue, 96, int(Config.selection_brightness[:-1]))

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

        # set height
        # for some reason it needs to be done twice, to prevent a glitch
        # only the smaller of those two heights is valid
        height = self._calculate_height()
        self.text_box.setFixedHeight(height)
        height = min(self._calculate_height(), height)
        self.text_box.setFixedHeight(height)
        self._height = height

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
            height = self.get_plane_height()
            gap = Config.text_gap * self.get_plane_scale() / self.manual_scale
            self.child_down.plane_pos = self.plane_pos + QPointF(0, height + gap)
            self.child_down.reposition()

    def place_right_children(self):
        if self.child_right is not None:
            width = self.get_plane_width()
            gap = Config.text_gap * self.get_plane_scale() / self.manual_scale
            self.child_right.plane_pos = self.plane_pos + QPointF(width + gap, 0)
            self.child_right.reposition()

    def _calculate_height(self):
        height = self.text_box.document().size().height() + 2
        height = min(height, Config.text_max_height)
        return height

    def get_plane_width(self):
        return self.get_plane_scale() * Config.text_width

    def get_plane_height(self):
        # this needs to be called only after this node's reposition
        return self.get_plane_scale() * self._height

    def get_center(self):
        # note: it's in screen coords, not plane coords
        return self.mapToScene(self.rect().center())

    # text related functions:

    def save(self, nvim):
        if self.filename is None:
            # this buffer was not created by this program, so don't save it
            return

        # take the actual filename from the buffer
        buf_filename = self.buffer.name
        buf_filename = Path(buf_filename).resolve().as_posix()
        # make sure the actual filename is the same as given one
        assert buf_filename == self.filename, (buf_filename, self.filename)

        # set this buffer as current
        nvim.api.set_current_buf(self.buffer.number)
        # save it
        nvim.command("w")

    def highlight(self, color, start, end, invert=False):
        if not isinstance(color, QColor):
            color = QColor(color)
        color_format = QTextCharFormat()
        color_format.setBackground(color)
        if invert:
            color_format.setForeground(QColor(Config.background_color))

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
                font = Config.fonts[real_indent]
            else:
                font = Config.fonts[-1]

            font_format = QTextCharFormat()
            font_format.setFont(font)
            cursor.setCharFormat(font_format)

            indent_width = QFontMetrics(font).horizontalAdvance(" " * (2 + real_indent))
            block_format.setIndent(indent_width)
            block_format.setTextIndent(-indent_width)
            cursor.setBlockFormat(block_format)

    def update_text(self, lines, extmarks):
        # maybeTODO optimization:
        # only during leaps all of the texts will be redrawn, so that can
        # become really slow - otherwise it's ok
        #  then I could go back to additionally checking if extmark changed

        # add space to empty lines so that cursor can be displayed there
        for i, line in enumerate(lines):
            if line == "":
                lines[i] = " "

        # set marks text (mainly for the leap plugin)
        mark_positions = []
        for _, y, x, details in extmarks:
            virt_text = details["virt_text"]
            assert len(virt_text) == 1, virt_text
            char, type_ = virt_text[0]
            if type_ == "Cursor":
                continue
            # maybeTODO later relax this?
            assert type_ in ["LeapLabelPrimary", "LeapLabelSecondary"], extmarks
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

    def update_current_text(self, mode_info, cur_buf_info, lines):
        # this function if called only if this node's buffer is the current buffer
        mode = mode_info["mode"]

        # get folds for potential future fold drawing
        self.folds = cur_buf_info["folds"]

        # get highlight bookmarks for potential future drawing
        self._set_sign_lines(cur_buf_info["bookmark_info"])

        # set selection
        if mode == "v" or mode == "V" or mode == "\x16":
            s = cur_buf_info["selection_start"][1:3]
            e = cur_buf_info["selection_end"][1:3]
            # if end before start, swap
            if s[0] > e[0] or (s[0] == e[0] and s[1] > e[1]):
                s, e = e, s
        if mode == "v":
            self.highlight(self.selection_color, s, e)
        elif mode == "V":
            # extend selection to full line
            s[1] = 1
            e[1] = len(lines[e[0] - 1])
            self.highlight(self.selection_color, s, e)
        elif mode == "\x16":
            # visual block selection
            x_start = min(s[1], e[1])
            x_end = max(s[1], e[1])
            for y in range(s[0], e[0] + 1):
                self.highlight(self.selection_color, (y, x_start), (y, x_end))

    def draw_cursor(self, mode_info, cur_buf_info):
        mode = mode_info["mode"]
        # set cursor
        curs_y, curs_x = cur_buf_info["cursor_position"]
        pos = self._yx_to_pos(curs_y, curs_x)
        if mode == "n":
            _yx_pos = (curs_y, curs_x + 1)
            self.highlight(self.text_color, _yx_pos, _yx_pos, invert=True)
        elif mode == "i":
            # get focus so that cursor is displayed
            self.text_box.setFocus()
        self.cursor_pos = pos

    def hide_folds(self):
        # set folds
        head_lines = set()
        hidden_lines = set()
        for fold in self.folds:
            head_lines.add(fold[0])
            current = fold[0] + 1
            while current <= fold[1]:
                hidden_lines.add(current)
                current += 1

        block = self.text_box.document().begin()
        cursor = self.text_box.textCursor()
        line_num = 1
        while block.isValid():
            if line_num in hidden_lines:
                cursor.setPosition(block.position())
                cursor.select(QTextCursor.BlockUnderCursor)
                block = block.next()
                cursor.removeSelectedText()
            elif line_num in head_lines:
                cursor.setPosition(block.position() + block.length() - 1)
                cursor.insertText(" ...")
                block = block.next()
            else:
                block = block.next()
            line_num += 1

    def draw_sign_lines(self, lines):
        for sign_line in self.sign_lines:
            line_width = len(lines[sign_line - 1])
            self.highlight(Config.sign_color, (sign_line, 1), (sign_line, line_width))

    def _set_sign_lines(self, signs):
        if signs != []:
            signs = signs[0]["signs"]
            self.sign_lines = [sign["lnum"] for sign in signs]
        else:
            self.sign_lines = []

    def set_invisible_cursor_pos(self):
        # to prevent weird line glitches, we need to set always the same cursor font
        # and have it as a normal caret, not selection
        cursor = self.text_box.textCursor()
        cursor.setPosition(self.cursor_pos)
        font = Config.fonts[0]
        font_format = QTextCharFormat()
        font_format.setFont(font)
        cursor.setCharFormat(font_format)
        self.text_box.setTextCursor(cursor)
