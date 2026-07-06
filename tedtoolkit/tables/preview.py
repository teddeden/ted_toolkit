'''tedtoolkit.tables.preview - variable/table preview and single-column
uniqueness analysis, plus the string-parsing helpers _guess_var() uses to
infer which variable the user means to preview.
'''

import collections
import re
import sys

from tedtoolkit.history import _get_last_command, _get_previous_command
from tedtoolkit.tables.columns import excel_column


def _isolated(string_in, search_string, loc):
    '''return True if search_string found at location loc is a complete var_name in context
    DOES NOT WORK WITH TRIPLE-QUOTED TEXT BLOCKS OR RAW STRINGS
    used by _all_pos()'''
    code = []
    strings = []
    status = 'CODE'
    cur_str_delim = None
    def flip_status():
        '''flip the status'''
        nonlocal status
        status = {'CODE':'STRINGS', 'STRINGS':'CODE'}[status]
    for index, item in enumerate(string_in):
        if status == 'CODE':
            if item in ['\'', '"']:
                flip_status()
                cur_str_delim = item
            code.append(index)
            continue
        else: #status == 'STRINGS'
            if item == cur_str_delim and string_in[index - 1] != '\\':
                code.append(index)
                flip_status()
                cur_str_delim = None
            else:
                strings.append(index)
    if loc in strings:
        return False
    if loc + len(search_string) < len(string_in):
        next_char = string_in[loc + len(search_string)]
        if next_char.lower() in "abcdefghijklmnopqrstuvwxyz_":
            return False
    if loc > 0:
        prev_char = string_in[loc-1]
        if prev_char.lower() in "abcdefghijklmnopqrstuvwxyz_":
            return False
    return True


def _all_pos(string_in, search_string):
    '''returns a list of all the starting positions of search_string in string_in
    only if string_in can be a full variable name in context of an expression
    used by _guess_var()'''
    return [pos.start() for pos in re.finditer(search_string, string_in) \
            if _isolated(string_in, search_string, pos.start())]


def _guess_var(calling_function):
    '''returns the best guess of what variable the user would like to execute the function on
    used by e.g. data_preview()'''
    last = _get_previous_command()
    curr = _get_last_command()
    ass_pos = last.find('=')
    col_pos = last.find(':')
    app_pos = last.find('.append(')
    in_pos = last.find(' in ') + 1
    brkt_pos = last.find('[')
    print('ass {}, col {}, app {}, in {}, brkt {}'.format(ass_pos, col_pos, app_pos,
                                                          in_pos, brkt_pos))
    ass_var = None

    if last[:4] == 'for ' and (ass_pos > 0 or app_pos > 0) and col_pos > 0 and in_pos > 5:
        '''(I) for item in my_list: item = []; (I)for item in my_list[1:]: item += 1;
        (I)for line in my_table[1:]: line.append(my_function(line));
        (I)for index, line in enumerate(abc): line.append(index)
        (II)for a in range(10): some_other_var_we_want_to_preview += a;
        (II)for index, item in enumerate(uninteresting_var):
                some_other_var_we_want_to_preview[index] += item'''
        loop_var_name = last.split(' ')[1 if 'enumerate' not in last else 2].strip()
        print('Loop var name: ', loop_var_name)
        loop_var_name_positions = _all_pos(last, loop_var_name)
        loop_var_sec_pos = -1 if len(loop_var_name_positions) == 1 else loop_var_name_positions[1]
        print('Loop Var Second Position: ', loop_var_sec_pos)
        if (loop_var_sec_pos > ass_pos and ass_pos != -1) or \
           (loop_var_sec_pos > app_pos and app_pos != -1):
            '''(II)'''
            print('Case II')
            ass_var = last[col_pos+1:app_pos+ass_pos+1].strip('/%*+- ')
            print('Assignment var = ', ass_var)
        else:
            '''(I)'''
            print('Case I')
            ass_var = last[in_pos+2:col_pos].strip()
            print('Assvar = ', ass_var)
        if ass_var.find('[') != -1:
            ass_var = ass_var[:ass_var.find('[')]
        if ass_var.find('enumerate(') != -1:
            ass_var = ass_var.replace('enumerate(', '').replace(')', '')
        if ass_var.find('range(len(') != -1:
            ass_var = ass_var.replace('range(len(', '').replace('))', '')

    print('Assignment var = ', ass_var)

    if last[:4] != 'for ' and ass_pos > 0 and app_pos == -1:
        '''abc = defg'''
        ass_var = last[:ass_pos].strip('%*/+- ')

    if last[:4] != 'for ' and ass_pos == -1 and app_pos > 0:
        '''a.append('cow')'''
        ass_var = last[:app_pos].strip()

    # Look up ass_var in the *interactive session's* globals, not this
    # module's own globals - _guess_var() only makes sense relative to
    # whatever namespace the user is actually typing commands into.
    caller_globals = sys._getframe(2).f_globals
    if ass_var != None and len(ass_var) and ass_var in caller_globals:
        return ass_var
    print('Ambiguous variable {}; {} canceled'.format(
        ass_var, calling_function))
    return None


