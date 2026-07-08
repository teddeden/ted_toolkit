'''toolkit_gui.session_manager - spawns/tracks GUI tabs and owns the shared
poll timer that drives variable/preview refresh and title-bar sync (CPU
sampling/busy-indicator join the same timer in Phase 5).
'''

import os

from PySide6.QtCore import QObject, QTimer, Signal

from toolkit_gui import config
from toolkit_gui.backend.bridge_client import BridgeClient
from toolkit_gui.backend.env_resolve import build_spawn_argv, find_free_port
from toolkit_gui.backend.pty_backend import get_pty_backend
from toolkit_gui.session_tab import SessionTabWidget

# A fresh child's bridge thread needs a moment to start listening - retried
# on this cadence via QTimer (non-blocking), NOT via BridgeClient.connect()'s
# own blocking retry loop, which would freeze the whole GUI on every new tab.
_BRIDGE_CONNECT_ASYNC_ATTEMPTS = 30
_BRIDGE_CONNECT_ASYNC_INTERVAL_MS = 500


class SessionManager(QObject):
    title_changed = Signal(object, str)  # (SessionTabWidget, new title)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend = get_pty_backend()
        self._tabs = []
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(int(config.POLL_INTERVAL_SECONDS * 1000))
        self._poll_timer.timeout.connect(self._poll_all)
        self._poll_timer.start()

    def spawn_tab(self, extra_args=None, parent=None):
        '''Spawn a new session process and return its SessionTabWidget
        immediately - the bridge connection happens asynchronously in the
        background, so this never blocks the UI thread waiting for the
        child to finish conda activation/startup.'''
        port = find_free_port()
        env = dict(os.environ)
        env['TEDTOOLKIT_GUI_BRIDGE_PORT'] = str(port)
        session = self._backend.spawn(build_spawn_argv(extra_args), env=env, cols=120, rows=40)
        bridge_client = BridgeClient(port)
        tab = SessionTabWidget(session, bridge_client, parent=parent)
        self._tabs.append(tab)
        self._connect_bridge_async(tab, _BRIDGE_CONNECT_ASYNC_ATTEMPTS)
        return tab

    def close_tab(self, tab):
        tab.stop()
        if tab in self._tabs:
            self._tabs.remove(tab)

    def _connect_bridge_async(self, tab, attempts_left):
        if tab not in self._tabs:
            return  # tab was closed before its bridge finished connecting
        try:
            tab.bridge_client.connect(retries=1, retry_delay=0)
            return
        except ConnectionError:
            if attempts_left > 0:
                QTimer.singleShot(
                    _BRIDGE_CONNECT_ASYNC_INTERVAL_MS,
                    lambda: self._connect_bridge_async(tab, attempts_left - 1))

    def _poll_all(self):
        for tab in list(self._tabs):
            tab.refresh_panels()
            self._poll_title(tab)

    def _poll_title(self, tab):
        try:
            resp = tab.bridge_client.get_title()
        except (ConnectionError, OSError):
            return
        if resp.get('ok'):
            self.title_changed.emit(tab, resp['result'])
