from PySide6.QtCore import Qt, QTimer

from infinote.config import Config


def parse_key_event_into_text(event):
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

    return text


class KeyHandler:
    def __init__(self, nvim, view):
        self.nvim = nvim
        self.view = view

        self.command = ""
        self.command_mode = False
        self.external_command_mode = False
        self.search_mode = False
        self.backward_search_mode = False
        self._leader_key_last_pressed = False

    def _absorb_key_into_command_line(self, text, event):
        if text == "<Esc>":
            if self.external_command_mode:
                self.nvim.input("<Esc>")
            self.command_mode = False
            self.external_command_mode = False
            self.search_mode = False
            self.backward_search_mode = False
            self.command = ""
        elif text == "<BS>":
            self.command = self.command[:-1]
        elif text == "<CR>":
            if self.command_mode:
                self.nvim.input(f":{self.command}<CR>")
            elif self.external_command_mode:
                self.nvim.input(f"{self.command}<CR>")
            elif self.search_mode:
                self.nvim.input(f"/{self.command}<CR>")
            elif self.backward_search_mode:
                self.nvim.input(f"?{self.command}<CR>")
            self.command_mode = False
            self.external_command_mode = False
            self.search_mode = False
            self.backward_search_mode = False
            self.command = ""
        elif event.text():
            self.command += event.text()

    def handle_key_event(self, event):
        text = parse_key_event_into_text(event)
        if text is None:
            return

        if text in Config.keys:
            # custom command pressed
            self.handle_custom_command(text)
            return

        mode = self.nvim.api.get_mode()["mode"]
        if mode != "n" and mode != "c":
            # send that key
            self.nvim.input(text)
            return
        # if we're here, we're in normal or command mode

        # handle custom commands
        if self._leader_key_last_pressed:
            self._leader_key_last_pressed = False
            self.handle_custom_command(Config.leader_key + text)
            return

        # monitor command and search input
        if (
            self.command_mode
            or self.external_command_mode
            or self.search_mode
            or self.backward_search_mode
        ):
            # eat the keypress into self.command
            self._absorb_key_into_command_line(text, event)
            return

        match text:
            case Config.leader_key:
                self._leader_key_last_pressed = True

            # handle entering command line
            case "<S-:>" | ":":
                self.command_mode = True
            case "/":
                self.search_mode = True
            case "<S-/>" | "<S-?>" | "?":
                self.backward_search_mode = True

            case _:
                # send that key
                self.nvim.input(text)

    def get_command_line(self):
        if self.command_mode:
            return ":" + self.command
        elif self.external_command_mode:
            return ":... " + self.command
        elif self.search_mode:
            return "/" + self.command
        elif self.backward_search_mode:
            return "?" + self.command
        else:
            return ""

    def handle_custom_command(self, key_combo):
        if key_combo not in Config.keys:
            return
        command = Config.keys[key_combo]

        buf_handler = self.view.buf_handler
        view = self.view

        match command:
            case "hop":
                cmd = ":lua require('leap').leap { target_windows = vim.api.nvim_list_wins() }"
                self.nvim.input(f":{cmd}<CR>")
            case "bookmark jump":
                cmd = (
                    '<Home>"fyt|f|<Right>"lyiw:buffer<Space><C-r>f<Enter>:<C-r>l<Enter>'
                )
                self.nvim.input(cmd)
                view.zoom_on_text(buf_handler.get_current_text())
            case "center on current text":
                current_text = buf_handler.get_current_text()
                view.global_scale = view.get_scale_centered_on_text(current_text)
            case "maximize on current text":
                current_text = buf_handler.get_current_text()
                view.global_scale = view.get_scale_maximized_on_text(current_text)
            case "create child down":
                buf_handler.create_child("down")
            case "create child right":
                buf_handler.create_child("right")
            case "move down":
                view.jump_to_neighbor("down")
            case "move up":
                view.jump_to_neighbor("up")
            case "move left":
                view.jump_to_neighbor("left")
            case "move right":
                view.jump_to_neighbor("right")
            case "zoom up":
                if view.timer is None:
                    view.timer = QTimer()
                    view.timer.timeout.connect(lambda: view.zoom(-1))
                    view.timer.start(1000 / Config.FPS)
            case "zoom down":
                if view.timer is None:
                    view.timer = QTimer()
                    view.timer.timeout.connect(lambda: view.zoom(1))
                    view.timer.start(1000 / Config.FPS)
            case "grow box":
                if view.timer is None:
                    view.timer = QTimer()
                    view.timer.timeout.connect(lambda: view.resize(1))
                    view.timer.start(1000 / Config.FPS)
            case "shrink box":
                if view.timer is None:
                    view.timer = QTimer()
                    view.timer.timeout.connect(lambda: view.resize(-1))
                    view.timer.start(1000 / Config.FPS)
            case "jump back":
                buf_handler.jump_back()
                view.zoom_on_text(buf_handler.get_current_text())
            case "jump forward":
                buf_handler.jump_forward()
                view.zoom_on_text(buf_handler.get_current_text())
            case "catch child down":
                buf_handler.catch_child = "down"
                view.msg("catching child down")
            case "catch child right":
                buf_handler.catch_child = "right"
                view.msg("catching child right")
