'''tedtoolkit.gui.messagebox - tkinter messagebox wrappers.

Fixes a long-standing gap: g_ask_yn(), g_ask_okcancel(), and g_conditional_stop()
were called from several places in this codebase (dynamic_import()'s error
handler, compare_columns()'s tolerance/row-length guards, data_export_plus()'s
overwrite confirmation) but were never defined anywhere - every one of those
call sites raised NameError. This module defines them for real, plus
g_show_info/g_show_warning/g_show_error for symmetry.
'''

from tkinter import messagebox

MB_ICONS = {'error': messagebox.ERROR,
            'info': messagebox.INFO,
            'question': messagebox.QUESTION,
            'warning': messagebox.WARNING}


def g_ask_yn(prompt, title='', icon='question'):
    '''GUI yes/no confirmation dialog. Returns True/False.'''
    return messagebox.askyesno(title=title, message=prompt, icon=MB_ICONS.get(icon, messagebox.QUESTION))
g_ask_yn.desc = 'GUI prompt: yes/no'


def g_ask_okcancel(prompt, title='', icon='question', default='ok', detail=None):
    '''GUI OK/Cancel confirmation dialog. Returns True (OK) / False (Cancel).'''
    return messagebox.askokcancel(title=title, message=prompt, icon=MB_ICONS.get(icon, messagebox.QUESTION),
                                   default=default, detail=detail)
g_ask_okcancel.desc = 'GUI prompt: OK/Cancel'


def g_conditional_stop(message, title='', consequences=''):
    '''GUI OK/Cancel dialog for a recoverable problem: OK to continue anyway, Cancel to abort
    (raises Exception on Cancel). Returns True if the user chose to continue.'''
    full_message = message + ('\n\n' + consequences if consequences else '')
    if not messagebox.askokcancel(title=title or 'Continue?', message=full_message,
                                   icon=MB_ICONS['warning']):
        raise Exception(message)
    return True
g_conditional_stop.desc = 'GUI prompt: continue or abort (raises on abort)'


def g_show_info(message, title=''):
    '''GUI info dialog.'''
    return messagebox.showinfo(title=title, message=message)
g_show_info.desc = 'GUI info dialog'


def g_show_warning(message, title=''):
    '''GUI warning dialog.'''
    return messagebox.showwarning(title=title, message=message)
g_show_warning.desc = 'GUI warning dialog'


def g_show_error(message, title=''):
    '''GUI error dialog.'''
    return messagebox.showerror(title=title, message=message)
g_show_error.desc = 'GUI error dialog'
