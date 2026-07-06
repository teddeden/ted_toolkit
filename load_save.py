''' load_save.py - code for loading and saving files'''

import click  
#for progressbar; if needed, use "pip install click" at cmd line
import collections #for OrderedDict especially
import csv
import datetime
import inspect
import openpyxl
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
import os
import chardet
import re
import time
from tkinter import messagebox
from tedtoolkit.gui.dialogs import g_sel_file, g_sel_file_to_write, g_sel_folder
import traceback
import win32com.client
import xlrd
import zipfile
from tedtoolkit.history import (_add_kwarg_to_last_command,
                         _remove_keyword_argument_from_last_command,
                         _check_assignment,
                         _get_last_command,
                         _quoted,
                         )
from tedtoolkit.validation import _is_list_of_lists
from tedtoolkit.prompts import (_prompt_for_any_arg,
                         _prompt_for_bool_arg,
                         _prompt_for_list_arg,
                         ask_num,
                         ask_select,
                         ask_yn,
                         _kwarg_parse_prompt_str,
                         _kwarg_parse_prompt_bool,
                         _kwarg_parse_prompt_num,
                         _kwarg_parse_prompt_list,
                         )
from tedtoolkit.io.xlsx import _xlsx_data_check, xlsx_export, xlsx_import, ask_select_sheet, ALL_SHEETS_TEXT
from tedtoolkit.io.csv import _parse_csv_args, csv_export, _process_line, csv_import

LAST_PATH = os.getcwd()  #to be replaced by script accessing files
VERBOSE = False
#set VERBOSE to False when no longer testing in order to suppress extra console output in production

MB_ICONS = {'error': messagebox.ERROR,
            'info': messagebox.INFO,
            'question': messagebox.QUESTION,
            'warning': messagebox.WARNING}

MB_BUTTONS = {''
              }

def data_export(data, **kwargs):
    '''exports list of lists data as CSV or XLSX
    or dict of lists of lists as XLSX'''
    path = kwargs.get('file_path', None)
    if path is None:
        if _is_list_of_lists(data):
            path = g_sel_file_to_write(title='data_export() Save As', filetypes=[('Excel files', ('*.xlsx')), ('CSV files', ('*.csv'))])
        else:
            path = g_sel_file_to_write(title='data_export() Save As', filetypes=[('Excel files', ('*.xlsx'))])
            if path[-5:].lower() not in ('.xlsx'):
                path = path + '.xlsx'
        _add_kwarg_to_last_command('file_path', _quoted(path), fn_name='data_export')
    if path[-4:].lower() not in ('xlsx', '.csv'):
        raise Exception('data_export(): Ambiguous dile name type.  Canceling.')
    if path[-4:].lower() == 'xlsx':
        xl_options = {'file_path':path}
        xl_options['wb_filter'] = _kwarg_parse_prompt_bool('wb_filter', default_val=True, prompt='Include Data Filter?', **kwargs)
        xl_options['view_in_excel'] = _kwarg_parse_prompt_bool('view_in_excel', default_val=True, prompt='Open in Excel?', **kwargs)
        return xlsx_export(data, **xl_options)
    return csv_export(data, file_path=path)

def data_import():
    '''imports list of lists data from CSV 
    or dict of lists of lists from XLSX'''
    file_path = g_sel_file(\
        title='data_import() Open',
        filetypes=[('Excel/CSV Files', ('*.xlsx', '*.csv'))])
    if file_path[-4:].lower() not in ('xlsx', '.csv'):
        print('Only XLSX and CSV files supported. Canceling.')
        return None
    if file_path[-4:].lower() == 'xlsx':
        return xlsx_import(file_path=file_path)
    return csv_import(file_path=file_path)


