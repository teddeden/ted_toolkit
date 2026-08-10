'''toolkit_gui.backend.pty_backend - abstract pseudo-terminal backend
interface. Only a Windows ConPTY implementation (win_pty_backend.py) is
built today; posix_pty_backend.py is a documented stub for a future
Linux/Mac port - see that module's docstring for the planned approach.

Every GUI tab hosts its interactive session as a real OS process running
inside a genuine pseudo-terminal (not redirected pipes), specifically so the
Windows-only pyreadline3 console hook the toolkit's history/guided-function
mechanism depends on keeps working completely unmodified - confirmed via a
Phase 0 spike (arrow-key history recall executes correctly end-to-end
through this exact spawn path).
'''

import platform
from abc import ABC, abstractmethod


class PtySession(ABC):
    '''One spawned child process hosted inside a real pseudo-terminal.'''

    @property
    @abstractmethod
    def pid(self):
        '''PID of the actual target process. NOT necessarily the same as
        whatever pid the underlying pty library first reports - see
        win_pty_backend.WinPtySession.pid for why resolving the real
        descendant process matters on Windows.'''

    @abstractmethod
    def read(self, size=65536, timeout=None):
        '''Read up to size bytes of raw pty output. Returns b'' if timeout
        elapses with no data available; raises EOFError once the pty is
        closed for good.'''

    @abstractmethod
    def write(self, data):
        '''Write raw bytes (already-encoded key sequences) to the pty.'''

    @abstractmethod
    def resize(self, cols, rows):
        '''Resize the pseudo-terminal's character grid.'''

    @abstractmethod
    def is_alive(self):
        '''True if the underlying process is still running.'''

    @abstractmethod
    def terminate(self, force=False):
        '''Terminate the underlying process (and its process tree).'''


class PtyBackend(ABC):
    '''Factory for PtySession instances.'''

    @abstractmethod
    def spawn(self, argv, cwd=None, env=None, cols=120, rows=40):
        '''Start argv in a new pseudo-terminal and return a PtySession.'''


def get_pty_backend():
    '''Return the PtyBackend implementation for the current OS.'''
    if platform.system() == 'Windows':
        from toolkit_gui.backend.win_pty_backend import WinPtyBackend
        return WinPtyBackend()
    from toolkit_gui.backend.posix_pty_backend import PosixPtyBackend
    return PosixPtyBackend()
