'''tedtoolkit.tables.join - guided key-based table join.'''

import collections

from tedtoolkit.history import _check_assignment, _add_kwarg_to_last_command, _quoted
from tedtoolkit.validation import _check_var_table, _is_list_of_lists
from tedtoolkit.prompts import ask_select, ask_select_column_index, _kwarg_parse_prompt_bool, _kwarg_parse_prompt_str
from tedtoolkit.util import beep
from tedtoolkit.tables.columns import _decimate
from tedtoolkit.tables.reconcile import key_analysis


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
    suppress_key_table_return = kwargs.get('suppress_key_table_return', False)
    no_match_text = kwargs.get('no_match_text', '-no match-')
    ambiguous_text = kwargs.get('ambiguous_text', '-ambiguous-')
    join_error_text = kwargs.get('join_error_text', '-join error-')

    if join_type == 'base':
        unm_prompt = 'Currently making table of unmatched records from joined: < {1} >. OK?'
        incl_unm = _kwarg_parse_prompt_bool('include_unmatched_ext_in_ret_val', default_val='True',
                                           prompt=unm_prompt, **kwargs)
    else:
        incl_unm = False
    unm_name = None
    if incl_unm:
        _prompt = 'Current sheet name for unmatched report (var <{}>) is <{}>. Is that ok?'
        unm_name = _kwarg_parse_prompt_str('unmatched_ext_sheet_name', 'unmatched', prompt=_prompt,
                                          **kwargs)

    ret_dict = _data_join_core(base_table, ext_table, join_type, base_key_col, ext_key_col,
                               neg_list, neg_key_col, headers, base_hdr_tag, ext_hdr_tag,
                               suppress_key_table_return, no_match_text, ambiguous_text,
                               join_error_text, incl_unm, unm_name)
    print('\nJOIN: Done. Saved to variable {}'.format(ass_var))
    beep()
    return ret_dict
data_join.desc = 'Prompted list of lists join'


def _data_join_core(base_table, ext_table, join_type, base_key_col, ext_key_col, neg_list,
                    neg_key_col, headers, base_hdr_tag, ext_hdr_tag, suppress_key_table_return,
                    no_match_text, ambiguous_text, join_error_text,
                    include_unmatched_ext_in_ret_val, unmatched_ext_sheet_name):
    '''Pure join logic (no prompting/history side effects). Takes every value the
    interactive wrapper would otherwise have prompted for, already resolved.
    (Extracts key columns inline rather than via sel_col()/extract_column_from_table(),
    since those call _check_assignment() as a side effect - not appropriate from a pure core.)'''
    def _col(table, col, has_headers):
        return [line[col] for line in (table[1:] if has_headers else table)]
    base_keys = _col(base_table, base_key_col, headers)
    ext_keys = _col(ext_table, ext_key_col, headers)
    if neg_list:
        neg_keys = _col(neg_list, neg_key_col, headers)
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
    if not suppress_key_table_return:
        ret_dict['all_keys'] = [['Key Analysis Result', 'Key']]
        for key_cat in key_dict:
            for key in key_dict[key_cat]:
                if key == 'reverse':
                    continue
                ret_dict['all_keys'].append([key_cat, key])

    base_blank = [no_match_text] * len(base_table[0])
    ext_blank = [no_match_text] * len(ext_table[0])
    base_ambig = [ambiguous_text] * len(base_table[0])
    ext_ambig = [ambiguous_text] * len(ext_table[0])

    joined = []
    if headers:
        if None in base_table[0]:
            print('data_join(): WARNING: Empty header cells encountered in *original* table header.')
            base_table[0] = ['' if item is None else item for item in base_table[0]]
        if None in ext_table[0]:
            print('data_join(): WARNING: Empty header cells encountered in *joined* table header.')
            ext_table[0] = ['' if item is None else item for item in ext_table[0]]
        joined.append(['Key', 'Key Code'] + [base_hdr_tag + item for item in base_table[0]] + \
                      [ext_hdr_tag + item for item in ext_table[0]])

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

    if include_unmatched_ext_in_ret_val:
        print('\nJOIN: Creating table of unused external table records')
        unmatched = key_dict['C'] + key_dict['E'] + key_dict['F'] + key_dict['H']
        ret_dict[unmatched_ext_sheet_name] = [line for index, line in enumerate(ext_table)\
                              if (index == 0 and headers) or line[ext_key_col] in unmatched]
        print(' ...number of unmatched records: {}'.format(str(len(unmatched))))
        if len(unmatched) == 0:
            ret_dict[unmatched_ext_sheet_name].append(['no unmatched records found in joined table'])

    ret_dict['joined'] = joined
    return ret_dict
