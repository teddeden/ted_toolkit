'''toolkit_gui.backend.posix_pty_backend - stub for a future Linux/Mac port.

Windows needs ConPTY (via pywinpty) specifically because pyreadline3 hooks a
Windows-only C API (PyOS_ReadlineFunctionPointer via the Win32 console).
On POSIX, the toolkit would run under stdlib GNU readline instead - a
different, standard mechanism with none of pyreadline3's console-hook
fragility - so a real pseudo-terminal is still required for full fidelity,
but the stdlib `pty` module (pty.openpty() + os.fork()/subprocess, or the
third-party `ptyprocess` package for a higher-level API) is the standard way
to host one; no ConPTY-equivalent third-party dependency is needed the way
pywinpty is on Windows. Not implemented yet - Windows is the only target for
this feature today (see CLAUDE.md/ABOUT.md).
'''

from toolkit_gui.backend.pty_backend import PtyBackend


class PosixPtyBackend(PtyBackend):
    '''Not implemented. See module docstring for the planned approach.'''

    def spawn(self, argv, cwd=None, env=None, cols=120, rows=40):
        raise NotImplementedError(
            'POSIX pty backend not implemented yet - see '
            'toolkit_gui.backend.posix_pty_backend module docstring for the '
            'planned approach (stdlib pty.openpty() + subprocess).')
