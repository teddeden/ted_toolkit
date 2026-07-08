# About Ted's Toolkit

This document is for a developer who needs to get productive in this codebase quickly. It
explains what the toolkit does, how the interactive session model works (the part that looks
strangest on first read), what's in each module, and what's known-broken or known-missing.

For contribution rules (git workflow, versioning, linting), see [CLAUDE.md](CLAUDE.md).

## What this is

Ted's Toolkit is a personal, Windows-only, interactive Python CLI for data analysis and
transformation — pivoting, joining, reconciling, and comparing tabular data without leaving a
Python prompt, and without pandas. Tables are plain **lists of lists**: `[[header1, header2],
[row1col1, row1col2], ...]`. This is deliberate, not a legacy gap — lists of lists are considered
more intuitive than a DataFrame for this tool's intended use, and no PR should introduce pandas.

It's launched by double-clicking (or running) `start_ted_toolkit.bat`, which activates the
`toolkit-env` conda environment and runs `python -i ted_toolkit.py`. The `-i` flag is essential:
it runs the script to load every function into the global namespace, then drops into an
interactive `>>>` prompt in that same namespace — so every function in the toolkit is callable
bare, by name, with no imports, exactly like a beefed-up calculator.

## The core interaction pattern (read this before touching any "guided" function)

This is the one idea that makes the rest of the codebase make sense.

Most of the toolkit's real functions (`data_aggregate`, `data_join`, `compare_columns`, `reconcile`,
`data_import`, ...) are **guided**: you call them with as few or as many arguments as you already
know, and they interactively prompt you for whatever's missing.

```
>>> x = data_de_aggregate(my_table)
Does your data contain headers? (Y/n):
```

Here's the part that's easy to miss: **after you answer the prompts, the toolkit doesn't just use
your answer — it rewrites the command you already typed**, splicing your answer in as a keyword
argument, using Python's `readline` history buffer (via `pyreadline3` on Windows). If you press
the ↑ (up-arrow) key after the prompts finish, you won't see `data_de_aggregate(my_table)` — you'll
see something like:

```
x = data_de_aggregate(my_table, headers=True, aggregation_key_col=2, delim=', ')
```

fully filled in, ready to re-run without any prompts. This is the entire point of the tool: you
work interactively once, and `save_history()` then dumps your whole rewritten session to a `.py`
file — a fully-parameterized, non-interactive script that reproduces the same analysis. That
script can later be replayed with `_run_script()` (triggered by passing the script's path as an
argument to `ted_toolkit.py`) with zero prompts.

This means:
- **A guided function's public name and call signature are a durable contract.** A previously
  saved script has a hardcoded call to that exact name with that exact keyword. Renaming a
  parameter, or changing what a bare call does, breaks every script anyone has ever saved.
- **Every guided function follows the same internal shape**: resolve each parameter via
  `kwargs.get(...)` or a `_kwarg_parse_prompt_*` helper (which prompts only if the kwarg wasn't
  already given, then calls `_add_kwarg_to_last_command()` to bake the answer into the history
  line), then run the actual logic.
- **The actual logic is split out into a pure `_<name>_core` function.** This was added during the
  2026 refactor specifically so the logic could be unit-tested without needing a live, seeded
  `readline` history. `_data_de_aggregate_core()` next to `data_de_aggregate()` in
  `tedtoolkit/tables/aggregate.py` is the simplest example to read first.

## Package layout

