'''tedtoolkit.tables.columns - single-column extraction and Excel column-letter helpers.'''

from tedtoolkit.history import _check_assignment, _add_kwarg_to_last_command
from tedtoolkit.validation import _check_var_table
from tedtoolkit.prompts import ask_yn, ask_select_column_index


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
