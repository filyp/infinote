from collections import defaultdict, deque
from pathlib import Path
from typing import List

from boltons.dictutils import OrderedMultiDict
from PySide6.QtCore import QPointF

from infinote.config import Config
from infinote.text_object import BoxInfo, DraggableText, EditorBox, is_buf_empty


class BufferHandler:
    def __init__(self, nvim, view):
        self.nvim = nvim

        self.view = view
        self.jumplist = None  # must be set by view
        self.buf_num_to_text = {}
        self.forward_jumplist = []
        self.last_file_nums = defaultdict(lambda: 0)
        self.savedir_hues = {}
        self.to_redraw = set()
        self.parents = OrderedMultiDict()

        # start in insert mode if not in vim mode
        if not Config.vim_mode:
            self.nvim.command("startinsert")

    def get_num_unbound_buffers(self):
        return len(self.nvim.buffers) - len(self.buf_num_to_text)

    def open_filename(self, box_info, filename=None, buffer=None):
        if buffer is None and filename is not None:
            # no buffer provided, so open the one with the given filename
            num_of_texts = len(self.buf_num_to_text)
            if num_of_texts == 0:
                self.nvim.command(f"edit {filename}")
            elif num_of_texts == len(self.nvim.buffers):
                # create new file
                # this line is the loading time bottleneck - each call is 36ms
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

        text = DraggableText(box_info, self.nvim, buffer, filename, self.view, self.parents)
        self.view.scene().addItem(text)

        self.buf_num_to_text[buffer.number] = text
        return text

    def create_text(self, savedir, box_info):
        num_of_texts = len(self.buf_num_to_text)
        if num_of_texts == len(self.nvim.buffers) or num_of_texts == 0:
            self.last_file_nums[savedir] += 1
            filename = f"{savedir}/{self.last_file_nums[savedir]}.md"
            return self.open_filename(box_info, filename)

        # some buffer was created some other way than calling create_text,
        # so mark it to not be saved
        filename = None

        # get the unused buffer
        for buf in self.nvim.buffers:
            if buf.number not in self.buf_num_to_text:
                return self.open_filename(box_info, filename, buf)
        raise RuntimeError("no unused buffer found")

    def jump_to_buffer(self, buf_num):
        # jumping with ":buf <num>" would make some buffers hidden and break leap
        # so we need to jump to the right tab instead
        self.nvim.command(f"call GoToTabWithBuffer({buf_num})")

    def jump_to_file(self, filename):
        # jumping straight to the file would make some buffers hidden and break leap
        # so we need to jump to the right tab instead
        tab_num = None
        for tab in self.nvim.api.list_tabpages():
            wins = self.nvim.api.tabpage_list_wins(tab)
            assert len(wins) == 1, "each tab must have exactly one window"
            candidate_buf_num = self.nvim.api.win_get_buf(wins[0]).number
            candidate_filename = self.nvim.api.buf_get_name(candidate_buf_num)
            candidate_filename = Path(candidate_filename).relative_to(Path.cwd()).as_posix()
            if candidate_filename == filename:
                # found it
                tab_num = tab.number
                break
        assert tab_num is not None, "file not found"
        self.nvim.command(f"tabnext {tab_num}")

    def delete_buf(self, buf):
        text = self.buf_num_to_text.get(buf.number)
        # don't allow deleting if it has children
        children = self.parents.inverted().getlist(text)
        if children:
            self.view.msg("can't delete a text with children")
            return

        if text.filename is not None:
            # delete the file
            self.nvim.command(f"call delete('{text.filename}')")

        self.nvim.command(f"bwipeout! {buf.number}")
        self.view.scene().removeItem(text)
        self.buf_num_to_text.pop(buf.number)

        # delete from jumplists
        self.jumplist = [x for x in self.jumplist if x != buf.number]
        self.forward_jumplist = [x for x in self.forward_jumplist if x != buf.number]

        del text

    def get_texts(self):
        yield from self.buf_num_to_text.values()

    def get_root_texts(self):
        roots = set()
        for text in self.get_texts():
            while self.parents.get(text) is not None:
                text = self.parents[text]
            roots.add(text)
        return roots

    def get_current_text(self):
        return self.buf_num_to_text.get(self.nvim.current.buffer.number)

    def create_child(self):
        current_text = self.buf_num_to_text.get(self.nvim.current.buffer.number)

        if current_text.filename is None:
            # it's not a persistent buffer, so it shouldn't have children
            self.view.msg("can't create children for non-persistent buffers")
            return

        child = self.create_text(
            self.view.current_folder, BoxInfo(parent_filename=current_text.get_rel_filename())
        )
        self.parents[child] = current_text

        current_text.reposition()

        if Config.track_jumps_on_neighbor_moves:
            self.view.track_jump(current_text, child)

        self.view.zoom_on_text(child)

    def jump_back(self):
        if len(self.jumplist) <= 2:
            return
        old = self.jumplist.pop()
        self.forward_jumplist.append(old)
        self.jump_to_buffer(self.jumplist[-1])
        self.to_redraw.add(old)
        # old_buf = self.nvim.buffers[old]
        # if is_buf_empty(old_buf) or old_buf[:] == [Config.input_on_creation]:
        #     self.delete_buf(old_buf)

    def jump_forward(self):
        if len(self.forward_jumplist) == 0:
            return
        old = self.get_current_text().buffer.number
        self.to_redraw.add(old)
        new = self.forward_jumplist.pop()
        self.jumplist.append(new)
        self.jump_to_buffer(new)
        # old_buf = self.nvim.buffers[old]
        # if is_buf_empty(old_buf) or old_buf[:] == [Config.input_on_creation]:
        #     self.delete_buf(old_buf)

    def _sanitize_buffers(self):
        current_buffer, wins = self.nvim.api.call_atomic(
            [
                ["nvim_get_current_buf", []],
                ["nvim_tabpage_list_wins", [self.nvim.current.tabpage]],
            ]
        )[0]

        # make sure current tab has the current buffer
        # get the num of wins in this tab
        if len(wins) != 1:
            bufs_in_tab = {self.nvim.api.win_get_buf(win): win for win in wins}
            unbound_bufs = [buf for buf in bufs_in_tab if buf.number not in self.buf_num_to_text]
            for unb_buf in unbound_bufs:
                # delete its window
                win = bufs_in_tab[unb_buf]
                self.nvim.api.win_close(win, True)
            current_buffer = self.nvim.current.buffer

        # if hidden buffer focused, focus on the last chosen text
        if current_buffer.number not in self.buf_num_to_text:
            self.jump_to_buffer(self.jumplist[-1])
            current_buffer = self.nvim.current.buffer

        return current_buffer

    def _batched_get_nvim_info(self, to_fetch: List[int]):
        # get all relevalt data in a batched call
        functions = [
            ["nvim_eval", ["GetAllFolds()"]],
            ["nvim_eval", ['getpos("v")']],
            ["nvim_eval", ['getpos(".")']],
            ["nvim_win_get_cursor", [0]],
            ["nvim_eval", ["sign_getplaced()"]],
        ]
        for buf_num in to_fetch:
            functions.append(["nvim_buf_get_lines", [buf_num, 0, -1, False]])

        for buf_num in to_fetch:
            _args = [buf_num, -1, (0, 0), (-1, -1), {"details": True}]
            functions.append(["nvim_buf_get_extmarks", _args])

        # later also get highlight info of bookmarks

        results, errors = self.nvim.api.call_atomic(functions)
        assert errors is None, errors
        results = deque(results)

        cur_buf_info = dict(
            folds=results.popleft(),
            selection_start=results.popleft(),
            selection_end=results.popleft(),
            cursor_position=results.popleft(),
            bookmark_info=results.popleft(),
        )

        all_lines = dict()
        for buf_num in to_fetch:
            all_lines[buf_num] = results.popleft()

        all_extmarks = dict()
        for buf_num in to_fetch:
            all_extmarks[buf_num] = results.popleft()

        return cur_buf_info, all_lines, all_extmarks

    def update_all_texts(self):
        # TODO this line hangs if vim-ai is completing
        # so probably we'd neet to have our own completion
        mode_info = self.nvim.api.get_mode()
        if mode_info["blocking"]:
            return

        # unfocus the text boxes - but better would be to always have focus
        self.view.dummy.setFocus()
        self.to_redraw.add(self.jumplist[-1])

        # (note: sanitize_buffers can change the current buffer)
        current_buf = self._sanitize_buffers()

        # grow jumplist
        if current_buf.number != self.jumplist[-1] and current_buf.number in self.buf_num_to_text:
            self.jumplist.append(current_buf.number)
            self.forward_jumplist = []
            self.jumplist = self.jumplist[-30:]
            # if we jumped, make sure we are in insert mode (in case of leap or other motions)
            if not Config.vim_mode and mode_info["mode"] == "n":
                self.nvim.command("startinsert")
                mode_info = self.nvim.api.get_mode()

        self._redraw(mode_info, current_buf)

    def _redraw(self, mode_info, current_buf):
        # choose which ones to redraw
        self.to_redraw.add(current_buf.number)
        all_bufs = self.buf_num_to_text.keys()
        to_redraw = self.to_redraw & set(all_bufs)
        self.to_redraw = set()

        # get batched info from nvim about potentially changed buffers
        cur_buf_info, all_lines, all_extmarks = self._batched_get_nvim_info(all_bufs)
        for buf_num, extmarks in all_extmarks.items():
            if extmarks != []:
                to_redraw.add(buf_num)

        ####################################################
        # actual redraw

        # initial redraw
        for buf_num in to_redraw:
            text = self.buf_num_to_text[buf_num]
            lines = all_lines[buf_num]
            extmarks = all_extmarks[buf_num]
            text.insides_renderer.update_text(lines, extmarks)

        # draw the things that the current buffer has
        current_text = self.buf_num_to_text[current_buf.number]
        lines = all_lines[current_buf.number]
        current_text.insides_renderer.update_current_text(mode_info, cur_buf_info, lines)

        # draw sign lines
        for buf_num in to_redraw:
            text = self.buf_num_to_text[buf_num]
            text.insides_renderer.highlight_special_lines(all_lines[buf_num])

        # draw cursor in current
        if not self.view.show_editor:
            # note: it's deprecated
            # only draw if editor is hidden
            # otherwise, normal mode curson is shown but insert mode cursor not
            # and that's confusing
            # we'd need to find a way to display two cursors,
            # but only one widget can have focus
            current_text.insides_renderer.draw_cursor(mode_info, cur_buf_info)

        # set (invisible) cursor, hide folds
        for buf_num in to_redraw:
            text = self.buf_num_to_text[buf_num]
            # # hide folds deletes lines so it needs to be at the end
            # text.insides_renderer.set_invisible_cursor_pos()
            # text.insides_renderer.hide_folds() # todo maybe add it back later
            text.insides_renderer.hide_unimportant_lines()

        # reposition all text boxes
        for text in self.get_root_texts():
            text.reposition()

        # draw the editor
        if self.view.show_editor:
            buf_num = current_buf.number
            lines = all_lines[buf_num]
            extmarks = all_extmarks[buf_num]
            editor_box = self.view.editor_box
            editor_box.insides_renderer.update_text(lines, extmarks)
            editor_box.insides_renderer.update_current_text(mode_info, cur_buf_info, lines)
            editor_box.insides_renderer.highlight_special_lines(lines)
            editor_box.insides_renderer.draw_cursor(mode_info, cur_buf_info)
            editor_box.insides_renderer.set_invisible_cursor_pos()
            # editor_box.insides_renderer.hide_folds() # todo maybe add it back later

        ####################################################

        # mark texts with extmarks to be redrawn on next call
        for buf_num, extmarks in all_extmarks.items():
            if extmarks != []:
                self.to_redraw.add(buf_num)
