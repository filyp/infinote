from PySide6.QtCore import Qt


def translate_key_event_to_vim(event):
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
