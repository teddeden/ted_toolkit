'''toolkit_gui.backend.win_pty_backend - Windows ConPTY-backed PtyBackend,
implemented via pywinpty (the `winpty` package). This is the only backend
built today; see posix_pty_backend.py for the future Linux/Mac approach.
'''

import time

import psutil
import winpty

from toolkit_gui import config
from toolkit_gui.backend.pty_backend import PtyBackend, PtySession


def find_descendant_pid_by_cmdline(root_pid, cmdline_substring,
                                    timeout=config.PID_RESOLVE_TIMEOUT_SECONDS, poll=0.5):
    '''Walk root_pid's descendants looking for a python.exe whose command
    line contains cmdline_substring (e.g. "ted_toolkit.py").

    Needed because when spawning via `cmd /c call activate.bat && python...`,
    pywinpty reports the PID of the outermost cmd.exe it launched, not the
    real python.exe - confirmed via a Phase 0 spike. Matching descendants by
    executable name alone is ALSO unsafe: conda's activate.bat can spawn its
    own short-lived helper python.exe as a sibling/child process, and the
    first "python.exe" found by name is not reliably the actual interactive
    `-i ted_toolkit.py` session (this was observed directly in the same
    spike - a name-only match returned a stale/incorrect PID with no window
    ownership, while the real session's PID, found only by checking cmdline,
    did). Matching on cmdline substring avoids both problems.'''
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            root = psutil.Process(root_pid)
            for child in root.children(recursive=True):
                try:
                    if child.name().lower() != 'python.exe':
                        continue
                    if cmdline_substring in ' '.join(child.cmdline()):
                        return child.pid
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except psutil.NoSuchProcess:
            pass
        time.sleep(poll)
    return None


class WinPtySession(PtySession):
    def __init__(self, proc, target_cmdline_substring):
        self._proc = proc
        self._target_cmdline_substring = target_cmdline_substring
        self._resolved_pid = None

    @property
    def pid(self):
        if self._resolved_pid is not None:
            return self._resolved_pid
        resolved = find_descendant_pid_by_cmdline(self._proc.pid, self._target_cmdline_substring)
        if resolved is not None:
            self._resolved_pid = resolved
            return resolved
        return self._proc.pid  # fall back to the (likely-wrong) root pid rather than None

    def read(self, size=65536, timeout=None):
        if timeout is not None:
            self._proc.fileobj.settimeout(timeout)
        try:
            text = self._proc.read(size)
        except EOFError:
            raise
        except Exception:
            return b''  # socket timeout or similar transient error - no data this tick
        return text.encode('utf-8', errors='surrogateescape')

    def write(self, data):
        if isinstance(data, bytes):
            data = data.decode('utf-8', errors='surrogateescape')
        self._proc.write(data)

    def resize(self, cols, rows):
        self._proc.setwinsize(rows, cols)

    def is_alive(self):
        return self._proc.isalive()

    def terminate(self, force=False):
        try:
            self._proc.close(force=force)
        except Exception:
            pass


class WinPtyBackend(PtyBackend):
    def spawn(self, argv, cwd=None, env=None, cols=120, rows=40):
        proc = winpty.PtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=(rows, cols))
        # ted_toolkit.py is the file every spawn (fresh interactive session
        # or script-replay launch) launches by name, so it's a stable marker
        # for "this is the real toolkit session, not a conda helper process".
        return WinPtySession(proc, target_cmdline_substring='ted_toolkit.py')
