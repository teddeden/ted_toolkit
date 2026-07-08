'''toolkit_gui.backend.env_resolve - replicates start_ted_toolkit.bat's conda
activation exactly, so the GUI's spawned sessions are byte-for-byte
equivalent to a user double-clicking that .bat file (including whatever
activate.d hooks conda has registered for toolkit-env, e.g.
openssl_activate.bat - hand-replicating environment variables instead of
calling activate.bat itself would silently drift from that whenever such a
hook changes).
'''

import socket

from toolkit_gui import config


def build_spawn_argv(extra_args=None):
    '''Return the argv list to hand to a PtyBackend.spawn(), reproducing:
        call <activate.bat> <toolkit-env> && <toolkit-env>\\python.exe -i ted_toolkit.py [extra_args...]
    i.e. everything start_ted_toolkit.bat does except the trailing `pause`
    (the GUI doesn't need a "press any key to close" step).

    None of config.ACTIVATE_BAT / config.ENV_PATH / config.TOOLKIT_PY contain
    spaces today, so this deliberately avoids adding its own quote
    characters around them: embedding pre-quoted paths in a string that
    pywinpty's spawn() re-quotes internally (via subprocess.list2cmdline())
    causes a double-escaping bug that breaks cmd.exe's parsing entirely -
    confirmed via a Phase 0 spike. If any of these paths need to support
    spaces in the future, quote only that specific segment (e.g. via
    subprocess.list2cmdline([segment])) rather than adding hand-rolled quote
    characters to the whole command string.
    '''
    command = (
        f'call {config.ACTIVATE_BAT} {config.ENV_PATH} && '
        f'{config.ENV_PATH}\\python.exe -i {config.TOOLKIT_PY}'
    )
    for arg in extra_args or []:
        command += f' {arg}'
    return ['cmd.exe', '/c', command]


def find_free_port():
    '''Ask the OS for a free ephemeral port, then release it immediately so
    the child process can bind it. Narrow TOCTOU race (something else could
    grab the port between release and the child binding) is acceptable here:
    localhost-only, and BridgeClient.connect() retries on connection
    failure regardless.'''
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]
