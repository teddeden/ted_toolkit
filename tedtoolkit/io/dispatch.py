'''tedtoolkit.io.dispatch - consolidated data_import/data_export.

Supersedes the old data_import/data_export (xlsx+csv only, GUI-only path
selection, no way to script a full non-interactive call) and
data_import_plus/data_export_plus (broken: Python-2-only builtins raw_input/
getpass, bare ZipFile, and a dependency on a nonexistent XlData class). This
is a fresh implementation built on the already-working xlsx_import/
xlsx_export/csv_import/csv_export/read_txt/_txt_export/ask_select_sheet.

Per the refactor plan (Decision 4): supports xlsx + csv + txt with Excel
sheet-selection, fully scriptable via kwargs with GUI-prompt fallback when
kwargs are missing. Zip/password-protected CSV support is deliberately NOT
ported forward - a pre-refactor saved script calling
data_import_plus(process_as='zip', ...) will now fail with NameError since
that function no longer exists; this is a deliberate, called-out behavior
change, not an oversight.
'''

import os

from tedtoolkit.history import _add_kwarg_to_last_command, _quoted
from tedtoolkit.prompts import ask_select, _kwarg_parse_prompt_bool
from tedtoolkit.validation import _is_list_of_lists
from tedtoolkit.gui.dialogs import g_sel_file, g_sel_file_to_write
from tedtoolkit.io.xlsx import xlsx_import, xlsx_export, ask_select_sheet, ALL_SHEETS_TEXT
from tedtoolkit.io.csv import csv_import, csv_export
from tedtoolkit.io.txt import read_txt, _txt_export

LAST_PATH = os.getcwd()  # remembers the last folder used, to pre-seed subsequent GUI dialogs

_CSV_IMPORT_KWARGS = ('delim', 'quote_mark', 'quoting', 'encoding', 'line_terminator',
                      'convert_numbers', 'convert_dates', 'date_format')
_CSV_EXPORT_KWARGS = ('delim', 'quote_mark', 'quoting', 'encoding', 'line_terminator',
                      'convert_dates', 'date_format')


def _file_ext(path):
    '''return the lowercased extension of path, without the leading dot (e.g. 'xlsx', 'csv', 'txt')'''
    return os.path.splitext(path)[1].lstrip('.').lower()


def _resolve_process_as(file_path, kwargs, fn_name):
    '''resolve which format (xlsx/csv/txt) to use for file_path, prompting if ambiguous
    and baking the resolved choice into history if it wasn't already an explicit kwarg'''
    process_as = kwargs.get('process_as', _file_ext(file_path))
    if process_as not in ('xlsx', 'csv', 'txt'):
        process_as = ask_select({'xlsx':'Excel 2003/2010 file', 'csv':'Comma separated values',
                                 'txt':'Plain text file'},
                                prompt='File type for "{}" is ambiguous; select the file type:'.format(
                                    file_path),
                                orig_out=True)
        if 'process_as' not in kwargs:
            _add_kwarg_to_last_command('process_as', _quoted(process_as), fn_name=fn_name)
    return process_as


