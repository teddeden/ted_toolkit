'''tedtoolkit.tables.reconcile - key analysis and two-table reconciliation/diff.

KNOWN GAP (preserved as-is from the original codebase, not invented here):
data_recon()'s col_select='LIST' path calls _sel_compare_cols() (when no
`columns` kwarg is supplied) and, in col_mode='NAME', _check_convert_text_cols()
(to translate name-based column specs to indices) - neither function is
defined anywhere in this codebase. Those two specific sub-paths of
data_recon() raise NameError; col_select='AUTO-OR'/'AUTO-AND' work fine, as
does col_select='LIST' with col_mode='POSITION' and columns already supplied
as a kwarg. This was discovered during the Phase 2 migration and is called
out rather than silently patched, since there's no reference implementation
to restore (unlike the header_row fix in tables/compare.py).
'''

import collections

import click

from tedtoolkit.history import _check_assignment, _add_kwarg_to_last_command, _remove_keyword_argument_from_last_command
from tedtoolkit.validation import _check_var_table
from tedtoolkit.prompts import ask_yn, ask_num, ask_select, _kwarg_parse_prompt_bool, _kwarg_parse_prompt_str
from tedtoolkit.tables.preview import single_col_analysis, data_preview


def key_analysis(left_keys, right_keys, negative_list=None):
    '''simple key comparison to determine uniqueness of keys in tables, what can be explained
    by negative list (if any), and anything missing'''
    if not isinstance(left_keys, list) or not isinstance(right_keys, list):
        raise Exception('keys must be passed as lists of values')
    if len(left_keys) == 0 or len(right_keys) == 0:
        raise Exception('at least one key list passed to key_analysis() empty')
    if isinstance(left_keys[0], list) or isinstance(right_keys[0], list):
        raise Exception('keys passed to key_analysis() must be in single dim lists')
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
            data_preview(orig_table, internal=True, var_name='data_recon(): ORIGINAL table')
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
            data_preview(new_table, internal=True, var_name='data_recon(): NEW table')
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
                for (lcol, rcol, cmp_type) in columns:
                    err_text = 'Column {} out of range of {} table; skipping spec.'
                    if lcol > -1 and lcol not in range(len(orig_table[0])):
                        column_errors.append(err_text.format(lcol, 'original'))
                    elif rcol > -1 and rcol not in range(len(new_table[0])):
                        column_errors.append(err_text.format(rcol, 'new'))
                    else:
                        temp_cols.append((lcol, rcol, cmp_type))
                if not temp_cols:
                    del kwargs['columns']
                else:
                    kwargs['columns'] = temp_cols
            #Check the columns received; exclude and write to error log if any are not valid
        if 'columns' not in kwargs:  #cannot use else because want to catch above deleted cases
            #Prompt the user to select the columns wanted
            # NOTE: _sel_compare_cols() is not defined anywhere in this codebase - see module
            # docstring. This path (col_select='LIST' with no columns kwarg) will raise
            # NameError, exactly as it did before this migration.
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
    if columns is None:
        columns = []
        for index in range(max(len(orig_table[0]), len(new_table[0]))):
            columns.append((index if index < len(orig_table[0]) else -1,
                            index if index < len(new_table[0]) else -1,
                            0))

    #Prepare input tables according to strip value
    print('Preparing input tables (strip if necessary)...')
    def txt_strip(val):
        return val if not isinstance(val, str) else val.strip()
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
    #Order is unimportant, so we can use sets.
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
    ret_dict = collections.OrderedDict()
    ret_dict['detail'] = ret_table
    ret_dict['duplicates in original'] = ret_orig_duplicates
    ret_dict['duplicates in new'] = ret_new_duplicates
    ret_dict['summary'] = ret_stats
    if include_source_data_in_output:
        ret_dict['original'] = left
        ret_dict['new'] = right
    return ret_dict
reconcile.desc = 'Reconcile 2 data tables (usually data_recon)'
