from PySide6.QtCore import Qt


class KeyHandler:
    def __init__(self, nvim):
        self.nvim = nvim
        self.command = ""
        self.command_mode = False
        self.search_mode = False
        self.backward_search_mode = False

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

        # monitor command and search input
        mode = self.nvim.api.get_mode()["mode"]
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
            if text == "<Esc>":
                self.command_mode = False
                self.search_mode = False
                self.backward_search_mode = False
                self.command = ""
            elif text == "<BS>":
                self.command = self.command[:-1]
            elif text == "<CR>":
                if self.command_mode:
                    out = self.nvim.command_output(self.command)
                    print(f"output: '{out}'")
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
