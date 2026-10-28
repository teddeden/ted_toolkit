'''tedtoolkit.util - small stand-alone utilities (timestamps, session elapsed time,
benchmarking timer, current user, window title, notepad++ discovery, beep). No
intra-package dependencies.

START_TIME is set once, when this module is first imported (i.e. at session start),
and backs elapsed(). TIMER_START backs timer_start()/timer_elapsed(): it is reset by
every timer_start() call, and equals START_TIME until the first one.
'''

import datetime
import os
import time

START_TIME = datetime.datetime.now()
TIMER_START = START_TIME


def _format_timedelta(delta):
    '''Return a timedelta as "h:mm:ss" (or "N day(s), h:mm:ss"), microseconds dropped.
    str(timedelta) omits the ".ffffff" part entirely when microseconds == 0, so the
    fraction is removed from the timedelta itself rather than by searching for "."'''
    return str(delta - datetime.timedelta(microseconds=delta.microseconds))


def elapsed():
    '''Returns the time (in string format h:mm:ss) since the START_TIME of the session'''
    return _format_timedelta(datetime.datetime.now() - START_TIME)
elapsed.desc = 'Returns time (str) since start'


def timer_start():
    '''Starts (or restarts) a benchmarking timer; read it back with timer_elapsed().
    Independent of elapsed(), which always measures from session start.
    USAGE:
    >>> timer_start()
    Timer start at 2026-10-28 14:03:11.204518
    >>> x = data_join(a, b)
    >>> timer_elapsed()
    3.481207
    >>> timer_elapsed(output_format='string')
    '0:00:03'
    '''
    global TIMER_START
    TIMER_START = datetime.datetime.now()
    print(f'Timer start at {TIMER_START}')
timer_start.desc = 'Start benchmarking timer'


def timer_elapsed(output_format='number'):
    '''Returns the time since the last timer_start() call (or since session start if
    timer_start() has not been called yet).
    output_format='number' (default): seconds as a float, e.g. 3.481207
    output_format='string': "h:mm:ss" string, e.g. "0:00:03" (same format as elapsed())'''
    delta = datetime.datetime.now() - TIMER_START
    if output_format == 'number':
        return delta.total_seconds()
    if output_format == 'string':
        return _format_timedelta(delta)
    raise ValueError("timer_elapsed(): output_format must be 'number' or 'string', "
                     f'got {output_format!r}')
timer_elapsed.desc = 'Time since timer_start() (s or str)'


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
