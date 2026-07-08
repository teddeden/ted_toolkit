'''toolkit_gui.main_window - the QMainWindow shell: tabbed sessions with
close ("x") buttons and right-click rename. Menu/toolbar actions land in
Phase 6; the CPU status bar and per-tab busy indicator in Phase 5.
'''

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QLabel, QMainWindow, QMenu, QTabWidget

from toolkit_gui.session_manager import SessionManager
from toolkit_gui.widgets.icons import make_status_dot_icon

_IDLE_DOT_COLOR = '#888888'
_BUSY_DOT_COLOR = '#e05a3c'


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ted's Toolkit")
        self.setMinimumWidth(1024)
        self.resize(1400, 900)

        self.session_manager = SessionManager(self)
        self.session_manager.title_changed.connect(self._on_title_changed)
        self.session_manager.cpu_total_changed.connect(self._on_cpu_total_changed)
        self.session_manager.tab_busy_changed.connect(self._on_tab_busy_changed)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._on_tab_context_menu)
        self.setCentralWidget(self.tabs)

        self._idle_icon = make_status_dot_icon(_IDLE_DOT_COLOR)
        self._busy_icon = make_status_dot_icon(_BUSY_DOT_COLOR)
        self._cpu_label = QLabel('CPU (sessions): 0.0%', self)
        self.statusBar().addPermanentWidget(self._cpu_label)

        self.new_tab()

    def new_tab(self, extra_args=None):
        '''Spawn a new session tab. extra_args (e.g. a script path) is
        forwarded to the spawned process's command line - used by the
        "Run Script in New Tab" menu action (Phase 6).'''
        tab = self.session_manager.spawn_tab(extra_args=extra_args, parent=self.tabs)
        index = self.tabs.addTab(tab, 'New Session')
        self.tabs.setTabIcon(index, self._idle_icon)
        self.tabs.setCurrentIndex(index)
        return tab

    def current_tab(self):
        return self.tabs.currentWidget()

    def _on_tab_close_requested(self, index):
        tab = self.tabs.widget(index)
        self.session_manager.close_tab(tab)
        self.tabs.removeTab(index)
        tab.deleteLater()

    def _on_tab_context_menu(self, pos):
        index = self.tabs.tabBar().tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        rename_action = menu.addAction('Rename Tab...')
        chosen = menu.exec(self.tabs.tabBar().mapToGlobal(pos))
        if chosen == rename_action:
            self._rename_tab(index)

    def _rename_tab(self, index):
        current = self.tabs.tabText(index)
        new_name, ok = QInputDialog.getText(self, 'Rename Tab', 'Tab name:', text=current)
        if ok and new_name.strip():
            self.tabs.setTabText(index, new_name.strip())
            self.tabs.widget(index).manually_renamed = True

    def _on_title_changed(self, tab, title):
        '''Auto-sync a tab's label from set_window_title() via the bridge's
        GetConsoleTitleW polling - suppressed once the user has manually
        renamed that tab (manual override wins for the tab's lifetime).'''
        if tab.manually_renamed:
            return
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.setTabText(index, title)

    def _on_cpu_total_changed(self, total_percent):
        '''Sum of every open tab's own process CPU% (not the GUI's own
        process, not system-wide) - matches this feature's explicit
        requirement.'''
        self._cpu_label.setText(f'CPU (sessions): {total_percent:.1f}%')

    def _on_tab_busy_changed(self, tab, is_busy):
        '''Lets a background tab visibly show whether a long-running command
        is still executing, without switching to it - derived from the same
        per-tab CPU sample driving the status bar sum.'''
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.setTabIcon(index, self._busy_icon if is_busy else self._idle_icon)

    def closeEvent(self, event):
        for index in range(self.tabs.count()):
            self.session_manager.close_tab(self.tabs.widget(index))
        super().closeEvent(event)
