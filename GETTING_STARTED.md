# Getting started with Ted's Toolkit

This guide takes a fresh Windows machine to a running toolkit session. Pick **one** of the
two installation flows:

| | Flow A: conda (recommended) | Flow B: standard Python + pip |
|---|---|---|
| Needs | Anaconda or Miniconda | Python **3.12** from python.org |
| Dependency file | `environment.yml` | `requirements.txt` |
| Command-line toolkit (`start_ted_toolkit.bat`) | yes | yes |
| Desktop GUI (`start_ted_toolkit_gui.bat`) | yes | not yet (conda only) |

> **Python 3.12 exactly.** Do not use Python 3.13 or newer. Its new default interactive
> console bypasses the `pyreadline3` hook that the toolkit's history capture depends on. That
> breaks the up-arrow recall of completed commands, `save_history()`, and session replay.

## Quick start: guided setup script

Double-click **`setup_toolkit.bat`** (or run it from a command prompt in the toolkit folder).
It will:

1. detect conda and/or Python 3.12 and ask which flow to use;
2. ask where to put the environment (default: a folder next to the toolkit folder);
3. create the environment, or update an existing one, and check that it is Python 3.12;
4. write **`local_env.cmd`**, a one-line, machine-specific activation command that
   `start_ted_toolkit.bat` and `regression_test.bat` use automatically;
5. optionally run the regression test suite.

The script can also run unattended, for example:
`powershell -ExecutionPolicy Bypass -File setup_toolkit.ps1 -Flow venv -EnvPath D:\envs\toolkit -Defaults`

To set up by hand instead, follow one of the flows below.

## Flow A: conda

1. Install [Miniconda or Anaconda](https://docs.conda.io/) if you don't have it.
2. Open an **Anaconda Prompt** in the toolkit folder and create the environment:
   ```
   conda env create -p C:\path\to\toolkit-env -f environment.yml
   ```
   (Or use a named environment: `conda env create -n toolkit-env -f environment.yml`.)
3. To rebuild it later, for example after `environment.yml` changes:
   ```
   conda env remove -p C:\path\to\toolkit-env
   conda env create -p C:\path\to\toolkit-env -f environment.yml
   ```
   To update it in place instead: `conda env update -p C:\path\to\toolkit-env -f environment.yml --prune`
4. Create `local_env.cmd` in the toolkit folder (see [Configure the launchers](#configure-the-launchers)):
   ```
   call "C:\ProgramData\Anaconda3\Scripts\activate.bat" "C:\path\to\toolkit-env"
   ```

## Flow B: standard Windows Python + pip

1. Install **Python 3.12.x** from <https://www.python.org/downloads/windows/>, using the
   "Windows installer (64-bit)". Keeping the default "py launcher" option is recommended.
2. Open a command prompt in the toolkit folder and create a virtual environment:
   ```
   py -3.12 -m venv C:\path\to\toolkit-venv
   ```
   (Without the py launcher: `"C:\Program Files\Python312\python.exe" -m venv C:\path\to\toolkit-venv`.)
3. Install the dependencies:
   ```
   C:\path\to\toolkit-venv\Scripts\python -m pip install --upgrade pip
   C:\path\to\toolkit-venv\Scripts\python -m pip install -r requirements.txt
   ```
4. Create `local_env.cmd` in the toolkit folder:
   ```
   call "C:\path\to\toolkit-venv\Scripts\activate.bat"
   ```

## Configure the launchers

`start_ted_toolkit.bat` and `regression_test.bat` look for a file named **`local_env.cmd`** in
the toolkit folder and `call` it to activate the environment. If the file does not exist, they
fall back to the original author's hardcoded conda paths
(`C:\ProgramData\Anaconda3`, `C:\Users\User\Documents\toolkit-env`).

`local_env.cmd` is machine-specific and is excluded from git via `.gitignore`. Delete it to go
back to the defaults.

The **desktop GUI** does not read `local_env.cmd` yet. To use it with a conda environment in a
different location, edit `ACTIVATE_BAT`, `ENV_PATH` and `TOOLKIT_PY` in `toolkit_gui\config.py`,
plus the paths in `start_ted_toolkit_gui.bat`. The setup script prints the values to use.

## First run

Double-click `start_ted_toolkit.bat`. You should see:

```
TED TOOLKIT Python tools interactive mode.

For fn reference type help_all().

Title for this session: >>>
```

Type a title (or just press Enter), then try `help_all()`. To check that history capture works,
type any command, press Enter, and then press **Up**: the command should be recalled. See
[README.md](README.md) for what the toolkit does and how guided functions work.

## Running the tests

Double-click `regression_test.bat`, or run `python -m pytest tests/` with the environment
activated. The generated report in `test_reports/` lists the features that can only be
verified by hand (clipboard, native dialogs, Excel automation, real keystrokes).

## Troubleshooting

- **Up-arrow history doesn't work / `save_history()` output is empty.** You are probably on
  Python 3.13+. Check with `python --version` in the activated environment, and rebuild it
  with 3.12.
- **"running scripts is disabled on this system"** when running `setup_toolkit.ps1` directly:
  use `setup_toolkit.bat`, which applies a process-only `-ExecutionPolicy Bypass`, or run
  `powershell -ExecutionPolicy Bypass -File setup_toolkit.ps1`.
- **`conda` is not recognized.** Use an Anaconda Prompt, or call conda by its full path
  (`C:\ProgramData\Anaconda3\Scripts\conda.exe`). The setup script finds common install
  locations on its own.
- **`pip install` fails on `pywin32` or `PySide6`.** Make sure the venv's Python is 64-bit 3.12
  (`python -c "import struct, sys; print(sys.version, struct.calcsize('P')*8)"`).
- **Paths with spaces.** `local_env.cmd` quotes every path, so these work for the command-line
  toolkit. The GUI's `toolkit_gui\config.py` paths must not contain spaces (see the note in
  `toolkit_gui\backend\env_resolve.py`).
