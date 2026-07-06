'''tedtoolkit.tables.aggregate - guided pivot/aggregation engine and its inverse.'''

import collections

from tedtoolkit.history import input, _quoted, _check_assignment, _add_kwarg_to_last_command
from tedtoolkit.validation import _check_var_table
from tedtoolkit.prompts import (ask_yn, ask_select, ask_select_column_index,
                                 _kwarg_parse_prompt_bool, _kwarg_parse_prompt_str)


def _review_options(options_in, table_in):
    '''takes in dict of options, prompts the user to modify according to type, or confirm'''
    CAT_PROMPT = 'Which column to use as category? \n(each value found will get own column) >> '
    for key in options_in:
        if key in ['cat_key_col']:
            continue
        if isinstance(options_in[key], bool):
            while ask_yn(default='n', prompt='Current value of {} is <{}>. Change it?'.format(
                key, str(options_in[key]))):
                options_in[key] = not options_in[key]
            continue
        if isinstance(options_in[key], str):
            while ask_yn(default='n', prompt='Current value of {} is <{}>. Change it?'.format(
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
    Inverse of data_aggregate()

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
