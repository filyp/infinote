from time import sleep, time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
    QTextBrowser,
    QTextEdit,
)

from global_objects import nvim


class NonSelectableTextEdit(QTextEdit):
    def mousePressEvent(self, event):
        # Skip the mouse press event to prevent it from being handled by QTextBrowser
        event.ignore()

    def mouseMoveEvent(self, event):
        # Skip the mouse move event to prevent it from being handled by QTextBrowser
        event.ignore()

    def mouseReleaseEvent(self, event):
        # Skip the mouse release event to prevent it from being handled by QTextBrowser
        event.ignore()


class DraggableText(QGraphicsProxyWidget):
    def __init__(self, buffer_handle):
        super().__init__()

        self.buffer = buffer_handle

        self.text_box = NonSelectableTextEdit()
        self.text_box.setFont(QFont("monospace", 12))
        self.text_box.setFixedWidth(300)
        self.text_box.setFixedHeight(100)
        # make bg black, create a pale grey border
        self.text_box.setStyleSheet(
            """
            background-color: black; color: white;
            border: 1px solid grey;
            """
        )

        self.setWidget(self.text_box)

    def update_text(self):
        # set new text
        lines = self.buffer[:]
        for i, line in enumerate(lines):
            if line == "":
                # add space so that cursor can be displayed there
                lines[i] = " "
        new_text = "\n".join(lines)
        self.text_box.setText(new_text)

        # draw marks

        # the rest if done only if this node's buffer is the current buffer
        if nvim.current.buffer != self.buffer:
            return

        mode = nvim.api.get_mode()["mode"]
        doc = self.text_box.document()

        # set cursor
        curs_y, curs_x = nvim.current.window.cursor
        curs_y -= 1
        # get the one number char position
        pos = doc.findBlockByLineNumber(curs_y).position() + curs_x
        # get focus so that cursor is displayed
        cursor = self.text_box.textCursor()

        if mode == "n":
            cursor.setPosition(pos, QTextCursor.MoveAnchor)
            cursor.setPosition(pos + 1, QTextCursor.KeepAnchor)

        elif mode == "i":
            self.text_box.setFocus()
            cursor.setPosition(pos)
        self.text_box.setTextCursor(cursor)

    def wheelEvent(self, event):
        pos = self.boundingRect().center()
        # pos = event.pos()   # this is unstable

        self.setTransformOriginPoint(pos)
        scale = self.scale() * 1.0005 ** event.delta()
        self.setScale(scale)

    def mouseMoveEvent(self, event):
        # drag around
        movevent = event.screenPos() - event.lastScreenPos()
        self.moveBy(movevent.x(), movevent.y())
