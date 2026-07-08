'''toolkit_gui.main_window - the QMainWindow shell: menu bar, toolbar,
tabbed sessions with close ("x") buttons and right-click rename, and a
status bar showing the sessions' combined CPU usage.
'''

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QInputDialog, QLabel, QMainWindow, QMenu, QStyle,
                                QTabWidget)

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

        self._build_actions()
        self._build_menu()
        self._build_toolbar()

        self.new_tab()

    def _build_actions(self):
        style = self.style()
        self.action_new_tab = QAction(
            style.standardIcon(QStyle.SP_FileDialogNewFolder), 'New &Tab', self)
        self.action_new_tab.setShortcut(QKeySequence('Ctrl+T'))
        self.action_new_tab.triggered.connect(lambda: self.new_tab())

        self.action_run_script_current = QAction(
            style.standardIcon(QStyle.SP_MediaPlay), 'Run Script in &Current Tab...', self)
        self.action_run_script_current.triggered.connect(self._run_script_in_current_tab)

        self.action_run_script_new = QAction(
            style.standardIcon(QStyle.SP_DialogOpenButton), 'Run Script in &New Tab...', self)
        self.action_run_script_new.triggered.connect(self._run_script_in_new_tab)

        self.action_save_history = QAction(
            style.standardIcon(QStyle.SP_DialogSaveButton), 'Save &History', self)
        self.action_save_history.triggered.connect(self._save_history_current_tab)

        self.action_save_chat = QAction(
            style.standardIcon(QStyle.SP_DriveFDIcon), 'Save All &Chat Content...', self)
        self.action_save_chat.triggered.connect(self._save_chat_current_tab)

        self.action_exit = QAction('E&xit', self)
        self.action_exit.triggered.connect(self.close)

    def _build_menu(self):
        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(self.action_new_tab)
        file_menu.addSeparator()
        file_menu.addAction(self.action_run_script_current)
        file_menu.addAction(self.action_run_script_new)
        file_menu.addSeparator()
        file_menu.addAction(self.action_save_history)
        file_menu.addAction(self.action_save_chat)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

    def _build_toolbar(self):
        toolbar = self.addToolBar('Main')
        toolbar.setMovable(False)
        toolbar.addAction(self.action_new_tab)
        toolbar.addAction(self.action_run_script_current)
        toolbar.addAction(self.action_run_script_new)
        toolbar.addAction(self.action_save_history)
        toolbar.addAction(self.action_save_chat)

    def _run_script_in_current_tab(self):
        '''Injects the equivalent of typing _run_script([path], view_comments=True)
        into the active tab - matches ted_toolkit.py's own ARGS-based
        script-replay invocation exactly.'''
        tab = self.current_tab()
        if tab is None:
            return
        path, _filter = QFileDialog.getOpenFileName(
            self, 'Run Script in Current Tab', '', 'Python files (*.py);;All Files (*)')
        if not path:
            return
        command = f'_run_script([{path!r}], view_comments=True)\r\n'
        tab.session.write(command.encode('utf-8'))

    def _run_script_in_new_tab(self):
        '''Spawns a brand-new tab with the script path as its CLI arg -
        identical to running start_ted_toolkit.bat <script.py> today.'''
        path, _filter = QFileDialog.getOpenFileName(
            self, 'Run Script in New Tab', '', 'Python files (*.py);;All Files (*)')
        if not path:
            return
        self.new_tab(extra_args=[path])

    def _save_history_current_tab(self):
        '''Equivalent to the user typing save_history() in the active tab -
        reuses the existing tkinter Save-As + Notepad flow verbatim.'''
        tab = self.current_tab()
        if tab is None:
            return
        tab.session.write(b'save_history()\r\n')

    def _save_chat_current_tab(self):
        '''Purely GUI-side: dumps the active tab's full terminal scrollback
        (not just what's currently visible) to a plain text file.'''
        tab = self.current_tab()
        if tab is None:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, 'Save All Chat Content', '', 'Text files (*.txt);;All Files (*)')
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as fil:
            fil.write(tab.terminal.screen_text_for_save())

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
