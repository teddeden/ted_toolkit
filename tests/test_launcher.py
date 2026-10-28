'''Tests for the ted_toolkit.py launcher itself: help_all() coverage of the public namespace,
and startup dispatch of command-line / drag-and-drop arguments (_launch_from_args()).'''

import inspect
import readline

import pytest

import ted_toolkit
from tedtoolkit import session


def test_every_public_function_has_a_help_all_category():
    # Regression: maybe_start_bridge() leaked into help_all() under "**no category**"
    namespace = vars(ted_toolkit)
    uncategorised = [name for name, value in namespace.items()
                     if inspect.isfunction(value) and not name.startswith('_')
                     and name not in ted_toolkit.FUNCTION_CATEGORIES]
    assert uncategorised == []


# --- startup dispatch for command-line / drag-and-drop arguments ----------------------

def _history():
    return [readline.get_history_item(i) for i in range(1, readline.get_current_history_length() + 1)]


@pytest.fixture
def launcher(monkeypatch):
    '''Neutralise console side effects (cls, window title) and record titles set.'''
    titles = []
    monkeypatch.setattr(ted_toolkit.os, 'system', lambda command: 0)
    monkeypatch.setattr(ted_toolkit, 'set_window_title',
                        lambda text, include_timestamp=None: titles.append((text, include_timestamp)))
    namespace = vars(ted_toolkit)
    before = set(namespace)
    yield titles
    for name in set(namespace) - before:
        del namespace[name]


def test_classify_launch_arg(tmp_path):
    for name in ('s.py', 'S.PY', 'x.tedsession', 'a.csv', 'b.txt', 'c.xlsx', 'd.tar.gz', 'noext'):
        (tmp_path / name).write_text('')
    expected = {'s.py': 'script', 'S.PY': 'script', 'x.tedsession': 'session', 'a.csv': 'data',
                'b.txt': 'data', 'c.xlsx': 'data', 'd.tar.gz': 'data', 'noext': 'data'}
    for name, kind in expected.items():
        assert ted_toolkit._classify_launch_arg(str(tmp_path / name)) == kind
    assert ted_toolkit._classify_launch_arg(str(tmp_path)) == 'data'
    assert ted_toolkit._classify_launch_arg(str(tmp_path / 'missing.csv')) == 'invalid'


def test_no_args_falls_back_to_interactive_start():
    assert ted_toolkit._launch_from_args([]) is False


def test_missing_file_falls_back_to_interactive_start(tmp_path, launcher, capsys):
    assert ted_toolkit._launch_from_args([str(tmp_path / 'gone.csv')]) is False
    assert 'not found' in capsys.readouterr().out
    assert launcher == []


def test_single_data_file_imports_into_data(tmp_path, launcher, monkeypatch):
    path = str(tmp_path / 'orders.csv')
    open(path, 'w').close()
    calls = []
    monkeypatch.setattr(ted_toolkit, 'data_import', lambda **kw: calls.append(kw) or [['h'], [1]])
    assert ted_toolkit._launch_from_args([path]) is True
    assert calls == [{'file_path': path}]
    assert ted_toolkit.data == [['h'], [1]]
    assert _history() == [f'data = data_import(file_path={path!r})']
    assert launcher == [('orders.csv', 'LOCAL')]


def test_several_data_files_import_into_numbered_vars(tmp_path, launcher, monkeypatch):
    paths = [str(tmp_path / name) for name in ('a.csv', 'b.xlsx')]
    for path in paths:
        open(path, 'w').close()
    monkeypatch.setattr(ted_toolkit, 'data_import', lambda **kw: kw['file_path'])
    assert ted_toolkit._launch_from_args(paths) is True
    assert (ted_toolkit.data_1, ted_toolkit.data_2) == tuple(paths)
    assert _history() == [f'data_1 = data_import(file_path={paths[0]!r})',
                          f'data_2 = data_import(file_path={paths[1]!r})']
    assert launcher == [('a.csv, b.xlsx', 'LOCAL')]


def test_import_error_keeps_session_usable(tmp_path, launcher, monkeypatch, capsys):
    path = str(tmp_path / 'bad.csv')
    open(path, 'w').close()

    def _boom(**kw):
        raise ValueError('cannot parse')
    monkeypatch.setattr(ted_toolkit, 'data_import', _boom)
    monkeypatch.setattr(ted_toolkit, 'beep', lambda: None)
    assert ted_toolkit._launch_from_args([path]) is True
    assert 'cannot parse' in capsys.readouterr().err


def test_mixed_args_follow_first_kind_and_warn(tmp_path, launcher, monkeypatch, capsys):
    data_path, script_path = str(tmp_path / 'a.csv'), str(tmp_path / 's.py')
    open(data_path, 'w').close()
    open(script_path, 'w').close()
    monkeypatch.setattr(ted_toolkit, 'data_import', lambda **kw: 1)
    ted_toolkit._launch_from_args([data_path, script_path])
    assert 'ignoring additional startup argument' in capsys.readouterr().out
    assert _history() == [f'data = data_import(file_path={data_path!r})']


def test_script_arg_replays_via_run_script(tmp_path, launcher, monkeypatch):
    script_path = str(tmp_path / 's.py')
    open(script_path, 'w').close()
    calls = []
    monkeypatch.setattr(ted_toolkit, '_run_script', lambda args, **kw: calls.append((args, kw)))
    assert ted_toolkit._launch_from_args([script_path]) is True
    assert calls == [([script_path], {'view_comments': True})]
    assert launcher == []


def test_tedsession_arg_restores_session(tmp_path, launcher):
    path = str(tmp_path / 'day1.tedsession')
    session._save_session_core({'restored_tree': {'a': [1, 2]}}, ['restored_tree = build()'], path,
                               toolkit_version='0.77', saved_by='T', saved_at_utc='now')
    readline.add_history('#SCRIPT START')
    assert ted_toolkit._launch_from_args([path]) is True
    assert ted_toolkit.restored_tree == {'a': [1, 2]}
    history = _history()
    assert history[0] == '#SCRIPT START'
    assert history[1].startswith('# --- restored session from')
    assert history[2:] == ['restored_tree = build()']
    assert launcher == [('day1.tedsession', 'LOCAL')]