```
toolkit/
├── start_ted_toolkit.bat     launcher: activates conda env, runs `python -i ted_toolkit.py`
├── environment.yml           conda environment spec (python=3.12, pinned - see CLAUDE.md)
├── ted_toolkit.py            thin session launcher - see its own module docstring
├── tedtoolkit/                the actual package
│   ├── history.py             readline history-rewrite primitives (input(), _add_kwarg_to_last_command, _check_assignment, ...)
│   ├── validation.py          table-shape checks (_is_list_of_lists, _check_var_table)
│   ├── prompts.py             console prompt primitives (ask_yn, ask_num, ask_select, ...) and the _kwarg_parse_prompt_* wrappers
│   ├── util.py                elapsed(), timestamps, get_current_user, beep, set_window_title
│   ├── clipboard.py           Windows clipboard I/O (win_copy/win_paste/*_table)
│   ├── introspect.py          dynamic_import() and the function-reference helpers help_all()/save_function_reference() build on
│   ├── gui/
│   │   ├── dialogs.py          tkinter file/folder picker dialogs (g_sel_file, g_sel_file_to_write, g_sel_folder)
│   │   └── messagebox.py       tkinter messagebox wrappers (g_ask_yn, g_ask_okcancel, g_conditional_stop, g_show_*)
│   ├── io/
│   │   ├── xlsx.py             Excel import/export (openpyxl) + core split, ask_select_sheet
│   │   ├── csv.py              CSV import/export + core split, _parse_csv_args
│   │   ├── txt.py              plain text import/export
│   │   └── dispatch.py         consolidated data_import()/data_export() (xlsx/csv/txt, format auto-detected from extension)
│   └── tables/
│       ├── columns.py          single-column extraction, Excel column-letter conversion
│       ├── preview.py          data_preview(), single_col_analysis(), the _guess_var() heuristic
│       ├── aggregate.py         data_aggregate()/data_de_aggregate() + cores (the pivot/aggregation engine)
│       ├── join.py              data_join() + core (key-based table join)
│       ├── reconcile.py         key_analysis(), reconcile(), data_recon() (two-table diff engine)
│       └── compare.py           compare_columns()/try_compare_columns() + core (column-vs-column comparison)
└── tests/                      pytest suite, mirrors tedtoolkit/ by theme - see CLAUDE.md
```

`ted_toolkit.py` re-exports everything from `tedtoolkit` (`from tedtoolkit import *` plus a few
explicit imports) so the interactive namespace looks exactly like one flat module, matching the
original single-file design. `FUNCTION_CATEGORIES` (a dict in `ted_toolkit.py`) drives
`help_all()`'s categorized function listing — add new public functions there when you add them.

A separate top-level package, `toolkit_gui/`, contains an optional desktop GUI shell built on top
of this — see "The desktop GUI shell" section below. It never modifies how `tedtoolkit`/
`ted_toolkit.py` behave when run the plain command-line way.

## Why `help_all()`/`help_vars()`/`_run_script()` live in `ted_toolkit.py`, not the package

These functions call bare `globals()`/`eval(name)` against **whatever module is running as
`__main__`** — i.e., the interactive session's own namespace, so they can see variables and
functions the user typed at the prompt. If they lived inside a `tedtoolkit` submodule, `globals()`
there would return that submodule's namespace instead, and they'd stop seeing anything the user
actually defined. This is a namespace-binding requirement, not a style choice — don't "clean this
up" by moving them into the package.

## Data import/export

`data_import()`/`data_export()` in `tedtoolkit/io/dispatch.py` are the blessed entry points —
they auto-detect xlsx/csv/txt from the file extension (prompting if ambiguous), support Excel
sheet selection, and are fully scriptable via kwargs with GUI-prompt fallback when kwargs are
missing. `xlsx_import`/`xlsx_export`/`csv_import`/`csv_export` remain public (not just internal
helpers) since existing saved scripts may call them directly for their non-prompting return
shapes. **Zip/password-protected CSV import was deliberately dropped** during the 2026 refactor
(it was already broken — Python-2-only code) and is not coming back without a specific ask.

## Known gaps (do not silently "fix" these — see CLAUDE.md's bug-fix philosophy)

- **`data_recon()`'s `col_select='LIST'` path is incomplete.** It calls `_sel_compare_cols()`
  (when no `columns` kwarg is given) and, in `col_mode='NAME'`, `_check_convert_text_cols()` — a
  function that translates name-based column specs to indices. **Neither function exists
  anywhere in this codebase.** This was discovered during the 2026 refactor; there's no removed/
  commented-out reference implementation to restore, so nothing was invented. `col_select` values
  `'AUTO-OR'`/`'AUTO-AND'` work fully; `'LIST'` with `col_mode='POSITION'` and `columns` already
  supplied as a kwarg also works. If you need the `'LIST'` + missing-columns or `'LIST'` +
  `'NAME'` paths, you'll need to design and implement `_sel_compare_cols()`/
  `_check_convert_text_cols()` from scratch — ask the user what behavior they actually want first.

