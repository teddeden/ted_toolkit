# ted_toolkit.py: Swiss knife in python
'''
Required environment: see environment.yml (python=3.12; pyreadline3 depends on the classic
CPython REPL, which 3.12 uses by default - 3.13's new _pyrepl console bypasses the readline
hook this toolkit's history-rewrite mechanism depends on).

This file is intentionally a thin interactive-session launcher, not the toolkit itself - the
actual implementation lives in the tedtoolkit/ package (an installable, independently-testable
package). This file does three things: (1) imports everything from tedtoolkit so the interactive
session gets the same flat, bare-callable namespace the original single-file toolkit provided,
(2) defines FUNCTION_CATEGORIES plus help_all()/save_function_reference()/help_vars()/
_run_script()/continue_execution(), and (3) the __main__ entry point.

help_all(), save_function_reference(), help_vars(), and _run_script() are kept here rather than
in the tedtoolkit package ON PURPOSE: they inspect globals()/eval() names against the *interactive
session's own namespace*, which is only correct when they live in whatever module is actually
running as __main__. Moving them into a tedtoolkit submodule would make them introspect that
submodule's namespace instead of the user's session - do not "clean this up" by relocating them.
'''


import datetime
import inspect
import os
import readline
import subprocess
import sys
import traceback

from tedtoolkit.history import (input, _quoted, _get_last_command, _get_previous_command,
                                 _add_kwarg_to_last_command,
                                 _remove_keyword_argument_from_last_command, _check_assignment)
from tedtoolkit.validation import _is_list_of_lists, _check_var_table
from tedtoolkit.prompts import (ask_yn, ask_num, ask_select, ask_select_column_index,
                                 _prompt_for_any_arg, _prompt_for_list_arg, _prompt_for_bool_arg,
                                 _kwarg_parse_prompt_str, _kwarg_parse_prompt_bool,
                                 _kwarg_parse_prompt_num, _kwarg_parse_prompt_list)
from tedtoolkit.util import (elapsed, get_utc_timestamp, get_local_timestamp, get_current_user,
                              _find_notepad_pp, beep, set_window_title)
from tedtoolkit.clipboard import win_copy, win_paste, win_paste_table, win_copy_table
from tedtoolkit.introspect import (dynamic_import, _get_function_declaration, _get_module_functions,
                                    DYNAMIC_IMPORTS)
from tedtoolkit.gui.dialogs import g_sel_file, g_sel_file_to_write, g_sel_folder
from tedtoolkit.io.txt import read_txt
from tedtoolkit.tables.columns import extract_column_from_table, sel_col, _decimate, excel_column
from tedtoolkit.tables.join import data_join
from tedtoolkit.tables.preview import data_preview, single_col_analysis, _guess_var, _prev_s
from tedtoolkit.tables.reconcile import (key_analysis, data_recon, reconcile, in_tolerance,
                                          _square_tables, _add_key_info_to_stats)
from tedtoolkit.tables.aggregate import data_aggregate, data_de_aggregate
from tedtoolkit.tables.compare import (try_compare_columns, compare_columns,
                                        pre_process_specs_detail, _try_convert_date, _detect_blank)
from tedtoolkit.io.xlsx import xlsx_export, xlsx_import, ask_select_sheet, ALL_SHEETS_TEXT
from tedtoolkit.io.csv import csv_export, csv_import
from tedtoolkit.io.dispatch import data_import, data_export
from tedtoolkit.gui.messagebox import (g_ask_yn, g_ask_okcancel, g_conditional_stop,
                                        g_show_info, g_show_warning, g_show_error)

VERSION = "0.72"

