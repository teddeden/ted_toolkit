'''tedtoolkit.prompts - console prompt primitives and the kwarg-resolve-or-prompt
wrappers that guided functions build on. Depends only on tedtoolkit.history
(for the history-safe `input` override and the kwarg-baking primitives) and
tedtoolkit.validation (for table checks).
'''

import traceback
from collections import OrderedDict
import csv

from tedtoolkit.history import input, _quoted, _add_kwarg_to_last_command, _remove_keyword_argument_from_last_command
from tedtoolkit.validation import _check_var_table

# Single source of truth for CSV quoting-mode choices; previously duplicated
# as ad hoc OrderedDict literals (without importing OrderedDict) in three
# separate places in load_save.py.
QUOTING_OPTIONS = OrderedDict([
    ('QUOTE_ALL', csv.QUOTE_ALL),
    ('QUOTE_MINIMAL', csv.QUOTE_MINIMAL),
    ('QUOTE_NONNUMERIC', csv.QUOTE_NONNUMERIC),
    ('QUOTE_NONE', csv.QUOTE_NONE),
])


def ask_yn(default='no', prompt=''):
    '''prompt for a yes/no answer; hit enter to use the default value'''
    default_yes = default.lower() in ('y', 'yes')
    a_in = input(prompt + (' (Y/n): ' if default_yes else ' (y/N): '))
    if a_in[:3].lower() in ('y', 'yes') or (len(a_in) == 0 and default_yes):
        return True
    return False
ask_yn.desc = 'user prompt: yes/no'


def ask_num(**kwargs):
    '''Get a number from the user; if a default is used/selected, (-) and *.* checks raise exceptions
    possible keyword arguments:
    allow_negative (default True)
    allow_decimal (default True)
    prompt (text string to prompt user)
    allow_default (default False)
    default (ignored if allow_default is False'''
    allow_negative = kwargs.get('allow_negative', True)
    allow_decimal = kwargs.get('allow_decimal', True)
    allow_default = kwargs.get('allow_default', False)
    default = kwargs.get('default', 0 if allow_default else None)
    prompt = kwargs.get('prompt', '#: ' if ((not allow_default) or default is None) else f'(default {default}) #: ')
    if default is None:
        allow_default = False
    if isinstance(default, float):
        if int(default) != default and not allow_decimal:
            raise TypeError(f'ask_num(): default value given as {str(default)} but allow_decimal is False. Canceling.')
    if allow_default:
        if default < 0 and not allow_negative:
            raise ValueError(f'ask_num(): default value given as {str(default)} but allow_negative is False. Canceling.')
    while True:
        abc = input(prompt)
        if allow_default and not abc:
            return default
        try:
            abc = float(abc)
        except ValueError:
            print('Invalid input. You must enter a number.')
            continue
        if abc < 0 and not allow_negative:
            print('Invalid input. You must enter a positive number.')
            continue
        if not allow_decimal:
            if abc - int(abc) != 0:
                print('Invalid input. You must enter an integer (decimal values not allowed).')
                continue
            return int(abc)
        break
    return abc
ask_num.desc = 'user prompt: number'


def ask_select(var_in, prompt='Select an index from the following:', print_keys=True,
               orig_out=False, default_val=None):
    '''prompt for selecting something from a list or dict of things
    print_keys applicable for a dict of items; if set False will only display values.
    orig_out applicable is a list of items; if set True will return the actual thing selected rather than the index
    default_val, if set, must be a key in the dict or a value in the list
       N.B.: if your dict has a key == None then default_val cannot be set to this (interpreted as no default_val)
       N.B.: if your list has multiple values matching the default_val, then the first will be interpreted as default
             (this is immaterial if orig_out is True but may be problematic if you want to select a particular index -
             in the latter case, use unambiguous values in order to properly differentiate)'''
    print(prompt, '\n')
    line = '{:<5}{:35}'
    temp_dict = {}
    for index, element in enumerate(var_in):
        if isinstance(var_in, dict) and print_keys:
            to_print = '{} - {}'.format(element, var_in[element])
        else:
            if isinstance(var_in, dict):
                to_print = str(var_in[element])[:35]
            else:
                to_print = str(element)[:35]
        print(line.format(index, to_print))
        temp_dict[index] = element
    print('\n')
    if default_val is None:
        selection = ask_num(allow_decimal=False, allow_negative=False, prompt='#: ')
    else:
        temp = [index for index, item in enumerate(var_in) if item == default_val]
        if len(temp) == 1:
            default_index = temp[0]
        else:
            default_index = 0
            print('ask_select(): WARNING: default value passed to ask_select not found in var_in / setting first element as default.')
        selection = ask_num(allow_decimal=False, allow_negative=False, allow_default=True, default=default_index,
                            prompt=f'(enter for default value {default_index})#: ')
    if selection not in range(len(var_in)):
        return ask_select(var_in, prompt=prompt, print_keys=print_keys, orig_out=orig_out)
    if isinstance(var_in, dict):
        return temp_dict[selection]
    if orig_out:
        return var_in[selection]
    return selection
