import time
from collections import defaultdict
from pathlib import Path

import pynvim
from config import Config
from PySide6.QtCore import QPointF, Qt, QTimer
from text_object import DraggableText


class BufferHandler:
    def __init__(self, nvim, view):
        self.nvim = nvim

        self.view = view
        self.jumplist = None  # must be set by view
        self.last_file_nums = defaultdict(lambda: 0)
        self._buffer_to_text = {}
        self.forward_jumplist = []
        self.savedir_indexes = {}
        self._last_forced_redraw = None

    def get_num_unbound_buffers(self):
        return len(self.nvim.buffers) - len(self._buffer_to_text)

    def open_filename(self, pos, manual_scale, filename=None, buffer=None):
        if isinstance(pos, (tuple, list)):
            pos = QPointF(*pos)

        if buffer is None and filename is not None:
            # no buffer provided, so open the one with the given filename
            num_of_texts = len(self._buffer_to_text)
            if num_of_texts == 0:
                self.nvim.command(f"edit {filename}")
            elif num_of_texts == len(self.nvim.buffers):
                # create new file
                self.nvim.command(f"tabnew {filename}")
            buffer = self.nvim.current.buffer
        elif buffer is not None and filename is None:
            # buffer provided, so open it
            self.nvim.command("tabnew")
            self.nvim.command(f"buffer {buffer.number}")
            # delete the buffer that was created by tabnew
            self.nvim.command("bwipeout! #")
        else:
            raise ValueError("either buffer or filename must be provided")

        text = DraggableText(self.nvim, buffer, filename, self.view, pos, manual_scale)
        self.view.scene().addItem(text)

        _tab_num = self.nvim.api.get_current_tabpage().number
        self._buffer_to_text[buffer] = text
        return text

    def jump_to_buffer(self, buf_num):
        # jumping with ":buf <num>" would make some buffers hidden and break leap
        tab_num = None
        for tab in self.nvim.api.list_tabpages():
            wins = self.nvim.api.tabpage_list_wins(tab)
            assert len(wins) == 1, "each tab must have exactly one window"
            candidate_buf_num = self.nvim.api.win_get_buf(wins[0]).number
            if candidate_buf_num == buf_num:
                # found it
                tab_num = tab.number
                break
        assert tab_num is not None, "buffer not found"
        self.nvim.command(f"tabnext {tab_num}")

    def jump_to_file(self, filename):
        tab_num = None
        for tab in self.nvim.api.list_tabpages():
            wins = self.nvim.api.tabpage_list_wins(tab)
            assert len(wins) == 1, "each tab must have exactly one window"
            candidate_buf_num = self.nvim.api.win_get_buf(wins[0]).number
            candidate_filename = self.nvim.api.buf_get_name(candidate_buf_num)
            candidate_filename = (
                Path(candidate_filename).relative_to(Path.cwd()).as_posix()
            )
            if candidate_filename == filename:
                # found it
                tab_num = tab.number
                break
        assert tab_num is not None, "file not found"
        self.nvim.command(f"tabnext {tab_num}")

    def create_text(self, savedir, pos, manual_scale=Config.starting_box_scale):
        num_of_texts = len(self._buffer_to_text)
        if num_of_texts == len(self.nvim.buffers) or num_of_texts == 0:
            self.last_file_nums[savedir] += 1
            filename = f"{savedir}/{self.last_file_nums[savedir]}.md"
            return self.open_filename(pos, manual_scale, filename)

        # some buffer was created some other way than calling create_text,
        # so mark it to not be saved
        filename = None

        # get the unused buffer
        for buf in self.nvim.buffers:
            if buf not in self._buffer_to_text:
                return self.open_filename(pos, manual_scale, filename, buf)
        raise RuntimeError("no unused buffer found")

    def update_all_texts(self):
        start = time.time()
        mode = self.nvim.api.get_mode()
        if mode["blocking"]:
            return

        start = time.time()
        # unfocus the text boxes - better would be to always have focus
        self.view.dummy.setFocus()

        # (it's better to do this once and pass around, bc every nvim api query is ~3ms)
        current_buffer = self.nvim.current.buffer
        jumped = current_buffer != self.jumplist[-1]

        # there are glitches when moving texts around
        # so redraw the background first
        # TODO this does not work
        # note: this happens only when maximized

        # delete empty texts
        for last_buf in self.jumplist[-1:]:
            text = self._buffer_to_text.get(self.nvim.buffers[last_buf])
            if text.buffer == current_buffer:
                # current buffer can be empty
                continue
            if self.nvim.api.buf_line_count(text.buffer) > 1:
                continue
            only_line = text.buffer[0]
            if only_line.strip() == "":
                if text.filename is not None:
                    self.nvim.command(f"call delete('{text.filename}')")
                self.nvim.command(f"bwipeout! {text.buffer.number}")
                self.view.scene().removeItem(text)
                self._buffer_to_text.pop(text.buffer)
                # detach
                text.detach_parent()
                text.detach_children()
                # delete from jumplists
                buf_num = text.buffer.number
                self.jumplist = [x for x in self.jumplist if x != buf_num]
                self.forward_jumplist = [
                    x for x in self.forward_jumplist if x != buf_num
                ]

                del text

        # make sure current tab has the current buffer
        current_tab = self.nvim.api.get_current_tabpage()
        # get the num of buffers in this tab
        wins = self.nvim.api.tabpage_list_wins(current_tab)
        if len(wins) != 1:
            bufs_in_tab = {self.nvim.api.win_get_buf(win): win for win in wins}
            unbound_bufs = [
                buf for buf in bufs_in_tab if buf not in self._buffer_to_text
            ]
            for unb_buf in unbound_bufs:
                # delete its window
                win = bufs_in_tab[unb_buf]
                self.nvim.api.win_close(win, True)

        # if hidden buffer focused, focus on the last chosen text
        if current_buffer not in self._buffer_to_text:
            self.jump_to_buffer(self.jumplist[-1])
            current_buffer = self.nvim.current.buffer

        # grow jumplist
        if (
            current_buffer.number != self.jumplist[-1]
            and current_buffer in self._buffer_to_text
        ):
            self.jumplist.append(current_buffer.number)
            self.forward_jumplist = []
            self.jumplist = self.jumplist[-10:]

        # redraw
        cur_buf_marks = self.nvim.api.buf_get_extmarks(
            current_buffer.number, -1, (0, 0), (-1, -1), {}
        )
        # note that in principle other buffers could have marks
        # but when it comes to leap marks, they are only present iff current buffer
        # has some too
        get_marks = cur_buf_marks != []
        force_redraw_now = cur_buf_marks != []
        force_redraw = (
            force_redraw_now
            or self._last_forced_redraw
            or self._last_forced_redraw is None  # first time
            or jumped
        )
        self._last_forced_redraw = force_redraw_now
        # print()
        for text in self.get_texts():
            start = time.time()
            text.update_text(current_buffer, force_redraw, mode, get_marks)
            # print("update_text", time.time() - start)
        for text in self.get_texts():
            # TODO actually reposition should be called only on root texts
            # but the overhead is tiny
            text.reposition()
        # print("update_all_texts", time.time() - start)

    def get_texts(self):
        yield from self._buffer_to_text.values()

    def get_current_text(self):
        return self._buffer_to_text.get(self.nvim.current.buffer)

    def create_child(self, side):
        current_text = self.get_current_text()

        if current_text.filename is None:
            # it's not a persistent buffer, so it shouldn't have children
            self.view.msg("can't create children for non-persistent buffers")
            return

        if side == "right":
            if current_text.child_right is not None:
                self.view.msg("right child already exists")
                return
            child = self.create_text(self.view.current_folder, (0, 0))
            current_text.child_right = child
        elif side == "down":
            if current_text.child_down is not None:
                self.view.msg("down child already exists")
                return
            child = self.create_text(self.view.current_folder, (0, 0))
            current_text.child_down = child
        else:
            raise ValueError("side must be 'right' or 'down'")

        child.parent = current_text
        current_text.reposition()
