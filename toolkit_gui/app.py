'''toolkit_gui.app - entry point for the desktop GUI shell.

Phase 3 milestone: a single hardcoded tab hosting one real interactive
toolkit session, proving the terminal widget behaves like a real console
(typing, arrow-key history recall, output rendering) before multi-tab
management, panels, and menus are layered on top in later phases.
'''

import os
import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from toolkit_gui.backend.env_resolve import build_spawn_argv, find_free_port
from toolkit_gui.backend.pty_backend import get_pty_backend
from toolkit_gui.terminal.terminal_widget import TerminalWidget


def spawn_session_widget(parent=None):
    '''Spawn one new toolkit session process and return a TerminalWidget
    connected to it. Does not yet wire up a BridgeClient (that lands in
    Phase 4 alongside the Variables/Preview panels).'''
    port = find_free_port()
    env = dict(os.environ)
    env['TEDTOOLKIT_GUI_BRIDGE_PORT'] = str(port)
    backend = get_pty_backend()
    session = backend.spawn(build_spawn_argv(), env=env, cols=120, rows=40)
    widget = TerminalWidget(session, parent=parent)
    widget.bridge_port = port
    return widget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ted's Toolkit")
        self.setMinimumWidth(1024)
        self.resize(1280, 800)
        self._terminal = spawn_session_widget(parent=self)
        self.setCentralWidget(self._terminal)

    def closeEvent(self, event):
        self._terminal.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
