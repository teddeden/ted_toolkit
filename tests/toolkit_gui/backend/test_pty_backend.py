'''Tests for toolkit_gui.backend.pty_backend's OS-dispatch and abstract
interface. Does not spawn any real process - see the Phase 0/2 spike scripts
and manual verification notes for actual ConPTY behavior, which cannot be
exercised by the automated suite (real console/ConPTY spawning, same as this
codebase's existing precedent for tkinter dialogs/Excel COM/clipboard).
'''

import platform

import pytest

from toolkit_gui.backend.pty_backend import PtyBackend, PtySession, get_pty_backend


def test_get_pty_backend_returns_windows_backend_on_windows():
    if platform.system() != 'Windows':
        pytest.skip('this codebase targets Windows only (see CLAUDE.md)')
    from toolkit_gui.backend.win_pty_backend import WinPtyBackend
    assert isinstance(get_pty_backend(), WinPtyBackend)


def test_pty_session_is_abstract():
    with pytest.raises(TypeError):
        PtySession()


def test_pty_backend_is_abstract():
    with pytest.raises(TypeError):
        PtyBackend()