def data_import(**kwargs):
    '''Unified import for xlsx/csv/txt.
    kwargs:
      file_path (prompts via GUI if not given)
      process_as ('xlsx'|'csv'|'txt') - only needed if file_path's extension is ambiguous
      selected_sheet (xlsx only) - sheet name to return, or ALL_SHEETS_TEXT to get a dict of all sheets
      include_formulas, override_ro (xlsx only)
      delim, quote_mark, quoting, encoding, line_terminator, convert_numbers, convert_dates,
        date_format (csv only)
    Returns a list-of-lists (single sheet/csv/txt) or a dict of
    {sheet_name: list-of-lists} (xlsx with selected_sheet=ALL_SHEETS_TEXT).
    '''
    global LAST_PATH
    file_path = kwargs.get('file_path', '')
    if not file_path or not os.path.isfile(file_path):
        file_path = g_sel_file(title=kwargs.get('gui_prompt', 'data_import(): select file'),
                               initialdir=LAST_PATH,
                               filetypes=[('Data files', ('*.xlsx', '*.csv', '*.txt')),
                                          ('All files', ('*.*'))])
        if not file_path:
            print('No file selected: data import cancelled.\n')
            return None
        if 'file_path' not in kwargs:
            _add_kwarg_to_last_command('file_path', _quoted(file_path), fn_name='data_import')
    LAST_PATH = os.path.split(file_path)[0]
    process_as = _resolve_process_as(file_path, kwargs, 'data_import')

    if process_as == 'xlsx':
        sheets = xlsx_import(file_path=file_path, include_formulas=kwargs.get('include_formulas', False),
                             override_ro=kwargs.get('override_ro', False))
        selected_sheet = kwargs.get('selected_sheet', None)
        if selected_sheet not in list(sheets) + [ALL_SHEETS_TEXT]:
            selected_sheet = ask_select_sheet(sheets)
            if 'selected_sheet' not in kwargs:
                _add_kwarg_to_last_command('selected_sheet', _quoted(selected_sheet), fn_name='data_import')
        if selected_sheet == ALL_SHEETS_TEXT:
            return sheets
        return sheets[selected_sheet]

    if process_as == 'csv':
        return csv_import(file_path=file_path,
                          **{k: kwargs[k] for k in _CSV_IMPORT_KWARGS if k in kwargs})

    return read_txt(file_path=file_path, encoding=kwargs.get('encoding', 'utf-8'))
data_import.desc = 'Unified import: xlsx/csv/txt'


def data_export(data, **kwargs):
    '''Unified export for xlsx/csv/txt.
    kwargs:
      file_path (prompts via GUI if not given)
      process_as ('xlsx'|'csv'|'txt') - only needed if file_path's extension is ambiguous
      wb_filter, view_in_excel, sheet_name (xlsx only)
      delim, quote_mark, quoting, encoding, line_terminator, convert_dates, date_format (csv only)
    '''
    global LAST_PATH
    file_path = kwargs.get('file_path', '')
    if not file_path:
        is_table = _is_list_of_lists(data, strict_nonempty=True)
        filetypes = [('Excel files', ('*.xlsx')), ('CSV files', ('*.csv')), ('Text files', ('*.txt'))] \
                    if is_table else [('Excel files', ('*.xlsx'))]
        file_path = g_sel_file_to_write(title='data_export(): save as', initialdir=LAST_PATH,
                                        filetypes=filetypes)
        if not file_path:
            print('No file selected: data export cancelled.\n')
            return None
        if 'file_path' not in kwargs:
            _add_kwarg_to_last_command('file_path', _quoted(file_path), fn_name='data_export')
    LAST_PATH = os.path.split(file_path)[0]
    process_as = _resolve_process_as(file_path, kwargs, 'data_export')
    if not file_path.lower().endswith('.' + process_as):
        file_path = file_path + '.' + process_as

    if process_as == 'xlsx':
        xl_kwargs = {'file_path': file_path}
        if 'sheet_name' in kwargs:
            xl_kwargs['sheet_name'] = kwargs['sheet_name']
        xl_kwargs['wb_filter'] = _kwarg_parse_prompt_bool('wb_filter', default_val='True',
                                                          prompt='Include data filter?', **kwargs)
        xl_kwargs['view_in_excel'] = _kwarg_parse_prompt_bool('view_in_excel', default_val='True',
                                                              prompt='Open in Excel?', **kwargs)
        return xlsx_export(data, **xl_kwargs)

    if not _is_list_of_lists(data):
        raise Exception('data_export(): CSV/TXT export requires a list-of-lists table.')

    if process_as == 'csv':
        return csv_export(data, file_path=file_path,
                          **{k: kwargs[k] for k in _CSV_EXPORT_KWARGS if k in kwargs})

    return _txt_export(data, file_path, encoding=kwargs.get('encoding', 'utf-8'))
data_export.desc = 'Unified export: xlsx/csv/txt'
