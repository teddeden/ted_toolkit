# CLAUDE.md

Guidance for Claude (or any agent) working in this repository. See also [ABOUT.md](ABOUT.md)
for the architecture/onboarding doc — read that first if you're new to the codebase.

## Project summary

Ted's Toolkit is a Windows-only, conda-based interactive Python data-analysis CLI. It stores
tabular data as lists-of-lists (intentionally, no pandas/numpy) and is launched via
`start_ted_toolkit.bat`, which activates the `toolkit-env` conda environment and runs
`python -i ted_toolkit.py`. The bulk of the implementation lives in the installable `tedtoolkit/`
package; `ted_toolkit.py` at the repo root is a thin interactive-session launcher only — see its
own module docstring for why several functions (`help_all`, `help_vars`, `save_function_reference`,
`_run_script`, `continue_execution`) must stay there rather than move into the package.

## Environment

- Required: `python=3.12` specifically. Do not upgrade past 3.12 — Python 3.13's new default
  REPL (`_pyrepl`) bypasses the `PyOS_ReadlineFunctionPointer` hook `pyreadline3` depends on,
  which breaks this toolkit's entire history-capture/replay mechanism. This was root-caused and
  fixed once already; don't reintroduce it.
- Environment spec lives in `environment.yml`. Recreate with:
  `conda env remove -p <path>` then `conda env create -p <path> -f environment.yml`.
- Add new dependencies to `environment.yml`, not just to the live environment.

## Design conventions (established during the 2026 refactor — keep following these)

- **Lists-of-lists, not pandas.** This is a deliberate design choice, not a gap. Do not introduce
  pandas/numpy as a dependency.
- **Core/wrapper split for every "guided" function.** Interactive functions that prompt the user
  (`data_aggregate`, `data_join`, `compare_columns`, etc.) are split into a thin public wrapper
  (handles `_check_assignment`, prompting, and baking resolved kwargs into readline history via
  `_add_kwarg_to_last_command`) and a pure `_<name>_core` function (explicit args in, explicit
  result out, no prompting, no history side effects). When adding a new guided function or
  extending an existing one, follow this same pattern — see `tedtoolkit/tables/aggregate.py`'s
  `data_de_aggregate`/`_data_de_aggregate_core` pair for the simplest worked example.
- **The wrapper's public name and signature never change.** `save_history()`/`_run_script()`
  replay saved sessions via `exec()` on a single history line — a wrapper's call signature is a
  durable, load-bearing contract, not an implementation detail.
- **`eval()`/`exec()` usage in this codebase is intentional, not a bug.** History replay,
  `compare_columns()`'s `first_col_conv` user-transform-expression feature, and the `help_all()`/
  `help_vars()` introspection helpers all use `eval()`/`exec()` by design. Do not sandbox, remove,
  or "fix" these under a code-quality banner — see the do-not-touch note in ABOUT.md.
- **Preserve the interactive UI/UX flow exactly.** Prompt wording, prompt order, and default
  values are part of the product, not incidental code. Refactors, lint fixes, and dependency
  bumps must not change what a user sees or how many keystrokes a guided function takes, unless
  the user explicitly asks for a UX change.
- **Fix bugs you find, but don't invent missing functionality.** If you find a defect with an
  obvious, narrow, correct fix (an undefined name, a missing `continue`, a typo), fix it and add a
  regression test — this has repeatedly turned up real bugs during the refactor (see git log).
  If you find a call to a function that's missing entirely with no reference implementation to
  restore (e.g. `data_recon()`'s `_sel_compare_cols`/`_check_convert_text_cols` — see ABOUT.md),
  do not invent an implementation. Document the gap and ask the user, don't guess at intent.

## Testing

- `pytest` suite lives under `tests/`, mirroring `tedtoolkit/`'s package structure by theme.
- Run the full suite with `regression_test.bat` (see below) or directly via
  `python -m pytest tests/`.
- Shared fixtures live in `tests/conftest.py`: `reset_readline_history` (autouse), `seed_history`,
  `no_prompts`, `recording_kwarg_adder`. Reuse these rather than reinventing history-state setup.
- Some functionality cannot be exercised by the automated suite (real console keystroke capture,
  tkinter dialogs, Excel COM automation, Windows clipboard). `regression_test.bat`'s generated
  report always lists these explicitly — read that list before claiming "all tests pass" means
  the toolkit fully works.

## Git workflow

- **Never push directly to `main`.** Always work on a feature branch
  (`feature/<short-description>`), push there, and open a merge into `main` only after the full
  regression suite passes.
- **Version bump on every merge to `main`.** `VERSION` in `ted_toolkit.py` starts at `"0.70"`.
  Each merge into `main` increments it by `0.01` (`0.70` → `0.71` → `0.72` ...). Bump the version
  as part of the merge, after tests pass, not before.
- **Merge commit messages must include the new version number**, e.g.
  `Merge feature/xyz into main (v0.71)`.
- **Review [ABOUT.md](ABOUT.md) on every merge request** and update it if the change affects
  architecture, module responsibilities, known gaps, or how to run/test the toolkit. Stale
  onboarding docs are worse than no docs.

## Linting

- `pylint` is available in `toolkit-env`. Minor/style findings should just be fixed inline as
  part of normal work. Findings that would change public behavior, or that flag something on the
  do-not-touch list above (`eval`/`exec` usage, the guided-function prompting pattern, deliberate
  broad exception handling in interactive error paths) should be reported, not auto-fixed —
  confirm with the user before changing anything that touches the interactive UI/UX.
