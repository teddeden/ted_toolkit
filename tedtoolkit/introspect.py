'''tedtoolkit.introspect - dynamic module loading and function-reference
introspection helpers used by dynamic_import()/help_all()/help_vars() (the
latter two stay in the root ted_toolkit.py launcher since they inspect the
interactive session's own globals() - see that file's module docstring).
'''

import datetime
import importlib.util
import inspect
import os

from tedtoolkit.history import _check_assignment, _add_kwarg_to_last_command, _quoted
from tedtoolkit.gui.dialogs import g_sel_file
from tedtoolkit.gui.messagebox import g_conditional_stop
from tedtoolkit.util import get_local_timestamp

DYNAMIC_IMPORTS = {}

# Container types _preview_repr() renders itself, with their repr() delimiters.
_PREVIEW_DELIMITERS = {
    dict: ('{', '}'),
    list: ('[', ']'),
    tuple: ('(', ')'),
    set: ('{', '}'),
    frozenset: ('{', '}'),
}


class _PreviewFull(Exception):
    '''Raised internally by _PreviewWriter once the preview width is used up.'''


class _PreviewWriter:
    '''Accumulates preview text and stops the render (via _PreviewFull) as soon as
    `width` characters have been produced.'''
    def __init__(self, width):
        self.parts = []
        self.remaining = width

    def write(self, text):
        self.parts.append(text)
        self.remaining -= len(text)
        if self.remaining <= 0:
            raise _PreviewFull


def _preview_repr(value, width=40):
    '''Return repr(value)[:width] WITHOUT building the full repr() first.

    help_vars() (and the GUI Variables panel via _variable_snapshot_core()) only show a
    40-character preview, but repr() of a large table/tree serialises the whole object
    first - seconds per variable for big data. This renders dict/list/tuple/set/frozenset
    (recursively) and str in iteration order, and stops as soon as `width` characters
    exist, so the cost is proportional to the preview, not to the object.

    For built-in types (and subclasses that keep the built-in __repr__) the result is
    identical to repr(value)[:width]. Dict/list subclasses with their own __repr__
    (defaultdict, Counter, ...) are approximated as "TypeName({...})"; other objects
    fall back to their own repr().'''
    if width <= 0:
        return ''
    writer = _PreviewWriter(width)
    try:
        _preview_emit(value, writer, set())
    except _PreviewFull:
        pass
    return ''.join(writer.parts)[:width]


def _preview_emit(value, writer, active):
    '''Recursive worker for _preview_repr(); `active` holds the ids of the containers
    currently being rendered, to reproduce repr()'s "[...]" for self-references.'''
    cls = type(value)
    if isinstance(value, str) and cls.__repr__ is str.__repr__:
        writer.write(_preview_str(value, writer.remaining))
        return
    base = next((item for item in _PREVIEW_DELIMITERS if isinstance(value, item)), None)
    if base is None or (base is tuple and cls.__repr__ is not tuple.__repr__):
        writer.write(_preview_safe_repr(value))
        return
    open_char, close_char = _PREVIEW_DELIMITERS[base]
    prefix = ''
    if base in (set, frozenset):
        # set.__repr__ itself prints "set()" when empty and "Name({...})" for frozenset/subclasses
        if not value:
            writer.write(f'{cls.__name__}()')
            return
        if cls is not set:
            prefix = f'{cls.__name__}('
    elif cls.__repr__ is not base.__repr__:
        prefix = f'{cls.__name__}('
    suffix = ')' if prefix else ''
    if id(value) in active:
        writer.write(f'{prefix}{open_char}...{close_char}{suffix}')
        return
    active.add(id(value))
    writer.write(prefix + open_char)
    for index, item in enumerate(value.items() if base is dict else value):
        if index:
            writer.write(', ')
        if base is dict:
            _preview_emit(item[0], writer, active)
            writer.write(': ')
            _preview_emit(item[1], writer, active)
        else:
            _preview_emit(item, writer, active)
    if base is tuple and len(value) == 1:
        writer.write(',')
    writer.write(close_char + suffix)
    active.discard(id(value))


def _preview_str(text, width):
    '''repr() of just the first `width` characters of text, using the quote style repr()
    would choose for the WHOLE string (repr() picks double quotes only when the string
    contains ' but no "). The appended sentinel quote forces the slice's repr() into the
    same style; it lands beyond `width`, so it is always cut off again by the caller.'''
    if len(text) <= width:
        return repr(text)
    sentinel = "'" if ("'" in text and '"' not in text) else '"'
    return repr(text[:width] + sentinel)


