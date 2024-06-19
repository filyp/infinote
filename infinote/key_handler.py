from PySide6.QtCore import Qt, QTimer

from infinote.config import Config


_cmd_normalizer = {"<S-:>": ":", ":": ":", "/": "/", "<S-?>": "?", "?": "?", "<S-/>": "?"}


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

def _handle_non_vim_visual_mode(nvim, text):
    match text:
        case "<BS>": # delete text
            nvim.input("c")
        case "<Esc>":  # leave visual mode
            nvim.input("<Esc>")  # NOSONAR
        case _:  # replace text 
            nvim.input("c" + text)


class KeyHandler:
    def __init__(self, nvim, view):
        self.nvim = nvim
        self.view = view

        self.command = ""
        self.external_command_mode = False

    def _absorb_key_into_command_line(self, text, raw_text):
        match text:
            case "<Esc>":
                if self.external_command_mode:
                    self.nvim.input("<Esc>")
                    self.external_command_mode = False
                self.command = ""
            case "<CR>":
                # execute the command
                self.nvim.input(f"{self.command}<CR>")
                self.external_command_mode = False
                self.command = ""
            case "<BS>":
                self.command = self.command[:-1]
            case _:
                if raw_text:
                    self.command += raw_text

    def handle_key_event(self, event):
        text = parse_key_event_into_text(event)
        if text is None:
            return

        mode = self.nvim.api.get_mode()["mode"]
        if text in Config.keys:
            # custom command pressed
            self.handle_custom_command(text, mode)
            return

        if not Config.vim_mode: 
            if mode == "i" and text == "<Esc>":
                # don't allow leaving insert mode
                return
            if mode == "v" or mode == "V":
                _handle_non_vim_visual_mode(self.nvim, text)
                return

        if mode not in ["n", "c"]:
            # send that key
            self.nvim.input(text)
            return

        # if we're here, we're in normal or command mode
        # monitor command and search input
        if self.command or self.external_command_mode:
            # eat the keypress into self.command
            self._absorb_key_into_command_line(text, event.text())
            return
        assert self.command == ""
        if text in _cmd_normalizer:
            self.command = _cmd_normalizer[text]
            return
        
        # send that key
        self.nvim.input(text)

    def get_command_line(self):
        if self.external_command_mode:
            return "..." + self.command
        else:
            return self.command
    
    def _continuous_command(self, function):
        view = self.view
        if view.timer is None:
            view.timer = QTimer()
            view.timer.timeout.connect(function)
            view.timer.start(1000 / Config.FPS)

    def handle_custom_command(self, key_combo, mode):
        if key_combo not in Config.keys:
            return
        command = Config.keys[key_combo]

        buf_handler = self.view.buf_handler
        view = self.view

        match command:
            case "hop":
                if mode == "i":
                    self.nvim.input("<Esc>")
                cmd = "lua require('leap').leap { target_windows = vim.api.nvim_list_wins() }"
                self.nvim.input(f":{cmd}<CR>")
            case "bookmark jump":
                if mode == "i":
                    self.nvim.input("<Esc>")
                cmd = '<Home>"fyt|f|<Right>"lyiw:buffer<Space><C-r>f<Enter>:<C-r>l<Enter>'
                self.nvim.input(cmd)
                view.zoom_on_text(buf_handler.get_current_text())
            case "center on current text":
                current_text = buf_handler.get_current_text()
                view.global_scale = view.get_scale_centered_on_text(current_text)
            case "maximize on current text":
                current_text = buf_handler.get_current_text()
                view.global_scale = view.get_scale_maximized_on_text(current_text)
            case "create child right":
                buf_handler.create_child()
            case "move down":
                view.jump_to_neighbor("down")
            case "move up":
                view.jump_to_neighbor("up")
            case "move left":
                view.jump_to_neighbor("left")
            case "move right":
                view.jump_to_neighbor("right")
            case "zoom up":
                self._continuous_command(lambda: view.zoom(-1))
            case "zoom down":
                self._continuous_command(lambda: view.zoom(1))
            case "grow box":
                self._continuous_command(lambda: view.resize(1))
            case "shrink box":
                self._continuous_command(lambda: view.resize(-1))
            case "jump back":
                buf_handler.jump_back()
                view.zoom_on_text(buf_handler.get_current_text())
            case "jump forward":
                buf_handler.jump_forward()
                view.zoom_on_text(buf_handler.get_current_text())
            case "delete text":
                buf_handler.delete_buf(self.nvim.current.buffer)
            # case "toggle editor":
            #     if view.show_editor:
            #         view.show_editor = False
            #         view.editor_box.hide()
            #     else:
            #         view.show_editor = True
            #         view.editor_box.show()