ask_select.desc = 'user prompt: list/dict select'


def ask_select_column_index(table_in, **kwargs):
    '''gets a list of lists as table_in, displays preview and asks for a column selection'''
    _check_var_table(table_in, 'table_in/ask_select_column_index')
    prompt = kwargs.get('prompt', 'Select column index number >> ')
    show_sample_data = kwargs.get('show_sample_data', True) and len(table_in) > 1
    print('Columns in table:\n')
    for index, item in enumerate(table_in[0]):
        if show_sample_data and len(table_in[1]) > index:
            print(index, ' - ', item, '     ', table_in[1][index])
        else:
            print(index, ' - ', item)
    selection = -1
    while selection not in range(len(table_in[0])):
        selection = ask_num(prompt=prompt, allow_negative=False, allow_decimal=False)
    return selection
ask_select_column_index.desc = 'user prompt: column index'


def _prompt_for_any_arg(arg_name, default_val, numeric=False):
    '''Prompts for arg_name value to be default_val; if user
       does not want to use default_val, user can specify any
       value desired. If numeric is True, user is forced to enter
       a numeric value and this will be converted to a float.
       Otherwise, response will be interpreted as a text string'''
    prompt = 'The argument <{}> is set to <{}>. Is this ok?'
    if not ask_yn(default='y', prompt=prompt.format(arg_name,
        repr(default_val))):
        ok = False
        while not ok:
            pmt = 'Enter new value for <{}> >>> '
            user_in = input(pmt.format(arg_name))
            if numeric:
                try:
                    user_in = float(user_in)
                except ValueError:
                    print('Error: you must enter a number.')
                    continue
            else:
                user_in = eval(f'"{user_in}"')
            ok = True
        ret_val = user_in
    else:
        ret_val = default_val
    print(f'<{arg_name}> has been set to <{repr(ret_val)}>.')

    return ret_val


def _prompt_for_list_arg(arg_name, choices_list,
                         default_index=None):
    '''prompts for arg_name which must be a selection from
       the choices in choices_list.  If default_index is
       given, will first prompt user if this is ok.
       Otherwise (or if it is not ok), user will see choice
       selection and be given the option to choose.
       Function returns selected value (not index).'''
    if len(choices_list) == 0:
        raise Exception('You must pass a nonempty choices_list')
    if default_index is not None:
        if default_index >= len(choices_list):
            default_index = None
            print('Warning: default_index beyond choices range!')

    if default_index is not None:
        pmt = 'The argument <{}> is set to <{}>. Is this ok?'
        if ask_yn(default='y', prompt=pmt.format(arg_name,
            choices_list[default_index])):
            return choices_list[default_index]
    print('For <{}> you have the following choices:'.format(
        arg_name))
    for index, item in enumerate(choices_list):
        print('{}:\t{}'.format(index, item))
    ok = False
    while not ok:
        pmt = 'Select the index number of your choice for <{}>: '
        user_in = input(pmt.format(arg_name))
        try:
            ret_val = choices_list[int(user_in)]
        except ValueError:
            print('You must enter the number of your choice.')
            continue
        except IndexError:
            print('Your selection is out of range. Try again.')
            continue
        ok = True
    print('<{}> has been set to <{}>.'.format(arg_name, ret_val))
    return ret_val