def _preview_safe_repr(value):
    '''repr() that never raises - e.g. ints beyond sys.get_int_max_str_digits() raise
    ValueError from repr() in Python 3.12.'''
    try:
        return repr(value)
    except Exception:
        return f'<{type(value).__name__}: preview unavailable>'


def _variable_snapshot_core(namespace, exclude_globals=True):
    '''Pure, namespace-explicit counterpart to help_vars()'s variable-listing
    filter (ted_toolkit.py) - takes an explicit dict instead of eval()-ing
    against globals(), so it is safe to call from any module/process given a
    copy of (or direct reference to) a session's namespace. Used by the GUI
    bridge (tedtoolkit/gui_bridge.py) to build the live Variables panel.

    Mirrors help_vars()'s type allowlist and _-prefix/ALL-CAPS exclusion
    rules exactly, so the GUI panel matches what help_vars() would show.
    Returns a list of {'name', 'type', 'preview'} dicts.'''
    allowed_types = (int, float, bool, str, list, set, dict, datetime.datetime)
    result = []
    for name, value in namespace.items():
        if name[0] == '_':
            continue
        if not isinstance(value, allowed_types):
            continue
        if exclude_globals and name.isupper():
            continue
        result.append({'name': name, 'type': type(value).__name__, 'preview': _preview_repr(value)})
    return result


def dynamic_import(**kwargs):
    '''import a Python module from an aribitrary file in Python
    kwargs:
    - file_path (will prompt if not given)
    Usage:
        mod = dynamic_import(file_path='c:/temp/pythonfile.py') #prompts for path if not given
    Above usage functionally equivalent to:
        import pythonfile as mod
    (except that the pythonfile can be anywhere and not necessarily in the toolkit folder / path)
    '''
    global DYNAMIC_IMPORTS
    ass_var = _check_assignment(function_name='dynamic_import')
    file_path = kwargs.get('file_path', '')
    if not file_path or not os.path.isfile(file_path):
        file_path = g_sel_file(title='Select the Python module to dynamically load.',
                               filetypes=[('Python Module', ('*.py', '*.pyw'))])
    if 'file_path' not in kwargs:
        _add_kwarg_to_last_command('file_path', _quoted(file_path), fn_name='dynamic_import')
    file_name = os.path.split(file_path)[1]
    module_name = f'{file_name[:file_name.rfind(".")]}'
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as exc:
        g_conditional_stop(f'Error encountered loading the module at {file_path}: \n\n{str(exc)}',
                           title='dynamic_import(): Module Load Error',
                           consequences='Your module code will not be returned.\n'+
                                        'Any steps based on this module will fail.')
        return None
    print(f'Code imported from {file_path}.')
    print(f'Access via dot notation e.g. {ass_var}.my_function()\n')
    DYNAMIC_IMPORTS[f'{module_name} [{get_local_timestamp()}]'] = [ass_var, file_path, mod.__doc__]
    return mod
dynamic_import.desc = 'Dynamically load a Python module'


def _get_function_declaration(fn_name, namespace):
    '''return function declaration string given a function name, looked up in namespace (a dict, e.g. globals())'''
    try:
        source = inspect.getsource(namespace[fn_name])
    except OSError as exc:
        if str(exc) == 'could not get source code':
            source = f'def {fn_name}(...?...):'
        else:
            raise exc
    if not source:
        return ''
    return source.split('\n', maxsplit=1)[0].strip()


def _get_module_functions(module):
    '''return list of lists with functions found in a loaded module:
    [[Function definition, First line of function docstring]]'''
    ret_table = [['Function', 'Description']]
    function_names = [key for key in dir(module)
                      if key[0] != '_' and inspect.isfunction(getattr(module, key))]
    for name in function_names:
        fn = getattr(module, name)
        try:
            definition = inspect.getsource(fn).strip()
            if definition[:4] == 'def ':
                definition = definition[4:]
            definition = definition[:definition.find(':')]
        except OSError:
            definition = f'module.{name}(...?...)'
        try:
            desc = fn.__doc__
            if desc and '\n' in desc:
                desc = desc[:desc.find('\n')]
        except AttributeError:
            desc = '-no description available-'
        ret_table.append([definition, desc or '-no description available-'])
    return ret_table
