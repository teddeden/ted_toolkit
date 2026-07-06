'''tedtoolkit.io.txt - plain text file import.'''

import codecs

from tedtoolkit.gui.dialogs import g_sel_file


def read_txt(**kwargs):
    '''reads in a text file, returning list of strings found
    kwargs:
    - file_path (str, will prompt if not given)
    - encoding (str, default utf-8)
    '''
    if 'file_path' in kwargs:
        file_path = kwargs.get('file_path', '')
        del kwargs['file_path']
    else:
        file_path = g_sel_file(**kwargs)
    if not file_path:
        return None
    if 'encoding' not in kwargs:
        kwargs['encoding'] = 'utf-8'
    fil = codecs.open(file_path, **kwargs)
    data = list(fil)
    fil.close()
    return data
read_txt.desc = 'Import text file'
