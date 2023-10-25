from global_objects import nvim
from time import sleep, time
from PySide6.QtWidgets import (
    QMainWindow,
    QApplication,
    QGraphicsView,
    QGraphicsScene,
    QTextBrowser,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QTextBrowser, QTextEdit
from PySide6.QtGui import QTextCursor, QTextCharFormat


class NonSelectableTextBrowser(QTextBrowser):
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

        self.text_browser = NonSelectableTextBrowser()
        # self.text_browser = QTextEdit()
        self.text_browser.setFont(QFont("monospace", 12))
        self.text_browser.setFixedWidth(300)
        self.text_browser.setFixedHeight(100)
        # make bg black
        # create a pale grey border
        self.text_browser.setStyleSheet(
            # background-color: black; color: white;
            """
            border: 1px solid grey;
            """
        )
        self.setWidget(self.text_browser)
        
        # make it editable


        # self.setFlag(QGraphicsProxyWidget.ItemIsMovable, True)
        # self.textBrowser.setFlag(QTextBrowser.ItemIsMovable, True)
        # self.setFlag(QGraphicsProxyWidget.ItemIsSelectable, True)
        # self.setFlag(QGraphicsProxyWidget.ItemSendsGeometryChanges, True)

    def update_text(self):
        # set new text
        lines = self.buffer[:]
        for i, line in enumerate(lines):
            if line == "":
                # add space so that cursor can be displayed there
                lines[i] = " "
        new_text = "\n".join(lines)
        self.text_browser.setText(new_text)

        # draw marks

        # the rest if done only if this node's buffer is the current buffer
        if nvim.current.buffer != self.buffer:
            return

        mode = nvim.api.get_mode()["mode"]
        doc = self.text_browser.document()

        # set cursor
        curs_y, curs_x = nvim.current.window.cursor
        curs_y -= 1
        # get the one number char position
        pos = doc.findBlockByLineNumber(curs_y).position() + curs_x
        if mode == "n":
            pass
            # cursor = QTextCursor(doc)
            # # cursor.setPosition(pos, QTextCursor.MoveAnchor)
            # # cursor.setPosition(pos + 1, QTextCursor.KeepAnchor)
            # cursor.setPosition(pos)
            # focus widget to display cursor

            # self.text_browser.setFocus()
            # # self.text_browser.setDocument(doc)
            # self.text_browser.repaint()

            # self.text_browser.setTextCursor(cursor)

            # fmt = QTextCharFormat()
            # fmt.setBackground(Qt.magenta)
            # cursor.setCharFormat(fmt)
            # this highlights all the text
            # instead of just the one char
            # cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)

    def wheelEvent(self, event):
        pos = self.boundingRect().center()
        # pos = event.pos()   # this is unstable

        self.setTransformOriginPoint(pos)
        scale = self.scale() * 1.0005 ** event.delta()
        self.setScale(scale)

    # def mouseMoveEvent(self, event):
    #     # drag around
    #     movevent = event.screenPos() - event.lastScreenPos()
    #     self.moveBy(movevent.x(), movevent.y())