## Do-not-touch list

- The `eval()`/`exec()` usages that are load-bearing to the design: `_run_script()`'s replay
  `exec()`, `compare_columns()`'s `first_col_conv` user-transform-expression `eval()`, and the
  `help_all()`/`help_vars()` introspection `eval(name)` calls. These are intentional features, not
  bugs — see CLAUDE.md.
- `compare_columns()`'s in-place mutate-and-return contract (it mutates the `data` argument and
  returns the same object, rather than returning a copy). Existing/replayed scripts depend on the
  mutation being visible on the original variable afterward.
- The interactive prompt wording, prompt order, and default values of any guided function — these
  are UI/UX, not implementation detail.

## The desktop GUI shell (`toolkit_gui/`)

A separate top-level package, sibling to `tedtoolkit/` — **not** the same thing as
`tedtoolkit/gui/` (the tkinter dialog/messagebox helpers used by guided functions themselves).
`toolkit_gui/` is an optional PySide6 desktop shell around the toolkit; `start_ted_toolkit.bat`
and everything under `tedtoolkit/` work exactly as before, completely unaware this package
exists. Launch it by double-clicking (or running) `start_ted_toolkit_gui.bat`, the GUI's
counterpart to `start_ted_toolkit.bat` — it activates `toolkit-env` the same way, then runs
`python -m toolkit_gui.app` instead of `python -i ted_toolkit.py`.

**The core architectural idea**: each GUI tab hosts its interactive session as its own real
`python -i ted_toolkit.py` **OS process**, spawned inside a genuine Windows pseudo-console
(ConPTY, via the `pywinpty` package) rather than redirected pipes. This is not an implementation
detail — it's the only way to keep `pyreadline3`'s console hook (see "The core interaction
pattern" above) working completely unmodified. A GUI tab is a real console session with a Qt
widget drawn on top of it, not a reimplementation of one.

- `toolkit_gui/backend/` — `pty_backend.py` (abstract `PtyBackend`/`PtySession`, with
  `win_pty_backend.py` as the only implementation built so far; `posix_pty_backend.py` is a
  documented stub for a future Linux/Mac port, since POSIX would use stdlib GNU readline instead
  of `pyreadline3` and needs no ConPTY-equivalent dependency). `env_resolve.py` replicates
  `start_ted_toolkit.bat`'s conda activation command exactly (verified against `toolkit-env`'s
  actual `activate.d` hooks) rather than hand-replicating environment variables, and resolves the
  *real* interactive `python.exe` PID from a spawned process tree by matching descendant command
  lines — matching by process name alone is unsafe, since conda's `activate.bat` can spawn its
  own short-lived helper `python.exe`. `bridge_client.py` is the GUI-side client for the wire
  protocol below.
- `toolkit_gui/terminal/` — `terminal_widget.py`, a `pyte`-backed VT100/xterm emulator widget: a
  background `QThread` (`pty_io_thread.py`) pumps the pty's raw output into a Qt signal, `pyte`
  turns it into a character grid, and keystrokes are forwarded as raw xterm escape sequences. No
  readline/history logic is reimplemented here — arrow-key recall works purely because the child
  process sees the same bytes it would from a real console.
- `toolkit_gui/session_manager.py` / `session_tab.py` / `main_window.py` — spawn/track tabs, own
  the shared poll timer (variable/preview refresh, title sync, CPU sampling), and the
  menu/toolbar/status-bar shell itself.
- `toolkit_gui/session_bundle.py` / `session_persistence.py` — the `.tedsession` save/restore
  format and its GUI-side orchestration (see below).

### The GUI ↔ session bridge (`tedtoolkit/gui_bridge.py`)

Since each tab is a separate OS process, the GUI can't just call Python functions inside a
session to inspect its variables — it needs an IPC channel into that specific process. This is
what `tedtoolkit/gui_bridge.py` is for: a background thread, started by `maybe_start_bridge()`,
which is called from `ted_toolkit.py` right after `ARGS = sys.argv[1:]` and does **nothing at all**
unless the GUI has set `TEDTOOLKIT_GUI_BRIDGE_PORT` before spawning the process —
`start_ted_toolkit.bat` never sets this, so plain command-line usage is unaffected. When active,
it opens a localhost TCP socket and answers newline-delimited JSON requests
(`list_vars`, `get_var_preview`, `get_title`, `save_session`, `restore_session`).

