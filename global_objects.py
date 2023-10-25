import pynvim
import sys
from PySide6.QtWidgets import (
    QApplication,
)

nvim = pynvim.attach("child", argv=["/usr/bin/env", "nvim", "--embed", "--headless"])

