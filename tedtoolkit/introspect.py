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
        result.append({'name': name, 'type': type(value).__name__, 'preview': repr(value)[:40]})
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
