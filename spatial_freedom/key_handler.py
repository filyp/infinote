from config import Config
from PySide6.QtCore import Qt

# # getting cmd output, but it's blocking:
# out = self.nvim.command_output(self.command)
# print(f"output: '{out}'")


class KeyHandler:
    def __init__(self, nvim, view):
        self.nvim = nvim
        self.view = view

        self.command = ""
        self.command_mode = False
        self.search_mode = False
        self.backward_search_mode = False
        self.leader_key_pressed = False

    def handle_key_event(self, event):
        special_keys = {
            32: "Space",
            16777219: "BS",
            16777216: "Esc",
            16777220: "CR",
            16777217: "Tab",
            16777232: "Home",
            16777233: "End",
            16777223: "Del",
            16777237: "Down",
            16777235: "Up",
            16777234: "Left",
            16777236: "Right",
            16777239: "PageDown",
            16777238: "PageUp",
        }
        key = event.key()
        if key in special_keys:
            text = special_keys[key]
        elif key < 0x110000:
            text = chr(key).lower()
        else:
            return

        mods = event.modifiers()
        # if ctrl
        if mods & Qt.ControlModifier:
            text = "C-" + text
        if mods & Qt.ShiftModifier:
            text = "S-" + text
        if mods & Qt.AltModifier:
            text = "A-" + text
        if mods & Qt.MetaModifier:
            text = "M-" + text
        # if mods & Qt.KeypadModifier:
        #     text = "W-" + text

        if mods or (key in special_keys):
            text = "<" + text + ">"

        mode = self.nvim.api.get_mode()["mode"]
        assert mode != "c", "there should be no way to get into command mode"

        # handle custom commands
        if self.leader_key_pressed:
            self.leader_key_pressed = False
            self.handle_custom_command(text)
            return
        if mode == "n" and text == Config.leader_key:
            # custom leader key pressed
            self.leader_key_pressed = True
            return

        # monitor command and search input
        if mode == "n":
            if text == "<S-:>" or text == ":":
                self.command_mode = True
                return
            elif text == "/":
                self.search_mode = True
                return
            elif text in ["<S-/>", "<S-?>", "?"]:
                self.backward_search_mode = True
                return
        if self.command_mode or self.search_mode or self.backward_search_mode:
            # eat the keypress into self.command
            if text == "<Esc>":
                self.command_mode = False
                self.search_mode = False
                self.backward_search_mode = False
                self.command = ""
            elif text == "<BS>":
                self.command = self.command[:-1]
            elif text == "<CR>":
                if self.command_mode:
                    self.nvim.input(f":{self.command}<CR>")
                elif self.search_mode:
                    self.nvim.input(f"/{self.command}<CR>")
                elif self.backward_search_mode:
                    self.nvim.input(f"?{self.command}<CR>")
                self.command_mode = False
                self.search_mode = False
                self.backward_search_mode = False
                self.command = ""
            elif event.text():
                self.command += event.text()
            return

        # custom C-o and C-i, because normal ones create unwanted buffers
        buf_handler = self.view.buf_handler
        if mode == "n" and text == "<C-o>":
            if len(buf_handler.jumplist) == 2:
                return
            current = buf_handler.jumplist.pop()
            buf_handler.forward_jumplist.append(current)
            buf_handler.jump_to_buffer(buf_handler.jumplist[-1])
            return
        if mode == "n" and text == "<C-i>":
            if len(buf_handler.forward_jumplist) == 0:
                return
            new = buf_handler.forward_jumplist.pop()
            buf_handler.jumplist.append(new)
            buf_handler.jump_to_buffer(new)
            return

        # send that key
        self.nvim.input(text)

    def get_command_line(self):
        if self.command_mode:
            return ":" + self.command
        elif self.search_mode:
            return "/" + self.command
        elif self.backward_search_mode:
            return "?" + self.command
        else:
            return ""

    def handle_custom_command(self, cmd_char):
        match cmd_char:
            case Config.hop_key:
                cmd = ":lua require('leap').leap { target_windows = vim.api.nvim_list_wins() }"
                self.nvim.input(f":{cmd}<CR>")
            case Config.bookmark_jump_key:
                cmd = (
                    '<Home>"fyt|f|<Right>"lyiw:buffer<Space><C-r>f<Enter>:<C-r>l<Enter>'
                )
                self.nvim.input(cmd)
            case Config.create_child_down_key:
                self.view.buf_handler.create_child("down")
            case Config.create_child_right_key:
                self.view.buf_handler.create_child("right")
