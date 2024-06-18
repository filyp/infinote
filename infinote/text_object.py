from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Tuple

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

# from PySide6.QtWidgets import QGraphicsDropShadowEffect


def is_buf_empty(buf):
    if len(buf) > 1:
        return False
    only_line = buf[0]
    if only_line.strip() == "":
        return True
    return False


class IgnoringKeysTextEdit(QTextEdit):
    # def mousePressEvent(self, event):
    #     # Skip the mouse press event to prevent it from being handled by QTextBrowser
    #     event.ignore()

    # def mouseMoveEvent(self, event):
    #     # Skip the mouse move event to prevent it from being handled by QTextBrowser
    #     event.ignore()

    # def mouseReleaseEvent(self, event):
    #     # Skip the mouse release event to prevent it from being handled by QTextBrowser
    #     event.ignore()

    def keyPressEvent(self, event):
        event.ignore()


class TextboxInsidesRenderer:
    def __init__(self, hue, init_folds, init_signs, style=None, set_width=True):
        self.text_box = IgnoringKeysTextEdit()
        if set_width:
            self.text_box.setFixedWidth(Config.text_width)
        self.folds = init_folds
        self._set_sign_lines(init_signs)
        self.cursor_pos = 0

        if style is None:
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
        self._border_glowing = False

        doc = self.text_box.document()
        doc.setIndentWidth(1)

    def _yx_to_pos(self, y, x):
        # get the one number char position
        doc = self.text_box.document()
        return doc.findBlockByLineNumber(y - 1).position() + x

    def _pos_to_yx(self, pos):
        # todo this will fail if some lines are hidden
        doc = self.text_box.document()
        block = doc.findBlock(pos)
        y = block.blockNumber() + 1
        x = pos - block.position()
        return y, x

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

    def sync_qt_cursor_into_vim(self, nvim):
        cursor = self.text_box.textCursor()
        cursor_pos = cursor.position()
        y, x = self._pos_to_yx(cursor_pos)
        nvim.api.win_set_cursor(0, (y, x))

    def if_qt_selection_sync_into_vim(self, nvim):
        # cursors https://doc.qt.io/qt-6/qtextedit.html#using-qtextedit-as-an-editor
        cursor = self.text_box.textCursor()
        # check if editor has selection
        if not cursor.hasSelection():
            return

        y_start, x_start = self._pos_to_yx(cursor.selectionStart())
        y_end, x_end = self._pos_to_yx(cursor.selectionEnd() - 1)

        nvim.input("<Esc>")
        nvim.api.win_set_cursor(0, (y_start, x_start))
        nvim.input("v")
        nvim.api.win_set_cursor(0, (y_end, x_end))

        # todo it will be buggy for now
        # in non-vim mode, backspace should do d
        # everything else chould be c...
        # we could now stop drawing manually vim selection
        # but then we also need sync it from vim into qt
        #     actually we can't bc rect selection can't be represented
        #     so just set the same style
        # and maybe change the style into something nicer in qt

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
            if "virt_text" not in details:
                continue
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

        # make sure border is not glowing
        self.set_border_glow(False)

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

        # make the text border glow
        self.set_border_glow(True)

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
        if self.folds == []:
            return
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

    def hide_indented_lines(self):
        # todo don't hide if
        lines = self.text_box.toPlainText().split("\n")
        line_nums_to_hide = []
        for i, line in enumerate(lines):
            if line.strip() == "":
                # keep empty lines
                continue
            if i + 1 in self.sign_lines:
                # keep bookmarked lines
                continue
            if line[0] == " " or line[0] == "\t":
                line_nums_to_hide.append(i)

        # delete the lines
        # note: it would be more efficient to only draw from the start what is necessary
        # but that complicates text marking positionings
        # maybe do it in the future if this part looks slow during profiling
        block = self.text_box.document().begin()
        cursor = self.text_box.textCursor()
        line_num = 0
        while block.isValid():
            if line_num in line_nums_to_hide:
                cursor.setPosition(block.position())
                cursor.select(QTextCursor.BlockUnderCursor)
                block = block.next()
                cursor.removeSelectedText()
            else:
                block = block.next()
            line_num += 1

    def draw_sign_lines(self, lines):
        for sign_line in self.sign_lines:
            if sign_line > len(lines):
                # print("warning: bookmarked line no longer exists")
                continue
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

    def set_border_glow(self, state):
        if state == self._border_glowing:
            return
        # replace border brightness
        brightness = Config.text_brightness if state else Config.border_brightness
        style = re.sub(
            r"(border: 1px solid hsl\(.*, .*,) (.*)\);",
            rf"\1 {brightness});",
            self.text_box.styleSheet(),
        )
        self.text_box.setStyleSheet(style)
        self._border_glowing = state


@dataclass
class BoxInfo:
    plane_pos: Tuple[float, float] = Config.initial_position
    manual_scale: float = Config.starting_box_scale
    scale_rel_to_parent: float = Config.child_relative_scale
    pos_rel_to_parent: Tuple[float, float] | None = None
    parent_filename: str | None = None


