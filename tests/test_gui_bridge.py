'''Tests for tedtoolkit.gui_bridge's pure/testable logic: variable
classification, per-variable pickling failure handling, history collection,
and the save/restore RPC handlers. Deliberately excludes the real socket
server loop and the Windows-only GetConsoleTitleW call - those are exercised
manually alongside the rest of the GUI shell (see regression_test.bat's
KNOWN_UNTESTABLE list), consistent with this codebase's existing precedent
for tkinter dialogs/Excel COM/clipboard.
'''

import pickle
import types

from tedtoolkit.gui_bridge import (
    SESSION_INTERNAL_DENYLIST,
    _classify_session_variables,
    _collect_history_lines,
    _dispatch,
    _pickle_variables,
    rpc_restore_session,
    rpc_save_session,
)


def test_classify_excludes_dunders_and_denylisted_internals():
    namespace = {
        '__builtins__': {},
        'VERSION': '0.72',
        'ARGS': [],
        'my_table': [['a']],
        'my_count': 5,
    }
    assert _classify_session_variables(namespace) == ['my_count', 'my_table']


def test_classify_excludes_functions_modules_and_classes():
    namespace = {'fn': lambda: None, 'mod': types, 'cls': int, 'data': 1}
    assert _classify_session_variables(namespace) == ['data']


def test_classify_does_not_exclude_all_caps_user_variables():
    '''Deliberate divergence from help_vars()'s display filter: a user's own
    ALL-CAPS variable must never be silently dropped from a save.'''
    namespace = {'TOTAL_REVENUE': 1000}
    assert _classify_session_variables(namespace) == ['TOTAL_REVENUE']


def test_denylist_covers_every_known_ted_toolkit_global():
    assert SESSION_INTERNAL_DENYLIST == {
        'VERSION', 'FUNCTION_CATEGORIES', 'ARGS', 'LAST_LINE_ATTEMPTED',
        'DYNAMIC_IMPORTS', 'SCRIPT_RUNNING',
    }


def test_pickle_variables_round_trips_normal_values():
    namespace = {'a': [1, 2], 'b': {'k': 'v'}}
    pickled, succeeded, failed = _pickle_variables(namespace, ['a', 'b'])
    assert succeeded == ['a', 'b']
    assert failed == []
    assert pickle.loads(pickled) == namespace


def test_pickle_variables_isolates_one_bad_value():
    namespace = {'good': [1, 2], 'bad': (lambda: None)}
    pickled, succeeded, failed = _pickle_variables(namespace, ['good', 'bad'])
    assert succeeded == ['good']
    assert len(failed) == 1
    assert failed[0]['name'] == 'bad'
    assert pickle.loads(pickled) == {'good': [1, 2]}


def test_collect_history_lines(seed_history):
    import readline
    seed_history('x = 1')
    readline.add_history('y = 2')
    assert _collect_history_lines() == ['x = 1', 'y = 2']


def test_rpc_save_session_returns_history_and_pickled_variables(seed_history):
    seed_history('x = 1')
    session_globals = {'x': 1, 'VERSION': '0.72'}
    resp = rpc_save_session(session_globals)
    assert resp['ok'] is True
    assert resp['history'] == ['x = 1']
    assert resp['variables_succeeded'] == ['x']
    assert resp['variables_failed'] == []


def test_rpc_save_session_blocked_while_script_running():
    resp = rpc_save_session({'SCRIPT_RUNNING': True})
    assert resp == {'ok': False, 'error': 'script_running'}


def test_rpc_restore_session_injects_variables_without_executing(seed_history):
    seed_history('leftover = 999')
    session_globals = {}
    resp = rpc_restore_session(session_globals, ['x = 42'], _encode({'x': 42}))
    assert resp['ok'] is True
    assert session_globals['x'] == 42
    assert resp['history_restored'] == 1
    assert resp['variables_restored'] == ['x']


def test_rpc_restore_session_reports_pickle_error_without_failing_history():
    session_globals = {}
    resp = rpc_restore_session(session_globals, ['a = 1'], 'not-valid-base64!!!')
    assert resp['ok'] is True
    assert resp['history_restored'] == 1
    assert resp['variables_restored'] == []
    assert resp['variables_error'] is not None


def test_rpc_restore_session_blocked_while_script_running():
    resp = rpc_restore_session({'SCRIPT_RUNNING': True}, [], '')
    assert resp == {'ok': False, 'error': 'script_running'}


def test_dispatch_list_vars():
    resp = _dispatch({'id': 1, 'cmd': 'list_vars'}, {'x': [1, 2]})
    assert resp['ok'] is True
    assert resp['id'] == 1
    assert resp['result'] == [{'name': 'x', 'type': 'list', 'preview': '[1, 2]'}]


def test_dispatch_get_var_preview_table(orders_table):
    resp = _dispatch({'id': 2, 'cmd': 'get_var_preview', 'params': {'name': 't'}},
                      {'t': orders_table})
    assert resp['ok'] is True
    assert resp['result']['kind'] == 'table'
    assert resp['result']['row_count'] == 6


def test_dispatch_get_var_preview_scalar():
    resp = _dispatch({'id': 3, 'cmd': 'get_var_preview', 'params': {'name': 's'}},
                      {'s': 'hello'})
    assert resp['ok'] is True
    assert resp['result']['kind'] == 'scalar'


def test_dispatch_get_var_preview_missing_variable():
    resp = _dispatch({'id': 4, 'cmd': 'get_var_preview', 'params': {'name': 'missing'}}, {})
    assert resp['ok'] is False


def test_dispatch_unknown_command():
    resp = _dispatch({'id': 5, 'cmd': 'nonsense'}, {})
    assert resp['ok'] is False
    assert 'unknown command' in resp['error']


def _encode(variables_dict):
    import base64
    return base64.b64encode(pickle.dumps(variables_dict)).decode('ascii')
