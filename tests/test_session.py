'''Tests for session save/restore: the pure cores in tedtoolkit.session, and the CLI
save_session()/restore_session() wrappers in ted_toolkit.py (driven against that
module's own globals(), which is exactly the namespace they act on in a real session).'''

import datetime
import json
import readline
import zipfile

import pytest

import ted_toolkit
from tedtoolkit import session
from toolkit_gui import session_bundle


def _history():
    return [readline.get_history_item(i) for i in range(1, readline.get_current_history_length() + 1)]


def _set_history(lines):
    readline.clear_history()
    for line in lines:
        readline.add_history(line)


@pytest.fixture
def toolkit_ns(monkeypatch):
    '''ted_toolkit's globals(), with any test-created user variables removed afterwards.'''
    namespace = vars(ted_toolkit)
    before = set(namespace)
    yield namespace
    for name in set(namespace) - before:
        del namespace[name]


def _tree():
    return {'root': {'children': [{'id': 1, 'tags': {'a'}}, {'id': 2}]},
            'when': datetime.datetime(2026, 10, 28)}


# --- pure cores -----------------------------------------------------------------------

def test_classify_skips_names_still_bound_to_baseline_objects():
    constant = 'toolkit constant'
    baseline = {'ALL_SHEETS_TEXT': constant}
    namespace = {'ALL_SHEETS_TEXT': constant, 'mine': 1}
    assert session._classify_session_variables(namespace, baseline) == ['mine']


def test_classify_keeps_rebound_baseline_names():
    baseline = {'ALL_SHEETS_TEXT': 'toolkit constant'}
    namespace = {'ALL_SHEETS_TEXT': 'user value'}
    assert session._classify_session_variables(namespace, baseline) == ['ALL_SHEETS_TEXT']


def test_save_and_load_core_round_trip(tmp_path):
    path = str(tmp_path / 's.tedsession')
    namespace = {'tree': _tree(), 'n': 3, 'bad': (x for x in []), '_private': 1}
    succeeded, failed = session._save_session_core(
        namespace, ['a = 1', 'tree = build()'], path, toolkit_version='0.77',
        saved_by='TESTER', saved_at_utc='2026-10-28-10-00-00')
    assert succeeded == ['n', 'tree']
    assert [item['name'] for item in failed] == ['bad']
    loaded = session._load_session_core(path)
    assert loaded['variables'] == {'n': 3, 'tree': _tree()}
    assert loaded['history_lines'] == ['a = 1', 'tree = build()']
    assert loaded['errors'] == []
    assert loaded['manifest']['saved_by'] == 'TESTER'


def test_cli_saved_file_is_a_valid_gui_bundle(tmp_path):
    path = str(tmp_path / 's.tedsession')
    session._save_session_core({'x': 1}, ['x = 1'], path, toolkit_version='0.77',
                               saved_by='T', saved_at_utc='now')
    bundle = session_bundle.read_bundle(path)
    assert bundle['history_lines'] == ['x = 1']
    assert bundle['transcript_text'] == ''


def test_find_restore_conflicts():
    namespace = {'a': 1, 'b': 'x', 'ALL_SHEETS_TEXT': 'const'}
    conflicts = session._find_restore_conflicts(
        namespace, {'a': [1], 'c': 2, 'ALL_SHEETS_TEXT': 'const'}, {'ALL_SHEETS_TEXT': namespace['ALL_SHEETS_TEXT']})
    assert conflicts == [('a', 'int', 'list')]


def test_restore_core_appends_history_after_marker():
    _set_history(['#SCRIPT START', 'y = 2'])
    namespace = {}
    session._restore_session_core(namespace, {'x': 1}, ['x = 1'], marker='# --- restored ---')
    assert namespace == {'x': 1}
    assert _history() == ['#SCRIPT START', 'y = 2', '# --- restored ---', 'x = 1']


def test_load_core_reports_corrupt_pickle(tmp_path):
    path = str(tmp_path / 's.tedsession')
    session._save_session_core({'x': 1}, [], path, toolkit_version='0', saved_by='T', saved_at_utc='t')
    with zipfile.ZipFile(path) as zin:
        members = {name: zin.read(name) for name in zin.namelist()}
    members['variables.pkl'] = b'not a pickle'
    with zipfile.ZipFile(path, 'w') as zout:
        for name, data in members.items():
            zout.writestr(name, data)
    loaded = session._load_session_core(path)
    assert loaded['variables'] is None
    assert any('unpickle' in error for error in loaded['errors'])


# --- CLI wrappers ---------------------------------------------------------------------

def _save(toolkit_ns, path, history):
    _set_history(history + [f'save_session(file_path={path!r})'])
    ted_toolkit.save_session(file_path=path)


