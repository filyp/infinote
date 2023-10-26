from time import sleep, time

import pynvim
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsItem,
    QMainWindow,
    QTextBrowser,
)

from global_objects import nvim, FPS
from text_object import DraggableText

# TODO
# saving
# only update when nvim notifies of a change
#
# low:
# polish chars seem to break stuff, because they throuw position out of range,
#     they are probably more chars than one
# custom wrappint, extending height
# native node dragging would maybe be more efficient (there are cases with big text where it lags)



class GraphicView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(Qt.black))
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)
        self.setScene(QGraphicsScene())
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.global_scale = 1.0

    def mousePressEvent(self, event):
        item = self.scene().itemAt(event.screenPos(), self.transform())
        if not isinstance(item, DraggableText):
            self.create_text(event.screenPos())
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        self.scene().setSceneRect(0, 0, event.size().width(), event.size().height())
        super().resizeEvent(event)

    def create_text(self, pos):
        num_of_texts = len(self.scene().items())
        if num_of_texts == len(nvim.buffers):
            # create new buffer
            nvim.command("new")
        text = DraggableText(nvim.current.buffer, 1)
        text.setPos(pos)
        self.scene().addItem(text)

    def keyPressEvent(self, event):
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
        # if mods & Qt.MetaModifier:
        #     text = "M-" + text
        # if mods & Qt.KeypadModifier:
        #     text = "W-" + text

        if mods or (key in special_keys):
            text = "<" + text + ">"

        nvim.input(text)
        # super().keyPressEvent(event)

    def wheelEvent(self, event):
        zoom_factor = 1.0005 ** event.angleDelta().y()

        item = self.scene().itemAt(event.position(), self.transform())
        if isinstance(item, DraggableText):
            # zoom it
            item.zoom(zoom_factor, self.global_scale)
        else:
            # zoom the whole view
            self.global_scale *= zoom_factor
            # self.scale(zoom_factor, zoom_factor)
            self.update_texts()

    def update_texts(self):
        # unfocus the text boxes - better would be to always have focus here
        self.dummy.setFocus()

        if nvim.api.get_mode()["blocking"]:
            return

        for item in self.scene().items():
            if isinstance(item, DraggableText):
                item.update_text()
                item.reposition(self.global_scale)
        

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.view = GraphicView()
        self.setCentralWidget(self.view)
        # self.showMaximized()
        # not maximized, but 1000x1000
        self.resize(500, 500)
        self.show()

        
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)

    w = MainWindow()

    # make the cursor non-blinking
    app.setCursorFlashTime(0) 

    # create a dummy object that can grab focus, so that the text box can be unfocused
    dummy = QGraphicsRectItem()
    dummy.setFlag(QGraphicsItem.ItemIsFocusable)
    w.view.scene().addItem(dummy)
    w.view.dummy = dummy

    # create one text
    w.view.create_text(w.view.mapToScene(100, 100))
    
    timer = QTimer()
    timer.timeout.connect(w.view.update_texts)
    timer.start(1000 / FPS)

    sys.exit(app.exec())
