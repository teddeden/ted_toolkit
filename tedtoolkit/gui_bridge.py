'''tedtoolkit.gui_bridge - optional, opt-in local IPC bridge used ONLY by the
desktop GUI shell (toolkit_gui/, a separate top-level package - see ABOUT.md).

maybe_start_bridge() is called once from ted_toolkit.py right after
`ARGS = sys.argv[1:]` is defined, and no-ops instantly unless the GUI has set
TEDTOOLKIT_GUI_BRIDGE_PORT before spawning this process. start_ted_toolkit.bat
never sets that variable, so plain command-line usage is completely
unaffected by this module's existence.

When active, this starts a background daemon thread that accepts a single
localhost TCP connection at a time and answers newline-delimited JSON
requests, giving the GUI (a separate process/interpreter) structured access
to this session's live variables/tables and to two menu-only capabilities
(save_session / restore_session) that are deliberately NEVER imported into
ted_toolkit.py, so they are structurally invisible to help_all()'s listing
and to plain interactive typing.

Restoring a session never replays/exec()s history - it only re-adds lines to
the readline history buffer (exactly the same readline.add_history() call
_run_script() already makes, minus its paired exec()) and injects unpickled
variables directly into the live namespace, so a restored session is usable
with zero recomputation.
'''

import base64
import ctypes
import inspect
import json
import os
import pickle
import readline
import socket
import threading

from tedtoolkit.introspect import _variable_snapshot_core
from tedtoolkit.tables.preview import _prev_s
from tedtoolkit.tables.snapshot import _table_snapshot_core
from tedtoolkit.validation import _is_list_of_lists

# Known toolkit-internal globals that are never "working variables" a user
# would expect back after restoring a session. Deliberately NOT an ALL-CAPS
# blanket exclusion (unlike help_vars()'s display filter) - that would risk
# silently dropping a user's own all-caps variable from a save.
SESSION_INTERNAL_DENYLIST = {
    'VERSION', 'FUNCTION_CATEGORIES', 'ARGS', 'LAST_LINE_ATTEMPTED',
    'DYNAMIC_IMPORTS', 'SCRIPT_RUNNING',
}


def maybe_start_bridge(session_globals):
    '''Start the GUI bridge's background thread iff the GUI set
    TEDTOOLKIT_GUI_BRIDGE_PORT before spawning this process. No-ops
    instantly otherwise.'''
    port_str = os.environ.get('TEDTOOLKIT_GUI_BRIDGE_PORT')
    if not port_str:
        return
    try:
        port = int(port_str)
    except ValueError:
        return
    thread = threading.Thread(target=_bridge_server_loop, args=(port, session_globals), daemon=True)
    thread.start()


def _bridge_server_loop(port, session_globals):
    '''Accept one GUI connection at a time on 127.0.0.1:port and dispatch its
    requests until it disconnects, then wait for the next one. Never raises
    into the interactive session's main thread.'''
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', port))
        server.listen(1)
    except OSError:
        return
    while True:
        try:
            conn, _addr = server.accept()
        except OSError:
            return
        try:
            _handle_connection(conn, session_globals)
        except Exception:
            pass
        finally:
            conn.close()