FUNCTION_CATEGORIES = {
    'ask_num': 'User Input (text)',
    'ask_select': 'User Input (text)',
    'ask_yn': 'User Input (text)',
    'g_sel_file': 'User Input (GUI)',
    'g_sel_file_to_write': 'User Input (GUI)',
    'g_sel_folder': 'User Input (GUI)',
    'g_ask_yn': 'User Input (GUI)',
    'g_ask_okcancel': 'User Input (GUI)',
    'g_conditional_stop': 'User Input (GUI)',
    'g_show_info': 'User Input (GUI)',
    'g_show_warning': 'User Input (GUI)',
    'g_show_error': 'User Input (GUI)',
    'xlsx_export': 'Input / Output',
    'xlsx_import': 'Input / Output',
    'csv_export': 'Input / Output',
    'csv_import': 'Input / Output',
    'data_export': 'Input / Output',
    'data_import': 'Input / Output',
    'ask_select_sheet': 'User Input (text)',
    'input': 'User Input (text)',
    'elapsed': 'Utilities & Settings',
    'win_copy': 'Input / Output',
    'win_paste': 'Input / Output',
    'win_paste_table': 'Input / Output',
    'win_copy_table': 'Input / Output',
    'get_utc_timestamp': 'Utilities & Settings',
    'get_local_timestamp': 'Utilities & Settings',
    'ask_select_column_index': 'User Input (text)',
    'data_aggregate': 'Data Analysis & Manipulation',
    'data_de_aggregate': 'Data Analysis & Manipulation',
    'extract_column_from_table': '',
    'sel_col': 'User Input (text)',
    'data_join': 'Data Analysis & Manipulation',
    'excel_column': 'Utilities & Settings',
    'data_preview': 'Data Analysis & Manipulation',
    'single_col_analysis': 'Data Analysis & Manipulation',
    'key_analysis': 'Data Analysis & Manipulation',
    'data_recon': 'Data Analysis & Manipulation',
    'in_tolerance': 'Data Analysis & Manipulation',
    'reconcile': 'Data Analysis & Manipulation',
    'try_compare_columns': 'Data Analysis & Manipulation',
    'compare_columns': 'Data Analysis & Manipulation',
    'pre_process_specs_detail': 'Data Analysis & Manipulation',
    'get_current_user': 'Utilities & Settings',
    'save_history': 'Utilities & Settings',
    'beep': 'Utilities & Settings',
    'read_txt': 'Input / Output',
    'dynamic_import': 'Utilities & Settings',
    'help_all': 'Help / Reference',
    'save_function_reference': 'Help / Reference',
    'help_vars': 'Help / Reference',
    'set_window_title': 'Utilities & Settings',
    'continue_execution': 'Utilities & Settings'
    }

#start_history_size = readline.get_current_history_length()
readline.add_history('#SCRIPT START')

def save_history():
    '''Saves command history to a text file to enable easy later scripting of session
    INTENDED USAGE:
    1) Interactive session to explore data inputs and perform needed operations and output
    2) Use save_history() to export a toolkit-based .py file that can be re-run
         (optionally open directly in Notepad for editing after initial export)
    3) Edit the .py file as needed, removing erroneously-added steps or extra data_preview()s etc
    4) Test and deploy the edited file.
    N.B. Obviously these *.py files are not intended to be executed independently of the toolkit.
    '''
    history = [readline.get_history_item(index)+'\n'
               for index in range(1, readline.get_current_history_length() + 1)]

    filepath = g_sel_file_to_write(title='TED TOOLKIT: Select file to save session as script',
                                   filetypes=[('Python files', ('*.py')), ('All Files', ('*.*'))])
    if filepath[-3:] != '.py':
        filepath = filepath + '.py'
    template = '# TED_TOOLKIT-based (v{}) Python script, autogen by {} at UTC:{}\n\n'
    template = template.format(VERSION, get_current_user(), get_utc_timestamp())
    with open(filepath, 'w', encoding='utf-8') as fil:
        fil.writelines([template]+history+['\n\n'])
    print('History saved to: \n{}'.format(filepath))
    open_in_notepad = ask_yn(default='y', prompt='Do you want to open in Notepad?')
    if open_in_notepad:
        nppp_path = _find_notepad_pp()
        if nppp_path:
            subprocess.Popen([nppp_path, filepath])
        else:
            subprocess.Popen(['notepad.exe', filepath])
save_history.desc = 'Save interactive session to edit/re-run'

