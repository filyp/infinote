import pynvim
import sys
from PySide6.QtWidgets import (
    QApplication,
)

nvim = pynvim.attach("child", argv=["/usr/bin/env", "nvim", "--embed", "--headless"])


class Config:
    autoshrink = True
    # FPS = 60
    text_width = 300
    initial_position = (500, 40)
