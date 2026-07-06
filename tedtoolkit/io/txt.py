'''tedtoolkit.io.txt - plain text file import/export.'''

import codecs

from tedtoolkit.gui.dialogs import g_sel_file
from tedtoolkit.validation import _is_list_of_lists


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
    with codecs.open(file_path, **kwargs) as fil:
        data = list(fil)
    return data
read_txt.desc = 'Import text file'


def _txt_export(data, file_path, encoding='utf-8'):
    '''writes a list-of-lists table to a tab-delimited plain text file'''
    if not _is_list_of_lists(data, strict_nonempty=True):
        raise Exception('_txt_export(): data must be a non-empty list of lists.')
    with open(file_path, 'w', encoding=encoding) as file_out:
        for line in data:
            file_out.write('\t'.join(str(item) for item in line) + '\n')
    print('Done. File saved under <{}>.'.format(file_path))
