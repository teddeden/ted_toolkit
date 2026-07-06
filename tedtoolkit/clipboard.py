'''tedtoolkit.clipboard - Windows clipboard I/O for scalar values and tables.'''

import win32clipboard


def win_copy(var_in):
    '''Copies a variable as a string to the windows clipboard for pasting in another program
    Full functionality via Windows API'''
    var_in = str(var_in)
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(var_in)
    win32clipboard.CloseClipboard()
win_copy.desc = 'Copy to windows clipboard'


def win_paste():
    '''Copies a variable from the windows clipboard to a python variable (via return)
    Full functionality via Windows API'''
    win32clipboard.OpenClipboard()
    data = win32clipboard.GetClipboardData()
    win32clipboard.CloseClipboard()
    return data
win_paste.desc = 'Paste from clipboard (non-table)'


def win_paste_table():
    '''paste into python list the contents of excel table copied to windows clipboard'''
    contents = win_paste().strip()
    val = [item.split('\t') for item in contents.split('\r\n')]
    def func(x):
        return x if bool(set(x.strip()) - set('1234567890.')) else float(x.strip())
    table = [[func(line[index].strip('"')) for index in range(len(line))] for line in val]
    return table
win_paste_table.desc = 'Paste from (excel) table'


def win_copy_table(array):
    '''take 2d array in and convert to a text string that excel can copy into cells, then copy'''
    output_string = ''
    for row_data in array:
        for col, val in enumerate(row_data):
            output_string = output_string + str(val)
            if col+1 < len(row_data):
                output_string = output_string + '\t'
        output_string = output_string + '\r\n'
    win_copy(output_string)
win_copy_table.desc = 'Copy lists of lists table'
