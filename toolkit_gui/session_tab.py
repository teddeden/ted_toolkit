'''toolkit_gui.session_tab - one GUI tab: terminal + variables + preview panes.'''

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from toolkit_gui.panels.preview_panel import PreviewPanel
from toolkit_gui.panels.variables_panel import VariablesPanel
from toolkit_gui.terminal.terminal_widget import TerminalWidget


class SessionTabWidget(QWidget):
    '''Three-pane layout for one toolkit session: (1) the interactive
    terminal (main pane), (2) a live list of the session's working
    variables letting the user select at most one, (3) a bounded data
    preview of the selected variable.'''

    def __init__(self, session, bridge_client, parent=None):
        super().__init__(parent)
        self.session = session
        self.bridge_client = bridge_client
        self.manually_renamed = False

        self.terminal = TerminalWidget(session, parent=self)
        self.variables_panel = VariablesPanel(bridge_client, parent=self)
        self.preview_panel = PreviewPanel(bridge_client, parent=self)
        self.variables_panel.variable_selected.connect(self.preview_panel.show_variable)
        self.variables_panel.selection_cleared.connect(self.preview_panel.clear)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self.terminal)
        splitter.addWidget(self.variables_panel)
        splitter.addWidget(self.preview_panel)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def refresh_panels(self):
        self.variables_panel.refresh()
        self.preview_panel.refresh()

    def stop(self):
        self.terminal.stop()
        self.bridge_client.close()
        self.session.terminate(force=True)