def data_preview(data_in=None, **kwargs):
    '''Preview some data
       - if you run without specifying data_in, it attempts to guess the variable based on the previous command
       - In case of table (Lists of lists) data with a header line at the top, prints:
                column index     |   Excel column name e.g. "D"  |  Field/Column Name  |  Value of first field record
       - kwargs for internal use from other toolkit functions
    Typical use cases:
    - I just used data_import() to get some data in, and now I want to see what is there
    - I forgot what form my data is in, and I want to check
    - I just made some changes to the data, added a column, etc, and I want to see what it looks like
    '''
    internal = kwargs.get('internal', False)
    if internal:
        var_name = kwargs.get('var_name', None)
        if var_name:
            print(f'\nPreviewing ****  {var_name}  ****\n')
    else:
        if data_in == None:
            ass_var = _guess_var('data_preview')
            if ass_var == None:
                return
            else:
                data_in = sys._getframe(1).f_globals.get(ass_var)
        else:
            cmd = _get_last_command()
            ass_var = cmd[cmd.find('(')+1:cmd.find(')')]
        try:
            print(f'\nPreviewing ****  {ass_var}  ****\n')
        except UnboundLocalError:
            print('\nPreviewing ****  (ERROR GETTING VARIABLE NAME)  ****\n')
    if isinstance(data_in, list):
        if data_in:
            if isinstance(data_in[0], list):
                print('Data type is list of lists / 2-d data table\n')
                print('Line count (incl. header if present): {}, Columns: {}\n'.format(
                    str(len(data_in)), str(len(data_in[0]))))
                print('col. index (excel col), first row value, second row value\n')
                for index, line in enumerate(data_in[0]):
                    try:
                        print(index, f'({excel_column(index)})', line, str(data_in[1][index])[:50])
                    except IndexError:
                        print('<no data>\n')
                print('\n')
            else:
                print('Data type is list / 1-d data row\n')
                print('Item count: {}\n'.format(str(len(data_in))))
                print(_prev_s(data_in))
            return
        else:
            print('Variable contains empty list\n')
            return
    if isinstance(data_in, dict) or isinstance(data_in, collections.OrderedDict):
        print('Data is type **dict** with {} keys.\n\nkey - preview'.format(str(len(data_in))))
        for key in list(data_in)[:20]:
            item = data_in[key]
            print(key, ' - ', _prev_s(item))
        if len(data_in) > 20:
            print('...')
    elif isinstance(data_in, int):
        print('Data is type: int with value: {}'.format(str(data_in)))
    elif isinstance(data_in, float):
        print('Data is type: float with value: {}'.format(str(data_in)))
    elif isinstance(data_in, bool):
        print('Data is type: bool with value: {}'.format(str(data_in)))
    elif isinstance(data_in, str):
        print('String data: {}'.format(str(data_in[:64])))
data_preview.desc = 'Displays info on Python variable'


def _prev_s(item):
    '''internal function to preview single data point'''
    if isinstance(item, str):
        if len(item) < 60:
            return 'String: "{}"'.format(item)
        else:
            return 'String: "{}...'.format(item[:58])
    elif isinstance(item, int) or isinstance(item, float) or isinstance(item, bool):
        return str(item)
    elif isinstance(item, list):
        return 'List: ' + ', '.join([str(element) for element in item])[:60]
    elif isinstance(item, dict):
        return 'Dict: ' + ', '.join([str(element) for element in item])[:60]
    else:
        return 'Other type: ', str(type(item))


def single_col_analysis(input_list, **kwargs):
    '''Identify unique and non-unique elements in a given input list
    TYPICAL USAGE EXAMPLE:
    >>> mylist = [1,1,2,3,'four', 'four', 'five']
    >>> u, n = single_col_analysis(mylist)
    SINGLE COL ANALYSIS: Starting
    >>> print(u)
    [2, 3, 'five']
    >>> print(n)
    [1, 'four']
    '''
    if not kwargs.get('suppress_start_notify', False):
        print('SINGLE COL ANALYSIS: Starting')
    unique = []
    non_unique = []
    freq_dict = {key:0 for key in input_list}
    for key in input_list:
        freq_dict[key] += 1
    for key in freq_dict:
        if freq_dict[key] > 1:
            non_unique.append(key)
        else:
            unique.append(key)
    return unique, non_unique
single_col_analysis.desc = 'returns unique, non-unique elements'