def _handle_connection(conn, session_globals):
    buf = b''
    while True:
        chunk = conn.recv(65536)
        if not chunk:
            return
        buf += chunk
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            if not line.strip():
                continue
            try:
                req = json.loads(line.decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                continue
            resp = _dispatch(req, session_globals)
            conn.sendall((json.dumps(resp) + '\n').encode('utf-8'))


def _dispatch(req, session_globals):
    req_id = req.get('id')
    cmd = req.get('cmd')
    params = req.get('params', {})
    try:
        if cmd == 'list_vars':
            return {'id': req_id, 'ok': True, 'result': _variable_snapshot_core(session_globals)}
        if cmd == 'get_var_preview':
            resp = _handle_get_var_preview(session_globals, params)
            resp['id'] = req_id
            return resp
        if cmd == 'get_title':
            return {'id': req_id, 'ok': True, 'result': _get_console_title()}
        if cmd == 'save_session':
            resp = rpc_save_session(session_globals)
            resp['id'] = req_id
            return resp
        if cmd == 'restore_session':
            resp = rpc_restore_session(session_globals, params.get('history', []),
                                        params.get('variables_pickle_b64', ''))
            resp['id'] = req_id
            return resp
        return {'id': req_id, 'ok': False, 'error': f'unknown command: {cmd}'}
    except Exception as exc:
        return {'id': req_id, 'ok': False, 'error': str(exc)}


def _handle_get_var_preview(session_globals, params):
    name = params.get('name')
    if name not in session_globals:
        return {'ok': False, 'error': f'no such variable: {name}'}
    value = session_globals[name]
    if _is_list_of_lists(value):
        max_rows = params.get('max_rows', 250)
        max_cols = params.get('max_cols', 250)
        snapshot = _table_snapshot_core(value, max_rows, max_cols)
        return {'ok': True, 'result': {'kind': 'table', **snapshot}}
    return {'ok': True, 'result': {'kind': 'scalar', 'preview': _prev_s(value)}}


def _get_console_title():
    '''Poll the real Windows console title via GetConsoleTitleW. This is the
    mechanism the GUI uses to sync a tab's label with set_window_title() -
    ConPTY has no outer window of its own to read a title from, so polling
    from inside the child (which does own a real, if invisible, console
    object) is the only viable approach, not merely the preferred one.'''
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.kernel32.GetConsoleTitleW(buf, 512)
    return buf.value


def _classify_session_variables(namespace):
    '''Pure function: given a globals()-like dict, return the sorted list of
    names that save_session() should attempt to pickle. Excludes dunders,
    known toolkit internals (SESSION_INTERNAL_DENYLIST), and anything that
    is a function/module/class rather than data.'''
    result = []
    for name, value in namespace.items():
        if name.startswith('_'):
            continue
        if name in SESSION_INTERNAL_DENYLIST:
            continue
        if inspect.isfunction(value) or inspect.ismodule(value) or inspect.isclass(value):
            continue
        result.append(name)
    return sorted(result)


def _pickle_variables(namespace, names):
    '''Try pickling each named variable individually so one unpicklable
    object (e.g. a live dynamic_import() module) can't abort the whole save.
    Returns (pickled_bytes, succeeded, failed) where failed is a list of
    {'name', 'type', 'reason'} dicts.'''
    succeeded = []
    failed = []
    values = {}
    for name in names:
        value = namespace[name]
        try:
            pickle.dumps(value)
        except Exception as exc:
            failed.append({'name': name, 'type': type(value).__name__, 'reason': str(exc)})
            continue
        values[name] = value
        succeeded.append(name)
    return pickle.dumps(values), succeeded, failed


def _collect_history_lines():
    '''Same source loop save_history() (ted_toolkit.py) uses: every entry
    currently in the process readline history buffer, in order.'''
    return [readline.get_history_item(index) for index in range(1, readline.get_current_history_length() + 1)]


def rpc_save_session(session_globals):
    '''Bridge RPC handler for the GUI's "Save Session" menu action. Returns
    everything the GUI needs EXCEPT the transcript (which the GUI already
    holds client-side from its own terminal scrollback) to build a
    .tedsession bundle: history lines, and pickled working variables.'''
    if session_globals.get('SCRIPT_RUNNING', False):
        return {'ok': False, 'error': 'script_running'}
    names = _classify_session_variables(session_globals)
    pickled_bytes, succeeded, failed = _pickle_variables(session_globals, names)
    return {
        'ok': True,
        'history': _collect_history_lines(),
        'variables_pickle_b64': base64.b64encode(pickled_bytes).decode('ascii'),
        'variables_succeeded': succeeded,
        'variables_failed': failed,
    }


def rpc_restore_session(session_globals, history_lines, variables_pickle_b64):
    '''Bridge RPC handler for the GUI's "Restore Session" menu action. Never
    executes any history line - only re-adds it to the readline buffer
    (mirroring the add_history() call _run_script() already makes, minus its
    paired exec()) and injects unpickled variables directly into the live
    namespace. This is what makes "pick up where you left off without
    re-running anything" possible.'''
    if session_globals.get('SCRIPT_RUNNING', False):
        return {'ok': False, 'error': 'script_running'}
    readline.clear_history()
    for line in history_lines:
        readline.add_history(line)
    variables_restored = []
    variables_error = None
    try:
        variables = pickle.loads(base64.b64decode(variables_pickle_b64))
        session_globals.update(variables)
        variables_restored = sorted(variables.keys())
    except Exception as exc:
        variables_error = str(exc)
    print(f'\n--- Session restored: {len(history_lines)} history line(s), '
          f'{len(variables_restored)} variable(s) restored. Continuing below. ---\n')
    return {
        'ok': True,
        'history_restored': len(history_lines),
        'variables_restored': variables_restored,
        'variables_error': variables_error,
    }
