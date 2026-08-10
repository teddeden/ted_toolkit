'''toolkit_gui.widgets.icons - small generated icons (no external image
assets needed).'''

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

_CACHE = {}


def make_status_dot_icon(color, size=10):
    '''Return a cached QIcon: a filled circle of `color` on a transparent
    background - used as the busy/idle indicator on a session tab.'''
    key = (color, size)
    if key in _CACHE:
        return _CACHE[key]
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    icon = QIcon(pixmap)
    _CACHE[key] = icon
    return icon
