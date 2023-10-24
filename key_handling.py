SPECIAL_KEYS = {
    'Escape': 'Esc',
    'Return': 'CR',
    'BackSpace': 'BS',
    'Prior': 'PageUp',
    'Next': 'PageDown',
    'Delete': 'Del',
}

# TODO ? replace termcodes?
# what are they? do they help?

    # if event.keysym == 'Escape':
    #     root.destroy()
    #     return


def key_translate(event):
    if event.keycode == 248:  # this is spammed over
        return
    if 0xffe1 <= event.keysym_num <= 0xffee:
        # this is a modifier key, ignore. Source:
        # https://www.tcl.tk/man/tcl8.4/TkCmd/keysyms.htm
        return
    # Translate to Nvim representation of keys
    send = []
    if event.state & 0x1:
        send.append('S')
    if event.state & 0x4:
        send.append('C')
    if event.state & (0x8 | 0x80):
        send.append('A')
    special = len(send) > 0
    key = event.char
    if len(key) != 1 or ord(key[0]) < 0x20:
        special = True
        key = event.keysym
    send.append(SPECIAL_KEYS.get(key, key))
    send = '-'.join(send)
    if special:
        send = '<' + send + '>'
    # nvim.session.threadsafe_call(lambda: nvim.input(send))
    return send