class DraggableText(QGraphicsProxyWidget):
    # it has position related functions
    def __init__(self, box_info, nvim, buffer_handle, filename, view, all_parents):
        super().__init__()

        # note that num doesn't need to be the same as buffer_handle.number
        self.buffer = buffer_handle
        self.filename = filename
        self.view = view
        self.all_parents = all_parents
        self.setScale(box_info.manual_scale)
        self._pin_pos = None
        self.folds = []
        self.sign_lines = []
        self._height = 0

        self.plane_pos = QPointF(*box_info.plane_pos)
        self.manual_scale = box_info.manual_scale
        # children specific: if this box is a child, only those have effect, and not the two above
        self.scale_rel_to_parent = box_info.scale_rel_to_parent
        # if kept at none, it will just be displayed to the right of the parent
        # otherwise, it's a tuple with x and y relative position to the parent
        self.pos_rel_to_parent = (
            QPointF(*box_info.pos_rel_to_parent) if box_info.pos_rel_to_parent else None
        )
        self.parent_filename = box_info.parent_filename

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

        # get folds and signs for potential future drawing
        assert self.buffer == nvim.current.buffer
        folds = nvim.eval("GetAllFolds()")
        signs = nvim.eval("sign_getplaced()")

        self.insides_renderer = TextboxInsidesRenderer(hue, folds, signs)

        self.setWidget(self.insides_renderer.text_box)

    def mouseMoveEvent(self, event):
        # # this reserves dragging for ctrl+drag, and normal selection for drag
        # is_ctrl_pressed = event.modifiers() & Qt.ControlModifier
        # if not is_ctrl_pressed:
        #     super().mouseMoveEvent(event)
        #     return

        # drag around
        mouse_end = QPointF(event.screenPos() / self.view.global_scale)
        displacement = self.get_plane_scale() * self._pin_pos
        self.plane_pos = mouse_end - displacement

        self.all_parents[self] = None
        self.reposition()
        # self.view.dummy.setFocus()

    def get_plane_scale(self):
        if self.parent_filename is not None:
            parent = self.all_parents[self]
            # todo the fact that it's recomputed may be inefficient for large trees
            return parent.get_plane_scale() * self.scale_rel_to_parent
        elif Config.autoshrink:
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
        self.update_height()

        # place children
        children = self.all_parents.inverted().getlist(self)
        width = self.get_plane_width()
        gap = Config.text_gap * self.get_plane_scale() / self.manual_scale
        height_acc = 0
        for child in children:
            child.plane_pos = self.plane_pos + QPointF(width + gap, height_acc)
            child.reposition()
            height_acc += child.get_plane_height() + gap

    def _calculate_height(self):
        height = self.insides_renderer.text_box.document().size().height() + 2
        height = min(height, Config.text_max_height)
        return height

    def update_height(self):
        # set height
        # for some reason it needs to be done twice, to prevent a glitch
        # only the smaller of those two heights is valid
        height = self._calculate_height()
        self.insides_renderer.text_box.setFixedHeight(height)
        height = min(self._calculate_height(), height)
        self.insides_renderer.text_box.setFixedHeight(height)
        self._height = height

    def get_plane_width(self):
        return self.get_plane_scale() * Config.text_width

    def get_plane_height(self):
        # this needs to be called after this node's reposition
        return self.get_plane_scale() * self._height

    def get_center(self):
        # note: it's in screen coords, not plane coords
        return self.mapToScene(self.rect().center())

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
    
    def get_rel_filename(self):
        if self.filename is None:
            return None
        return Path(self.filename).relative_to(self.view.workspace_dir).as_posix()
    
    def persist_info(self):
        if self.filename is None:
            return
        info = dict(
            plane_pos=tuple(self.plane_pos.toTuple()),
            manual_scale=self.manual_scale,
            scale_rel_to_parent=self.scale_rel_to_parent,
            pos_rel_to_parent=(
                tuple(self.pos_rel_to_parent.toTuple()) if self.pos_rel_to_parent else None
            ),
            parent_filename=self.parent_filename,
        )
        filepath = Path(self.filename).resolve()
        info_path = filepath.parent / ".box_info" / f"{filepath.stem}.json"
        info_path.write_text(json.dumps(info, indent=4))

    def load_info(self):
        if self.filename is None:
            return
        filepath = Path(self.filename).resolve()
        info_path = filepath.parent / ".box_info" / f"{filepath.stem}.json"
        info = json.loads(info_path.read_text())

        self.plane_pos = QPointF(*info["plane_pos"])
        self.manual_scale = info["manual_scale"]
        self.scale_rel_to_parent = info["scale_rel_to_parent"]
        if info["pos_rel_to_parent"] is not None:
            self.pos_rel_to_parent = QPointF(*info["pos_rel_to_parent"])
        self.parent_filename = info["parent_filename"]



class EditorBox(QGraphicsProxyWidget):
    def __init__(self, nvim, buffer_handle, view):
        super().__init__()
        self.view = view
        assert buffer_handle == nvim.current.buffer  # for correct fold & sign fetching

        hue = 180
        saturation = 0
        text_brightness = "100%"
        style = f"""
            QTextEdit {{
                background-color: {Config.background_color};
                border: 1px solid hsl({hue}, {saturation}%, {Config.text_brightness});
                color: hsl({hue}, {saturation}%, {text_brightness});
            }}
            QScrollBar:vertical {{
                width: 15px;
                background: {Config.background_color};
            }}
            QScrollBar::handle:vertical {{
                background-color: hsl({hue}, {saturation}%, {Config.border_brightness});
            }}
        """

        self.insides_renderer = TextboxInsidesRenderer(
            hue=hue,
            # get folds and signs for potential future drawing
            init_folds=nvim.eval("GetAllFolds()"),
            init_signs=nvim.eval("sign_getplaced()"),
            style=style,
            set_width=False,
        )

        self.setWidget(self.insides_renderer.text_box)

        # get screen dimensions
        screen = self.view.screen()
        x = screen.size().width()
        y = screen.size().height()

        # the box must take full height and right 1/3 of the screen
        margin = 0
        self.setGeometry(
            x * (1 - Config.editor_width_ratio),
            margin,
            x * Config.editor_width_ratio - margin - 2,
            y - 2 * margin - 2,
        )

        # make sure it is on top
        self.setZValue(1)
