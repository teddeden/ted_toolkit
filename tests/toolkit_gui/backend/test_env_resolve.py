'''Tests for toolkit_gui.backend.env_resolve's pure spawn-argv/port logic.'''

from toolkit_gui import config
from toolkit_gui.backend.env_resolve import build_spawn_argv, find_free_port


def test_build_spawn_argv_replicates_start_ted_toolkit_bat(monkeypatch):
    monkeypatch.setattr(config, 'ACTIVATE_BAT', r'C:\Anaconda\activate.bat')
    monkeypatch.setattr(config, 'ENV_PATH', r'C:\envs\toolkit-env')
    monkeypatch.setattr(config, 'TOOLKIT_PY', r'C:\toolkit\ted_toolkit.py')
    argv = build_spawn_argv()
    assert argv[0] == 'cmd.exe'
    assert argv[1] == '/c'
    assert argv[2] == (
        r'call C:\Anaconda\activate.bat C:\envs\toolkit-env && '
        r'C:\envs\toolkit-env\python.exe -i C:\toolkit\ted_toolkit.py'
    )


def test_build_spawn_argv_appends_extra_args(monkeypatch):
    monkeypatch.setattr(config, 'ACTIVATE_BAT', 'activate.bat')
    monkeypatch.setattr(config, 'ENV_PATH', 'envpath')
    monkeypatch.setattr(config, 'TOOLKIT_PY', 'ted_toolkit.py')
    argv = build_spawn_argv(extra_args=[r'C:\scripts\myscript.py'])
    assert argv[2].endswith(r'ted_toolkit.py C:\scripts\myscript.py')


def test_build_spawn_argv_contains_no_quote_characters(monkeypatch):
    '''Regression guard: embedding our own quote characters here causes a
    double-escaping bug when pywinpty's spawn() re-quotes the command via
    subprocess.list2cmdline() - confirmed via a Phase 0 spike.'''
    monkeypatch.setattr(config, 'ACTIVATE_BAT', 'activate.bat')
    monkeypatch.setattr(config, 'ENV_PATH', 'envpath')
    monkeypatch.setattr(config, 'TOOLKIT_PY', 'ted_toolkit.py')
    argv = build_spawn_argv()
    assert '"' not in argv[2]


def test_find_free_port_returns_usable_port():
    port = find_free_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535
