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
from tkinter import Tk
from tkinter import filedialog as tkFileDialog
from tkinter import messagebox
import traceback
import win32com.client
import xlrd
import zipfile
from ted_toolkit import (_add_kwarg_to_last_command,
                         _remove_keyword_argument_from_last_command,
                         _check_assignment,
                         _is_list_of_lists,
                         _get_last_command,
                         _quoted,
                         _prompt_for_any_arg,
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

LAST_PATH = os.getcwd()  #to be replaced by script accessing files
ALL_SHEETS_TEXT = '**ALL SHEETS**'  #Should contain characters not allowed in an excel sheet name
VERBOSE = False
#set VERBOSE to False when no longer testing in order to suppress extra console output in production

MB_ICONS = {'error': messagebox.ERROR,
            'info': messagebox.INFO,
            'question': messagebox.QUESTION,
            'warning': messagebox.WARNING}

MB_BUTTONS = {''
              }

def ask_yn(default='no', prompt=''):
    '''prompt for a yes/no answer; 
    hit enter to use default value'''
    default_yes = default.lower() in ('y', 'yes')
    a_in = input(prompt + (' (Y/n): ' if default_yes else\
                           ' (y/N): '))
    if a_in[:3].lower() in ('y', 'yes') or \
        (len(a_in) == 0 and default_yes):
        return True
    return False

def _prompt_for_any_arg(arg_name, default_val, numeric=False):
    '''prompts for arg_name value to be default_val; if user 
       does not want to use default_val, user can specify any
       value desired. If numeric is True, user is forced to enter
       a numeric value and this will be converted to a float.  
       Otherwise, response will be interpreted as test string'''
    prompt = 'The argument <{}> is set to <{}>. Is this ok?'
    if not ask_yn(default='y', prompt=prompt.format(arg_name,\
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
                user_in = eval('"{}"'.format(user_in))
            ok = True
        ret_val = user_in
    else:
        ret_val = default_val
    print('<{}> has been set to <{}>.'.format(arg_name, 
                                              repr(ret_val)))
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
        if ask_yn(default='y', prompt=pmt.format(arg_name,\
            choices_list[default_index])):
            return choices_list[default_index]
    print('For <{}> you have the following choices:'.format(\
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
    if not ask_yn(default='y', prompt=prompt.format(arg_name,\
        default_val)):
        ret_val = not default_val
    else:
        ret_val = default_val
    print('<{}> has been set to <{}>.'.format(arg_name, ret_val))
    return ret_val

def g_sel_file(**kwargs):
    '''Graphical file selection via tkinter; 
    returns path as string'''
    gui = Tk()
    gui.focus_force()
    path = tkFileDialog.askopenfilename(
        title=kwargs.get('title', 'Open file'),
        filetypes=kwargs.get('filetypes', 
                             [('All Files', ('*.*')),
                              ('Excel files', ('*.xlsx')),
                              ('CSV files', ('*.csv')),
                              ('Text files', ('*.txt'))]),
        initialdir=kwargs.get('initialdir', os.getcwd()),
        parent=gui
        )
    gui.withdraw()
    if path == None: #User cancels dialog
        print('User canceled file select dialog. Aborting')
        return ''
    return path

def g_sel_file_to_write(**kwargs):
    '''GUI Save As dialog returns valid path or empty string
    if cancel'''
    gui = Tk()
    gui.focus_force()
    path = tkFileDialog.asksaveasfilename(
        title=kwargs.get('title', 'Save As'),
        filetypes=kwargs.get('filetypes', 
                             [('All Files', ('*.*')),
                              ('Excel files', ('*.xlsx')),
                              ('CSV files', ('*.csv')),
                              ('Text files', ('*.txt'))]),
        initialdir=kwargs.get('initial_dir', os.getcwd()),
        parent=gui,
        initialfile=kwargs.get('initial_file', '')
        )
    if path == None or path == '': #User cancels dialog
        return ''
    if 'force_file_extension' in kwargs:
        target_ext = kwargs.get('force_file_extension')
        while target_ext[0] in ['*', '.']:
            target_ext = target_ext[1:]
        length = len(target_ext)
        if path[-length:] != target_ext:
            path = path + '.' + target_ext
    gui.withdraw()
    if not kwargs.get('overwrite', False):
        if os.path.isfile(path):
            if not ask_yn(\
                prompt='File exists at chosen path. Overwrite?'):
                path = g_sel_file_to_write(**kwargs)
    return path

def g_sel_folder(**kwargs):
    '''Graphical folder selection via tkinter
        Returns path as string'''
    gui = Tk()
    gui.focus_force()
    path = tkFileDialog.askdirectory(
        title=kwargs.get('title', 'Select Directory/Folder'),
        initialdir=kwargs.get('initialdir', os.getcwd()),
        parent=gui,
        )
    gui.withdraw()
    if path == None: #User cancels dialog
        print('User canceled dialog.  Aborting.')
        return ''
    return path

def _xlsx_data_check(data):
    '''function for xlsx_export, checks to see that data are in 
        the right form and raises exception if not.  
        Returns single_sheet_mode variable True if data is
        list of lists instead of dict of list of lists'''
    check_ok = True
    single_sheet_mode = False
    if not isinstance(data, dict):
        if isinstance(data, list):
            if isinstance(data, list):
                if data:
                    if isinstance(data[0], list):
                        single_sheet_mode = True
                    else:
                        check_ok = False
                else:
                    check_ok = False
            else:
                check_ok = False
        else:
            check_ok = False
    if check_ok and not single_sheet_mode:
        if not data: #if dictionary is empty
            check_ok = False
        if not data: #dictionary empty
            check_ok = False
        for sheetname in data:
            if not isinstance(data[sheetname], list):
                check_ok = False
                break
            if not data[sheetname]: #if the sheet is empty:
                check_ok = False
                break
            if not isinstance(data[sheetname][0], list): 
                #if first line not a list
                check_ok = False
        if check_ok:
            sheet_names = list(data.keys())
            if any([len(name) > 31 for name in sheet_names]):
                print('xlsx_export(): WARNING: Sheet names detected in excess of 31 characters; these will be truncated if possible.')
                if len(sheet_names) > len(set([name[:31] for name in sheet_names])):
                    raise Exception('xlsx_export(): Truncating long sheet names results in ambiguous names. Pass unique names with max. 31 characters')
    if not check_ok:
        raise Exception(\
            'Must be list of lists table or dict of tables')
    return single_sheet_mode

def xlsx_export(data_in, **kwargs):
    '''takes in a dictionary where the keys are sheet names
        and the values are lists of lists (sheet data),
        takes optional kwarg "file_path" or, if not provided,
        prompts the user for a path via gui

        If single list of lists passed instead of dict,
        writes single table to excel.  
        --kwarg "sheet_name" specifies the sheet name in this 
        case'''
    if _xlsx_data_check(data_in):
        data_in = {kwargs.get('sheet_name', 'Sheet1'):data_in}
    path = kwargs.get('file_path', None)
    if path is None:
        path = g_sel_file_to_write(title='Save As XLSX (Python)', filetypes=[('XLSX', ('*.xlsx'))])
        if path[-5:] != '.xlsx':
            path = path + '.xlsx'
        _add_kwarg_to_last_command('file_path', _quoted(path), fn_name='xlsx_export')
    kwargs['wb_filter'] = _kwarg_parse_prompt_bool('wb_filter', default_val='True', prompt='Include data filter?', **kwargs)
    wb_filter = kwargs['wb_filter']
    kwargs['view_in_excel'] = _kwarg_parse_prompt_bool('view_in_excel', default_val='True', prompt='Open in Excel?', **kwargs)
    wbk = openpyxl.Workbook(write_only=not wb_filter)
    existing_sheets = [name for name in wbk.sheetnames] #should be none is not using filter
    for index, sheetname in enumerate(data_in):
        wst = wbk.create_sheet(sheetname)
        print('Exporting sheet {}...'.format(sheetname[:31]))
        with click.progressbar(data_in[sheetname], 
            fill_char='>', empty_char='-') as data:
            for line in data:
                wst.append(line)
        if wb_filter:
            wst.auto_filter.ref = wst.dimensions
    if existing_sheets and not any([sheet in data_in for sheet in existing_sheets]):
        for sheet in existing_sheets:
            sheet_obj = wbk[sheet]
            wbk.remove(sheet_obj)
    print('Data prepared. Saving...')
    wbk.save(path)
    print('\nWorkbook saved under {}\n\n'.format(path))
    if kwargs.get('view_in_excel', False):
        excel = win32com.client.dynamic.Dispatch('excel.application')
        _ = excel.Workbooks.Open(path)
        excel.Visible = True
    return

def xlsx_import(**kwargs):
    '''returns dict of lists of lists with content from xlsx file
    optional keyword arguments:
    file_path (default None): full path to file or file name if 
                         file is in same folder as script;
                         If no path given, a gui prompt will 
                         prompt user to choose the file path
    include_formulas (default False): if True, will return 
        formulas from sheet instead of values
    override_ro: overrides the (default behavior) read only
        feature; needed in some cases to fix bugs in library'''
    path = kwargs.get('file_path', None)
    ro = not kwargs.get('override_ro', False)
    if path is None:
        path = g_sel_file(title='Open XLSX (Python)', 
                          filetypes=[('XLSX', ('*.xlsx'))])
    if not path:
        return None
    include_formulas = kwargs.get('include_formulas', False)
    fn = lambda line: [item.value for item in line]
    data_in = openpyxl.load_workbook(path, read_only=ro, 
        data_only=(not include_formulas))
    print('Reading workbook at path: {}'.format(path))
    ret_dict = collections.OrderedDict()
    for sheet_name in data_in.sheetnames:
        print('Importing sheet {}...'.format(sheet_name))
        with click.progressbar(data_in[sheet_name], \
            fill_char='*', empty_char=' ') as sheet:
            temp = [fn(line) for line in sheet]
        ret_dict[sheet_name] = temp
    return ret_dict

def _parse_csv_args(case, **kwargs):
    '''parses and prompts for keyword arguments as needed
    case must be 'import' or 'export' 
    returns updated kwargs dict'''
    file_path = kwargs.get('file_path', None)
    if file_path is None and case == 'import':
        file_path = g_sel_file(title='Import CSV data',\
            filetypes=[('CSV files', ('*.csv')), 
                       ('Text files', ('*.txt', '*.text'))])
    elif file_path is None and case == 'export':
        file_path = g_sel_file_to_write(title='Save As CSV', \
            filetypes=[('CSV files', ('*.csv')), 
                       ('Text files', ('*.txt', '*.text'))])
    if 'delim' not in kwargs:
        delim = _prompt_for_any_arg('delim', ',')
    else:
        delim = kwargs['delim']
    options = OrderedDict([
        ('QUOTE_ALL',csv.QUOTE_ALL),
        ('QUOTE_MINIMAL',csv.QUOTE_MINIMAL),
        ('QUOTE_NONNUMERIC',csv.QUOTE_NONNUMERIC),
        ('QUOTE_NONE',csv.QUOTE_NONE)])
    if 'quoting' not in kwargs:
        quoting = _prompt_for_list_arg('quoting', 
            list(options.keys()), default_index=1)
    else:
        quoting = kwargs['quoting']
    if 'quote_mark' not in kwargs:
        quote_mark = _prompt_for_any_arg('quote_mark', '"')
    else:
        quote_mark = kwargs['quote_mark']
    if 'encoding' not in kwargs:
        encoding = _prompt_for_list_arg('encoding',\
            ['utf_8', 'ascii', 'windows-1252', 'latin-1',
            'utf_16', 'utf_32'], default_index=0)
    else:
        encoding = kwargs['encoding']
    if encoding == 'autodetect':
        print('Auto-detecting encoding...  ', end='')
        with open(file_path, 'rb') as file_in:
            #temp = file_in.read(1024)  / problematic if given a UTF-8 file with the first non-ascii char later in the file.
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

def _is_list_of_lists(var):
    '''return true if list of lists, false if anything else'''
    if isinstance(var, list):
        if not var:
            return False
        for line in var:
            if not isinstance(line, list):
                return False
        return True
    else:
        return False


def csv_export(data, **kwargs):
    '''export list of lists as csv file
    kwargs: file_path, delim for delimiter (default = ',')
    quote_mark (default = '"'), encoding (default = 'utf_8')
    line_terminator (default = '\n')
    quoting, (default = 'QUOTE_MINIMAL')
    convert_dates - T/F option to specify non-default
        string format to be used to convert datetime objects;
        if True, date_format should be specified.'''
    kwargs = _parse_csv_args('export', **kwargs)
    file_path = kwargs['file_path']
    delim = kwargs['delim']
    quoting = kwargs['quoting']
    quote_mark = kwargs['quote_mark']
    encoding = kwargs['encoding']
    line_terminator = kwargs['line_terminator']
    convert_dates = kwargs['convert_dates']
    date_format = kwargs['date_format']
    options = OrderedDict([
        ('QUOTE_ALL',csv.QUOTE_ALL),
        ('QUOTE_MINIMAL',csv.QUOTE_MINIMAL),
        ('QUOTE_NONNUMERIC',csv.QUOTE_NONNUMERIC),
        ('QUOTE_NONE',csv.QUOTE_NONE)])
    if not _is_list_of_lists(data):
        raise Exception('Export CSV Failed: No content')
    print('Writing CSV...\n')
    with open(file_path, 'w', encoding=encoding) as file_out:
        o_writer = \
            csv.writer(file_out, delimiter=delim, 
                       quotechar=quote_mark,
                       quoting=options.get(quoting, 
                                           csv.QUOTE_MINIMAL),
                       lineterminator=line_terminator)
        with click.progressbar(data, fill_char='>', 
                               empty_char='-') as table:
            if convert_dates:
                for line in table:
                    line_to_write = []
                    for item in line:
                        if isinstance(item, datetime.datetime):
                            line_to_write.append(item.\
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
    if date_format == None:
        date_format = ('%Y-%m-%d %H:%M:%S.%f')
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
    line_terminator, default = '\n'
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
    file_path = kwargs['file_path']
    delim = kwargs['delim']
    quoting = kwargs['quoting']
    quote_mark = kwargs['quote_mark']
    encoding = kwargs['encoding']
    line_terminator = kwargs['line_terminator']
    convert_numbers = kwargs['convert_numbers']
    convert_dates = kwargs['convert_dates']
    date_format = kwargs['date_format']
    options = OrderedDict([
        ('QUOTE_ALL',csv.QUOTE_ALL),
        ('QUOTE_MINIMAL',csv.QUOTE_MINIMAL),
        ('QUOTE_NONNUMERIC',csv.QUOTE_NONNUMERIC),
        ('QUOTE_NONE',csv.QUOTE_NONE)])
    print('Reading CSV file at location {}'.format(file_path))
    print('Converting numbers.' if convert_numbers else \
          'NOT converting numbers.')
    print('Converting dates.' if convert_dates else \
          'NOT converting dates.')
    ret_table = []
    with open(file_path, 'r', encoding=encoding) as file_in:
        csv_reader = csv.reader(file_in, delimiter=delim, \
            quotechar=quote_mark, lineterminator=line_terminator,
            quoting=options.get(quoting, csv.QUOTE_MINIMAL))
        with click.progressbar(csv_reader, fill_char='*', \
            empty_char=' ') as data_in:
            for line in data_in:
                if convert_numbers or convert_dates:
                    ret_table.append(\
                        _process_line(line, convert_numbers,
                                      convert_dates, 
                                      date_format))
                else:
                    ret_table.append(line)
    return ret_table

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


def ask_select_sheet(dict_in, prompt='Select a sheet to import', include_all=True):
    '''Prompt for selecting a sheet from a sict of Excel sheets, or else choosing all sheets'''
    global ALL_SHEETS_TEXT
    if not instance(dict_in, dict):
        raise Exception('ERROR: ask_select_sheet() called without a dict of sheets as input!')
    if len(dict_in) == 1 and include_all == False:
        print(f'Only 1 sheet available: selecting it as default: {list(dict_in.keys())[0]}')
        return list(dict_in.keys())[0]
    print(prompt+'\n')
    line = '{:<5}{:35}'
    temp_dict = OrderedDict()
    for index, key in enumerate(([ALL_SHEETS_TEXT] if include_all else []) + list(dict_in.keys())):
        print(line.format(index, key))
        temp_dict[index] = key
    print()
    selection = ask_num(allow_decimal=False, allow_negative=False)
    if selection not in range(len(temp_dict)+(1 if include_all else 0)):
        return ask_select_sheet(dict_in, prompt, include_all)
    return temp_dict[selection]

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

