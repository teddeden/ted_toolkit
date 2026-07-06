'''tedtoolkit.history - readline-history-rewrite primitives.

Bottom of the package's dependency graph: no imports from any other
tedtoolkit submodule. Everything here operates on the process-wide
readline (pyreadline3, on Windows) history buffer.
'''

import readline
import traceback

old_input = input
def input(prompt):
    '''input from user without capturing to history'''
    user_input = old_input(prompt)
    if user_input:
        _remove_last_history_item()
    return user_input
input.desc = 'Capture keyboard input (no history)'


def _quoted(text_in):
    '''return string with quotes around it'''
    text_in = str(text_in)
    return '"'+text_in+'"' if '\'' in text_in else '\''+text_in+'\''


def _get_last_command():
    '''Return a text string that was last typed into the interpreter'''
    return readline.get_history_item(0)


def _remove_last_history_item():
    '''as it says'''
    full_history = [readline.get_history_item(index+1)
                        for index in range(readline.get_current_history_length())]
    readline.clear_history()
    for line in full_history[:-1]:
        readline.add_history(line)


def _replace_last_command(line_to_add):
    '''Gets last line and replaces with, e.g. the same thing but with a keyword argument added'''
    _remove_last_history_item()
    readline.add_history(line_to_add)


def _replace_arbitrary_history_item(index, replacement_line):
    '''Replaces some arbitrary line at index with replacement line'''
    full_history = [readline.get_history_item(index+1)
                        for index in range(readline.get_current_history_length())]
    readline.clear_history()
    new_history = [line if cur_index != index else replacement_line
                       for cur_index, line in enumerate(full_history)]
    for line in new_history:
        readline.add_history(line)


def _get_previous_command():
    '''get second to last command'''
    return readline.get_history_item(readline.get_current_history_length()-1)


def _add_kwarg_to_last_command(keyword, value, fn_name=''):
    '''exactly as it sounds'''
    if not fn_name:
        fn_name = traceback.extract_stack()[-2].name
    line_index = readline.get_current_history_length() + 1
    current = ''
    while line_index > 0 and (fn_name + '(') not in current:
        line_index -= 1
        current = readline.get_history_item(line_index)
    lpos, rpos = current.find('('), current.rfind(')')
    args_text = current[lpos+1:rpos]
    args = [item.strip().split('=') for item in args_text.split(',')]
    kwargs = {item[0].strip():'' for item in args if len(item) == 2}
    if keyword in kwargs:
        print('WARNING: Tried to add a keyword argument that already exists: command unchanged\n')
        return
    if lpos + 1 == rpos:
        _replace_arbitrary_history_item(line_index - 1,
            current[:rpos] + str(keyword) + '=' + str(value) + current[rpos:])
        return
    _replace_arbitrary_history_item(line_index - 1,
        current[:rpos]+', '+str(keyword) + '=' + str(value) + current[rpos:])


def _remove_keyword_argument_from_last_command(keyword):
    '''takes out keyword in command line history from the previos commans;
    keyword must be in form keyword=value or keyword = value.
    Does nothing if it cannot locate the keyword'''
    current = _get_last_command()
    if keyword + '=' in current:
        lpos = current.find(keyword+'=')
    elif keyword + ' =' in current:
        lpos = current.find(keyword+' =')
    else:
        print(f'WARNING: Tried to remove keyword <{keyword}> from last commany but it was not found.')
        print('          Keyword must be in the form keyword=value or keyword = value')
        return
    rpos = lpos + min([x for x in [current[lpos:].find(',')+1, current[lpos:].find(')')] if x > 0])
    new_command = (current[:lpos]+current[rpos:]).replace(',)', ')').replace(', )', ')').replace(',  )', ')').replace(',   )', ')')
    _replace_last_command(new_command)
    return


def _check_assignment(function_name=''):
    '''internal function to ensure that there is a variable to catch the data being produced
       if a function_name is given, this will raise an exception if called from the interpreter
       directly without an assignment variable, but not if called within a script'''
    command = _get_last_command()
    if function_name:
        if command.find(function_name) == -1:
            return '' #to allow <<if function_name: __>> logic later
    eq_pos = command.find('=')
    par_pos = command.find('(', eq_pos + 1)
    if eq_pos == -1 or par_pos == -1:
        raise Exception('\n\nYou must assign the function output to a variable. Canceling.\n')
    return command[:eq_pos].strip()