def help_all():
    '''print info for all public functions available in toolkit'''
    global DYNAMIC_IMPORTS
    main_space = 50
    temp = globals()
    master_list = [key for key in temp if inspect.isfunction(eval(key)) and key[0] != '_']
    fns = [_get_function_declaration(item, temp) for item in master_list]
    fns = [item for item in fns if item[:3] == 'def']
    fns = [item[4:].strip() for item in fns]
    fns.sort()
    names = [func[:func.find('(')] for func in fns]
    lookup_dec = dict(zip(names, fns))
    lookup_cat = FUNCTION_CATEGORIES
    cats = sorted(list(set(lookup_cat.values())))
    print('\n'+'*'*80+'\n\nTED_TOOLKIT available functions: \n (use "help(fn_name)" for more)\n')
    for cat in cats+['**no category**']:
        print(f'\n{cat}\n')
        for func_name in names:
            if lookup_cat.get(func_name, '**no category**') != cat:
                continue
            func = lookup_dec.get(func_name, '???')
            divider = '...' if len(func)>main_space else '   '
            desc = getattr(eval(func_name), 'desc', '--no short description--')
            print(f'{func[:-1][:main_space]:<50}{divider} {desc:<20}')
    print('\n'+'*'*80+'\n')
    if DYNAMIC_IMPORTS:
        print('\nThe followig modules have been imported dynamically:\n')
        print(f'{"Module name":<20} {"Initial Variable Name":<23} {"File Path":<30}')
        for mod_name in DYNAMIC_IMPORTS:
            mod_name_short = mod_name[:mod_name.find('[')].strip()
            print(f' {mod_name_short[:19]:<19} {DYNAMIC_IMPORTS[mod_name][0][:23]:<23} {DYNAMIC_IMPORTS[mod_name][1][:30]:<30}')
        print('')
        print(f'{"Variable name <Module name>":<27}   {"Function Definition":<27}   {"Function Description":<50}')
        for mod_name in DYNAMIC_IMPORTS:
            mod_name_short = mod_name[:mod_name.find('[')].strip()
            var_name = DYNAMIC_IMPORTS[mod_name][0]
            try:
                fn_details = _get_module_functions(eval(var_name))[1:]
            except NameError: #In case the module has been deleted.
                continue
            mod_name_and_var = f'{var_name} <{mod_name_short}>'
            for [func, desc] in fn_details:
                print(f' {mod_name_and_var[:26]:<26}{"   " if len(mod_name_and_var) < 27 else ".. "}{func[:27]:<27}{"   " if len(func) < 27 else ".. "}{desc[:50]:<50}')
        print('')
    print('To save an excel reference sheet, use save_function_reference()')
help_all.desc = 'Displays this function overview'

def save_function_reference(**kwargs):
    '''Saves an excel file containing a reference sheet of toolkit functions
                            **Generated dynamically**
    '''
    temp = globals()
    master_list = [key for key in temp if inspect.isfunction(eval(key)) and key[0] != '_']
    fns = [_get_function_declaration(item, temp) for item in master_list]
    fns = [item for item in fns if item[:3] == 'def']
    fns = [item[4:].strip() for item in fns]
    fns.sort()
    def get_name(func):
        return func[:func.find('(')]
    lookup_cat = FUNCTION_CATEGORIES
    table = [[lookup_cat.get(get_name(func), '**no category**'),
              get_name(func),
              getattr(eval(get_name(func)), 'desc', '--no short description--'),
              func,
              eval(f"{get_name(func)}.__doc__")]\
             for func in fns]
    table.sort(key=lambda line: line[0])
    table.insert(0, ['Category', 'Name', 'Short Description', 'Definition', 'Long Description'])
    xlsx_export({f'Toolkit Functions {VERSION}':table}, wb_filter=True, view_in_excel=True)
save_function_reference.desc = 'Export Toolkit Function Reference'

def help_vars(exclude_globals=True):
    '''Shows the current variables that have been defines in the Python encieonment
    Includes int, float, bool, str, list, set, dict, datetime.datetime
    if exclude_globals is True, the function skips the listing of variables in ALL CAPS'''
    var_list = [key for key in list(globals()) if isinstance(eval(key), (int, float, bool, str, list, set, dict, datetime.datetime)) and key[0] != '_']
    print('\nhelp_vars(): Showing the currently defined variables of common type\n')
    if exclude_globals:
        print('             (EXcluding GLOBAL_VARIABLES)\n')
    else:
        print('             (INcluding GLOBAL_VARIABLES)\n')
    print(f'  {"Variable name":<23}   {"Type":<18} {"Value Preview":>40}\n')
    for item in var_list:
        if item.isupper() and exclude_globals:
            continue
        spacer = "   " if len(item) < 24 else "..."
        item_type = eval(item).__class__.__name__
        preview = str(repr(eval(item)))
        print(f'  {item[:23]:<23}{spacer}{item_type[:18]:<18} {preview[:40]:<40}')
    if DYNAMIC_IMPORTS:
        for mod_name in DYNAMIC_IMPORTS:
            var_name = DYNAMIC_IMPORTS[mod_name][0]
            try:
                mod_vars = [item for item in dir(eval(var_name)) if isinstance(eval(f"{var_name}.{item}"), (int, float, bool, str, list, set, dict, datetime.datetime)) and item[0] != '_']
            except Exception:
                continue
            for item in mod_vars:
                if item.isupper() and exclude_globals:
                    continue
                handle = f"{var_name}.{item}"
                ref = eval(handle)
                spacer = "   " if len(handle) < 24 else "..."
                item_type = ref.__class__.__name__
                preview = str(repr(ref))
                print(f'  {handle[:23]:<23}{spacer}{item_type[:18]:<18} {preview[:40]:<40}')
    print('\n')