def data_import_plus(**kwargs):  # if no kwargs, just get all input via prompts...
    '''guided or kwarg-specified import data function
    Options:
     - gui_prompt='String' # String to be used in title bar of GUI popup
     - file_path='String' # File path to try to open (if successful, no further prompt)
     - process_as='String' # String must be in ['xlsx', 'csv', 'txt', 'zip'] (overrides input mode)
     - repress_all_sheets_option = Bool # For XLSX files, don't show option to import all/as dict
     - selected_sheet='Sheet name' # XLSX Sheet name of sheet to import (if success, no prompt)
     - delim='char' # Character to use as delimiter for CSV tables, e.g. ',' ';'
     - quote_mark='char' # Character that is used in CSV files to demarcate text strings, if any
     - encoding='code' # For text file imports; Code can be 'utf-8' or '1252' for example'''

    global LAST_PATH #Used to allow for quick subsequent file selection
    global ALL_SHEETS_TEXT
    import_var = _check_assignment(function_name='data_import_plus')
    #print('import_var = ', import_var)
    file_path = kwargs.get('file_path', '')
    if not file_path or not os.path.isfile(file_path):
        gui_prompt = kwargs.get('gui_prompt', 'TED_TOOLKIT: data_import_plus()')
        file_path = g_sel_file(filetypes=[('Data files', ('*.xlsx', '*.csv', '*.txt', '*.zip')),
                                          ('All files', ('*.*'))],
                               initialdir=LAST_PATH, title=gui_prompt)
        if 'file_path' in kwargs:
            _remove_keyword_argument_from_last_command('file_path')
        _add_kwarg_to_last_command('file_path', _quoted(file_path))

    LAST_PATH, _ = os.path.split(file_path)
    choice = None
    if file_path[-4:].lower() not in ['xlsx', '.csv', '.txt', '.zip' '']:
        if 'process_as' in kwargs:
            choice = kwargs.get('process_as', 'xlsx')
        elif ask_yn(default='n',
                    prompt='This tool must have XLSX, CSV, TXT, or ZIP data. File name '+\
                    'is ambiguous. Continue?\n(If yes, you will be prompted to select file type)'):
            choice = ask_select({'xlsx':'Excel 2003/2010 file',
                                 'csv':'Comma separated values',
                                 'txt':'Plain text file',
                                 'zip':'CSV stored in password-protected zip file'})
            _add_kwarg_to_last_command('process_as', _quoted(choice))
        print('Processing file with ambiguous name as ', choice)

    if file_path[-4:].lower() == 'xlsx' or choice == 'xlsx':
        repress_all = kwargs.get('repress_all_sheets_option', False)
        data_dict = xlsx_import(file_path=file_path,
                                include_formulas=kwargs.get('include_formulas', False),
                                override_ro=kwargs.get('override_ro', False))
        sheets = {key: data_dict[key] for key in data_dict}
        selected_sheet = kwargs.get('selected_sheet', '')
        if 'selected_sheet' not in kwargs:
            selected_sheet = ask_select_sheet(sheets, include_all=not repress_all)
            _add_kwarg_to_last_command('selected_sheet', _quoted(selected_sheet))
        elif selected_sheet not in list(sheets) + \
             [ALL_SHEETS_TEXT] if not repress_all else []:
            print('Pre-selected sheet not available; please choose another sheet to import.')
            selected_sheet = ask_select_sheet(sheets, include_all=not repress_all)
            _remove_keyword_argument_from_last_command('selected_sheet')
            _add_kwarg_to_last_command('Selected_sheet', _quoted(selected_sheet))

        if selected_sheet == ALL_SHEETS_TEXT:
            if import_var:
                print('Returning dict of all sheets in list of lists format')
                print('Assigning data to variable: {}\n'.format(import_var))
            return sheets
        else: # specific sheet selected:
            print('Returning sheet {}\n'.format(selected_sheet))
            return sheets[selected_sheet]

    elif file_path[-4:].lower() in ['.csv', '.zip'] or choice in ['csv', 'zip']:
        print('CSV/ZIP file process:', file_path, '\n')

        delim = kwargs.get('delim', ',')
        while 'delim' not in kwargs and not \
              ask_yn(default='y', prompt='Delimiter is < {} >. OK?'.format(delim)):
            new_delim = raw_input('Type new delimiter to use: >>> ')
            if len(new_delim) > 0:
                delim = new_delim
        if 'delim' not in kwargs:
            _add_kwarg_to_last_command('delim', _quoted(delim))

        quote_mark = kwargs.get('quote_mark', '"')
        while 'quote_mark' not in kwargs and not \
              ask_yn(default='y', prompt='Quote char is < {} >. OK?'.format(quote_mark)):
            new_quote = raw_input('Type new quote character to use: >>> ')
            if len(new_quote) > 0:
                quote_mark = new_quote
        if 'quote_mark' not in kwargs:
            _add_kwarg_to_last_command('quote_mark', _quoted(quote_mark))


        if file_path[-4:].lower() == '.csv' or choice == 'csv':
            with open(file_path, 'rb') as input_file:
                csvreader = csv.reader(input_file, delimiter=delim, quotechar=quote_mark)
                array = [row for row in csvreader]
            return array

        else:
            array = []
            with ZipFile(file_path, 'r') as input_zip:
                while not array:
                    passwd = getpass.getpass('Enter password to decode file >> ')
                    try:
                        csvfile = input_zip.open(os.path.split(file_path)[1][:-3]+'csv', 'r',
                                                 passwd)
                        csvreader = csv.reader(csvfile, delimiter=delim, quotechar=quote_mark)
                        array = [row for row in csvreader]
                    except KeyboardInterrupt:
                        del passwd
                        raise KeyboardInterrupt
                    except:
                        del passwd
                        print('Error with password or file.\nUse Ctrl+c to cancel')
            return array

    elif file_path[-4:].lower() == '.txt' or choice == 'txt':
        print('Text file process:', file_path, '\n')
        encoding = kwargs.get('encoding', 'utf-8')
        while 'encoding' not in kwargs and not \
              ask_yn(default='y', prompt='Encoding is < {} >. OK?'.format(encoding)):
            new_encoding = raw_input('Type new encoding to use: >>> ')
            if len(new_encoding) > 0:
                encoding = new_encoding
        if 'encoding' not in kwargs:
            _add_kwarg_to_last_command('encoding', _quoted(encoding))
        fil = codecs.open(file_path, encoding=encoding)
        ret_data = list(fil)
        fil.close()
        print('\n')
        return ret_data

    elif file_path == '':
        print('No file selected: data import cancelled.\n')

    else:
        print('Invalid source at {}; file must be xlsx, csv, zip or txt.\n'.format(file_path))
               
               
