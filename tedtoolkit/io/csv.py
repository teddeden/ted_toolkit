'''tedtoolkit.io.csv - CSV import/export.'''

import csv
import datetime

import click
import chardet

from tedtoolkit.prompts import (_prompt_for_any_arg, _prompt_for_list_arg, _prompt_for_bool_arg,
                                 QUOTING_OPTIONS)
from tedtoolkit.validation import _is_list_of_lists
from tedtoolkit.gui.dialogs import g_sel_file, g_sel_file_to_write


def _parse_csv_args(case, **kwargs):
    '''parses and prompts for keyword arguments as needed
    case must be 'import' or 'export'
    returns updated kwargs dict'''
    file_path = kwargs.get('file_path', None)
    if file_path is None and case == 'import':
        file_path = g_sel_file(title='Import CSV data',
            filetypes=[('CSV files', ('*.csv')),
                       ('Text files', ('*.txt', '*.text'))])
    elif file_path is None and case == 'export':
        file_path = g_sel_file_to_write(title='Save As CSV',
            filetypes=[('CSV files', ('*.csv')),
                       ('Text files', ('*.txt', '*.text'))])
    if 'delim' not in kwargs:
        delim = _prompt_for_any_arg('delim', ',')
    else:
        delim = kwargs['delim']
    if 'quoting' not in kwargs:
        quoting = _prompt_for_list_arg('quoting',
            list(QUOTING_OPTIONS.keys()), default_index=1)
    else:
        quoting = kwargs['quoting']
    if 'quote_mark' not in kwargs:
        quote_mark = _prompt_for_any_arg('quote_mark', '"')
    else:
        quote_mark = kwargs['quote_mark']
    if 'encoding' not in kwargs:
        encoding = _prompt_for_list_arg('encoding',
            ['utf_8', 'ascii', 'windows-1252', 'latin-1',
            'utf_16', 'utf_32'], default_index=0)
    else:
        encoding = kwargs['encoding']
    if encoding == 'autodetect':
        print('Auto-detecting encoding...  ', end='')
        with open(file_path, 'rb') as file_in:
            temp = file_in.read()
        res = chardet.detect(temp)
        encoding = res['encoding']
        print(encoding)
        if res['confidence'] != 1:
            print(f'WARNING: Less than full confidence (1.0) in autodetected encoding: {res["confidence"]}\n\n')
    if 'line_terminator' not in kwargs:
        line_terminator = \
            _prompt_for_any_arg('line_terminator', '\n')
    else:
        line_terminator = kwargs['line_terminator']
    if 'convert_numbers' not in kwargs and case == 'import':
        convert_numbers = \
            _prompt_for_bool_arg('convert_numbers', False)
    else:
        convert_numbers = kwargs.get('convert_numbers', False)
    if 'convert_dates' not in kwargs:
        convert_dates = \
            _prompt_for_bool_arg('convert_dates', False)
    else:
        convert_dates = kwargs.get('convert_dates', False)
    if convert_dates and ('date_format' not in kwargs):
        date_format = \
            _prompt_for_any_arg('date_format',
                                '%Y-%m-%d %H:%M:%S.%f')
    else:
        date_format = kwargs.get('date_format', None)
    return {'file_path':file_path, 'delim':delim,
            'quote_mark':quote_mark, 'encoding':encoding,
            'line_terminator':line_terminator,
            'quoting':quoting, 'convert_numbers':convert_numbers,
            'convert_dates':convert_dates,
            'date_format':date_format}


def csv_export(data, **kwargs):
    '''export list of lists as csv file
    kwargs: file_path, delim for delimiter (default = ',')
    quote_mark (default = '"'), encoding (default = 'utf_8')
    line_terminator (default = '\\n')
    quoting, (default = 'QUOTE_MINIMAL')
    convert_dates - T/F option to specify non-default
        string format to be used to convert datetime objects;
        if True, date_format should be specified.'''
    kwargs = _parse_csv_args('export', **kwargs)
    if not _is_list_of_lists(data):
        raise Exception('Export CSV Failed: No content')
    return _csv_export_core(data, kwargs['file_path'], kwargs['delim'], kwargs['quote_mark'],
                            kwargs['encoding'], kwargs['line_terminator'], kwargs['quoting'],
                            kwargs['convert_dates'], kwargs['date_format'])