help_vars.desc = 'Show all current variables of common types'

LAST_LINE_ATTEMPTED = -1

def _run_script(args_list, **kwargs):
    '''takes saved history and re-runs it'''
    global LAST_LINE_ATTEMPTED
    cntd = kwargs.get('continued', False)
    if cntd:
        print(f'Continuing execution of Python (tookit) script from last line {LAST_LINE_ATTEMPTED + 1}\n\nTo cancel, press Ctrl+c.\n')
    else:
        _ = os.system('cls')
        print('\nExecuting recorded history from prior Python session\n\n'+\
              'To cancel, press Ctrl+c.\n')
    py_file = args_list[0]
    print('File: ', py_file, '\n')
    if not cntd:
        #os.system(f'title {get_utc_timestamp()}: {py_file}')
        set_window_title(py_file, 'LOCAL')
    py_content = read_txt(file_path=py_file)
    problems = [str(index) for index, line in enumerate(py_content) if len(line) and line[0] == ' ']
    if problems:
        print(f'Problem with code at lines {", ".join(problems)}: contains multi-line statements; cannot execute. Aborting.\n')
        print(f'File ({py_file}) could not be processed.')
    else:
        view_comments = _kwarg_parse_prompt_bool('view_comments', default_val='False', **kwargs)
        for ind, line in enumerate(py_content[LAST_LINE_ATTEMPTED+1:], start=LAST_LINE_ATTEMPTED+1):
            LAST_LINE_ATTEMPTED = ind
            if not line or line == '\r\n':
                continue
            if line[0] == '#':
                if view_comments:
                    print('Comment >>> ' + line)
                    readline.add_history(line.strip())
                continue
            print('Replay >>> ' + line)
            readline.add_history(line.strip())
            if line.strip() == 'continue:execution()':
                print('***SKIPPING continue_execution() (ALREADY EXECUTING)***')
                continue
            try:
                exec(line, globals())
            except KeyboardInterrupt:
                print('Execution of pre-recorded script canceled by the user.')
                print('*************TRACEBACK**************')
                traceback.print_exception(*sys.exc_info())
                print('***********END TRACEBACK************')
                print('To continue later from this point, use continue_execution()')
                return
            except Exception as text:
                beep()
                print('Error encountered in line {}: \n{}\n'.format(str(ind+1), str(text)))
                print('*************TRACEBACK**************')
                traceback.print_exception(*sys.exc_info())
                print('***********END TRACEBACK************')
                if not ask_yn(prompt='Error encountered in script. Do you want to continue anyway?'):
                    print('To continue later from this point, use continue_execution()')
                    return
    print(f'\nExecution completed in {elapsed()}.')
    print('\nDone- You may continue session from this point or you may exit()\n')
    print('For function reference type "help_all()"')
    beep()

def continue_execution():
    '''Continue executing a pre-recorded script from the point it was was stopped
        (e.g. by exception or keyboard interrupt)'''
    global LAST_LINE_ATTEMPTED
    if LAST_LINE_ATTEMPTED == -1 or ARGS[0][-3:] != '.py' or not os.path.exists(ARGS[0]):
        raise Exception('ERROR: You must have a valid script that was previously running to continue its execution.')
    _run_script(sys.argv[1:], continued=True)
continue_execution.desc = 'Restart script execution post-error'

# Defined unconditionally (not just inside `if __name__ == '__main__':`) so continue_execution()
# can safely reference ARGS even if ted_toolkit.py is ever imported as a regular module instead
# of run as the entry script.
ARGS = sys.argv[1:]

if __name__ == '__main__':
    # for usage as a main module
    if ARGS:
        if ARGS[0][-3:] == '.py' and os.path.exists(ARGS[0]):
            pass
        else:
            print('Failed attempt to execute history: must be .py file!')
            print('History file attempted: '+ARGS[0])
            print('TED TOOLKIT Python tools reverting to interactive mode\n')
            print('For function reference type "help_all()"\n')
    else:
        _ = os.system('cls')
        print('TED TOOLKIT Python tools interactive mode.\n\nFor fn reference type help_all().\n')
        title = input(prompt='Title for this session: >>> ')
        print('\n')
        if title:
            #os.system(f'title {get_utc_timestamp()}: {title}')
            set_window_title(title, include_timestamp='LOCAL')
        else:
            #os.system(f'title {get_utc_timestamp()}: Ted Toolkit Interactive Mode')
            set_window_title('Ted Toolkit Interactive Mode', include_timestamp='LOCAL')
        print('Use set_window_title(title) to rename the window.\n')
        del title
    if ARGS:
        _run_script(ARGS, view_comments=True)