def data_export_plus(data, **kwargs):
    '''guided/automated data export function
    for creating sheets with graphs, use the following syntax:
    data_export_plus(dict_of_lists, graph_sheets=
    {'sheet1':{'chart_options':{'type':'column', 'subtype':'stacked'}, 
             'colors':[], 
             'swap_x_y':False, 
             'title':'My chart', 
             'units':'units', 
             'category':'category', 
             'size':{'width':480, 'height':576}, 
             'location':'A30'}}, 
             )
    '''
    global LAST_PATH #Used to pre-select save folder

    file_path = kwargs.get('file_path', '')
    if os.path.isfile(file_path):
        overwrite = kwargs.get('overwrite', '')
        if overwrite == '':
            pmt = 'File exists at given file path:\n{}\n\nOverwrite?'.format(file_path)
            overwrite = g_ask_yn(title='Overwrite file?', prompt=pmt)
            _add_kwarg_to_last_command('overwrite', overwrite)
        if overwrite not in [True, 'True', 'Yes', 'true', 'yes']:
            LAST_PATH, _ = os.path.split(file_path)
            file_path = ''
            _remove_keyword_argument_from_last_command('file_path')
            del kwargs['file_path']

    if not file_path:
        if kwargs.get('force_excel', False):
            file_path = g_sel_file_to_write(filetypes=[('Excel file', ('*.xlsx'))],
                                            force_file_extension='xlsx', initialdir=LAST_PATH,
                                            title='SAVE AS / select output file')
        else:
            file_path = g_sel_file_to_write(filetypes=[('Excel file', ('*.xlsx')),
                                                       ('CSV', ('*.csv')),
                                                       ('Text file', ('*.txt'))],
                                            initialdir=LAST_PATH,
                                            title='SAVE AS / select output file')
        if 'file_path' not in kwargs:
            _add_kwarg_to_last_command('file_path', _quoted(file_path))

    LAST_PATH, _ = os.path.split(file_path)
    choice = None
    if file_path[-4:] not in ['xlsx', '.csv', '.txt', '']:
        if 'save_as_type' in kwargs:
            choice = kwargs.get('save_as_type', 'xlsx')
        elif ask_yn(default='y', prompt='This tool saves only XLSX, CSV or TXT data. File name '+\
                    'is ambiguous. Continue?\n(If yes, you will be prompted to select file type)'):
            choice = ask_select({'xlsx':'Excel 2003/2010 file',
                                 'csv':'Comma separated values',
                                 'txt':'Plain text file'})
            _add_kwarg_to_last_command('save_as_type', _quoted(choice))
        print('Processing file with ambiguous name as '+ choice)

    if file_path[-4:] == 'xlsx' or choice == 'xlsx':
        strings_to_numbers = _kwarg_parse_prompt_bool('strings_to_numbers', default_val='True',
                                                     **kwargs)
        suppress_urls = _kwarg_parse_prompt_bool('suppress_urls', default_val='False', **kwargs)
        header_row = _kwarg_parse_prompt_bool('header_row', default_val='True', **kwargs)
        title = _kwarg_parse_prompt_str('title', default_val='TED_TOOLKIT Generated File', **kwargs)
        if header_row:
            autofilter = _kwarg_parse_prompt_bool('autofilter', default_val='True', **kwargs)
        else:
            autofilter = False

        view_in_excel = _kwarg_parse_prompt_bool('view_in_excel', default_val='True', **kwargs)

        if _is_list_of_lists(data, strict_nonempty=True):
            print('Creating XLSX file from single table (list of lists) source.')
            sheet_name = _kwarg_parse_prompt_str('sheet_name', default_val='Sheet1', **kwargs)
            description = kwarg_parse_prompt_sheet_descriptions(case='list_of_lists', **kwargs)
            print('no description' if not description else 'description: {}'.format(description))

            xlo = XlData(suppress_urls=suppress_urls)
            xlo.wb_options['strings_to_numbers'] = strings_to_numbers
            if kwargs.get('include_sheet_descriptions', False) or description is not None:
                xlo.wb_options['constant_memory'] = False
                print('***disabling low memory operation***')
            xlo.set_wb_properties({'title':title})
            xlo.file_path_and_name = file_path
            if header_row:
                xlo.add_sheet(data, sheet_name, header_rows=1, autofilter=autofilter,
                              description=description)
            else:
                xlo.add_sheet(data, sheet_name, description=description)
            print('Saving file to disk: ', xlo.file_path_and_name)
            xlo.write_to_disk()
            if view_in_excel:
                excel = win32com.client.dynamic.Dispatch('excel.application')
                _ = excel.Workbooks.Open(file_path)
                excel.Visible = True

        elif _is_dict_of_tables(data, strict_nonempty=False):
            print('Creating XLSX file from multiple table (dict of lists of lists) source.')
            xlo = XlData(suppress_urls=suppress_urls)
            xlo.wb_options['strings_to_numbers'] = strings_to_numbers
            xlo.set_wb_properties({'title':title})
            xlo.file_path_and_name = file_path
            xlo.graph_sheets = kwargs.get('graph_sheets', {})
            descriptions = kwarg_parse_prompt_sheet_descriptions(case='dict_of_sheets',
                                                                 names=data.keys(), **kwargs)
            print('no descriptions' if not descriptions else \
                  'descriptions: {}'.format(', '.join(descriptions.keys())))
            if kwargs.get('include_sheet_descriptions', False) or descriptions is not None:
                xlo.wb_options['constant_memory'] = False
                print('***disabling low memory operation***')
            else:
                descriptions = {sheet:'' for sheet in data}
            for sheet in data:
                if not _is_list_of_lists(data[sheet], strict_nonempty=True):
                    print('Skipping sheet {} due to empty content'.format(sheet))
                    continue
                if header_row:
                    xlo.add_sheet(data[sheet], sheet, header_rows=1, autofilter=autofilter,
                                  description=descriptions[sheet])
                else:
                    xlo.add_sheet(data[sheet], sheet, description=descriptions[sheet])
            print('Saving file to disk: ', xlo.file_path_and_name)
            xlo.write_to_disk()
            if view_in_excel:
                excel = win32com.client.dynamic.Dispatch('excel.application')
                _ = excel.Workbooks.Open(file_path)
                excel.Visible = True

        else:
            print('Data not usable for creating an excel file. Must be list of lists or dict of'+\
                   ' lists of lists.\nAborting.')
            return

    elif file_path[-4:] == '.csv' or choice == 'csv':
        if not _is_list_of_lists(data, strict_nonempty=True):
            print('Export CSV Failed. No content to export')
            return
        delim = kwargs.get('delim', ',')
        while 'delim' not in kwargs and not \
              ask_yn(default='y', prompt='Delimiter is < {} >. OK?'.format(delim)):
            new_delim = raw_input('Type new delimiter to use: >>> ')
            if len(new_delim) > 0:
                delim = new_delim
        if 'delim' not in kwargs:
            _add_kwarg_to_last_command('delim', _quoted(delim))

        quote_mark = kwargs.get('quote_mark', '"')
        while 'quote_mark' not in kwargs and not \
              ask_yn(default='y', prompt='Quote char is < {} >. OK?'.format(quote_mark)):
            new_quote = raw_input('Type new quote character to use: >>> ')
            if len(new_quote) > 0:
                quote_mark = new_quote
        if 'quote_mark' not in kwargs:
            _add_kwarg_to_last_command('quote_mark', _quoted(quote_mark))


        quoting = kwargs.get('quoting', 'QUOTE_MINIMAL')
        options = {'QUOTE_ALL':csv.QUOTE_ALL, 'QUOTE_MINIMAL':csv.QUOTE_MINIMAL,
                   'QUOTE_NONNUMERIC':csv.QUOTE_NONNUMERIC, 'QUOTE_NONE':csv.QUOTE_NONE}
        if 'quoting' not in kwargs and not \
           ask_yn(default='y', prompt='Quoting is < {} >. OK?'.format(quoting)):
            quoting = ask_select(list(options), orig_out=True,
                                 prompt='Select a CSV Quoting type: ')
        if 'quoting' not in kwargs:
            _add_kwarg_to_last_command('quoting', _quoted(quoting))

        print('Writing CSV...\n')
        with open(file_path, 'wb') as file_out:
            o_writer = csv.writer(file_out, delimiter=delim, quotechar=quote_mark,
                                  quoting=options[quoting])
            for line in data:
                o_writer.writerow(line)
        print('Done.. ')

    elif file_path[-4:] == '.txt' or choice == 'txt':
        to_write = []
        if isinstance(data, str):
            to_write = [data]
        elif isinstance(data, list):
            if isinstance(data[0], list):
                to_write = [', '.join([str(item) for item in line]) for line in data]
            else:
                to_write = [str(item) for item in data]
        else:
            print('Bad data passed to data_export. Aborting.')
        with codecs.open(file_path, 'w', 'utf-8') as outfile:
            for line in to_write:
                outfile.writelines(line+'\r\n')
        print('Done writing file. Text file written to {}'.format(file_path))

    else:
        print('Ambiguous file save type. Aborting command {}'.format(_get_last_command()))

