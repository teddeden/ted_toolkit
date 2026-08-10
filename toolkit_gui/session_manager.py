'''toolkit_gui.session_manager - spawns/tracks GUI tabs and owns the shared
poll timer that drives variable/preview refresh and title-bar sync (CPU
sampling/busy-indicator join the same timer in Phase 5).
'''

import os

import psutil
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

# Above this per-tab CPU%, a tab is considered "busy" for its status dot.
BUSY_CPU_THRESHOLD_PERCENT = 5.0


class SessionManager(QObject):
    title_changed = Signal(object, str)  # (SessionTabWidget, new title)
    cpu_total_changed = Signal(float)  # sum of every tab's own process CPU%
    tab_busy_changed = Signal(object, bool)  # (SessionTabWidget, is_busy)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend = get_pty_backend()
        self._tabs = []
        self._psutil_processes = {}  # id(tab) -> psutil.Process
        self._cpu_sampled_once = set()  # id(tab) already past psutil's meaningless first sample
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
        session = self._backend.spawn(build_spawn_argv(extra_args), env=env,
                                       cols=config.TERMINAL_COLS, rows=config.TERMINAL_ROWS)
        bridge_client = BridgeClient(port)
        tab = SessionTabWidget(session, bridge_client, parent=parent)
        self._tabs.append(tab)
        self._connect_bridge_async(tab, _BRIDGE_CONNECT_ASYNC_ATTEMPTS)
        return tab

    def close_tab(self, tab):
        tab.stop()
        self._psutil_processes.pop(id(tab), None)
        self._cpu_sampled_once.discard(id(tab))
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
        total_cpu = 0.0
        for tab in list(self._tabs):
            tab.refresh_panels()
            self._poll_title(tab)
            cpu = self._sample_cpu(tab)
            if cpu is not None:
                total_cpu += cpu
                self.tab_busy_changed.emit(tab, cpu >= BUSY_CPU_THRESHOLD_PERCENT)
        self.cpu_total_changed.emit(total_cpu)

    def _poll_title(self, tab):
        try:
            resp = tab.bridge_client.get_title()
        except (ConnectionError, OSError):
            return
        if resp.get('ok'):
            self.title_changed.emit(tab, resp['result'])

    def _sample_cpu(self, tab):
        '''Return this tab's own process CPU% since the last sample, or None
        if not yet measurable (process not resolved yet, or this is the
        first sample right after psutil.Process() creation - meaningless by
        psutil's own convention, since there's no prior interval to compare
        against).'''
        key = id(tab)
        process = self._psutil_processes.get(key)
        if process is None:
            try:
                process = psutil.Process(tab.session.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return None
            self._psutil_processes[key] = process
        try:
            cpu = process.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self._psutil_processes.pop(key, None)
            self._cpu_sampled_once.discard(key)
            return None
        if key not in self._cpu_sampled_once:
            self._cpu_sampled_once.add(key)
            return None
        return cpu