def _csv_export_core(data, file_path, delim, quote_mark, encoding, line_terminator, quoting,
                     convert_dates, date_format):
    '''Pure CSV-writing logic (no GUI, no prompting). All args already resolved.'''
    print('Writing CSV...\n')
    with open(file_path, 'w', encoding=encoding) as file_out:
        o_writer = \
            csv.writer(file_out, delimiter=delim,
                       quotechar=quote_mark,
                       quoting=QUOTING_OPTIONS.get(quoting,
                                           csv.QUOTE_MINIMAL),
                       lineterminator=line_terminator)
        with click.progressbar(data, fill_char='>',
                               empty_char='-') as table:
            if convert_dates:
                for line in table:
                    line_to_write = []
                    for item in line:
                        if isinstance(item, datetime.datetime):
                            line_to_write.append(item.
                                strftime(date_format))
                        else:
                            line_to_write.append(item)
                    o_writer.writerow(line_to_write)
            else:
                for line in table:
                    o_writer.writerow(line)
    print('Done.  File saved under <{}>. '.format(file_path))


def _process_line(line, convert_numbers, convert_dates,
                  date_format=None):
    '''used by csv_import to convert numbers and dates
    expecting line to be a list of strings
    convert_numbers = True if numbers should be converted
    pass string date_format to specify which format may be
    converted (will be ignored if convert_dates == False'''
    if date_format is None:
        date_format = '%Y-%m-%d %H:%M:%S.%f'
    ret_line = []
    for item in line:
        if convert_numbers:
            try:
                item = float(item)
            except ValueError:
                pass
            if isinstance(item, float):
                if item == int(item):
                    ret_line.append(int(item))
                    continue
                else:
                    ret_line.append(item)
                    continue
        #don't need an else because prev. cases continued
        if convert_dates:
            try:
                item = datetime.datetime.strptime(item,
                                                  date_format)
            except ValueError:
                pass
            except TypeError:
                pass
        ret_line.append(item)
    return ret_line


def csv_import(**kwargs):
    '''import list of lists from a csv text file
    kwargs:
    file_path (will prompt if no path given)
    delim for delimiter, default ','
    quote_mark, default = '"'
    encoding, default = 'utf_8'
    line_terminator, default = '\\n'
    convert_numbers, should numbers be converted to int or float?
                     default False
    convert_dates, should dates be detected and converted?
                   default False
    date_format, string format for date detection (string),
         default '%Y-%m-%d %H:%M:%S.%f'
         will be ignored if convert_dates == False
    quoting, (default = 'QUOTE_MINIMAL')
    '''
    kwargs = _parse_csv_args('import', **kwargs)
    print('Reading CSV file at location {}'.format(kwargs['file_path']))
    print('Converting numbers.' if kwargs['convert_numbers'] else
          'NOT converting numbers.')
    print('Converting dates.' if kwargs['convert_dates'] else
          'NOT converting dates.')
    return _csv_import_core(kwargs['file_path'], kwargs['delim'], kwargs['quote_mark'],
                            kwargs['encoding'], kwargs['line_terminator'], kwargs['quoting'],
                            kwargs['convert_numbers'], kwargs['convert_dates'],
                            kwargs['date_format'])


def _csv_import_core(file_path, delim, quote_mark, encoding, line_terminator, quoting,
                     convert_numbers, convert_dates, date_format):
    '''Pure CSV-reading logic (no GUI, no prompting). All args already resolved.'''
    ret_table = []
    with open(file_path, 'r', encoding=encoding) as file_in:
        csv_reader = csv.reader(file_in, delimiter=delim,
            quotechar=quote_mark, lineterminator=line_terminator,
            quoting=QUOTING_OPTIONS.get(quoting, csv.QUOTE_MINIMAL))
        with click.progressbar(csv_reader, fill_char='*',
            empty_char=' ') as data_in:
            for line in data_in:
                if convert_numbers or convert_dates:
                    ret_table.append(
                        _process_line(line, convert_numbers,
                                      convert_dates,
                                      date_format))
                else:
                    ret_table.append(line)
    return ret_table
