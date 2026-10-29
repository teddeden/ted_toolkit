'''tedtoolkit.clipboard - Windows clipboard I/O for scalar values and tables, plus
pickled-object copy/paste (win_copy_pickle/win_paste_pickle) for moving arbitrary
Python data structures through the clipboard or a plain text file losslessly.'''

import base64
import hashlib
import pickle
import zlib

import win32clipboard

from tedtoolkit.history import (_check_assignment, _add_kwarg_to_last_command, _quoted,
                                 _remove_keyword_argument_from_last_command)
from tedtoolkit.gui.dialogs import g_sel_file, g_sel_file_to_write

# First token of the header line of win_copy_pickle()'s text format; bump the trailing
# digit if the encoding below ever changes incompatibly.
PICKLE_TEXT_MAGIC = 'TTKPKL1'
_PICKLE_TEXT_LINE_WIDTH = 76
_PICKLE_TEXT_FILETYPES = [('Text files', ('*.txt')), ('All Files', ('*.*'))]


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


def _pickle_to_text(obj):
    '''Pure core of win_copy_pickle(): pickle obj (highest protocol), zlib-compress,
    base64-encode, and wrap at 76 columns under a one-line header:
        TTKPKL1 <sha256 of pickle bytes, 16 hex chars> <pickle byte count>
    The result is plain ASCII, so it survives Notepad, email, or qr_encode().'''
    raw = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    encoded = base64.b64encode(zlib.compress(raw, 9)).decode('ascii')
    lines = [encoded[pos:pos + _PICKLE_TEXT_LINE_WIDTH]
             for pos in range(0, len(encoded), _PICKLE_TEXT_LINE_WIDTH)]
    header = f'{PICKLE_TEXT_MAGIC} {hashlib.sha256(raw).hexdigest()[:16]} {len(raw)}'
    return '\n'.join([header] + lines) + '\n'


def _text_from_pickle(text):
    '''Pure core of win_paste_pickle(): reverse _pickle_to_text(). Tolerates anything
    before the header line (e.g. a note typed above it) and any whitespace/line-break
    changes in the payload (CRLF, re-wrapping, trailing spaces). Raises ValueError if
    the text is not TTKPKL1 data or was altered/truncated.
    WARNING: unpickling can execute arbitrary code - only paste text you created yourself
    or otherwise trust.'''
    lines = text.splitlines()
    header_index = next((index for index, line in enumerate(lines)
                         if line.strip().startswith(PICKLE_TEXT_MAGIC + ' ')), None)
    if header_index is None:
        raise ValueError(f'No {PICKLE_TEXT_MAGIC} header found: this text was not produced by win_copy_pickle().')
    try:
        _magic, checksum, byte_count = lines[header_index].split()
        byte_count = int(byte_count)
    except ValueError as exc:
        raise ValueError(f'Malformed {PICKLE_TEXT_MAGIC} header line: {lines[header_index]!r}') from exc
    payload = ''.join(''.join(lines[header_index + 1:]).split())
    try:
        raw = zlib.decompress(base64.b64decode(payload, validate=True))
    except (ValueError, zlib.error) as exc:
        raise ValueError(f'Pickled text is corrupted or incomplete: {exc}') from exc
    if len(raw) != byte_count or hashlib.sha256(raw).hexdigest()[:16] != checksum:
        raise ValueError('Pickled text failed its checksum: it was altered or truncated.')
    return pickle.loads(raw)


def win_copy_pickle(var_in, **kwargs):
    '''Copies ANY picklable Python object (nested dicts/lists/trees, sets, tuples,
    datetimes, tables, ...) to the windows clipboard as compact ASCII text, so it can be
    pasted into a text file and later restored exactly with win_paste_pickle() - no
    flattening to csv/xlsx and re-building needed.
    kwargs:
    - file_path: write the text straight to this file instead of the clipboard
                 (file_path='' opens a Save As dialog)
    USAGE:
    >>> win_copy_pickle(my_tree)                              # to clipboard
    >>> win_copy_pickle(my_tree, file_path='c:/temp/tree.txt') # to text file
    '''
    text = _pickle_to_text(var_in)
    if 'file_path' in kwargs:
        file_path = kwargs['file_path']
        if not file_path:
            file_path = g_sel_file_to_write(title='TED TOOLKIT: Save pickled variable as text',
                                            filetypes=_PICKLE_TEXT_FILETYPES,
                                            force_file_extension='txt')
            if not file_path:
                print('win_copy_pickle(): no file selected. Nothing written.')
                return
            _remove_keyword_argument_from_last_command('file_path')
            _add_kwarg_to_last_command('file_path', _quoted(file_path), fn_name='win_copy_pickle')
        with open(file_path, 'w', encoding='ascii', newline='\n') as fil:
            fil.write(text)
        print(f'Pickled {type(var_in).__name__} written to {file_path} ({len(text):,} characters).')
        print(f'Restore with:  x = win_paste_pickle(file_path={_quoted(file_path)})')
        return
    win_copy(text)
    print(f'Pickled {type(var_in).__name__} copied to clipboard ({len(text):,} characters).')
    print('Restore with:  x = win_paste_pickle()')
win_copy_pickle.desc = 'Copy any object as pickled text'


def win_paste_pickle(**kwargs):
    '''Restores an object copied with win_copy_pickle(), from the windows clipboard
    (default) or from a text file. Must be assigned to a variable.
    kwargs:
    - file_path: read the pickled text from this file instead of the clipboard
                 (file_path='' opens a file selection dialog)
    WARNING: unpickling can execute arbitrary code - only paste text you created yourself
    or otherwise trust.
    USAGE:
    >>> my_tree = win_paste_pickle()                               # from clipboard
    >>> my_tree = win_paste_pickle(file_path='c:/temp/tree.txt')   # from text file
    '''
    _check_assignment(function_name='win_paste_pickle')
    if 'file_path' not in kwargs:
        return _text_from_pickle(win_paste())
    file_path = kwargs['file_path']
    if not file_path:
        file_path = g_sel_file(title='TED TOOLKIT: Select pickled-variable text file',
                               filetypes=_PICKLE_TEXT_FILETYPES)
        if not file_path:
            raise ValueError('win_paste_pickle(): no file selected.')
        _remove_keyword_argument_from_last_command('file_path')
        _add_kwarg_to_last_command('file_path', _quoted(file_path), fn_name='win_paste_pickle')
    with open(file_path, 'r', encoding='utf-8-sig') as fil:
        return _text_from_pickle(fil.read())
win_paste_pickle.desc = 'Paste object from pickled text'