Two small pure helpers back this, following the same core/wrapper-adjacent pattern as the rest of
the codebase:
- `tedtoolkit/introspect.py::_variable_snapshot_core()` — the same type-filter logic
  `help_vars()` already has inline, but taking an explicit namespace dict instead of `eval()`-ing
  against `globals()`, so it's safe to call from a different module. Used for the live Variables
  panel.
- `tedtoolkit/tables/snapshot.py::_table_snapshot_core()` — a new, bounded (default 250×250)
  structured table slice, used for the Data Preview panel's truncated grid.

`help_vars()`/`help_all()` themselves are untouched — the extraction happened *underneath* them,
not by rewiring them.

### Save/Restore Session

Menu-only, and deliberately **not** part of the plain CLI surface: `rpc_save_session()`/
`rpc_restore_session()` live only in `gui_bridge.py` and are never imported into `ted_toolkit.py`,
so they're structurally invisible to `help_all()`'s listing (short of a user deliberately
importing the bridge module themselves at the prompt — an inherent, unavoidable property of a
real Python REPL, consistent with this codebase's existing eval/exec stance).

A saved `.tedsession` file is a zip (not one `pickle.dumps()` of everything, so a corrupt member
can never poison the rest): `manifest.json`, `transcript.txt` (GUI-side, from the tab's `pyte`
scrollback), `history.json`/`history.py` (the bridge's readline history, canonical + human-
readable), and `variables.pkl` (the bridge's pickled working variables — a per-variable
denylist-based filter, not `help_vars()`'s ALL-CAPS-blanket-exclusion display filter, so a user's
own ALL-CAPS variable is never silently dropped from a save).

Restore **never replays or `exec()`s a single history line** — it spawns a brand-new blank tab,
waits for that fresh session's own unconditional startup `os.system('cls')` + title prompt to
fully settle (auto-answering it with a blank Enter, exactly like a user pressing Enter there),
*then* seeds the old transcript into the tab's terminal display and sends the saved
history/variables over the bridge for pure `readline.add_history()` calls and direct namespace
injection. A restored session is usable immediately, with zero recomputation. (The ordering here
matters and was non-obvious: feeding the old transcript *before* the fresh session's own
`cls` call gets it silently wiped, since neither `pyte` nor real terminals preserve
erase-in-display content in scrollback.)

## Testing and what can't be automated

See CLAUDE.md for how to run the suite (`regression_test.bat`). The generated report always calls
out what the automated suite structurally cannot exercise:
- Real keystroke capture and ↑-arrow history recall (`pyreadline3` hooks the Windows console
  directly — there is no way to simulate this from a non-interactive test process). This was
  verified manually once, by hand, in a real terminal, after the Python 3.12 environment pin.
- tkinter file/folder dialogs and messagebox popups (`g_sel_file*`, `g_ask_*`, `g_show_*`) —
  these are one-line wrappers around blocking native dialogs; not unit tested by design.
- Excel COM automation (`view_in_excel=True` opening a real Excel window via `win32com`).
- Windows clipboard I/O (`win_copy`/`win_paste`/`*_table`).

Everything else — every guided function's core logic, the full xlsx/csv/txt import/export round
trip, the history-rewrite/kwarg-baking contract — is covered by the automated `pytest` suite.

`toolkit_gui/` adds several more manually-verified-only surfaces of its own (real ConPTY spawn
timing, `TerminalWidget` rendering and keystroke forwarding, the Save/Restore Session live
process handshake, CPU sampling) for the same fundamental reason as the items above — see
`run_regression_tests.py`'s `KNOWN_UNTESTABLE` list for the current, authoritative list and how
to verify each by hand. The pure logic underneath each of these (argv construction, pid
resolution, the `.tedsession` file format, the bridge RPC handlers, variable/table snapshot
filtering) is unit tested; only the parts requiring a live Qt event loop and a real spawned
process are not.
