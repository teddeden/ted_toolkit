'''tedtoolkit.util - small stand-alone utilities (timestamps, elapsed time,
current user, window title, notepad++ discovery, beep). No intra-package
dependencies except tedtoolkit's own START_TIME, which the root launcher sets.
'''

import datetime
import os
import time

START_TIME = datetime.datetime.now()


def elapsed():
    '''Returns the time (in string format hh:mm:ss) since the START_TIME of the session'''
    current = datetime.datetime.now()
    delta = current - START_TIME
    temp = str(delta)
    decimal_position = temp.find('.')
    return temp[:decimal_position]
elapsed.desc = 'Returns time (str) since start'


def get_utc_timestamp():
    """Get time stamp in UTC time """
    local_time = datetime.datetime.now()
    epoch_second = time.mktime(local_time.timetuple())
    utc_time = datetime.datetime.fromtimestamp(epoch_second, datetime.UTC)
    return utc_time.strftime("%Y-%m-%d-%H-%M-%S")
get_utc_timestamp.desc = 'UTC timestamp (str)'


def get_local_timestamp():
    '''Get time stamp in local time'''
    local = datetime.datetime.now()
    epoch_second = time.mktime(local.timetuple())
    local_time = datetime.datetime.fromtimestamp(epoch_second)
    return local_time.strftime("%Y-%m-%d-%H-%M-%S")
get_local_timestamp.desc = 'Local timestamp (str)'


def get_current_user():
    '''Get current user logged in Windows User ID'''
    try:
        return os.environ.get('USERNAME').upper()
    except AttributeError:
        return 'Unknown User'
get_current_user.desc = 'Current Windows User ID (str)'


def _find_notepad_pp(initial_dir='c:/ProgramData/App-V'):
    '''Returns path of Notepad++ if found
    Otherwise returns None'''
    standard_path = r"c:\Program Files\Notepad++"
    try:
        if os.path.isdir(standard_path):
            if os.path.isfile(os.path.join(standard_path, 'notepad++.exe')):
                return os.path.join(standard_path, 'notepad++.exe')
        res = os.listdir(initial_dir)
        for folder in res:
            subpath = os.path.join(initial_dir, folder)
            sublist = os.listdir(subpath)
            if not sublist:
                continue
            sub_subpath = os.path.join(subpath, sublist[0])
            if not os.path.isdir(sub_subpath):
                continue
            sub_sublist = os.listdir(sub_subpath)
            if 'Root' not in sub_sublist:
                continue
            final_path = os.path.join(sub_subpath, 'Root')
            if not os.path.isdir(final_path):
                continue
            if 'notepad++.exe' in os.listdir(final_path):
                return os.path.join(final_path, 'notepad++.exe')
    except OSError:
        return None
    return None


def beep():
    '''make a short beep (e.g. to let the user know that something is finished)'''
    print('\a', end='')
beep.desc = 'Windows chime'


def set_window_title(text, include_timestamp=None):
    '''Set title of command prompt window.
    include_timestamp may be None, "UTC", or "LOCAL" '''
    if include_timestamp == 'UTC':
        title_string = f'title {get_utc_timestamp()}: {text}'
    elif include_timestamp == 'LOCAL':
        title_string = f'title {get_local_timestamp()}: {text}'
    else:
        title_string = f'title {text}'
    os.system(title_string)
set_window_title.desc = 'Set title of command line window'
