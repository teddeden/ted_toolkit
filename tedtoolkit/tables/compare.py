'''tedtoolkit.tables.compare - guided column-vs-column comparison (text/numeric/date).'''

import collections
import datetime

from tedtoolkit.history import _add_kwarg_to_last_command, _quoted
from tedtoolkit.prompts import (ask_select_column_index, _kwarg_parse_prompt_bool,
                                 _kwarg_parse_prompt_list, _kwarg_parse_prompt_str,
                                 _kwarg_parse_prompt_num)
from tedtoolkit.gui.messagebox import g_ask_okcancel, g_conditional_stop
from tedtoolkit.tables.reconcile import in_tolerance


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
    header_row         (default True)   - whether there is a header_row
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
    header_row = _kwarg_parse_prompt_bool('header_row', default_val='True',
        prompt='{} (does header row exist?) is < {} >. OK?', **kwargs)
    if header_row:
        if 'header_row_index' not in kwargs:
            print('First ten rows (truncated):')
            for index, row in enumerate(table[:10]):
                print(f'  {index}:  {"|".join([str(item) for item in row])}'[:60])
        header_row_index = _kwarg_parse_prompt_num('header_row_index',
            prompt='Which row contains the header (zero-indexed)?: ', default_val=0,
            allow_decimal=False, allow_neg=False, **kwargs)
        if len(table) <= header_row_index:
            raise Exception(f'compare_columns(): CRITICAL ERROR: table has insufficient content '
                             f'(table length {len(table)} and declared header row {header_row_index})')
        data = table[header_row_index:]
    else:
        if len(table) < 1:
            raise Exception(f'compare_columns() CRITICAL ERROR: table has insufficient content (table length {len(table)})')
        data = table
    if len(data) < (2 if header_row else 1):
        raise Exception(f'compare_column() CRITICAL ERROR: table has insufficient content (table length {len(data)})')
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

    _compare_columns_core(
        data, cols, compare_type, header_row=header_row,
        require_nonblank=require_nonblank if compare_type == 'text' else False,
        case_sensitive=case_sensitive if compare_type == 'text' else True,
        strip_text_fields=strip_text_fields if compare_type == 'text' else False,
        convert_dates=convert_dates if compare_type == 'date' else False,
        first_date_format=first_date_format if compare_type == 'date' else None,
        second_date_format=second_date_format if compare_type == 'date' else None,
        require_nonzero=require_nonzero if compare_type == 'numerical' else False,
        conv_text_to_num=conv_text_to_num if compare_type == 'numerical' else False,
        first_col_conv=first_col_conv if compare_type == 'numerical' else None,
        tolerance=tolerance if compare_type == 'numerical' else 0,
        pass_text=pass_text, error_text=error_text, fail_text=fail_text,
        fail_text_blank=fail_text_blank if compare_type == 'text' and require_nonblank else 'FAIL_ALL_BLANK',
        fail_text_nonzero=fail_text_nonzero if compare_type == 'numerical' and require_nonzero else 'FAIL_ALL_ZERO',
        fail_detail=fail_detail, new_col_name=new_col_name, error_condition=error_condition,
    )
    print(f'compare_columns(): Completed comparison for "{new_col_name}"')
    return
compare_columns.desc = 'Guided; adds col with result'


def _compare_columns_core(data, cols, compare_type, header_row=True,
                          require_nonblank=False, case_sensitive=True, strip_text_fields=False,
                          convert_dates=False, first_date_format=None, second_date_format=None,
                          require_nonzero=False, conv_text_to_num=False,
                          first_col_conv=None, tolerance=0,
                          pass_text='PASS', error_text='ERROR', fail_text='FAIL',
                          fail_text_blank='FAIL_ALL_BLANK', fail_text_nonzero='FAIL_ALL_ZERO',
                          fail_detail=False, new_col_name='COMPARE', error_condition=''):
    '''Pure decision logic (no prompting/history side effects). Mutates `data` in place
    (appends a header cell + one result cell per row) and returns the same `data` object -
    this mutate-and-return contract (not copy-and-return) is deliberate: existing/replayed
    scripts call compare_columns(table) for its side effect and reference `table` afterward
    expecting the new column to be there. On a fatal error, rolls back any partial mutation
    before re-raising, matching compare_columns()'s existing behavior exactly.

    The first_col_conv eval()-based user-transform-expression feature (numerical compare
    only) is preserved exactly: this is an intentional, documented power-user capability,
    not something to sandbox or remove.'''
    pass_in_tolerance_text = f'{pass_text} (WITHIN TOLERANCE)'
    row_length = len(data[0])
    try:
        data[0].append(new_col_name)
        for row_index, row in enumerate((data[1:] if header_row else data), start=1):
            if any([len(row) <= cols[0], len(row) <= cols[1]]):
                raise Exception(f'compare_columns(): CRITICAL ERROR (Very strange) in data line {row_index}: row too short, column not readable')
                # This should never arise because of previous check but in case of a very strange data constellation, leave it there.
            if error_condition:
                row.append(error_condition)
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
                        row.append(fail_text_blank)
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
        for line in data:
            while(len(line) > row_length):
                _ = line.pop()
        raise exc
    return data


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
