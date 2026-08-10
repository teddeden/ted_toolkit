'''toolkit_gui.terminal.terminal_widget - pyte-backed VT100/xterm terminal
emulator widget. Renders the real byte stream coming from a ConPTY-hosted
session and forwards keystrokes as raw xterm-style escape sequences, so
arrow-key history recall (pyreadline3, inside the child) works purely
because the child process sees the same bytes it would from a real console -
no readline/history logic is reimplemented here.
'''

import pyte
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from toolkit_gui import config
from toolkit_gui.terminal.pty_io_thread import PtyIoThread

# xterm-style key -> escape sequence mapping for keys pyreadline3's history
# recall and line editing depend on. Printable characters go through
# QKeyEvent.text() directly, not through this table.
_KEY_SEQUENCES = {
    Qt.Key_Up: b'\x1b[A',
    Qt.Key_Down: b'\x1b[B',
    Qt.Key_Right: b'\x1b[C',
    Qt.Key_Left: b'\x1b[D',
    Qt.Key_Home: b'\x1b[H',
    Qt.Key_End: b'\x1b[F',
    Qt.Key_Delete: b'\x1b[3~',
    Qt.Key_Backspace: b'\x7f',
    Qt.Key_Tab: b'\t',
    Qt.Key_Return: b'\r',
    Qt.Key_Enter: b'\r',
    Qt.Key_Escape: b'\x1b',
}


def _row_to_text(row):
    '''pyte scrollback rows are StaticDefaultDict[col_index -> Char]; flatten
    to plain text in column order.'''
    return ''.join(char.data for _, char in sorted(row.items()))


class TerminalWidget(QWidget):
    '''One tab's terminal pane. Owns the PtySession's I/O thread and the
    pyte HistoryScreen/Stream that turns its raw byte stream into a
    renderable character grid.'''

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        # Must exactly match the cols/rows the session's pty was actually
        # spawned with (config.TERMINAL_COLS/TERMINAL_ROWS, applied in
        # session_manager.spawn_tab()) and must never be resized afterward -
        # see config.py's TERMINAL_COLS docstring for why.
        self._screen = pyte.HistoryScreen(config.TERMINAL_COLS, config.TERMINAL_ROWS,
                                           history=config.TERMINAL_SCROLLBACK_LINES)
        self._stream = pyte.Stream(self._screen)

        self._font = QFont('Consolas', 10)
        self._font.setStyleHint(QFont.Monospace)
        metrics = QFontMetrics(self._font)
        self._char_width = max(1, metrics.horizontalAdvance('M'))
        self._char_height = max(1, metrics.height())

        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

        self._input_blocked = False
        self._repaint_pending = False
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(33)  # ~30fps coalesced repaint
        self._repaint_timer.timeout.connect(self._flush_repaint)
        self._repaint_timer.start()

        self._io_thread = PtyIoThread(session, self)
        self._io_thread.output_ready.connect(self._on_output)
        self._io_thread.start()

    def title(self):
        '''pyte's own OSC-title-sequence tracking. NOT the mechanism used
        for the tab label (see gui_bridge._get_console_title(), which polls
        GetConsoleTitleW from inside the child instead - more robust, since
        ConPTY has no outer window of its own to read a title from). Exposed
        here only as a debugging aid.'''
        return self._screen.title

    def screen_text_for_save(self):
        '''Flatten the full scrollback (history + visible viewport) to plain
        text for the "Save All Chat Content" menu action and for reseeding a
        restored session's transcript (see feed_text()). Uses \\r\\n line
        endings deliberately: (1) classic Notepad (opened via save_history()'s
        own flow) needs CRLF to render line breaks at all, and (2) this same
        text gets re-fed through pyte's VT parser on restore, where a bare
        \\n (line feed) only moves the cursor down a row without resetting
        its column - producing a staircase/corrupted redraw - while \\r\\n
        (carriage return + line feed) reproduces normal terminal newline
        behavior correctly.'''
        lines = [_row_to_text(row) for row in self._screen.history.top]
        lines.extend(self._screen.display)
        lines.extend(_row_to_text(row) for row in self._screen.history.bottom)
        return '\r\n'.join(line.rstrip() for line in lines)

    def display_text(self):
        '''Current visible-viewport text (not full scrollback) - used to
        detect known startup markers, e.g. during Restore Session's
        handshake (see toolkit_gui.session_persistence).'''
        return '\n'.join(self._screen.display)

    def feed_text(self, text):
        '''Feed text directly into the display buffer without going through
        the pty - used to reseed a restored session's transcript before any
        live pty output arrives (see Phase 7's restore flow). Expects \\r\\n
        line endings (see screen_text_for_save()).'''
        self._stream.feed(text)
        self.update()

    def _on_output(self, chunk):
        self._stream.feed(chunk.decode('utf-8', errors='surrogateescape'))
        self._repaint_pending = True

    def _flush_repaint(self):
        if self._repaint_pending:
            self._repaint_pending = False
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self._font)
        painter.fillRect(self.rect(), QColor(12, 12, 12))
        painter.setPen(QColor(220, 220, 220))
        for row_index, line in enumerate(self._screen.display):
            baseline_y = row_index * self._char_height + self._char_height
            painter.drawText(0, baseline_y, line)
        cursor = self._screen.cursor
        if not cursor.hidden:
            cursor_x = cursor.x * self._char_width
            cursor_y = cursor.y * self._char_height
            painter.fillRect(cursor_x, cursor_y, self._char_width, self._char_height,
                              QColor(220, 220, 220, 100))

    def set_input_blocked(self, blocked):
        '''Suppress keyboard forwarding while a Restore Session is pending -
        closes the narrow race where a very fast typist could type into a
        freshly spawned tab before its history/variables have been injected.'''
        self._input_blocked = blocked

    def keyPressEvent(self, event):
        if self._input_blocked:
            event.accept()
            return
        key = event.key()
        if key in _KEY_SEQUENCES:
            self._session.write(_KEY_SEQUENCES[key])
            event.accept()
            return
        text = event.text()
        if text:
            self._session.write(text.encode('utf-8', errors='surrogateescape'))
            event.accept()
            return
        super().keyPressEvent(event)

    def stop(self):
        self._io_thread.stop()
        self._io_thread.wait(2000)

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)
