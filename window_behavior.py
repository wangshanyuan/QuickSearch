# window_behavior.py
from PyQt5.QtCore import Qt

class FramelessWindowMixin:
    MARGIN = 10 

    def _init_window_behavior(self):
        self._dragging = False
        self._resizing = False
        self._resize_dir = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            w, h = self.width(), self.height()
            l, r, t, b = pos.x()<self.MARGIN, pos.x()>w-self.MARGIN, pos.y()<self.MARGIN, pos.y()>h-self.MARGIN
            if l or r or t or b:
                self._resizing = True
                self._resize_dir = (l, r, t, b)
            else:
                self._dragging = True
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self._resizing:
            l, r, t, b = self._resize_dir
            geo = self.geometry()
            gp = event.globalPos()
            if l: geo.setLeft(gp.x())
            if r: geo.setRight(gp.x())
            if t: geo.setTop(gp.y())
            if b: geo.setBottom(gp.y())
            if geo.width() >= self.minimumWidth() and geo.height() >= self.minimumHeight():
                self.setGeometry(geo)
        elif self._dragging:
            self.move(event.globalPos() - self._drag_pos)
        else:
            w, h = self.width(), self.height()
            l, r, t, b = pos.x()<self.MARGIN, pos.x()>w-self.MARGIN, pos.y()<self.MARGIN, pos.y()>h-self.MARGIN
            if (l and t) or (r and b): self.setCursor(Qt.SizeFDiagCursor)
            elif (r and t) or (l and b): self.setCursor(Qt.SizeBDiagCursor)
            elif l or r: self.setCursor(Qt.SizeHorCursor)
            elif t or b: self.setCursor(Qt.SizeVerCursor)
            else: self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self._dragging = self._resizing = False
        self.setCursor(Qt.ArrowCursor)