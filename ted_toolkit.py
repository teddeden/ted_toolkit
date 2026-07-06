# ted_toolkit.py: Swiss knife in python
'''
Required environment may be create in Anaconda with conda create -p "P:/Documents/localpython" python=3.12 pip openssl sqlite vc click openpyxl pyreadline3 chardet pywin32 six xlrd

'''


VERSION = "0.69c"

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

from load_save import *

import codecs
import collections
import datetime
import importlib.util
import inspect
import os
import readline
import time
import traceback
import subprocess
import sys
import win32clipboard

FUNCTION_CATEGORIES = {
    'ask_num': 'User Input (text)',
    'ask_select': 'User Input (text)',
    'ask_yn': 'User Input (text)',
    'g_sel_file': 'User Input (GUI)',
    'g_sel_file_to_write': 'User Input (GUI)',
    'g_sel_folder': 'User Input (GUI)',
    'xlsx_export': 'Input / Output',
    'xlsx_import': 'Input / Output',
    'csv_export': 'Input / Output',
    'csv_import': 'Input / Output',
    'data_export': 'Input / Output',
    'data_import': 'Input / Output',
    'ask_select_sheet': 'User Input (text)',
    'data_import_plus': 'Input / Output',
    'data_export_plus': 'Input / Output',
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

def _review_options(options_in, table_in):
    '''takes in dict of options, prompts the user to modify according to type, or confirm'''
    CAT_PROMPT = 'Which column to use as category? \n(each value found will get own column) >> '
    for key in options_in:
        if key in ['cat_key_col']:
##            while options_in[key] not in range(len(table_in[0])) or\
##               ask_yn(default='n', prompt='Current cat key col. is <{}>. Change?'.format(\
##                   str(options_in[key]))):
##                options_in[key] = ask_select_column_index(table_in, prompt=CAT_PROMPT)
            continue
        if isinstance(options_in[key], bool):
            while ask_yn(default='n', prompt='Current value of {} is <{}>. Change it?'.format(\
                key, str(options_in[key]))):
                options_in[key] = not options_in[key]
            continue
        if isinstance(options_in[key], str):
            while ask_yn(default='n', prompt='Current value of {} is <{}>. Change it?'.format(\
                key, options_in[key])):
                options_in[key] = input('Type new string to use for <{}> >>'.format(key))
            continue
    return

def _add_values(ret_table, val_dict, title):
    '''Given a ret_table list of lists with header row in index 0 and key in col 0, add a column
    to the ret_table with values from val_dict and header label title'''
    ret_table[0].append(title)
    for line in ret_table[1:]:
        line.append(val_dict.get(line[0], ''))

def _bool_calc(array, operator, options):
    '''return a true, false or invalid result based on single-dimensional array input, operator
    and options'''
    transform = {True:True, False:False}
    if options['allow_yn']:
        transform['y'], transform['yes'], transform['n'], transform['no'] = \
                        True, True, False, False
        transform['Y'], transform['Yes'], transform['N'], transform['No'] = \
                        True, True, False, False
        transform['YES'], transform['NO'] = True, False
    if options['allow_01']:
        transform[0], transform['0'], transform[1], transform['1'] = False, False, True, True
    if options['allow_tf']:
        transform['t'], transform['true'], transform['f'], transform['false'] = \
                        True, True, False, False
        transform['T'], transform['True'], transform['F'], transform['False'] = \
                        True, True, False, False
        transform['TRUE'], transform['FALSE'] = True, False
    intermediate = []
    for item in array:
        if item in transform:
            intermediate.append(transform[item])
        elif len(str(item).strip()) == 0 and options['ignore_blanks']:
            continue
        else:
            return options['invalid_text']
    if len(intermediate) == 0:
        return ''
    temp = {'and':True, 'or':False}[operator]
    for item in intermediate:
        if item == True and operator == 'or':
            temp = True
        if item == False and operator == 'and':
            temp = False
    return temp

def _arithmetic_stats(array, operator, options):
    '''implements logic for sum, min, max, and average'''
    intermediate = []
    for item in array:
        if isinstance(item, float) or isinstance(item, int):
            intermediate.append(item)
            continue
        if isinstance(item, str):
            try:
                intermediate.append(float(item))
            except ValueError:
                if options['ignore_non_numbers'] or (len(item) == 0 and options['ignore_empty']):
                    continue
                else:
                    return options['non_numbers_text']
        if options['ignore_non_numbers']:
            continue
        else:
            return options['non_numbers_text']
    if len(intermediate) == 0:
        return options['empty_text']
    return {'sum':sum(intermediate), 'min':min(intermediate), 'max':max(intermediate), \
            'average':sum(intermediate)/float(len(intermediate))}[operator]

def _text_length_stats(array, operator, options):
    '''as it sounds'''
    lengths = []
    for item in array:
        if isinstance(item, str):
            lengths.append(len(item))
        else:
            return options['non_text_message']
    if len(lengths) == 0:
        return options['empty_text']
    return {'min_text_length':min(lengths), 'max_text_length':max(lengths), \
            'avg_text_length':sum(lengths)/float(len(lengths))}[operator]

def _filled_stats(array, operator):
    '''as it sounds'''
    filled = []
    for item in array:
        if item:
            filled.append(item)
    if len(filled) == 0:
        return {'all_filled':False, 'some_filled':False, 'none_filled':True}[operator]
    if len(filled) == len(array):
        return {'all_filled':True, 'some_filled':True, 'none_filled':False}[operator]
    else:
        return {'all_filled':False, 'some_filled':True, 'none_filled':False}[operator]

def _get_float(var, default_val='NaN'):
    '''try to convert to float; if impossible return return_val'''
    ret_val = default_val
    try:
        ret_val = float(var)
    except ValueError:
        pass
    return ret_val

def _get_type(line, index):
    '''used while parsing a table, returns BLANK, DATE, NUMBER, or TEXT
    Called by data_aggregate()'''
    months = ['jan', 'feb', 'mar', 'mär', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
              'dez']
    if index not in range(len(line)):
        return 'BLANK'
    tested = str(line[index])
    if not tested:
        return 'BLANK'
    if (len(tested) >= 6) and set(tested).intersection(set([str(x) for x in range(10)])) and \
       (tested.count('/') >= 2 or tested.count('\\') >= 2 or tested.count('-') >= 2 or \
        tested.count('.') >= 2 or \
        [x for x in months if tested.lower().count(x)]):
        return 'DATE'
    try:
        tested = float(tested)
    except ValueError:
        return 'TEXT'
    return 'NUMBER'

def data_aggregate(table_in, **kwargs):
    '''Aggregates data in specified columns based on an aggregation key
    Similar to an Excel Pivot but with a lot of additional features/possibilities
    Guided prompts provided to help with detail specification
    
    TYPICAL USE CASE:
          WE HAVE:
               Order ID     Client Name      Amount
                  1           George           100
                  2           Ben               50
                  3           George           230
                  4           George            10
                  5           Ben              110
          WE WANT:
               Client Name   Total Amount     Order IDs   Number of Orders
                 George       340               1,3,4       3
                 Ben          160               2,5         2
    '''
    _check_var_table(table_in, 'table_in')
    ass_var = _check_assignment(function_name='data_aggregate')
    headers = _kwarg_parse_prompt_bool('headers', default_val='True',
                                      prompt='Does your data contain headers?', **kwargs)
    agg_key_col = kwargs.get('aggregation_key_col', -1)
    if agg_key_col not in range(len(table_in[0])):
        pmt = 'AGGREGATION KEY COLUMN *unique* values will be the ROWS in the generated table >> '
        agg_key_col = ask_select_column_index(table_in, prompt=pmt)
    if 'aggregation_key_col' not in kwargs:
        _add_kwarg_to_last_command('aggregation_key_col', agg_key_col, fn_name='data_aggregate')
    agg_key_name = _kwarg_parse_prompt_str('agg_key_name',
                                          prompt='AGGREGATION KEY *label* is <{1}> - Ok?',
                                          default_val=table_in[0][agg_key_col] if headers \
                                          else 'KEY', **kwargs)
    att_agg_types = collections.OrderedDict([
        ('category', 'Aggregates according to category, creating multiple rows per attribute'),
        ('category-sum',
         'Sums records found per ID and category, creating multiple rows per attribute'),
        ('category-concat-unique', 'Concatenates the unique values found per ID and category'),
        ('category-and', 'Like *and* but on a category basis'),
        ('category-or', 'Like *or* but on a category basis'),
        ('category-count-nonempty', 'Like *count_nonempty* but on a category basis'),
        ('category-count-all', 'Like *count_all* but on a category basis'),
        ('category-count-unique', 'Like *count_unique* but on a category basis'),
        ('category-min', 'Like *min* but on a category basis'),
        ('category-max', 'Like *max* but on a category basis'),
        ('category-average', 'Like *average* but on a category basis'),
        ('category-are-same', 'Like *are_same* but on a category basis'),
        ('category-min-text-length', 'Like *min_text_length* but on a category basis'),
        ('category-max-text-length', 'Like *max_text_length* but on a category basis'),
        ('category-avg-text-length', 'Like *avg_text_length* but on a category basis'),
        ('category-all-filled', 'Like *all_filled* but on a category basis'),
        ('category-some-filled', 'Like *some_filled* but on a category basis'),
        ('category-none-filled', 'Like *none_filled* but on a category basis'),
        ('concatenate', 'Brings together the data as text strings lumped into a single result'),
        ('concatenate_unique', 'Concatenates a list of unique values found, removing duplicates'),
        ('and', 'Boolean AND of values'),
        ('or', 'Boolean OR of values'),
        ('count_nonempty',
         'Number of records aggregated under the agg_key_col, counted if attribute nonempty'),
        ('count_all',
         'Number of records aggregated under the agg_key_col, regardless of attribute status'),
        ('count_unique', 'Number of unique values found under the same agg_key_col'),
        ('sum', 'Sum the numeric values across aggregation scope'),
        ('min', 'Find the minimimum of numeric values across the aggregation scope'),
        ('max', 'Find the maximum of numeric values across the aggregation scope'),
        ('average', 'Find the average of the numeric values across the aggregation scope'),
        ('are_same', 'Report true if all values same across aggregation scope'),
        ('min_text_length', 'Minimum text length across aggregation scope, optional strip'),
        ('max_text_length', 'Maximum text length across aggregation scope, optional strip'),
        ('avg_text_length', 'Average text length across aggregation scope, optional strip'),
        ('all_filled', 'Report true only if all values filled across aggregation scope'),
        ('some_filled', 'Report true if at least one value filled across aggregation scope'),
        ('none_filled', 'Report true if there are no values filled across the aggregation scope'),
        ])
    att_agg_default_options = {
        'category':{'cat_key_col':-1, 'allow_duplicates_if_equal':False,
                    'duplicates_text':'-Duplicate entries-'},
        'category-sum':{'cat_key_col':-1, 'ignore_non_numbers':False,
                        'non_numbers_text':'-Non-numeric-'},
        'category-concat-unique':{'cat_key_col':-1, 'link_text':', '},
        'concatenate':{'strip':True, 'link_text':', '},
        'concatenate_unique':{'strip':True, 'link_text':', '},
        'and':{'allow_yn':True, 'allow_01':True, 'allow_tf':True, 'ignore_blanks':False,
               'invalid_text':'-Non-boolean value found-'},
        'or':{'allow_yn':True, 'allow_01':True, 'allow_tf':True, 'ignore_blanks':False,
              'invalid_text':'-Non-boolean value found-'},
        'count_nonempty':{'strip':True},
        'count_all':{},
        'count_unique':{'strip':True},
        'sum':{'ignore_non_numbers':False, 'non_numbers_text':'-Non-numeric-', 'ignore_empty':True,
               'empty_text':'-All empty-'},
        'min':{'ignore_non_numbers':False, 'non_numbers_text':'-Non-numeric-', 'ignore_empty':True,
               'empty_text':'-All empty-'},
        'max':{'ignore_non_numbers':False, 'non_numbers_text':'-Non-numeric-', 'ignore_empty':True,
               'empty_text':'-All empty-'},
        'average':{'ignore_non_numbers':False, 'non_numbers_text':'-Non-numeric-',
                   'ignore_empty':True, 'empty_text':'-All empty-'},
        'are_same':{'strip':True},
        'min_text_length':{'strip':True, 'non_text_message':'-Field(s) without text data-',
                           'empty_text':'-All empty-'},
        'max_text_length':{'strip':True, 'non_text_message':'-Field(s) without text data-',
                           'empty_text':'-All empty-'},
        'avg_text_length':{'strip':True, 'non_text_message':'-Field(s) without text data-',
                           'empty_text':'-All empty-'},
        'all_filled':{'strip':True},
        'some_filled':{'strip':True},
        'none_filled':{'strip':True},
        'category-and':{'allow_yn':True, 'allow_01':True, 'allow_tf':True, 'ignore_blanks':False,
                        'invalid_text':'-Non-boolean value found-', 'cat_key_col':-1},
        'category-or':{'allow_yn':True, 'allow_01':True, 'allow_tf':True, 'ignore_blanks':False,
                       'invalid_text':'-Non-boolean value found-', 'cat_key_col':-1},
        'category-count-nonempty':{'cat_key_col':-1, 'strip':True},
        'category-count-all':{'cat_key_col':-1, 'strip':True},
        'category-count-unique':{'cat_key_col':-1, 'strip':True},

        'category-min':{'cat_key_col':-1, 'ignore_non_numbers':False,
                        'non_numbers_text':'-Non-numeric-', 'ignore_empty':True,
                        'empty_text':'-All empty-'},
        'category-max':{'cat_key_col':-1, 'ignore_non_numbers':False,
                        'non_numbers_text':'-Non-numeric-', 'ignore_empty':True,
                        'empty_text':'-All empty-'},
        'category-average':{'cat_key_col':-1, 'ignore_non_numbers':False,
                            'non_numbers_text':'-Non-numeric-', 'ignore_empty':True,
                            'empty_text':'-All empty-'},
        'category-are-same':{'cat_key_col':-1, 'strip':True, 'not_found_text':'<No record found>'},
        'category-min-text-length':{'cat_key_col':-1, 'strip':True,
                                    'non_text_message':'-Field(s) without text data-',
                                    'empty_text':'-All empty-'},
        'category-max-text-length':{'cat_key_col':-1, 'strip':True,
                                    'non_text_message':'-Field(s) without text data-',
                                    'empty_text':'-All empty-'},
        'category-avg-text-length':{'cat_key_col':-1, 'strip':True,
                                    'non_text_message':'-Field(s) without text data-',
                                    'empty_text':'-All empty-'},
        'category-all-filled':{'cat_key_col':-1, 'strip':True},
        'category-some-filled':{'cat_key_col':-1, 'strip':True},
        'category-none-filled':{'cat_key_col':-1, 'strip':True},
        }
    agg_specs = kwargs.get('agg_specs', [])
    if len(agg_specs) == 0:
        print('No aggregation specs provided. You will be prompted for them, one at a time.\n')
        while True:
            print('Aggregation specification {}:'.format(str(len(agg_specs))))
            try:
                agg_type = ask_select(att_agg_types)
                if 'category' in agg_type or not \
                   ask_yn(default='n', prompt='Aggregate all columns? '):
                    if 'category' in agg_type:
                        pmt = 'Select CATEGORY (Unique values to be COLUMNS in result table) >> '
                        agg_options = {'cat_key_col':ask_select_column_index(table_in, prompt=pmt)}
                    else:
                        agg_options = {}
                    pmt = 'Select AGGREGATION ATTRIBUTE COLUMN (Values of interest to process) >> '
                    agg_col = ask_select_column_index(table_in, prompt=pmt)
                    agg_name = '{} - {} - {}'.format(str(len(agg_specs)), agg_type,
                                                     table_in[0][agg_col] if headers \
                                                     else 'col'+str(agg_col))
                    pmt = 'AGG NAME (columns to be formed by AGG NAME - CATEGORY) is <{}>. OK? '
                    while not ask_yn(default='y', prompt=pmt.format(agg_name)):
                        agg_name = input(\
                            'Enter new AGG NAME (column headers in form AGG NAME - CATEGORY >> ')
                    for key in att_agg_default_options[agg_type]:
                        if key not in agg_options:
                            agg_options[key] = att_agg_default_options[agg_type][key]
                    _review_options(agg_options, table_in)
                    new_spec = {'agg_type':agg_type, 'agg_col':agg_col, 'agg_options':agg_options,
                                'agg_name':agg_name}
                    agg_specs.append(new_spec)
                else:
                    agg_options = {key:att_agg_default_options[agg_type][key] \
                                   for key in att_agg_default_options[agg_type]}
                    _review_options(agg_options, table_in)
                    for agg_col in range(len(table_in[0])):
                        agg_name = '{} - {} - {}'.format(str(len(agg_specs)), agg_type,
                                                         table_in[0][agg_col] \
                                                         if headers else 'col'+str(agg_col))
                        new_spec = {'agg_type':agg_type, 'agg_col':agg_col,
                                    'agg_options':agg_options, 'agg_name':agg_name}
                        agg_specs.append(new_spec)
            except KeyboardInterrupt:
                print('New aggregation spec cancelled. Press Ctrl+c again to stop altogether.')
            if not ask_yn(default='y', prompt='Current agg. specs:\n {}; \n\nselect more?'.format(\
                '\n'.join([item['agg_name'] for item in agg_specs]))):
                break
        _add_kwarg_to_last_command('agg_specs', str(agg_specs), fn_name='data_aggregate')
    # Spec at hand, now the work starts..
    ret_table = [table_in[0]] if headers else []
    agg_key_col_dict = {line[agg_key_col]:[] for index, line in enumerate(table_in) \
                        if index or not headers}
    for index, line in enumerate(table_in):
        if headers and not index:
            continue
        agg_key_col_dict[line[agg_key_col]].append(index)

    keys = list(agg_key_col_dict)
    keys.sort()
    ret_table = [[agg_key_name]] + [[item] for item in keys]
    for index, spec in enumerate(agg_specs):
        atype = spec['agg_type']
        col = spec['agg_col']
        name = spec['agg_name']
        options = spec['agg_options']
        print('Calculating spec {} of {}:\n    {}'.format(str(index+1), str(len(agg_specs)), name))
        if 'category' in atype:
            cat_key_col = options['cat_key_col']
            if cat_key_col not in range(len(table_in[0])):
                print('Error: cat key col out of range of category aggregation. Skipping')
                continue
            cats = list(set([line[cat_key_col] for index, line in enumerate(table_in) \
                             if index or not headers]))
            cats.sort()

            if atype == 'category':
                cat_data = collections.OrderedDict([(cat, {line[agg_key_col]:None \
                                                           for index, line in enumerate(table_in) \
                                                               if index or not headers}) \
                                                                  for cat in cats])
                for line in table_in[1:] if headers else table_in:
                    if cat_data[line[cat_key_col]][line[agg_key_col]] is None:
   
                     cat_data[line[cat_key_col]][line[agg_key_col]] = line[col]
                    elif options.get('allow_duplicates_if_equal', False) and \
                         cat_data[line[cat_key_col]][line[agg_key_col]] == line[col]:
                        continue
                    else:
                        cat_data[line[cat_key_col]][line[agg_key_col]] = options['duplicates_text']

            if atype in ['category-and', 'category-or', 'category-min',
                         'category-max', 'category-average', 'category-count-nonempty',
                         'category-count-all', 'category-count-unique', 'category-are-same',
                         'category-min-text-length', 'category-max-text-length',
                         'category-avg-text-length', 'category-all-filled',
                         'category-some-filled', 'category-none-filled']:
                #Could also include category-sum here and eliminate from separate handling below
                cat_data = collections.OrderedDict([(cat, {line[agg_key_col]:[] \
                                                           for index, line in enumerate(table_in) \
                                                               if index or not headers}) \
                                                                  for cat in cats])
                for line in table_in[1:] if headers else table_in:
                    cat_data[line[cat_key_col]][line[agg_key_col]].append(\
                        line[col] if not options['strip'] else str(line[col]).strip())
                for cat in cat_data:
                    for key in cat_data[cat].keys():
                        if 'count' not in atype and 'text' not in atype and 'filled' not in atype\
                           and 'are-same' not in atype:
                            cat_data[cat][key] = \
                                               _bool_calc(cat_data[cat][key], atype[9:], options) \
                                               if atype in ['category-and', 'category-or'] else \
                                                  _arithmetic_stats(cat_data[cat][key], atype[9:],
                                                                    options)
                        elif 'count' in atype:
                            if 'unique' in atype:
                                cat_data[cat][key] = list(set(cat_data[cat][key]))
                            cat_data[cat][key] = len([item for item in cat_data[cat][key] if (
                                'all' in atype or 'unique' in atype or \
                                ('nonempty' in atype and bool(item.strip())))])
                        elif 'filled' in atype:
                            cat_data[cat][key] = _filled_stats(cat_data[cat][key],
                                                               atype[9:].replace('-', '_'))
                        elif 'text-length' in atype:
                            cat_data[cat][key] = _text_length_stats(cat_data[cat][key],
                                                                    atype[9:].replace('-', '_'),
                                                                    options)
                        elif 'are-same' in atype:
                            cat_data[cat][key] = {0:options['not_found_text'], 1:True}.get(
                                len(list(set(cat_data[cat][key]))), False)
                        else:
                            cat_data[cat][key] = 'Invalid aggregation type: {}'.format(atype)

            if atype == 'category-sum':
                ignore_non_numbers = options['ignore_non_numbers']
                non_numbers_text = options['non_numbers_text']
                cat_data = collections.OrderedDict([(cat, {line[agg_key_col]:0.0 \
                                                           for index, line in enumerate(table_in) \
                                                               if index or not headers}) \
                                                                  for cat in cats])
                for line in table_in[1:] if headers else table_in:
                    var_type = _get_type(line, col)
                    if var_type == 'BLANK' or \
                       cat_data[line[cat_key_col]][line[agg_key_col]] == non_numbers_text:
                        continue
                    elif var_type in ['DATE', 'TEXT'] and not ignore_non_numbers:
                        cat_data[line[cat_key_col]][line[agg_key_col]] = non_numbers_text
                    else:
                        cat_data[line[cat_key_col]][line[agg_key_col]] += _get_float(line[col],
                                                                                     default_val=0)

            if atype == 'category-concat-unique':
                cat_data = collections.OrderedDict([(cat, {line[agg_key_col]:[] \
                                                           for index, line in enumerate(table_in) \
                                                               if index or not headers}) \
                                                                  for cat in cats])
                for line in table_in[1:] if headers else table_in:
                    cat_data[line[cat_key_col]][line[agg_key_col]].append(line[col])
                for cat in cat_data:
                    for key in cat_data[cat].keys():
                        cat_data[cat][key] = options['link_text'].join(\
                            sorted(list(set(cat_data[cat][key]))))

            for cat in cat_data:
                _add_values(ret_table, cat_data[cat], name+' - {}'.format(str(cat)))
            continue

        val_dict = {key:[str(table_in[index][col]).strip() if options.get('strip', False) else \
                         table_in[index][col] for index in agg_key_col_dict[key]] \
                    for key in agg_key_col_dict}
        if atype == 'concatenate':
            _add_values(ret_table,
                        {key:options['link_text'].join(val_dict[key]) for key in agg_key_col_dict},
                        name)
            continue
        if atype == 'concatenate_unique':
            _add_values(ret_table,
                        {key:options['link_text'].join(sorted(list(set(val_dict[key])))) \
                         for key in agg_key_col_dict},
                        name)
            continue
        if atype in ['and', 'or']:
            _add_values(ret_table,
                        {key:_bool_calc(val_dict[key], atype, options) \
                         for key in agg_key_col_dict},
                        name)
            continue
        if atype in ['count_nonempty', 'count_all']:
            _add_values(ret_table,
                        {key:len([str(item) for item in val_dict[key] \
                                  if len(str(item)) > 0 or atype == 'count_all']) \
                                     for key in agg_key_col_dict},
                        name)
            continue
        if atype in ['count_unique']:
            _add_values(ret_table,
                        {key:len(set([str(item) for item in val_dict[key]])) \
                                     for key in agg_key_col_dict},
                        name)
            continue
        if atype in ['sum', 'min', 'max', 'average']:
            _add_values(ret_table,
                        {key:_arithmetic_stats(val_dict[key], atype, options) \
                         for key in agg_key_col_dict},
                        name)
            continue
        if atype == 'are_same':
            _add_values(ret_table,
                        {key: len(set(val_dict[key])) == 1 for key in agg_key_col_dict},
                        name)
            continue
        if atype in ['min_text_length', 'max_text_length', 'avg_text_length']:
            _add_values(ret_table,
                        {key:_text_length_stats(val_dict[key], atype, options) \
                         for key in agg_key_col_dict},
                        name)
            continue
        if atype in ['all_filled', 'some_filled', 'none_filled']:
            _add_values(ret_table,
                        {key:_filled_stats(val_dict[key], atype) \
                         for key in agg_key_col_dict},
                        name)
            continue
        print('Warning: Aggregation type for spec <{}> not available. Skipping'.format(name))

    if ass_var:
        print('Aggregation complete. Assigning result table to variable <{}>.'.format(ass_var))
    print('\n')
    return ret_table
data_aggregate.desc = 'List of lists guided aggregation'

def data_de_aggregate(table_in, **kwargs):
    '''de-aggregates data in specified columns based on an aggregation key col, delimiter
    Inverst of data_aggregate()
    
    TYPICAL USE CASE:
          WE HAVE:
               Client Name   Total Amount     Order IDs   Number of Orders
                 George       340               1,3,4       3
                 Ben          160               2,5         2
          
          (agg_key_col would be the Order IDs column index, delim would be ',')
          
          WE WANT:
               Order ID     Client Name      Total Amount
                  1           George           340
                  2           Ben              160
                  3           George           340
                  4           George           340
                  5           Ben              160
                 '''
    _check_var_table(table_in, 'table_in')
    ass_var = _check_assignment(function_name='data_de_aggregate')
    headers = _kwarg_parse_prompt_bool('headers', default_val='True',
                                      prompt='Does your data contain headers?', **kwargs)
    agg_key_col = kwargs.get('aggregation_key_col', -1)
    if agg_key_col not in range(len(table_in[0])):
        agg_key_col = ask_select_column_index(table_in,
                                              prompt='Select (de-)aggregation key column >> ')
    if 'aggregation_key_col' not in kwargs:
        _add_kwarg_to_last_command('aggregation_key_col', agg_key_col, fn_name='data_de_aggregate')
    delim = kwargs.get('delim', ', ')
    while 'delim' not in kwargs and not ask_yn(default='y', \
                                               prompt='Delimiter is < {} >. OK?'.format(delim)):
        new_delim = input('Type new delimiter to use: >>> ')
        if len(new_delim) > 0:
            delim = new_delim
    if 'delim' not in kwargs:
        _add_kwarg_to_last_command('delim', _quoted(delim), fn_name='data_de_aggregate')
    _strip = _kwarg_parse_prompt_bool('strip', default_val='True', **kwargs)
    ret_table = [table_in[0]] if headers else []
    scope = table_in[1:] if headers else table_in
    print('Data records before de-aggregation: {}'.format(str(len(scope))))
    for line in scope:
        for val in str(line[agg_key_col]).split(delim):
            ret_table.append(line[:agg_key_col] + \
                             [val.strip() if isinstance(val, str) and _strip else val] + \
                             line[agg_key_col + 1:])
    print('Data records after de-aggregation: {}'.format(str(len(ret_table)-(1 if headers else 0))))
    if ass_var:
        print('De-aggregation complete. Assigning result table to variable <{}>.'.format(ass_var))
    return ret_table
data_de_aggregate.desc = 'List of lists guided de-aggregation'

def extract_column_from_table(table_in, **kwargs):
    '''returns a one dimensional list from a single column, strips header by defualt
    kwargs:
        strip_header (bool, default True)
        col (int, prompt is not given)
    '''
    var_name = _check_assignment(function_name='extract_column_from_table')
    _check_var_table(table_in, 'table_in')
    col = kwargs.get('col', None)
    strip_header = kwargs.get('strip_header', None)
    if 'col' not in kwargs:
        col = ask_select_column_index(table_in, prompt='Select column to extract from table >> ')
        _add_kwarg_to_last_command('col', str(col))
    if 'strip_header' not in kwargs:
        strip_header = ask_yn(default='y', prompt='Do you want to strip off header line from col?')
        _add_kwarg_to_last_command('strip_header', str(strip_header))
    if not kwargs:
        print('Extracting column {} to variable: ** {} **'.format(str(col), var_name))
    if strip_header:
        return [line[col] for line in table_in[1:]]
    else:
        return [line[col] for line in table_in]
extract_column_from_table.desc = 'Get column as 1-d list'

def sel_col(table_in, column, strip_header=True):
    '''special case of extract_column_from_table, provided for backwards compatibility'''
    return extract_column_from_table(table_in, col=column, strip_header=strip_header)
sel_col.desc = '[PROVIDED FOR BACKWARDS COMPATIBILITY]'

def _decimate(list_in):
    '''return list of ten equally spaced index points
    used by data_join()'''
    length = len(list_in)
    if length < 11:
        return range(1, length)
    return [int(scalar * (float(length-1)/10)) for scalar in range(1, 11)]

def data_join(base_table, ext_table, **kwargs):
    '''guided/automated data join from one two dimensional table to another
    Joins based on comparison of key columsn in base and ext table
        Key analysis results categorized as follows:
            'Key Code': 'Key in base table / Key in ext table'
            'A':        'unique/unique'
            'B':        'unique/missing'
            'C':        'missing/unique'
            'D':        'non-unique/unique'
            'E':        'unique/non-unique'
            'F':        'non-unique/non-unique'
            'G':        'non-unique/missing'
            'H':        'missing/non-unique'
    In real life, not all tables match 1:1 as in (category A), so...
    Three join types possible:
    -  Restrictive Join: returns a table of unambiguous mappings from the base table.
                         (no dummy vals, duplication possible if joined data N:1)
                         (join categories A, D)
    -  Base Join: returns a table of all records from the base table, with dummy
                  values in place of ambiguous or missing data.
                  (data duplication okay for joined data but not for base table,
                  dummy data used in place of missing or ambiguous mappings.)
                  (join categories A, D, B, G, E*, F*)
                  (*Data from base only: joined table data ambiguous/dropped)
    -  Promiscuous Join: returns a table with all entries from both orig. tables,
                         matched where unambiguous and duplicated as necessary.
    '''
    _check_var_table(base_table, 'base_table')
    _check_var_table(ext_table, 'ext_table')
    ass_var = _check_assignment(function_name='data_join')
    valid_join_types = ['restrictive', 'base', 'promiscuous']
    join_type = kwargs.get('join_type', '')
    if join_type not in valid_join_types:
        print('First you need to select the type of join you wish to perform:\n\n')
        print('Restrictive Join: returns a table of unambiguous mappings from the base table.')
        print('                     (no dummy vals, duplication possible if joined data n:1)')
        print('                     (join categories A, D)\n')
        print('Base Join: returns a table of all records from the base table, with dummy')
        print('           values in place of ambiguous or missing data.')
        print('               (data duplication okay for joined data but not base table,')
        print('                dummy data used in place of missing or ambiguous mappings.)')
        print('               (join categories A, D, B, G, E*, F*)')
        print('               (*Data from base only: joined table data ambiguous/dropped)\n')
        print('Promiscuous Join: returns a table with all entries from both orig. tables,')
        print('                  matched where unambiguous and duplicated as necessary.\n\n')
        join_type = ask_select(valid_join_types, prompt='Select a join type >> ', orig_out=True)
        if 'join_type' not in kwargs:
            _add_kwarg_to_last_command('join_type', _quoted(join_type))
    base_key_col, ext_key_col, neg_key_col = -1, -1, -1
    if 'base_key_col' in kwargs:
        base_key_col = kwargs['base_key_col']
    if 'base_key_col' not in kwargs or base_key_col not in range(len(base_table[0])):
        base_key_col = ask_select_column_index(base_table, prompt='Base table key column >> ')
        _add_kwarg_to_last_command('base_key_col', base_key_col)
    if 'ext_key_col' in kwargs:
        ext_key_col = kwargs['ext_key_col']
    if 'ext_key_col' not in kwargs or ext_key_col not in range(len(ext_table[0])):
        ext_key_col = ask_select_column_index(ext_table, prompt='Table to join key column >> ')
        _add_kwarg_to_last_command('ext_key_col', ext_key_col)
    if 'neg_key_col' in kwargs:
        neg_key_col = kwargs['neg_key_col']
    neg_list = kwargs.get('neg_list', None)
    if neg_list:
        if not _is_list_of_lists(neg_list, strict_nonempty=True):
            print('neg list passed to data_join() not list of lists or is empty: ignoring')
            neg_list = None
        elif 'neg_key_col' not in kwargs or neg_key_col not in range(len(neg_list[0])):
            neg_key_col = ask_select_column_index(neg_list, prompt='Negative list key column >> ')
            _add_kwarg_to_last_command('neg_key_col', neg_key_col)

    headers = _kwarg_parse_prompt_bool('headers', default_val='True', **kwargs)

    _prompt = 'Current tag to be prepended to table for all {} is <{}>. Is that ok?'
    base_hdr_tag = '' if not headers else _kwarg_parse_prompt_str('base_hdr_tag', '_ORIG_',
                                                                 prompt=_prompt, **kwargs)
    ext_hdr_tag = '' if not headers else _kwarg_parse_prompt_str('ext_hdr_tag', '_JOINED_',
                                                                prompt=_prompt, **kwargs)
    base_keys = sel_col(base_table, base_key_col, headers)
    ext_keys = sel_col(ext_table, ext_key_col, headers)
    if neg_list:
        neg_keys = sel_col(neg_list, neg_key_col, headers)
    else:
        neg_keys = []

    print('JOIN: Performing key analysis')

    key_dict = key_analysis(base_keys, ext_keys, neg_keys) if neg_list else \
               key_analysis(base_keys, ext_keys)

    print('JOIN: Building index / key lookups')
    base_index_key_lookup = {key:[] for key in key_dict['reverse']}
    ext_index_key_lookup = {key:[] for key in key_dict['reverse']}
    for index, base_line in enumerate(base_table):
        if headers and not index:
            continue
        base_index_key_lookup[base_line[base_key_col]].append(index)

    for index, ext_line in enumerate(ext_table):
        if headers and not index:
            continue
        ext_index_key_lookup[ext_line[ext_key_col]].append(index)

    print('JOIN: Assembling data')

    ret_dict = collections.OrderedDict()
    ret_dict['joined'] = []
    if not kwargs.get('suppress_key_table_return', False):
        ret_dict['all_keys'] = [['Key Analysis Result', 'Key']]
        for key_cat in key_dict:
            for key in key_dict[key_cat]:
                if key == 'reverse':
                    continue
                ret_dict['all_keys'].append([key_cat, key])

    no_match_text = kwargs.get('no_match_text', '-no match-')
    ambiguous_text = kwargs.get('ambiguous_text', '-ambiguous-')
    join_error_text = kwargs.get('join_error_text', '-join error-')
    base_blank = [no_match_text] * len(base_table[0])
    ext_blank = [no_match_text] * len(ext_table[0])
    base_ambig = [ambiguous_text] * len(base_table[0])
    ext_ambig = [ambiguous_text] * len(ext_table[0])
##    base_error = [join_error_text] * len(base_table[0])
##    ext_error = [join_error_text] * len(ext_table[0])

    joined = []
    if headers:
        if None in base_table[0]:
            print('data_join(): WARNING: Empty header cells encountered in *original* table header.')
            base_table[0] = ['' if item in None else item for item in base_table[0]]
        if None in ext_table[0]:
            print('data_join(): WARNING: Empty header cells encountered in *joined* table header.')
            ext_table[0] = ['' if item in None else item for item in ext_table[0]]
        joined.append(['Key', 'Key Code'] + [base_hdr_tag + item for item in base_table[0]] + \
                      [ext_hdr_tag + item for item in ext_table[0]])

    #joined = [['Key'] + base_table[0] + ['Key Code'] + ext_table[0]] if headers else []
    print('JOIN: Parsing base table')
    report_points = _decimate(base_table)
    for index, base_line in enumerate(base_table):
        if index in report_points:
            print('.', end='')
        if headers and not index:
            continue
        key = base_line[base_key_col]
        cat = key_dict['reverse'][key] # 'A', 'B', etc
        if cat in ['A', 'D']:
            joined.append([key, cat] + base_line + ext_table[ext_index_key_lookup[key][0]])
        elif cat in ['B', 'G']:
            if join_type in ['base', 'promiscuous']:
                joined.append([key, cat] + base_line + ext_blank)
        elif cat in ['E']:
            if join_type in ['base']:
                joined.append([key, cat] + base_line + ext_ambig)
        elif cat in ['F']:
            if join_type in ['base', 'promiscuous']:
                joined.append([key, cat] + base_line + ext_ambig)
        else:
            print('Problem with join: key category found in base table that should '\
                  +'not be: category "{}", line: {}.'.format(cat, index))
    print('\nJOIN: Parsing table to join for remaining records')
    report_points = _decimate(ext_table)
    if join_type in ['promiscuous']:
        for index, ext_line in enumerate(ext_table):
            if index in report_points:
                print('.', end='')
            if headers and not index:
                continue
            key = ext_line[ext_key_col]
            cat = key_dict['reverse'][key]
            if cat in ['A', 'D']:
                continue
            elif cat in ['E']:
                joined.append([key, cat] + base_table[base_index_key_lookup[key][0]] + ext_line)
            elif cat in ['C', 'H']:
                joined.append([key, cat] + base_blank + ext_line)
            elif cat in ['F']:
                joined.append([key, cat] + base_ambig + ext_line)
            else:
                print('Problem with join: key category found in table to join that should '\
                       +'not be: category "{}", line: {}.'.format(cat, index))

    if neg_list:
        print('\nJOIN: Amending table to indicate presence in negative list')
        explained = key_dict['B explained'] + key_dict['G explained']
        unexplained = key_dict['B unexplained'] + key_dict['G unexplained']
        for index, line in enumerate(joined):
            if index == 0 and headers:
                line.insert(2, 'Explained by negative list')
            else:
                line.insert(2,\
                    'Yes' if line[0] in explained else 'No' if line[0] in unexplained else 'n/a')

    if join_type == 'base':
        unm_prompt = 'Currently making table of unmatched records from joined: < {1} >. OK?'
        incl_unm = _kwarg_parse_prompt_bool('include_unmatched_ext_in_ret_val', default_val='True',
                                           prompt=unm_prompt, **kwargs)
    else:
        incl_unm = False
    if incl_unm:
        print('\nJOIN: Creating table of unused external table records')
        unmatched = key_dict['C'] + key_dict['E'] + key_dict['F'] + key_dict['H']
        _prompt = 'Current sheet name for unmatched report (var <{}>) is <{}>. Is that ok?'
        unm_name = _kwarg_parse_prompt_str('unmatched_ext_sheet_name', 'unmatched', prompt=_prompt,
                                          **kwargs)
        ret_dict[unm_name] = [line for index, line in enumerate(ext_table)\
                              if (index == 0 and headers) or line[ext_key_col] in unmatched]
        print(' ...number of unmatched records: {}'.format(str(len(unmatched))))
        if len(unmatched) == 0:
            ret_dict[unm_name].append(['no unmatched records found in joined table'])

    ret_dict['joined'] = joined
    print('\nJOIN: Done. Saved to variable {}'.format(ass_var))
    beep()
    return ret_dict
data_join.desc = 'Prompted list of lists join'

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

def excel_column(index):
    '''converts zero-indexed column to excel column name'''
    lookup = dict(zip(range(26), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    if (not isinstance(index, (int, float))) or int(index) != index:
        raise TypeError('excel column indixes must be integers of int-convertible floats')
    if index > 16383 or index < 0:
        raise IndexError('excel column indices must be between 0 and 16383 ')
    index = int(index)
    if index // 26:
        return excel_column(index//26 -1) + lookup[index%26]
    return lookup[index%26]
excel_column.desc = '0->A, 1->B, 5->F etc.'

def _guess_var(calling_function):
    '''returns the best guess of what variable the user would like to execute the function on
    used by e.g. data_preview()'''
    last = _get_previous_command()
    curr = _get_last_command()
    status = 'ok'
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
##            loop_var_name = last[4:last[4:].find(' ')].strip() if enumerate not in last else \
##                            last[last.find(',')+1:in_pos].strip()
        loop_var_name_positions = _all_pos(last, loop_var_name)
##        loop_var_second_pos = last.find(loop_var_name, last.find(loop_var_name)+1)
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

    if ass_var != None and len(ass_var) and (ass_var in locals() or ass_var in globals()):
        exec ('data_in = {}'.format(ass_var))
    else:
        print('Ambiguous variable {}; {} canceled'.format(\
            ass_var, calling_function))
        return None
    return ass_var

def data_preview(data_in=None):
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
            #print('Previewing data:')
            pass
    else:
        if data_in == None:
            ass_var = _guess_var('data_preview')
            if ass_var == None:
                return
            else:
                data_in = eval(ass_var)
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
##    elif isinstance(data_in, list):
##        print('Data is type **list**\n\nindex - preview')
##        for index, item in enumerate(data_in):
##            print(index, ' - ', _prev_s(item))
    elif isinstance(data_in, int):
        print('Data is type: int with value: {}'.format(str(data_in)))
    elif isinstance(data_in, float):
        print('Data is type: float with value: {}'.format(str(data_in)))
    elif isinstance(data_in, bool):
        print('Data is type: bool with value: {}'.format(str(data_in)))
    elif isinstance(data_in, str):
        print('String data: {}'.format(str(data_in[:64])))
data_preview.desc = 'Displays info on Python variable'

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

def key_analysis(left_keys, right_keys, negative_list=None):
    '''simple key comparison to determine uniqueness of keys in tables, what can be explained
    by negative list (if any), and anything missing'''
    if not isinstance(left_keys, list) or not isinstance(right_keys, list):
        raise CustomException('keys must be passed as lists of values')
    if len(left_keys) == 0 or len(right_keys) == 0:
        raise CustomException('at least one key list passed to key_analysis() empty')
    if isinstance(left_keys[0], list) or isinstance(right_keys[0], list):
        raise CustomException('keys passed to key_analysis() must be in single dim lists')
    if negative_list:
        if not isinstance(negative_list, list):
            print('Invalid variable passed to key_analysis() as negative_list; ignoring')
            negative_list = None
        else:
            if isinstance(negative_list[0], list):
                print('negative_list passed to key_analysis()'+\
                       ' as list of lists; must be list! ignoring.')
                negative_list = None

    if negative_list:
        nset = set(negative_list)
    else:
        nset = set()

    print('KEY ANALYSIS: ANALYZING BASE KEYS')
    left_unique, left_non_unique = single_col_analysis(left_keys)
    print('KEY ANALYSIS: ANALYZING JOIN KEYS')
    right_unique, right_non_unique = single_col_analysis(right_keys)
    neg_list = list(nset)

    lset, rset = set(left_keys), set(right_keys)
    luset, lnset, ruset, rnset = set(left_unique), set(left_non_unique), set(right_unique),\
                                       set(right_non_unique)

    ret_dict = collections.OrderedDict()
    print('KEY ANALYSIS: Calculating Cat. A... (unique/unique)')
    ret_dict['A'] = list(luset.intersection(ruset))
    print('   ...records: {}'.format(str(len(ret_dict['A']))))
    print('KEY ANALYSIS: Calculating Cat. B... (unique/missing)')
    ret_dict['B'] = list(luset-rset)
    print('   ...records: {}'.format(str(len(ret_dict['B']))))
    if negative_list:
        print('KEY ANALYSIS: Calculating Cat. B explained/unexplained...')
        ret_dict['B explained'] = list((luset-rset).intersection(nset))
        ret_dict['B unexplained'] = list((luset-rset)-nset)
        print('   ...records Explained: {}'.format(str(len(ret_dict['B explained']))))
        print('   ...records UNexplained: {}'.format(str(len(ret_dict['B unexplained']))))
    print('KEY ANALYSIS: Calculating Cat. C... (missing/unique)')
    ret_dict['C'] = list(ruset-lset)
    print('   ...records: {}'.format(str(len(ret_dict['C']))))
    print('KEY ANALYSIS: Calculating Cat. D... (non-unique/unique)')
    ret_dict['D'] = list(lnset.intersection(ruset))
    print('   ...records: {}'.format(str(len(ret_dict['D']))))
    print('KEY ANALYSIS: Calculating Cat. E... (unique/non-unique)')
    ret_dict['E'] = list(luset.intersection(rnset))
    print('   ...records: {}'.format(str(len(ret_dict['E']))))
    print('KEY ANALYSIS: Calculating Cat. F... (non-unique/non-unique)')
    ret_dict['F'] = list(lnset.intersection(rnset))
    print('   ...records: {}'.format(str(len(ret_dict['F']))))
    print('KEY ANALYSIS: Calculating Cat. G... (non-unique/missing)')
    ret_dict['G'] = list(lnset-rset)
    print('   ...records: {}'.format(str(len(ret_dict['G']))))
    if negative_list:
        print('KEY ANALYSIS: Calculating Cat. G explained/unexplained... ')
        ret_dict['G explained'] = list((lnset-rset).intersection(nset))
        ret_dict['G unexplained'] = list((lnset-rset)-nset)
        print('   ...records Explained: {}'.format(str(len(ret_dict['G explained']))))
        print('   ...records UNexplained: {}'.format(str(len(ret_dict['G unexplained']))))
    print('KEY ANALYSIS: Calculating Cat. H... (missing/non-unique)')
    ret_dict['H'] = list(rnset-lset)
    print('   ...records: {}'.format(str(len(ret_dict['H']))))
    print('KEY ANALYSIS: Generating reverse (key to category) lookup table')
    ret_dict['reverse'] = collections.OrderedDict()
    for cat in ret_dict:
        if cat in ['reverse', 'G explained', 'G unexplained', 'B explained', 'B unexplained']:
            continue
        for item in ret_dict[cat]:
            ret_dict['reverse'][item] = cat
    return ret_dict
key_analysis.desc = 'Get info (dict) about key lists'

def _prev_s(item):
    '''internal function to preview single data point'''
    if isinstance(item, str):
        if len(item) < 60:
            return 'String: "{}"'.format(item)
        else:
            return 'String: "{}...'.format(item[:58])
    elif isinstance(item, int) or isinstance(item, float) or isinstance(item, bool):
        #type(item) in [int, float, bool]:
        return str(item)
    elif isinstance(item, list):
        #type(item) is list:
        return 'List: ' + ', '.join([str(element) for element in item])[:60]
    elif isinstance(item, dict):
        #type(item) is dict:
        return 'Dict: ' + ', '.join([str(element) for element in item])[:60]
    else:
        return 'Other type: ', str(type(item))

def data_recon(orig_table, new_table, **kwargs):
    '''Wrapper with argument prompting for the reconcile() function
    
    TYPICAL USE CASE: You have two versions of the same table, with some changes.
                      You want to figure out quickly where the changes are.
                      
    TYPICAL USAGE:
        >>> original = data_import()
        >>> modified = data_import()
        >>> diff = data_recon()
        >>> data_export(diff)

    See reconcile() docstring "help(reconcile)" for additional argument names and meanings
    Additional kwargs possible:
    col_mode: whether the POSITION or the NAME of columns determines comparison
    key_names: (orig_name, new_name) names of the columns to use as keys, if col_mode == "NAME"
       (if col_mode == "NAME" and key_names is given, key_indices as passed will be ignored
       and replaced by the corresponding indices in the call to reconcile())
    col_select: whether to specify a LIST or let the script select columns AUTOmatically
       AUTO-OR: select all column names found, even if they don't have a match (default)
       AUTO-AND: select only those column names that are the same in both tables
    col_sort: if mode is NAME, this specifies whether to alphabetize column names (default False)
    columns: [(a,b,c), ...] where a and b are col indices to compare and c is compare type:
       c = 0 -> text compare
       c = 1 -> numerical comparison
       default is [(0,0,0), (1,1,0), (2,2,0), ...]
       if a or b is -1, it indicates that there is no data to compare against (e.g. no name match)
    column_name_list: [(a,b,c), ...] just as in columns except:
       a and b will be column names
    auto_col_name: if True will auto select columns by name, ignored if auto_col_position selected

    '''
    print('\n\nWARNING: data_recon() has been newly developed and may contain bugs\n\n')
    _check_var_table(orig_table, 'orig_table')
    _check_var_table(new_table, 'new_table')
    ass_var = _check_assignment(function_name='data_recon')
    kwargs['strip'] = _kwarg_parse_prompt_bool('strip', default_val='True', **kwargs)
    kwargs['include_source_data_in_output'] = _kwarg_parse_prompt_bool(
        'include_source_data_in_output', default_val='True', **kwargs)
    kwargs['match_text'] = _kwarg_parse_prompt_str(
        'match_text', default_val='-',
        prompt='{} (string if compare is a match) is <{}>: Ok?', **kwargs)
    kwargs['empty_text'] = _kwarg_parse_prompt_str(
        'empty_text', default_val='<blank>',
        prompt='{} (string if value unfilled) is <{}>: Ok?', **kwargs)
    kwargs['missing_col_text'] = _kwarg_parse_prompt_str(
        'missing_col_text', default_val='<missing_col>',
        prompt='{} (string if col missing) is <{}>: Ok?', **kwargs)
    kwargs['missing_record_text'] = _kwarg_parse_prompt_str(
        'missing_record_text', default_val='<missing_rec>',
        prompt='{} (string if key not found) is <{}>: Ok?', **kwargs)
    kwargs['ambiguous_record_text'] = _kwarg_parse_prompt_str(
        'ambiguous_record_text', default_val='<ambig rec>',
        prompt='{} (string if key found multiple times) is <{}>: Ok?', **kwargs)
    kwargs['transition_text'] = _kwarg_parse_prompt_str(
        'transition_text', default_val=' --> ',
        prompt='{} (string to show a mutation) is <{}>: Ok?', **kwargs)


    col_mode = kwargs.get('col_mode', None)
    if col_mode not in ['NAME', 'POSITION']:
        col_mode = ask_select({'NAME':'Recognize which column is which by its HEADER NAME',
                               'POSITION':'Recognize columns by their positions'}, orig_out=True,
                              prompt='Select how you want to analyze columns to be compared:')
        if 'col_mode' in kwargs:
            _remove_keyword_argument_from_last_command('col_mode')
        _add_kwarg_to_last_command('col_mode', col_mode)
        kwargs['col_mode'] = col_mode

    col_select = kwargs.get('col_select', None)
    if col_select not in ['LIST', 'AUTO-OR', 'AUTO-AND']:
        pmt = 'Select how you want to specify which particular columns will be compared:'
        col_select = ask_select({'LIST':'Specify exact list of columns to compare',
                                 'AUTO-OR':'Automatically compare all columns with the same name',
                                 'AUTO-AND':'Like AUTO-OR but excl. names only found in one table',
                                }, orig_out=True, prompt=pmt)
        if 'col_select' in kwargs:
            _remove_keyword_argument_from_last_command('col_select')
        _add_kwarg_to_last_command('col_select', col_select)
        kwargs['col_select'] = col_select

    if col_mode == 'NAME':
        col_sort = _kwarg_parse_prompt_bool('col_sort', default_val='False',
                                           prompt='{} (sort cols by name) is <{}>. OK?', **kwargs)

    (l_key, r_key) = kwargs.get('key_indices', (None, None))
    if l_key is None or l_key not in range(-1, len(orig_table[0])):
        print('You need to specify a key column from the ORIGINAL table.')
        if ask_yn(prompt='preview columns?'):
            data_preview(orig_table, internal=True, ver_name='data_recon(): ORIGINAL table')
        while True:
            l_key = ask_num(allow_decimal=False, allow_negative=True, allow_default=True,
                            default=-1,
                            prompt='Select orig_table key (enter nothing to use row index) #: ')
            if l_key not in range(-1, len(orig_table[0])):
                print('You have selected an index out of range. Try again.')
            else:
                break
    if r_key is None or r_key not in range(-1, len(new_table[0])):
        print('You need to specify a key column from the UPDATED/NEW table.')
        if ask_yn(prompt='preview columns?'):
            data_preview(new_table, internal=True, ver_name='data_recon(): NEW table')
        while True:
            r_key = ask_num(allow_decimal=False, allow_negative=True, allow_default=True,
                            default=-1,
                            prompt='Select new_table key (enter nothing to use row index) #: ')
            if l_key not in range(-1, len(new_table[0])):
                print('You have selected an index out of range. Try again.')
            else:
                break

    if 'key_indices' not in kwargs:
        _add_kwarg_to_last_command('key_indices', (l_key, r_key))
    kwargs['key_indices'] = (l_key, r_key)

    if l_key == -1 or r_key == -1:
        kwargs['autogen_key_header_text'] = _kwarg_parse_prompt_str(
            'autogen_key_header_text', default_val='<Auto-generated key>',
            prompt='{} (header name for auto generated key / row index) is <{}>: Ok?', **kwargs)
    else:
        kwargs['numeric_key'] = _kwarg_parse_prompt_bool(
            'numeric_key', default_val='True',
            prompt='{} (treat key as number if possible / "01" == "1.0") is <{}>: Ok?', **kwargs)

##    columns: [(a,b,c), ...] where a and b are col indices to compare and c is compare type:
##       c = 0 -> text compare
##       c = 1 -> numerical comparison
##       default is [(0,0,0), (1,1,0), (2,2,0), ...]
##       if a or b is -1, it indicates that there is no data to compare against

    column_errors = []

    if col_select in ['AUTO-OR', 'AUTO-AND']:
        if 'columns' in kwargs:
            print('Warning: argument *columns* ignored as *col_select* set to AUTO')
            column_errors.append(['Columns passed in as argument despite AUTO column selection.'])
        if col_mode == 'POSITION':
            llen, rlen = (len(orig_table[0]), len(new_table[0]))
            columns = [(pos, pos, 0) for pos in range(min(llen, rlen))]
            if 'OR' in col_select:
                for pos in range(min(llen, rlen), max(llen, rlen)):
                    columns.append((pos, -1, 0) if llen > rlen else (-1, pos, 0))
        else: #col_mode == 'NAME'
            lu, ln = single_col_analysis(
                [str(item).strip() if kwargs['strip'] else item for item in orig_table[0]],
                suppress_start_notify=True)
            for name in sorted(ln):
                text = 'Warning: column name "{}" not unique in {} table; ignored'
                print(text.format(name, 'original'))
                column_errors.append([text.format(name, 'original')])
            ru, rn = single_col_analysis(
                [str(item).strip() if kwargs['strip'] else item for item in new_table[0]],
                suppress_start_notify=True)
            for name in sorted(rn):
                text = 'Warning: column name "{}" not unique in {} table; ignored'
                print(text.format(name, 'new'))
                column_errors.append([text.format(name, 'new')])
            columns = [(name, name, 0) for name in orig_table[0]
                       if name in lu and (name in ru or 'OR' in col_select)]
            if 'OR' in col_select:
                for name in new_table[0]:
                    if name in ru and name not in lu:
                        columns.append((name, name, 0))
    else: #col_select == 'LIST'
        if 'columns' in kwargs:
            columns = kwargs.get('columns')
            if col_mode == 'NAME':
                kwargs['columns'] = _check_convert_text_cols(orig_table, new_table,
                                                             kwargs['columns'], kwargs['strip'],
                                                             column_errors)
                if not kwargs['columns']:
                    #after processing specs, no valid comparisons are found
                    del kwargs['columns']
            else: #col_mode == 'POSITION'
                temp_cols = []
                for (lcol, rcol, type) in columns:
                    err_text = 'Column {} out of range of {} table; skipping spec.'
                    if lcol > -1 and lcol not in range(len(orig_table[0])):
                        column_errors.append(err_text.format(lcol, 'original'))
                    elif rcol > -1 and rcol not in range(len(new_table[0])):
                        column_errors.append(err_text.format(rcol, 'new'))
                    else:
                        temp_cols.append((lcol, rcol, type))
                if not temp_cols:
                    del kwargs['columns']
                else:
                    kwargs['columns'] = temp_cols
            #Check the columns received; exclude and write to error log if any are not valid
        if 'columns' not in kwargs:  #cannot use else because want to catch above deleted cases
            #Prompt the user to select the columns wanted
            kwargs['columns'] = _sel_compare_cols(orig_table, new_table, **kwargs)
            #Update kwargs['columns'] in history
            _remove_keyword_argument_from_last_command('columns')
            _add_kwarg_to_last_command('columns', kwargs['columns'])
            #Translate columns selected to number indices if needed
            if col_mode == 'NAME':
                kwargs['columns'] = _check_convert_text_cols(orig_table, new_table,
                                                             kwargs['columns'], kwargs['strip'],
                                                             column_errors)

    ret_dict = reconcile(orig_table, new_table, **kwargs)
    if column_errors:
        ret_dict['Column Errors'] = column_errors
    print('Result of data_check assigned to variable {}'.format(ass_var))
    return ret_dict
data_recon.desc = 'Guided fn to reconcile()'

def _square_tables(left, right, fill_char=''):
    '''function for reconcile(): forcibly makes line length equal
       based on first line of each table, padding or trimming as 
       necessary'''
    b_warn = 'Warning: line {} in {} table was padded with blanks'
    t_warn = 'Warning: line {} in {} table was trimmed for length'
    for index, table in enumerate([left, right]):
        length = len(table[0])
        for ind, line in enumerate(table[1:], 1):
            if len(line) == length:
                continue
            elif len(line) < length:
                print(b_warn.format(\
                    ind, 'right' if index else 'left'))
                table[ind] += [fill_char] * (length - len(line))
            else:
                print(t_warn.format(\
                    ind, 'right' if index else 'left'))
                table[ind] = table[ind][:length]
    return left, right

def _add_key_info_to_stats(ret_stats, key_info):
    '''function for reconcile(): append key_info to ret_stats table'''
    ret_stats.append([''])
    ret_stats.append(['KEY INFORMATION'])
    ret_stats.append([''])
    ret_stats.append(['Category', 'Description', 'Number found', 'Keys'])
    ret_stats.append(['A', '1:1 found in original and new tables', \
                      len(key_info['A']), '; '.join([str(key) for key in key_info['A']])])
    ret_stats.append(['B', 'unique in original; not found in new table', \
                      len(key_info['B']), '; '.join([str(key) for key in key_info['B']])])
    ret_stats.append(['C', 'not found in original; unique in new table', \
                      len(key_info['C']), '; '.join([str(key) for key in key_info['C']])])
    ret_stats.append(['D', 'non-unique in original; unique in new table', \
                      len(key_info['D']), '; '.join([str(key) for key in key_info['D']])])
    ret_stats.append(['E', 'unique in original; non-unique in new table', \
                      len(key_info['E']), '; '.join([str(key) for key in key_info['E']])])
    ret_stats.append(['F', 'non-unique in both original and new tables', \
                      len(key_info['F']), '; '.join([str(key) for key in key_info['F']])])
    ret_stats.append(['G', 'non-unique in original; not found in new table', \
                      len(key_info['G']), '; '.join([str(key) for key in key_info['G']])])
    ret_stats.append(['H', 'not found in original; non-unique in new table', \
                      len(key_info['H']), '; '.join([str(key) for key in key_info['H']])])
    ret_stats.append([''])

def in_tolerance(left, right, tolerance):
    '''Returns True if the left and right variables are within the tolerance level set.
       raises exception if tolerance outside of range 0...1
       Returns False if either operand is not numeric'''
    if tolerance >= 1 or tolerance < 0:
        raise Exception('in_tolerance() called with tolerance outside of range 0...1. Aborting.')
    if not ( isinstance(left, (int, float)) and isinstance(right, (int, float))):
        return False
    if 0 in (left, right):
        return left == right
    if not (left < 0) == (right < 0): #test for opposite sign
        return False
    (left, right) = (-left, -right) if left < 0 else (left, right)
    (upper, lower) = (left, right) if left > right else (right, left)
    return (upper * (1-tolerance) <= lower) or (lower * (1 + tolerance) >= upper)
in_tolerance.desc = 'Evaluare data points in a tolerance band'

def reconcile(orig_table, new_table, **kwargs):
    '''Compare two tables, both with headers, to:
    1) detect added/deleted/renamed/non-unique header names
    2) detect added/deleted/non-unique records
    3) detect point changes in data records
    and output an OrderedDict of tables:
    a) 'detail': detail view of data changes
    b) 'duplicates in original': table of duplicated original records (non-unique keys)
    c) 'duplicates in new': table of duplicated new records (non-unique keys)
    d) 'summary': summary statistics of data changes
    e)*** 'original': original table as modified acc. to script (e.g. strip, etc)
    f)*** 'new': new table as modified acc. to script (e.g. strip, etc)
    INPUTS as kwargs:
    strip: whether to strip white space from data before comparing; default=True
    include_source_data_in_output: ***whether to return source tables (modified) as part of dict
       default=True
    match_text: text to use in detail view of result if compare is a match, default='-'
    empty_text: text to use to show that a data point started or ended empty, default = '<blank>'
    missing_col_text: text to use when a column isn't there (or is -1 in a or b),
       default = '<missing col>'
    missing_record_text: text to use when a record key is not found, default = '<missing record>'
    ambiguous_record_text: to use if a key is found more than once, default = '<ambiguous>'
    transition_text: denotes transition from orig to new, default ' --> '
    autogen_key_header_text: if row index used for key, use this text for header column name
    key_indices: (x,y) where x and y are integers representing key indices in orig,new respectively
       x, y must be in header length ranges, also can be -1 if the line index should be used
       default key_indices = (-1, -1)
    numeric_key: True if '001' should be treated the same as '1', default=True
        (alphanumeric keys treated as strings anyway)
    columns: [(a,b,c), ...] where a and b are col indices to compare and c is compare type:
       c = 0 -> text compare
       c = 1 -> numerical comparison
       default is [(0,0,0), (1,1,0), (2,2,0), ...]
       if a or b is -1, it indicates that there is no data to compare against
    tolerance: float value between 0 and 1 indicating percentage how far off it can be, default 0
    in_tolerance_text: text to be used to show that there is a match within tolerance, default '--'
    '''
    #Empty return vars to fill:
    ret_stats = []
    ret_table = []
    ret_orig_duplicates = []
    ret_new_duplicates = []

    #Get (set default if necessary) input variables from kwargs
    strip = kwargs.get('strip', True)
    include_source_data_in_output = kwargs.get('include_source_data_in_output', True)
    match_text = kwargs.get('match_text', '-')
    empty_text = kwargs.get('empty_text', '<blank>')
    missing_col_text = kwargs.get('missing_col_text', '<missing col>')
    missing_record_text = kwargs.get('missing_record_text', '<missing record>')
    ambiguous_record_text = kwargs.get('ambiguous_record_text', '<ambiguous>')
    transition_text = kwargs.get('transition_text', ' --> ')
    key_indices = list(kwargs.get('key_indices', (-1, -1)))
    autogen_key_header_text = kwargs.get('autogen_key_header_text', 'Index [Autogen]')
    numeric_key = kwargs.get('numeric_key', True)
    columns = kwargs.get('columns', None)
    tolerance = kwargs.get('tolerance', 0)
    in_tolerance_text = kwargs.get('in_tolerance_text', '--')
    if columns == None:
##        columns = [(ind, ind, 0) for ind in range(min(len(orig_table[0]), len(new_table[0])))]
        columns = []
        for index in range(max(len(orig_table[0]), len(new_table[0]))):
            columns.append((index if index < len(orig_table[0]) else -1,
                            index if index < len(new_table[0]) else -1,
                            0))

    #Prepare input tables according to strip value
    print('Preparing input tables (strip if necessary)...')
    txt_strip = lambda input: input if not isinstance(input, str) else input.strip()
    left = orig_table if not strip else [[txt_strip(item) for item in line] for line in orig_table]
    right = new_table if not strip else [[txt_strip(item) for item in line] for line in new_table]

    #Check column name uniqueness; add to statistics to be returned
    print('Analyzing column name uniqueness; adding to statistics...')
    l_u, l_n = single_col_analysis(left[0])
    r_u, r_n = single_col_analysis(right[0])
    ret_stats.append(['Original header names, unique:', ', '.join(sorted(l_u))])
    ret_stats.append(['Original header names, non-unique:', ', '.join(sorted(l_n))])
    ret_stats.append(['New header names, unique:', ', '.join(sorted(r_u))])
    ret_stats.append(['New header names, non-unique:', ', '.join(sorted(r_n))])

    #Square tables if necessary (with warning) to length of headers
    print('Squaring tables as necessary...')
    left, right = _square_tables(left, right)

    #Add key column (index) if necessary to each table, convert keys to numeric as necessary
    print('Creating key indices as necessary...')
    for index, table in enumerate([left, right]):
        if key_indices[index] == -1:
            table[0].append(autogen_key_header_text)
            for ind, line in enumerate(table[1:], 1):
                line.append(ind)
            key_indices[index] = len(table[0]) -1
        if numeric_key or -1 in kwargs.get('key_indices', (-1, -1)):
            for line in table[1:]:
                if isinstance(line[key_indices[index]], (int, float)):
                    continue
                try:
                    temp_float = float(line[key_indices[index]])
                except ValueError:
                    continue
                try:
                    temp_int = int(line[key_indices[index]])
                except ValueError:
                    line[key_indices[index]] = temp_float
                    continue
                line[key_indices[index]] = temp_int
        else:
            for line in table[1:]:
                line[key_indices[index]] = str(line[key_indices[index]])

    #Check key uniqueness (and presence) in each table
    print('Checking key uniqueness and presence in each table, adding to stats...')
    key_info = key_analysis([line[key_indices[0]] for line in left[1:]],
                            [line[key_indices[1]] for line in right[1:]])

    #Add key info to statistics output
    _add_key_info_to_stats(ret_stats, key_info)

    #Prepare tables of duplicated records
    print('Preparing tables of duplicate records, as needed...')
    ret_orig_duplicates = [left[0]] + \
                          [line for line in left[1:] \
                           if key_info['reverse'][line[key_indices[0]]] in ('D', 'F', 'G')]
    ret_new_duplicates = [right[0]] + \
                         [line for line in right[1:] \
                          if key_info['reverse'][line[key_indices[1]]] in ('E', 'F', 'H')]

    #Prepare main detail output: header
    print('Preparing header for main detail table...')
    ret_table = [['', ''], ['', '']]
    for col in columns:
        info = ['Column compare info: {}'.format(col)]
        name = ''
        if col[0] not in range(len(left[0])):
            info.append('Warning: Original column index out of range!')
            name = missing_col_text
        else:
            name = str(left[0][col[0]])
            if left[0][col[0]] in l_n:
                info.append('Warning: Original column name not unique in table!')
        if col[1] not in range(len(right[0])):
            info.append('Warning: New column index out of range!')
            if name != missing_col_text:
                name = name + transition_text + missing_col_text
        else:
            if name != str(right[0][col[1]]):
                name = name + transition_text + str(right[0][col[1]])
            if right[0][col[1]] in r_n:
                info.append('Warning: New column name not unique in table!')
        ret_table[0].append('\n'.join(info))
        ret_table[1].append(name)

    #Prepare main detail output: keys
    print('Preparing keys for main detail table...')
    # listed_keys = []
    # for l_line in left[1:]:
        # key = l_line[key_indices[0]]
        # if key not in listed_keys:
            # listed_keys.append(key)
    # for r_line in right[1:]:
        # key = r_line[key_indices[1]]
        # if key not in listed_keys:
            # listed_keys.append(key)
    #Code above refactored for speed; since order is unimportant, we can use sets.
    l_keys = {line[key_indices[0]] for line in left[1:]}
    r_keys = {line[key_indices[1]] for line in right[1:]}
    try:
        listed_keys = sorted(list(l_keys)) + sorted(list(r_keys - l_keys))
    except TypeError: #will be generated if some keys are numeric and others text
        listed_keys = list(l_keys) + list(r_keys - l_keys)

    #Prepare main detail output: column detail per key
    left_dict = {line[key_indices[0]]:line for line in left[1:]}
    right_dict = {line[key_indices[1]]:line for line in right[1:]}

    print('\n\nStarting main reconciliation...\n')
    with click.progressbar(listed_keys, fill_char='>', empty_char='-') as records:
        for key in records:
            key_cat = key_info['reverse'][key]
            line = [key, key_cat]
            l_line = left_dict.get(key, None)
            r_line = right_dict.get(key, None)
            for (l_index, r_index, comparison_type) in columns:
                if key_cat in ('A', 'B', 'E'): # left record unique
                    l_result = missing_col_text if l_index not in range(len(l_line)) else \
                               l_line[l_index] if l_line[l_index] else empty_text
                elif key_cat in ('C', 'H'): # left record missing
                    l_result = missing_record_text
                else: # key_cat in ('D', 'F', 'G') - left record (key) non-unique
                    l_result = ambiguous_record_text
                if key_cat in ('A', 'C', 'D'): # right record unique
                    r_result = missing_col_text if r_index not in range(len(r_line)) else \
                               r_line[r_index] if r_line[r_index] else empty_text
                elif key_cat in ('B', 'G'): # right record missing
                    r_result = missing_record_text
                else: # key_cat in ('E', 'F', 'H') - right record (key) non-unique
                    r_result = ambiguous_record_text
                if key_cat == 'A':
                    if comparison_type: #if numeric comparison
                        try:
                            l_result = float(l_result)
                        except ValueError:
                            pass
                        try:
                            r_result = float(r_result)
                        except ValueError:
                            pass
                    if l_result == r_result:
                        line.append(match_text)
                        continue
                    elif tolerance and in_tolerance(l_result, r_result, tolerance):
                        line.append(in_tolerance_text)
                        continue
                line.append(str(l_result) + transition_text + str(r_result))
            ret_table.append(line)

    #pack it all in and return
    ret_dict = OrderedDict()
    ret_dict['detail'] = ret_table
    ret_dict['duplicates in original'] = ret_orig_duplicates
    ret_dict['duplicates in new'] = ret_new_duplicates
    ret_dict['summary'] = ret_stats
    if include_source_data_in_output:
        ret_dict['original'] = left
        ret_dict['new'] = right
    return ret_dict
reconcile.desc = 'Reconcile 2 data tables (usually data_recon)'

def try_compare_columns(table, gui=True, **kwargs):
    '''attempts to call function compare_columns() with the parameters passed.
         If an exception is thrown, the exception text is displayed but execution is not necessarily halted.
         This allows for poorly-specified tests to be skipped, with information given to the user.
         
         The gui option will temporarily suspend the script and let the user decide whether to continue
         without the test or abort the script.  If gui==False, test is displayed on the console but no option
         is offered to the user to abort.
    SUGGESTED USAGE:
    1) compose column compare specifications either dyamically/prompted
        via compare_columns() or else via excel specification file
    2) when operationalizing the script/post save_history() step: change all
        compare_columns() function calls to try_compare_columns()
        in order to handle exceptional data constellations, etc., more elegantly
    '''
    try:
        compare_columns(table, **kwargs)
    except Exception as exc:
        exc_text = exc.__str__()
        info_text = f"{'*'*80}\n\nWhile running compare_columns() the following exception was thrown:\n\n{exc_text}\n\n"
        info_text += 'Parameters given to the function were as follows:\n\n'
        for kwarg in kwargs:
            info_text += f"    {kwarg[:20]}{kwargs[kwarg][:30]}\n"
        info_text += f"\n{'*'*80}\n"
        if gui:
            if not g_ask_okcancel(info_text, title='compare_columns(): ERROR', icon='error', default='ok', detail='Click OK to skip this compare step and continue, or Cancel to abort the whole operation (raise Exception).'):
                raise Exception(info_text)
            else:
                print(info_text)
        else:
            print(info_text)
        print('Skipping the above test and continuing with the remaining script execution...')
    return
try_compare_columns.desc = 'compare_columns(): extra exception handling'

def _try_convert_date(item, date_format):
    '''Given some data point (item) attempt to convert to a date using both a text date_format as well as
        excel date conversion from an integer.  If conversion is possible, deliver converted date in 
        datetime.datetime format.  If not, return None'''
    if isinstance(item, datetime.date):
        return item
    try:
        temp = datetime.datetime.strptime(str(item).strip(), date_format)
        return temp
    except Exception:
        pass
    try:
        if isinstance(item, str):
            item = item.strip()
        temp = int(item)
        assert temp == float(item)
        return datetime.datetime.fromordinal(datetime.datetime(1900, 1, 1).toordinal() + temp -2)
    except Exception:
        pass
    return None


def _detect_blank(item):
    '''given a data point, return True if it is None or empty string or string with whitespace only, False otherwise'''
    if item is None:
        return True
    if not isinstance(item, str):
        return False
    if not item.strip():
        return True
    return False

def compare_columns(table, **kwargs):
    '''given a list of lists table, compare twp columns and add column with result of comparison:
           changes the original table by adding a column, but does not return anything.
    Arguments possible:
    header_row         (default True)   - whether there is a header_row  <- REMOVED!!
    header_row_index   (default 0)      - row index of the header line
    column_select_mode (default "name", alternative "index") - whether to compare based on the column name or position
    first_col          (no defauilt)    - the first column (name or index according to column_select_mode) to compare
    second_col         (no default)     - the second column (name or index according to column_select_mode) to compare
    compare_type       (default "text", alternative "numerical") whether to regard the data as text ot numerical data
    conv_text_to_num   (default False)  - if a numerical test is run on a text object, try to convert it to t number
    require_nonblank   (default False)  - if a text comparison, does the test fail if both are blank?
    case_sensitive     (default True)   - if a text comparison, does the case have to match, or just the letters?
    require_nonzero    (default False)  - if a numerical comparison, does the test fail if both are zero?
    *tolerance         (default 0)      - if numerical, allow for passing (PASS*) if the values are not exactly equal but close
                                        - for a 10% tolerance, use 0.1 as value.
                                        - tolerance must be a positive number less than 1, or it may be 0.
                                        - tolerance is calculated in both directions:
                                          PASS if EITHER smaller * (1+tolerance) >= larget OR larger*(1-tolerance) <= smaller
    strip_text_fields  (default False)  - whether to remove leading and trailing white space from text fields before comparing
    pass_text          (default "PASS") - the text to add when the values are the same
    error_text         (default "ERROR")- the text to use when e.g. a numerical check has text inputs
    fail_text          (default "FAIL") - the text to use when a check fails
    fail_text_blank    (default "ALL BLANK") - the text to use when require_nonblank is True and all are blank
    fail_text_nonzero  (default "ALL ZERO") - the text to use when require_nonzero is True and all are zero
    fail_detail        (defailt False)  - whether to include detail on the failure in the result
                                        - if True, instead of "{fail_text}" alonw you have "{fail_text}: {first_val} -> {second_val}" 
    new_col_name       (default auto)   - name to assign to new check column, if a header is present
                                        - (default is autocalculated based on first_col, second_col names)
    *first_col_conv     (default None)   - (numerical only) if a string is provided, that operation is performed
                                           on the first_col data prior to comparidon (e.g. "*-1")
    
    *STARRED items not subject to prompting; will be processed if given bot not explicitly required if not given
    
    NOT implemented, possible future implementation: 
        
    const_compare      (default False)  - whether to compare a constant to the second column, rather than the first column value
                                        - (if True, then no first_col will be set, resp. it will be ignored)
    const              (default None)   - the value to use to compare to the second column value, if const_compare is True
                                        - (if const_compare is False, this will be ignored/unused)

    '''
    error_condition = '' #Replaces some exceptions; allows for reporting errors like missing columns as part of results
    
    # Check all inputs and prompt where needed; also sanity checks on the inputs
    if not isinstance(table, list):
        raise Exception('compare_columns(): table passed to function is not a list object. Aborting.')
    # header_row = _kwarg_parse_prompt_bool("header_row", prompt='{} (does header row exist?) is < {} >. OK?', default=True, **kwargs)
    # if header_row:
        # if 'header_row_index' not in kwargs:
            # print('First ten rows (truncated):')
            # for index, row in enumerate(table[:10]):
                # print(f'  {index}:  {"|".join([str(item) for item in row])}'[:60])
        # header_row_index = _kwarg_parse_prompt_num('header_row_index', prompt='Which row contains the header (zero-indexed)?: ', default_val=0, allow_decimal=False, allow_neg=False, **kwargs)
        # if len(table) <= header_row_index:
            # raise Exception(f'compare_columns(): CRITICAL ERROR: table has insufficient content (table length {len(table)} and declared header row {header_row_index})')
        # else:
            # data = table[header_row_index:]
    # else:
        # if len(table) < 1:
            # raise Exception(f'compare_columns() CRITICAL ERROR: table has insufficient content (table length {len(table)})')
        # else:
            # data = table
    if len(table) < 2:
        raise Exception(f'compare_column() CRITICAL ERROR: table has insufficient content (table length {len(table)})')
    else:
        data = table
    #End re-writing header stuff
    if len(set([len(row) for row in data])) > 1:
        raise Exception('compare_columns() CRITICAL ERROR: table data rows have different lengths. Aborting.')
    column_select_mode = _kwarg_parse_prompt_list('column_select_mode', ['name', 'index'], **kwargs)
    if column_select_mode not in ['name', 'index']:
        raise Exception(f'compare_columns() CRITICAL ERROR: column_select_mode should be either "name" or "index" - Aborting.')
    cols = [-1, -1]
    if column_select_mode == 'name':
        hdr = {item:index for index, item in enumerate(data[0])}
        for index, which_col in enumerate(['first_col', 'second_col']):
            if which_col in kwargs:
                col_name = kwargs[which_col]
                if col_name not in hdr:
                    #raise Exception...
                    if error_condition:
                        error_condition += '\n'
                    error_condition += f'SPECIFICATION ERROR: column name specified ("{col_name}") not found in table provided.'
                    print(f'compare_columns() SPECIFICATION ERROR WARNING: column name specified ("{col_name}") not found in table provided.')
                elif len([item for item in data[0] if item == col_name]) > 1:
                    #raise Exception...
                    if error_condition:
                        error_condition += '\n'
                    error_condition +=f'SPECIFICATION ERROR: column name specified ("{col_name}") is not unique in the table provided.'
                    print(f'compare_columns() SPECIFICATION ERROR WARNING: column name specified ("{col_name}") is not unique in the table provided.')
                else:
                    cols[index] = hdr[col_name]
            else:
                cols[index] = ask_select_column_index(data, prompt=f'Select the column to compare <{which_col}>:')
                col_name = data[0][cols[index]]
                print(f'For <{which_col}> you have selected "{col_name}"')
                if len([item for item in data[0] if item == col_name]) > 1:
                    #raise Exception...
                    if error_condition:
                        error_condition += '\n'
                    error_condition += f'SPECIFICATION ERROR: column name specified ("{col_name}") is not unique in the table provided.'
                    print(f'compare_columns() SPECIFICATION ERROR WARNING: column name specified ("{col_name}") is not unique in the table provided.')
                _add_kwarg_to_last_command(which_col, _quoted(col_name), fn_name='compare_columns')
    else: #column_select_mode == 'index'
        for index, which_col in enumerate(['first_col', 'second_col']):
            if which_col in kwargs:
                col_idx = kwargs[which_col]
                if col_idx not in range(len(data[0])):
                    #raise Exception...
                    if error_condition:
                        error_condition += '\n'
                    error_condition += f'SPECIFICATION ERROR: column index specified ("{col_idx}") beyond bounds of table provided.'
                    print(f'compare_columns() SPECIFICATION ERROR WARNING: column index specified ("{col_idx}") beyond bounds of table provided.')
                else:
                    cols[index] = col_idx
            else:
                cols[index] = ask_select_column_index(data, prompt=f'Select the column to compare <{which_col}>:')
                print(f'For <{which_col}> you have selected "{cols[index]}"')
                _add_kwarg_to_last_command(which_col, cols[index], fn_name='compare_columns')
    compare_type = _kwarg_parse_prompt_list('compare_type', ['text', 'numerical', 'date'], **kwargs)
    if compare_type not in ['text', 'numerical', 'date']:
        #raise Exception...
        if error_condition:
            error_condition += '\n'
        error_condition += f'SPECIFICATION ERROR: compare_type (goven as "{compare_type}") should be either "text" or "numerical" or "date"'
        print(f'compare_columns() SPECIFICATION ERROR WARNING: compare_type (goven as "{compare_type}") should be either "text" or "numerical" or "date"')
    if compare_type == 'text':
        require_nonblank = _kwarg_parse_prompt_bool('require_nonblank', default_val=False, prompt='{} (test fail if both data points blank) is < {} >. OK?', **kwargs)
        case_sensitive = _kwarg_parse_prompt_bool('case_sensitive', default_val=True, prompt='{} (eliminate leading/trailing whitespace before comparing) is < {} >. OK?', **kwargs)
        strip_text_fields = _kwarg_parse_prompt_bool('strip_text_fields', default_val=False, prompt='{} (eliminate leading/trailing whitespace before comparing) is < {} >. OK?', **kwargs)
    elif compare_type == 'date':
        if 'convert_dates' not in kwargs:
            convert_dates = _kwarg_parse_prompt_bool('convert_dates', prompt='{} (try to convert dates from text format?) is < {} >. OK?', **kwargs)
        else:
            convert_dates = kwargs.get('convert_dates', False)
        if convert_dates and ('first_date_format' not in kwargs):
            first_date_format = _kwarg_parse_prompt_str('first_date_format', default_val='%Y-%m-%d %H:%M:%S.%f', prompt='{} (Date format for first_col) is < {} >. OK?', min_len=2, max_len=50, **kwargs)
        else:
            first_date_format = kwargs.get('first_date_format', None)
        if convert_dates and ('second_date_format' not in kwargs):
            second_date_format = _kwarg_parse_prompt_str('second_date_format', default_val='%Y-%m-%d %H:%M:%S.%f', prompt='{} (Date format for second_col) is < {} >. OK?', min_len=2, max_len=50, **kwargs)
        else:
            second_date_format = kwargs.get('second_date_format', None)
    else:  #compare_type == 'numerical'
        require_nonzero = _kwarg_parse_prompt_bool('require_nonzero', prompt='{} (test fail if both data points zero?) is < {} >. OK?', **kwargs)
        conv_text_to_num = _kwarg_parse_prompt_bool('conv_text_to_num', prompt='{} (try to convert text items to numbers?) is < {} >. OK?', **kwargs)
        first_col_conv = kwargs.get('first_col_conv', None) #No prompting for this one.
        tolerance = kwargs.get('tolerance', 0) #no prompting
        if tolerance < 0 or tolerance >= 1:
            g_conditional_stop('compare_columns(): tolerance level given is outside of acceptable range (must be positive number less than 1)',
                               consequences='If you continue, the tolerance for this comparison will be removed (set to 0)',
                               title='compare_columns(): invalid tolerance for numerical compare.')
            tolerance = 0
    pass_text = _kwarg_parse_prompt_str('pass_text', default_val='PASS', prompt='{} (Text when test passes.) is < {} >. OK?', min_len=1, max_len=20, **kwargs)
    pass_in_tolerance_text = f'{pass_text} (WITHIN TOLERANCE)'
    error_text = _kwarg_parse_prompt_str('error_text', default_val='ERROR', prompt='{} (Text when test cannot run (e.g. text in number field).) is < {} >. OK?', min_len=1, max_len=20, **kwargs)
    fail_text = _kwarg_parse_prompt_str('fail_text', default_val='FAIL', prompt='{} (Text when test fails.) is < {} >. OK?', min_len=1, max_len=20, **kwargs)
    if compare_type == 'text':
        if require_nonblank:
            fail_text_blank = _kwarg_parse_prompt_str('fail_text_blank', default_val='FAIL_ALL_BLANK', prompt='{} (Text when test fails because all points blank.) is < {} >. OK?', min_len=1, max_len=20, **kwargs)
    elif compare_type == 'numerical':
        if require_nonzero:
            fail_text_nonzero = _kwarg_parse_prompt_str('fail_text_nonzero', default_val='FAIL_ALL_ZERO', prompt='{} (Text when test fails because all points zero.) is < {} >. OK?', min_len=1, max_len=20, **kwargs)
    else: #compare_type == 'date'
        pass
    fail_detail = _kwarg_parse_prompt_bool('fail_detail', default_val=False, prompt='{} (add detail to result column in case of fail) is < {} >. OK?', **kwargs)
    new_col_name = _kwarg_parse_prompt_str('new_col_name', default_val=f'COMPARE: {data[0][cols[0]]} | {data[0][cols[1]]}', prompt='{} (Text to use as new column header name.) is < {} >. OK?', min_len=1, max_len=None, **kwargs)

    # Check on table size before continuing, log width
    row_lengths = set([len(row) for row in data])
    if len(row_lengths) > 1:
        g_conditional_stop(f'Unequal row lengths detected: {sorted(list(row_lengths))}',
                           title='compare_columns(): UNABLE TO PROCEED due to INCONSISTENT ROW LENGTHS.',
                           consequences='If you click OK, the script will proceed without performing the column comparison.')
        return
    
    #If execution continues here, the rows are the same length
    row_length = list(row_lengths)[0]
    
    #Main evaluation
    try:
        data[0].append(new_col_name)
        for row_index, row in enumerate((data[1:] if header_row else data), start=1):
            if any([len(row) <= cols[0], len(row) <= cols[1]]):
                raise Exception(f'compare_columns(): CRITICAL ERROR (Very strange) in data line {row_index}: row too short, column not readable')
                # This should never arise because of previous check but in case of a very strange data constellation, leave it there.
            if error_condition:
                row_append(error_condition)
                continue
            data_points = [row[col] for col in cols]
            if compare_type == 'text':
                if not all([(isinstance(point, str) or point is None) for point in data_points]):
                    if fail_detail:
                        row.append(f'{error_text}: Non-string data: {str(data_points[0])} ({type(data_points[0])}) -> {str(data_points[1])} ({type(data_points[1])})')
                    else:
                        row.append(error_text)
                    continue
                if strip_text_fields:
                    data_points = [(point if point is None else point.strip()) for point in data_points]
                if not case_sensitive:
                    data_points = [(point if point is None else point.lower()) for point in data_points]
                if data_points[0] == data_points[1]: #strings equal
                    if data_points[0] in ('', None) and require_nonblank:
                        row_append(fail_text_blank)
                    else:
                        row.append(pass_text)
                    continue
                else: #test fail
                    if fail_detail:
                        row.append(f'{fail_text}: {data_points[0]} -> {data_points[1]}')
                    else:
                        row.append(fail_text)
                    continue
            elif compare_type == 'date':
                to_str = lambda dt: f'{dt.year}-{dt.month}-{dt.day}'
                if convert_dates:
                    data_points = [_try_convert_date(data_points[0], first_date_format),
                                   _try_convert_date(data_points[1], second_date_format)]
                    if None in data_points and fail_detail:
                        row.append(f'{error_text}: (date compare conversion fail) {str(data_points[0])} ({type(data_points[0])}) -> {str(data_points[1])} ({type(data_points[1])})')
                        continue
                if any([not isinstance(data_points[0], datetime.date), not isinstance(data_points[1], datetime.date)]):
                    if fail_detail:
                        row.append(f'{error_text}: (date compare fail) {str(data_points[0])} ({type(data_points[0])}) -> {str(data_points[1])} ({type(data_points[1])})')
                    else:
                        row.append(error_text)
                    continue
                if all([data_points[0].year == data_points[1].year, data_points[0].month == data_points[1].month, data_points[0].day == data_points[1].day]):
                    row.append(pass_text)
                    continue
                else:
                    if fail_detail:
                        row.append(f'{fail_text}: {to_str(data_points[0])} -> {to_str(data_points[1])}')
                    else:
                        row.append(fail_text)
                    continue
            else: #compare_type == 'numerical'
                if not all([isinstance(point, (int, float)) for point in data_points]):
                    if conv_text_to_num:
                        success = True
                        for index in (0, 1):
                            if isinstance(data_points[index], (int, float)):
                                pass
                            elif isinstance(data_points[index], str):
                                try:
                                    data_points[index] = float(data_points[index].strip())
                                except ValueError:
                                    success = False
                            else:
                                success = False
                        if not success:
                            if fail_detail:
                                row.append(f'{error_text}: (numerical compare conversion fail) {str(data_points[0])} ({type(data_points[0])}) -> {str(data_points[1])} ({type(data_points[1])})')
                            else:
                                row.append(error_text)
                            continue
                    else:
                        if fail_detail:
                            row.append(f'{error_text}: (numerical compare fail) {str(data_points[0])} ({type(data_points[0])}) -> {str(data_points[1])} ({type(data_points[1])})')
                        else:
                            row.append(error_text)
                        continue
                if first_col_conv:
                    conv_fn = lambda data_in: eval(str(first_col_conv).format(x=data_in))
                    try:
                        data_points[0] = conv_fn(data_points[0])
                    except Exception as exc:
                        if fail_detail:
                            row.append(f'{error_text}: first_col_conv failure: {str(exc)}')
                        else:
                            row.append(error_text)
                        continue
                if in_tolerance(data_points[0], data_points[1], tolerance): #values equal or in tolerance band
                    if require_nonzero and data_points[0] == 0:
                        row.append(fail_text_nonzero)
                        continue
                    elif data_points[0] != data_points[1]: # in tolerance band but not exactly equal
                        if fail_detail:
                            row.append(f'{pass_in_tolerance_text}: {str(data_points[0])} -> {str(data_points[1])}')
                        else:
                            row.append(pass_in_tolerance_text)
                    else: #exactly equal
                        row.append(pass_text)
                        continue
                else: #values not equal
                    if fail_detail:
                        row.append(f'{fail_text}: {data_points[0]} -> {data_points[1]}')
                    else:
                        row.append(fail_text)
                    continue
    except Exception as exc:
        print(f'\n{"*"*80}\ncompare_columns(): FATAL ERROR: \n\n{str(exc)}\n\nUNDOING CHANGES TO DATA TABLE...\n{"*"*80}\n\n')
        #
        for line in data:
            while(len(line) > row_length):
                _ = line.pop()
        raise exc
    print(f'compare_columns(): Completed comparison for "{new_col_name}"')
    return
compare_columns.desc = 'Guided; adds col with result'
    
def pre_process_specs_detail(specs_detail):
    '''takes in a table of specs, parses to look for entries in the form of
    **CONST type value
    and returns an OrderedDict with keys as column names
    (matching **CONST entries) and values as the actual values to use
    type may be str, int, float, bool
    
    EXAMPLE USAGE: (specs_path has Excel with columns which are keyword parameters for column_compare())
                   (first_col may also contain "**CONST <type> <value>" like "**CONST str Hello world")
    >>> standard_specs = {'header_row':True, 'header_row_index':0, 'column_select_mode':'name', 'pass_text':'PASS', 'fail_text':'FAIL', 'fail_text_blank':'FAIL: ALL BLANK', 'fail_text_nonzero':'FAIL: ALL ZERO'}
    >>> specs_file_path = g_sel_file(title='SELECT the file containing the COMPARE SPECS', filetypes=['Excel Files', ('.xlsx')])
    >>> specs_content = data_import(file_path=specs_file_path)
    >>> if COLUMN_SPECS_SHEETNAME not in specs_content: raise Exception('...')
    >>> specs_detail = specs_content[COLUMN_SPECS_SHEETNAME]
    >>> specs_material_columns = [index for index, item in enumerate(specs_detail[0]) if item]
    >>> specs_detail = [[row[index] for index in specs_material_columns] for row in specs_detail if row[2]]
    >>> #Pre-processing of specs_detail file to convert **CONST items in first_col to actual columns in input file
    >>> const_cols = pre_process_specs_detail(specs_detail)
    >>> for const in const_cols.keys(): res['joined'][0].append(const); _ = [line.append(const_cols[cibst]) for line in res['joined'][1:]]
    >>> specs = []
    >>> for row in specs_detail[1:]: specs.append(dict(zip(specs_detail[0], row)))
    >>> for spec in specs: spec.update(standard_specs)
    >>> for spec in specs: try_compare_columns(res['joined'], **spec)
    '''
    ret_dict = collections.OrderedDict()
    if not specs_detail: return ret_dict
    specs_hdr = {item:index for index, item in enumerate(specs_detail[0])}
    if 'first_col' not in specs_hdr.keys(): raise Exception('pre_process_specs_detail(): Expected to find a column for "first_col" in the specs file.  Not found.  Aborting.')
    f_idx = specs_hdr['first_col']
    encoded_consts = [line[f_idx] for line in specs_detail[1:] if line[f_idx][:7] == '**CONST']
    for encoded_const in encoded_consts:
        unpacked = [item.strip() for item in encoded_const.split(' ')]
        if unpacked[1] == 'str':
            str_start = encoded_const.find(unpacked[2])
            ret_dict[encoded_const] = encoded_const[str_start:]
        elif unpacked[1] == 'bool':
            if unpacked[2].lower() in ('true', 'y', 'yes', 't', '1'):
                ret_dict[encoded_const] = True
            elif unpacked[2].lower() in ('false', 'n', 'no', 'f', '0'):
                ret_dict[encoded_const] = False
            else:
                raise Exception(f'pre_process_specs_detail(): Error with **CONST definition in specs file. bool type declared but value not recognized: "{unpacked[2]}" ..Aborting.')
        elif unpacked[1] == 'int':
            try:
                ret_dict[encoded_const] = int(unpacked[2])
            except Exception as exc_text:
                raise Exception(f'pre_process_specs_detail(): Error with **CONST definition in specs file. int type could not be converted from text string: {unpacked[2]}.\n\n Error: {str(exc_text)}')
        elif unpacked[1] == 'float':
            try:
                ret_dict[encoded_const] = float(unpacked[2])
            except Exception as exc_text:
                raise Exception(f'pre_process_specs_detail(): Error with **CONST definition in specs file. float type could not be converted from text string: {unpacked[2]}.\n\n Error: {str(exc_text)}')
        else:
            raise Exception(f'pre_process_specs_detail(): Error with **CONST definition in specs file. format is "**CONST <type> <value>" where type must be str, int, float, or bool. Received {unpacked[2]}.. Aborting.')
    return ret_dict
pre_process_specs_detail.desc = 'Get specs ready for compare_columns()'

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
               for index in range(1, readline.get_current_history_length())]

    filepath = g_sel_file_to_write(title='TED TOOLKIT: Select file to save session as script',
                                   filetypes=[('Python files', ('*.py')), ('All Files', ('*.*'))])
    if filepath[-3:] != '.py':
        filepath = filepath + '.py'
    fil = open(filepath, 'w')
    template = '# TED_TOOLKIT-based (v{}) Python script, autogen by {} at UTC:{}\n\n'
    template = template.format(VERSION, get_current_user(), get_utc_timestamp())
    toolkit_check = [
        'import os, sys, time\n',
        f'originating_version = "{VERSION}"\n',
        'if os.path.basename(sys.argv[0]) != "ted_toolkit.py": raise Exception("\\n\\n********This python file must be run from Ted\'s Toolkit. Canceling.********\\n")\n',
        'if VERSION != originating_version: print(f"\\n*********************\\nWARNING: This toolkit script created with toolkit version {originating_version} but is being run in version {VERSION}.\\n*********************\\n\\n"); time.sleep(5)',
        '\n'
        ]
    fil.writelines([template]+history+['\n\n'])
    fil.close()
    print('History saved to: \n{}'.format(filepath))
    open_in_notepad = ask_yn(default='y', prompt='Do you want to open in Notepad?')
    if open_in_notepad:
        nppp_path = _find_notepad_pp()
        if nppp_path:
            subprocess.Popen([nppp_path, filepath])
        else:
            subprocess.Popen(['notepad.exe', filepath])
    return
save_history.desc = 'Save interactive session to edit/re-run'

def beep():
    '''make a short beep (e.g. to let the user know that something is finished)'''
    print('\a', end='')
    return
beep.desc = 'Windows chime'

def help_all():
    '''print info for all public functions available in toolkit'''
    global DYNAMIC_IMPORTS
    MAIN_SPACE = 50
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
            divider = '...' if len(func)>MAIN_SPACE else '   '
            desc = getattr(eval(func_name), 'desc', '--no short description--')
            print(f'{func[:-1][:MAIN_SPACE]:<50}{divider} {desc:<20}')
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
    get_name = lambda func: func[:func.find('(')]
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
    return
save_function_reference.desc = 'Export Toolkit Function Reference'

def help_vars():
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
            except:
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
    return
help_vars.desc = 'Show all current variables of common types'

LAST_LINE_ATTEMPTED = -1

def _run_script(ARGS, **kwargs):
    '''takes saved history and re-runs it'''
    global LAST_LINE_ATTEMPTED
    cntd = kwargs.get('continued', False)
    if cntd:
        print(f'Continuing execution of Python (tookit) script from last line {LAST_LINE_ATTEMPTED + 1}\n\nTo cancel, press Ctrl+c.\n')
    else:
        _ = os.system('cls')
        print('\nExecuting recorded history from prior Python session\n\n'+\
              'To cancel, press Ctrl+c.\n')
    py_file = ARGS[0]
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

if __name__ == '__main__':
    # for usage as a main module
    ARGS = sys.argv[1:]
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


