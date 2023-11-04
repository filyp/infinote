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
        self._buf_num_to_text = {}
        self.forward_jumplist = []
        self.savedir_indexes = {}
        self._full_redraw_on_next_update = True

    def get_num_unbound_buffers(self):
        return len(self.nvim.buffers) - len(self._buf_num_to_text)

    def open_filename(self, pos, manual_scale, filename=None, buffer=None):
        if isinstance(pos, (tuple, list)):
            pos = QPointF(*pos)

        if buffer is None and filename is not None:
            # no buffer provided, so open the one with the given filename
            num_of_texts = len(self._buf_num_to_text)
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
        self._buf_num_to_text[buffer.number] = text
        return text

    def jump_to_buffer(self, buf_num):
        # jumping with ":buf <num>" would make some buffers hidden and break leap
        # so we need to jump to the right tab instead
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
        # jumping straight to the file would make some buffers hidden and break leap
        # so we need to jump to the right tab instead
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
        num_of_texts = len(self._buf_num_to_text)
        if num_of_texts == len(self.nvim.buffers) or num_of_texts == 0:
            self.last_file_nums[savedir] += 1
            filename = f"{savedir}/{self.last_file_nums[savedir]}.md"
            return self.open_filename(pos, manual_scale, filename)

        # some buffer was created some other way than calling create_text,
        # so mark it to not be saved
        filename = None

        # get the unused buffer
        for buf in self.nvim.buffers:
            if buf.number not in self._buf_num_to_text:
                return self.open_filename(pos, manual_scale, filename, buf)
        raise RuntimeError("no unused buffer found")

    def _is_buf_empty(self, buf):
        if self.nvim.api.buf_line_count(buf) > 1:
            return False
        only_line = buf[0]
        if only_line.strip() == "":
            return True
        return False

    def _delete_buf(self, buf):
        text = self._buf_num_to_text.get(buf.number)

        if text.filename is not None:
            # delete the file
            self.nvim.command(f"call delete('{text.filename}')")

        self.nvim.command(f"bwipeout! {buf.number}")
        self.view.scene().removeItem(text)
        self._buf_num_to_text.pop(buf.number)

        # detach
        text.detach_parent()
        text.detach_children()

        # delete from jumplists
        self.jumplist = [x for x in self.jumplist if x != buf.number]
        self.forward_jumplist = [x for x in self.forward_jumplist if x != buf.number]

        del text

    def update_all_texts(self):
        mode_info = self.nvim.api.get_mode()
        if mode_info["blocking"]:
            return

        # unfocus the text boxes - better would be to always have focus
        self.view.dummy.setFocus()

        # (it's better to do this once and pass around, bc every nvim api query is ~3ms)
        current_buffer = self.nvim.current.buffer
        last_focused = self.jumplist[-1]

        # there are glitches when moving texts around
        # so redraw the background first
        # TODO this does not work
        # note: this happens only when maximized

        # delete last buf if it's empty and unfocused
        if self.jumplist[-1] != current_buffer.number:
            _last_buf = self.nvim.buffers[self.jumplist[-1]]
            if self._is_buf_empty(_last_buf):
                self._delete_buf(_last_buf)

        # make sure current tab has the current buffer
        # get the num of buffers in this tab
        wins = self.nvim.current.tabpage.windows
        if len(wins) != 1:
            wins = self.nvim.current.tabpage.windows
            bufs_in_tab = {self.nvim.api.win_get_buf(win): win for win in wins}
            unbound_bufs = [
                buf for buf in bufs_in_tab if buf.number not in self._buf_num_to_text
            ]
            for unb_buf in unbound_bufs:
                # delete its window
                win = bufs_in_tab[unb_buf]
                self.nvim.api.win_close(win, True)

        # if hidden buffer focused, focus on the last chosen text
        if current_buffer.number not in self._buf_num_to_text:
            self.jump_to_buffer(self.jumplist[-1])
            current_buffer = self.nvim.current.buffer

        # grow jumplist
        if (
            current_buffer.number != self.jumplist[-1]
            and current_buffer.number in self._buf_num_to_text
        ):
            self.jumplist.append(current_buffer.number)
            self.forward_jumplist = []
            self.jumplist = self.jumplist[-10:]

        # redraw
        # note that in principle other buffers could have marks
        # but when it comes to leap marks, they are only present iff current buffer
        # has some too
        get_extmarks = [] != self.nvim.api.buf_get_extmarks(
            current_buffer.number, -1, (0, 0), (-1, -1), {}
        )

        if get_extmarks or self._full_redraw_on_next_update:
            # redraw all
            to_redraw = set(self._buf_num_to_text.keys())
        else:
            to_redraw = set((current_buffer.number, last_focused))

        for buf_num in to_redraw:
            text = self._buf_num_to_text[buf_num]
            text.update_text(get_extmarks)

        current_text = self._buf_num_to_text[current_buffer.number]
        current_text.update_current_text(mode_info)

        for text in self.get_texts():
            # TODO actually reposition should be called only on root texts, but the overhead is tiny
            text.reposition()

        self._full_redraw_on_next_update = get_extmarks

    def get_texts(self):
        yield from self._buf_num_to_text.values()

    def get_current_text(self):
        return self._buf_num_to_text.get(self.nvim.current.buffer.number)

    def create_child(self, side):
        current_text = self._buf_num_to_text.get(self.nvim.current.buffer.number)

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

        if Config.track_jumps_on_neighbor_moves:
            self.view.track_jump(current_text, child)