def _prompt_for_bool_arg(arg_name, default_val=True):
    '''prompts for arg_name which must be boolean'''
    prompt = 'The argument <{}> is set to <{}>. Is this ok?'
    if not ask_yn(default='y', prompt=prompt.format(arg_name,
        default_val)):
        ret_val = not default_val
    else:
        ret_val = default_val
    print('<{}> has been set to <{}>.'.format(arg_name, ret_val))
    return ret_val


def _kwarg_parse_prompt_str(var_name, default_val='', **kwargs):
    '''check if variable passed as argument, set default, prompt to confirm, set as arg, return'''
    val = kwargs.get(var_name, default_val)
    prompt = kwargs.get('prompt', '{} is < {} >. OK?')
    min_len = kwargs.get('min_len', None)
    max_len = kwargs.get('max_len', None)
    if min_len is not None and max_len is not None and min_len > max_len:
        print('min and max lengths specified are invalid. Ignoring.')
        min_len = None
        max_len = None
    while var_name not in kwargs and not ask_yn(default='y', prompt=prompt.format(var_name, val)):
        while True:
            new_val = input('Type new {} to use: >>> '.format(var_name))
            val = new_val
            if min_len is not None and len(val) < min_len:
                print('Given string too short (min. is {})'.format(min_len))
                continue
            if max_len is not None and len(val) > max_len:
                print('Given string too long (max. is {})'.format(max_len))
                continue
            break
    if var_name not in kwargs:
        _add_kwarg_to_last_command(var_name, _quoted(val), fn_name=traceback.extract_stack()[-2].name)
    return val
_kwarg_parse_prompt_str.desc = '[INTERNAL FUNCTION]'


def _kwarg_parse_prompt_bool(var_name, default_val='True', **kwargs):
    '''check if variable passed as argument, set default, prompt to confirm, set as arg, return'''
    val = kwargs.get(var_name, str(default_val))
    prompt = kwargs.get('prompt', '{} is < {} >. OK?')
    while var_name not in kwargs and not ask_yn(default='y', prompt=prompt.format(var_name, val)):
        new_val = 'False' if val == 'True' else 'True'
        val = new_val
    if var_name not in kwargs:
        _add_kwarg_to_last_command(var_name, val, fn_name=traceback.extract_stack()[-2].name)
    return str(val) == 'True'
_kwarg_parse_prompt_bool.desc = '[INTERNAL FUNCTION]'


def _kwarg_parse_prompt_num(var_name, default_val=0, allow_decimal=True, allow_neg=True, **kwargs):
    '''check if variable passed as argument, set default, prompt to confirm, set as arg, return;
    use allow_negative=False to prevent a user from entering a negative value'''
    if var_name in kwargs:
        return kwargs[var_name]
    val = ask_num(allow_default=True, allow_decimal=allow_decimal, allow_negative=allow_neg,
                  default=default_val, prompt=kwargs.get('prompt', '#: '))
    if var_name not in kwargs:
        _add_kwarg_to_last_command(var_name, val, fn_name=traceback.extract_stack()[-2].name)
    return val
_kwarg_parse_prompt_num.desc = '[INTERNAL FUNCTION]'


def _kwarg_parse_prompt_list(var_name, choices_list, **kwargs):
    '''check if variable passed as argument, if so, check that value in choices list
                                             if not, or if not passed: prompt for it and adjust last command'''
    overwrite = False
    if var_name in kwargs:
        if kwargs[var_name] in choices_list:
            return kwargs[var_name]
        overwrite = True
    val = ask_select(choices_list, prompt=f'for <{var_name}> please choose an option:', orig_out=True)
    if overwrite:
        _remove_keyword_argument_from_last_command(var_name)
    if var_name not in kwargs:
        _add_kwarg_to_last_command(var_name, _quoted(val), fn_name=traceback.extract_stack()[-2].name)
    return val
_kwarg_parse_prompt_list.desc = '[INTERNAL FUNCTION]'
