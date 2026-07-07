# Ted's Toolkit

A Windows-only, conda-based interactive Python CLI for exploring and transforming tabular data —
pivoting, joining, reconciling, and comparing tables from a `python -i` prompt, without pandas.

## Why lists of lists, not pandas?

Tables here are plain Python `list[list]` objects: `[[header1, header2], [row1col1, row1col2], ...]`.
This is a deliberate design choice, not a legacy gap — for this toolkit's workflow (ad hoc,
interactive, one column/table at a time) a list of lists is considered more transparent and
easier to reason about at a `>>>` prompt than a DataFrame. No pandas/numpy dependency is planned.

## How it works

You launch into a live Python session with every toolkit function already loaded into the global
namespace — every function below is called bare, by name, no imports needed.

The toolkit's core functions (`data_aggregate`, `data_join`, `compare_columns`, `reconcile`,
`data_import`, `data_export`, ...) are **guided**: call them with as few or as many arguments as
you already know, and they'll interactively prompt you for whatever's missing.

```
>>> x = data_de_aggregate(my_table)
Does your data contain headers? (Y/n):
```

The interesting part: once you answer the prompts, the toolkit doesn't just use your answer — it
rewrites the command you already typed in your shell history, splicing your answers in as keyword
arguments. Press ↑ afterwards and instead of `data_de_aggregate(my_table)` you'll see:

```
x = data_de_aggregate(my_table, headers=True, aggregation_key_col=2, delim=', ')
```

fully parameterized and ready to re-run with zero prompts. That's the point of the tool: work
interactively once, then call `save_history()` to dump your whole rewritten session to a `.py`
script — a fully-parameterized, non-interactive script that reproduces the same analysis. Run that
script again later by passing its path as an argument to `ted_toolkit.py`, and it replays with no
prompts at all.

For the full architectural write-up (module-by-module layout, the core/wrapper split pattern
every guided function follows, known gaps, and the do-not-touch list), see [ABOUT.md](ABOUT.md).

## Requirements

- Windows (the history-capture mechanism and several I/O helpers — clipboard, Excel COM, native
  file dialogs — are Windows-specific)
- [Anaconda or Miniconda](https://docs.conda.io/)
- Python **3.12** exactly — pinned in `environment.yml`. Python 3.13's new default REPL bypasses
  the hook that the history-capture feature depends on, so don't bump past 3.12.

## Setup

```
conda env create -n toolkit-env -f environment.yml
```

`start_ted_toolkit.bat` currently hardcodes this machine's conda install path, environment path,
and toolkit checkout path. If you're setting this up on a different machine, edit the three paths
in `start_ted_toolkit.bat` to match your own conda installation, environment location, and where
you cloned this repo.

## Running it

Double-click (or run) `start_ted_toolkit.bat`. This activates `toolkit-env` and runs
`python -i ted_toolkit.py`, which loads every toolkit function into your session and drops you
into an interactive prompt.

To replay a previously saved script with no prompts:

```
start_ted_toolkit.bat path\to\saved_script.py
```

## Getting contextual help

- `help_all()` — prints every public function, grouped by category, with a one-line description
  of each.
- `help(function_name)` — standard Python help, shows the function's full docstring (usage,
  kwargs, examples).
- `help_vars()` — lists every variable currently defined in your session, with type and a preview
  of its contents — useful mid-session when you've lost track of what you've created.
- `data_preview(some_variable)` — prints a quick structural summary of any table/list/dict
  (row/column counts, first couple of values) without dumping the whole thing to the screen.

## Testing

```
regression_test.bat
```

Runs the full `pytest` suite and writes a Markdown report to `test_reports/`. The report always
lists which functionality *can't* be covered by an automated run (real keystroke/history-recall
capture, native file/message dialogs, Excel COM, clipboard I/O) so a green run is never mistaken
for full coverage of those paths.

## Project docs

- [ABOUT.md](ABOUT.md) — architecture deep dive, module layout, known gaps, do-not-touch list.
- [CLAUDE.md](CLAUDE.md) — conventions for contributing (git workflow, versioning, linting, design
  rules) followed by both human and AI contributors to this repo.
