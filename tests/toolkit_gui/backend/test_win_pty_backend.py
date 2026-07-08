'''Tests for toolkit_gui.backend.win_pty_backend.find_descendant_pid_by_cmdline()
- the fix for a Phase 0 finding: pywinpty reports an intermediate cmd.exe's
pid when spawning via `cmd /c call activate.bat && python...`, and even among
its python.exe descendants, conda's activate.bat can spawn its own
short-lived helper process that must not be mistaken for the real session.

Uses real (non-pty) child processes via subprocess, since the goal here is
to test the psutil-based descendant-walking/cmdline-matching logic, not
ConPTY itself (that part is covered by manual verification - see
regression_test.bat's KNOWN_UNTESTABLE list).
'''

import platform
import subprocess
import sys
import time

import pytest

from toolkit_gui.backend.win_pty_backend import find_descendant_pid_by_cmdline

pytestmark = pytest.mark.skipif(platform.system() != 'Windows', reason='Windows-only backend')


def test_finds_descendant_matching_cmdline_substring():
    # Pass argv as separate list items (not a pre-assembled quoted string) so
    # subprocess's own list2cmdline() quoting is applied exactly once -
    # pre-quoting our own command string here would hit the same
    # double-escaping bug a Phase 0 spike found in the pywinpty spawn path.
    marker = 'test_win_pty_backend_marker.py'
    root = subprocess.Popen(
        ['cmd.exe', '/c', sys.executable, '-c', 'import time; time.sleep(5)', marker])
    try:
        found = find_descendant_pid_by_cmdline(root.pid, marker, timeout=10, poll=0.2)
        assert found is not None
    finally:
        root.kill()
        root.wait(timeout=5)


def test_returns_none_when_no_descendant_matches():
    root = subprocess.Popen(['cmd.exe', '/c', sys.executable, '-c', 'import time; time.sleep(2)'])
    try:
        found = find_descendant_pid_by_cmdline(root.pid, 'this-string-will-never-match', timeout=3, poll=0.2)
        assert found is None
    finally:
        root.kill()
        root.wait(timeout=5)
