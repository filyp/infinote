import tkinter as tk

import pydantic
import pynvim

from global_objects import nvim, root


class Node(pydantic.BaseModel):
    class Config:
        # to allow tk and nvim types
        arbitrary_types_allowed = True

    text_widget: tk.Text
    buffer: pynvim.api.Buffer

    def __init__(self, x, y, create_new_buffer=True):
        text = tk.Text(
            root,
            bg="black",
            fg="white",
            width=30,
            height=1,
            # no border
            bd=0,
            highlightthickness=0,
            # wrap="word",
            insertbackground="white",  # insert cursor color
            font=("Monospace", 12),
        )
        text.place(x=x, y=y)
        text.tag_configure("highlight", background="gray")
        text.tag_configure("ncursor", background="brown")
        text.tag_configure("mark", background="orange")
        text.configure(insertofftime=0)

        # create a new nvim buffer
        if create_new_buffer:
            nvim.command("new")
        buffer = nvim.current.buffer

        # bind mouse events

        super().__init__(text_widget=text, buffer=buffer)

    def update(self, nvim):
        text = self.text_widget

        # set new text
        lines = self.buffer[:]
        for i, line in enumerate(lines):
            if line == "":
                # add space so that cursor can be displayed there
                lines[i] = " "
        new_text = "\n".join(lines)
        text.delete("1.0", "end")
        text.insert("1.0", new_text)

        # draw marks
        buf_num = self.buffer.number
        marks = nvim.api.buf_get_extmarks(
            buf_num, -1, (0, 0), (-1, -1), {"details": True}
        )
        # print(buf_num, marks)
        for _, y, x, details in marks:
            y += 1  # transform to 1-based ordering
            virt_text = details["virt_text"]
            assert len(virt_text) == 1
            char, type_ = virt_text[0]
            if type_ == "Cursor":
                continue
            # TODO later relax this
            assert type_ == "LeapLabelPrimary", marks

            # put that char into text
            text.delete(f"{y}.{x}")
            text.insert(f"{y}.{x}", char)
            text.tag_add("mark", f"{y}.{x}", f"{y}.{x + 1}")

        # the rest if done only if this node's buffer is the current buffer
        if nvim.current.buffer != self.buffer:
            return

        mode = nvim.api.get_mode()["mode"]

        # set cursor
        curs_y, curs_x = nvim.current.window.cursor
        if mode == "n":
            text.configure(insertunfocussed="none")
            text.tag_add("ncursor", f"{curs_y}.{curs_x}", f"{curs_y}.{curs_x + 1}")
        elif mode == "i":
            text.configure(insertunfocussed="solid")
            text.mark_set("insert", f"{curs_y}.{curs_x}")

        # set selection
        if mode == "v" or mode == "V" or mode == "\x16":
            s = nvim.eval('getpos("v")')[1:3]
            e = nvim.eval('getpos(".")')[1:3]
            # if end before start, swap
            if s[0] > e[0] or (s[0] == e[0] and s[1] > e[1]):
                s, e = e, s
        if mode == "v":
            text.tag_add("highlight", f"{s[0]}.{s[1]-1}", f"{e[0]}.{e[1]}")
        elif mode == "V":
            # extend selection to full line
            s[1] = 1
            e[1] = len(self.buffer[e[0] - 1])
            text.tag_add("highlight", f"{s[0]}.{s[1]-1}", f"{e[0]}.{e[1]}")
        elif mode == "\x16":
            # visual block selection
            x_start = min(s[1], e[1]) - 1
            x_end = max(s[1], e[1])
            y_start = min(s[0], e[0])
            y_end = max(s[0], e[0])
            for y in range(y_start, y_end + 1):
                text.tag_add("highlight", f"{y}.{x_start}", f"{y}.{x_end}")

        # set height
        num_lines = text.index("end-1c").split(".")[0]
        text.configure(height=int(num_lines))
