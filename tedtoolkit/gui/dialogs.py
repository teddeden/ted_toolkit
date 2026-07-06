'''tedtoolkit.gui.dialogs - tkinter file/folder picker dialogs.'''

import os
from tkinter import Tk
from tkinter import filedialog as tkFileDialog

from tedtoolkit.prompts import ask_yn


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
            if not ask_yn(
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
