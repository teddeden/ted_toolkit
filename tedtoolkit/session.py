'''tedtoolkit.session - pure cores behind session save/restore, shared by the CLI's
save_session()/restore_session() (ted_toolkit.py) and the GUI bridge's
rpc_save_session()/rpc_restore_session() (tedtoolkit/gui_bridge.py).

Everything here takes an explicit namespace dict rather than calling globals(), so it
can be unit tested and called from any module; the CLI wrappers stay in ted_toolkit.py
because they need the interactive session's own globals() (same reason as help_vars()).

The on-disk format is the GUI's .tedsession zip (toolkit_gui/session_bundle.py, pure
json+zipfile), so a session saved from the CLI can be restored in the GUI and vice versa.
That module is imported lazily, only when a bundle is actually read or written - the
CLI never needs PySide6, and the GUI process deliberately never imports this package.
'''

import inspect
import pickle
import readline

# Known toolkit-internal globals that are never "working variables" a user
# would expect back after restoring a session. Deliberately NOT an ALL-CAPS
# blanket exclusion (unlike help_vars()'s display filter) - that would risk
# silently dropping a user's own all-caps variable from a save.
SESSION_INTERNAL_DENYLIST = {
    'VERSION', 'FUNCTION_CATEGORIES', 'ARGS', 'LAST_LINE_ATTEMPTED',
    'DYNAMIC_IMPORTS', 'SCRIPT_RUNNING',
}

SESSION_FILETYPES = [('Ted Toolkit session', ('*.tedsession')), ('All Files', ('*.*'))]

_MISSING = object()


def _classify_session_variables(namespace, baseline=None):
    '''Pure function: given a globals()-like dict, return the sorted list of
    names that a session save should attempt to pickle. Excludes dunders,
    known toolkit internals (SESSION_INTERNAL_DENYLIST), and anything that
    is a function/module/class rather than data.

    baseline (optional): a {name: value} snapshot of the namespace taken right after the
    toolkit finished loading (ted_toolkit.py's _SESSION_BASELINE). A name still bound to
    the very same object it had at load time is toolkit-provided (e.g. ALL_SHEETS_TEXT,
    QUOTING_OPTIONS) and is skipped; if the user rebound it, it is the user's data.'''
    baseline = baseline or {}
    result = []
    for name, value in namespace.items():
        if name.startswith('_'):
            continue
        if name in SESSION_INTERNAL_DENYLIST:
            continue
        if inspect.isfunction(value) or inspect.ismodule(value) or inspect.isclass(value):
            continue
        if baseline.get(name, _MISSING) is value:
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


def _save_session_core(namespace, history_lines, path, *, toolkit_version, saved_by,
                       saved_at_utc, baseline=None):
    '''Write namespace's working variables plus history_lines to a .tedsession bundle at
    path (CLI saves have no terminal transcript, so transcript.txt is empty).
    Returns (succeeded_names, failed) as reported by _pickle_variables().'''
    from toolkit_gui.session_bundle import write_bundle
    names = _classify_session_variables(namespace, baseline)
    pickled_bytes, succeeded, failed = _pickle_variables(namespace, names)
    write_bundle(path, transcript_text='', history_lines=list(history_lines),
                 variables_pickle_bytes=pickled_bytes, variables_succeeded=succeeded,
                 variables_failed=failed, toolkit_version=toolkit_version,
                 saved_at_utc=saved_at_utc, saved_by=saved_by)
    return succeeded, failed


def _load_session_core(path):
    '''Read a .tedsession bundle and unpickle its variables. Returns a dict with
    'manifest', 'history_lines', 'variables' (a {name: value} dict, or None if
    variables.pkl was missing/unreadable) and 'errors' (list of str). Raises
    toolkit_gui.session_bundle.BundleError if the file isn't a usable bundle at all.
    WARNING: unpickling can execute arbitrary code - only restore trusted files.'''
    from toolkit_gui.session_bundle import read_bundle
    bundle = read_bundle(path)
    errors = list(bundle['read_errors'])
    variables = None
    if bundle['variables_pickle_bytes'] is not None:
        try:
            variables = pickle.loads(bundle['variables_pickle_bytes'])
        except Exception as exc:
            errors.append(f'Could not unpickle variables.pkl: {exc}')
    return {'manifest': bundle['manifest'],
            'history_lines': [line for line in bundle['history_lines'] if line is not None],
            'variables': variables,
            'errors': errors}


def _find_restore_conflicts(namespace, variables, baseline=None):
    '''Names in `variables` (about to be restored) that are already bound to working data
    in namespace - i.e. that a restore would overwrite. Toolkit-provided names (see
    _classify_session_variables()) are not conflicts. Returns a sorted list of
    (name, current_type_name, archived_type_name) tuples.'''
    current = set(_classify_session_variables(namespace, baseline))
    return [(name, type(namespace[name]).__name__, type(variables[name]).__name__)
            for name in sorted(variables) if name in current]


def _restore_session_core(namespace, variables, history_lines, marker=None):
    '''Inject variables into namespace and APPEND history_lines (preceded by an optional
    marker comment line) to the readline history. Never executes any history line -
    restored history is for up-arrow recall and save_history() only.'''
    namespace.update(variables or {})
    if marker:
        readline.add_history(marker)
    for line in history_lines:
        readline.add_history(line)
