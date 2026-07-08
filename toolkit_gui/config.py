'''toolkit_gui.config - paths and tunables for the GUI shell.

ACTIVATE_BAT/ENV_PATH/TOOLKIT_PY mirror start_ted_toolkit.bat's own hardcoded
paths exactly, so the GUI's spawned sessions are byte-for-byte equivalent to
double-clicking that .bat file.
'''

ACTIVATE_BAT = r"C:\ProgramData\Anaconda3\Scripts\activate.bat"
ENV_PATH = r"C:\Users\User\Documents\toolkit-env"
TOOLKIT_PY = r"C:\Users\User\Documents\toolkit\ted_toolkit.py"

# Shared timer interval (seconds) for CPU sampling, title polling, and
# variable-panel refresh.
POLL_INTERVAL_SECONDS = 1.0

# Data Preview panel row/column cap - mirrors tedtoolkit.tables.snapshot's
# own defaults, kept here too so the GUI can reference it without importing
# the toolkit package just for a constant.
PREVIEW_MAX_ROWS = 250
PREVIEW_MAX_COLS = 250

# pyte terminal scrollback size (lines) - large enough for "Save all chat
# content" to capture a full session's realistic output volume (a Phase 0
# spike measured ~2,300 lines/sec sustained parse throughput at this size).
TERMINAL_SCROLLBACK_LINES = 200_000

# A freshly spawned child needs a moment before its gui_bridge thread starts
# listening - BridgeClient.connect() retries on this cadence.
BRIDGE_CONNECT_RETRIES = 30
BRIDGE_CONNECT_RETRY_DELAY_SECONDS = 0.5

# Ceiling for resolving the real descendant python.exe pid from the pty's
# reported root pid (see backend.win_pty_backend._find_descendant_pid_by_cmdline).
PID_RESOLVE_TIMEOUT_SECONDS = 15