def test_save_session_excludes_own_call_and_toolkit_names(tmp_path, toolkit_ns):
    path = str(tmp_path / 's.tedsession')
    toolkit_ns['tree'] = _tree()
    toolkit_ns['MY_TOTAL'] = 42
    _save(toolkit_ns, path, ['#SCRIPT START', 'tree = build()'])
    assert _history() == ['#SCRIPT START', 'tree = build()']
    with zipfile.ZipFile(path) as zin:
        manifest = json.loads(zin.read('manifest.json'))
        assert json.loads(zin.read('history.json')) == ['#SCRIPT START', 'tree = build()']
    assert manifest['variables']['succeeded'] == ['MY_TOTAL', 'tree']
    assert manifest['toolkit_version'] == ted_toolkit.VERSION


def test_restore_session_into_clean_session(tmp_path, toolkit_ns, monkeypatch):
    path = str(tmp_path / 's.tedsession')
    toolkit_ns['tree'] = _tree()
    _save(toolkit_ns, path, ['#SCRIPT START', 'tree = build()'])
    del toolkit_ns['tree']

    monkeypatch.setattr(ted_toolkit, 'ask_select', lambda *a, **k: pytest.fail('unexpected prompt'))
    _set_history(['#SCRIPT START', 'z = 9', f'restore_session(file_path={path!r})'])
    ted_toolkit.restore_session(file_path=path)
    assert toolkit_ns['tree'] == _tree()
    history = _history()
    assert history[:2] == ['#SCRIPT START', 'z = 9']
    assert history[2].startswith(f'# --- restored session from {path}')
    assert history[3:] == ['#SCRIPT START', 'tree = build()']
    assert not any('restore_session(' in line or 'save_session(' in line for line in history)


@pytest.mark.parametrize('choice, expect_overwrite', [(0, False), (1, True)])
def test_restore_session_conflict_prompt(tmp_path, toolkit_ns, monkeypatch, capsys, choice, expect_overwrite):
    path = str(tmp_path / 's.tedsession')
    toolkit_ns['tree'] = _tree()
    _save(toolkit_ns, path, ['tree = build()'])
    toolkit_ns['tree'] = 'current value'
    prompts = []
    monkeypatch.setattr(ted_toolkit, 'ask_select', lambda options, **k: prompts.append(options) or choice)
    _set_history(['z = 9', 'restore_session()'])
    ted_toolkit.restore_session(file_path=path)
    out = capsys.readouterr().out
    assert 'already exist in this session' in out and 'tree' in out
    assert len(prompts) == 1
    if expect_overwrite:
        assert toolkit_ns['tree'] == _tree()
        assert _history()[-1] == 'tree = build()'
    else:
        assert toolkit_ns['tree'] == 'current value'
        assert _history() == ['z = 9']
        assert 'Restore aborted' in out


def test_restore_session_on_conflict_kwarg_skips_prompt(tmp_path, toolkit_ns, monkeypatch):
    path = str(tmp_path / 's.tedsession')
    toolkit_ns['tree'] = _tree()
    _save(toolkit_ns, path, [])
    toolkit_ns['tree'] = 'current'
    monkeypatch.setattr(ted_toolkit, 'ask_select', lambda *a, **k: pytest.fail('unexpected prompt'))
    ted_toolkit.restore_session(file_path=path, on_conflict='abort')
    assert toolkit_ns['tree'] == 'current'
    ted_toolkit.restore_session(file_path=path, on_conflict='overwrite')
    assert toolkit_ns['tree'] == _tree()


def test_save_and_restore_blocked_while_script_running(tmp_path, toolkit_ns, monkeypatch, capsys):
    path = tmp_path / 's.tedsession'
    monkeypatch.setattr(ted_toolkit, 'SCRIPT_RUNNING', True)
    ted_toolkit.save_session(file_path=str(path))
    assert not path.exists()
    ted_toolkit.restore_session(file_path=str(path))
    assert capsys.readouterr().out.count('script is running') == 2


def test_restore_session_unreadable_file(tmp_path, capsys):
    path = tmp_path / 'junk.tedsession'
    path.write_text('not a zip')
    _set_history(['a = 1'])
    ted_toolkit.restore_session(file_path=str(path))
    assert 'Nothing restored' in capsys.readouterr().out
    assert _history() == ['a = 1']


def test_cancelled_dialog_does_nothing(monkeypatch, capsys):
    monkeypatch.setattr(ted_toolkit, 'g_sel_file_to_write', lambda **k: '')
    monkeypatch.setattr(ted_toolkit, 'g_sel_file', lambda **k: '')
    ted_toolkit.save_session()
    ted_toolkit.restore_session()
    out = capsys.readouterr().out
    assert 'Nothing saved' in out and 'Nothing restored' in out


def test_new_functions_are_categorised():
    for name in ('save_session', 'restore_session', 'timer_start', 'timer_elapsed',
                 'win_copy_pickle', 'win_paste_pickle'):
        assert name in ted_toolkit.FUNCTION_CATEGORIES
