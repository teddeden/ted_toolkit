'''toolkit_gui.terminal.pty_io_thread - background QThread that pumps a
PtySession's raw output into a Qt signal, so the (blocking) pty read() call
never runs on the UI thread. All pyte.Stream feeding and widget repainting
happens on the main thread, in response to output_ready.
'''

from PySide6.QtCore import QThread, Signal


class PtyIoThread(QThread):
    output_ready = Signal(bytes)
    session_ended = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        while not self._stop_requested:
            try:
                chunk = self._session.read(65536, timeout=0.2)
            except EOFError:
                break
            if chunk:
                self.output_ready.emit(chunk)
        self.session_ended.emit()
