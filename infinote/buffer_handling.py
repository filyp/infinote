from collections import defaultdict

import pynvim
from config import Config
from PySide6.QtCore import QPointF, Qt, QTimer
from text_object import DraggableText


class BufferHandler:
    def __init__(self, nvim, view):
        self.nvim = nvim

        self.view = view
        # defaultdict use for last file nums
        self.last_file_nums = defaultdict(lambda: 0)
        self._buffer_to_text = {}
        self._buf_num_to_tab_num = {}
        self.jumplist = [None]
        self.forward_jumplist = []
        self.savedir_indexes = {}

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
        self._buf_num_to_tab_num[buffer.number] = _tab_num
        self._buffer_to_text[buffer] = text

        self.update_all_texts()
        return text

    def jump_to_buffer(self, buf_num):
        # jumping with ":buf <num>" would make some buffers hidden and break leap
        tab_num = self._buf_num_to_tab_num[buf_num]

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
        # unfocus the text boxes - better would be to always have focus
        self.view.dummy.setFocus()

        if self.nvim.api.get_mode()["blocking"]:
            return

        # there are glitches when moving texts around
        # so redraw the background first (black)
        # TODO this does not work
        # note: this happens only when maximized

        # delete empty texts
        for text in list(self.get_texts()):
            if text.buffer == self.nvim.current.buffer:
                # current buffer can be empty
                continue
            if text.buffer[:] == [""] or not text.buffer[:]:
                if text.filename is not None:
                    self.nvim.command(f"call delete('{text.filename}')")
                self.nvim.command(f"bwipeout! {text.buffer.number}")
                self.view.scene().removeItem(text)
                self._buffer_to_text.pop(text.buffer)
                self._buf_num_to_tab_num.pop(text.buffer.number)
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

        # make sure each tab has exactly one buffer
        for tab in self._buf_num_to_tab_num.values():
            # get the num of buffers in this tab
            wins = self.nvim.api.tabpage_list_wins(tab)
            if len(wins) == 1:
                continue
            bufs_in_tab = {self.nvim.api.win_get_buf(win): win for win in wins}
            unbound_bufs = [
                buf for buf in bufs_in_tab if buf not in self._buffer_to_text
            ]
            for unb_buf in unbound_bufs:
                # delete its window
                win = bufs_in_tab[unb_buf]
                self.nvim.api.win_close(win, True)

        # if hidden buffer focused, focus on the last chosen text
        if self.nvim.current.buffer not in self._buffer_to_text:
            self.jump_to_buffer(self.jumplist[-1])

        # grow jumplist
        current_buf = self.nvim.current.buffer
        if (
            current_buf.number != self.jumplist[-1]
            and current_buf in self._buffer_to_text
        ):
            self.jumplist.append(current_buf.number)
            self.forward_jumplist = []
            self.jumplist = self.jumplist[-10:]

        # redraw
        for text in self.get_texts():
            text.update_text()
            text.reposition()

    def get_texts(self):
        yield from self._buffer_to_text.values()

    def _get_current_text(self):
        return self._buffer_to_text.get(self.nvim.current.buffer)

    def create_child(self, side):
        current_text = self._get_current_text()

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
