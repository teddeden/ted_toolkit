# PyInstaller spec stub for toolkit_gui.app - NOT wired up or tested yet.
#
# This is a placeholder for the "package as a standalone installable app
# with its own bundled interpreter" step the user described as deliberate
# future/second-step work (see the GUI shell feature's plan) - it is not
# part of this feature and has not been run. When that work starts:
#   pyinstaller toolkit_gui.spec
# will need at minimum:
#   - hiddenimports for PySide6's plugin-loaded modules
#   - datas for tedtoolkit/ (the interpreter runs ted_toolkit.py as a real
#     script via ConPTY, not as frozen bytecode - the bundled interpreter
#     needs a real, unfrozen copy of the toolkit source tree alongside it)
#   - a bundled conda-equivalent Python environment (or a venv built from
#     environment.yml's pip section) in place of relying on toolkit-env
#     existing on the target machine - see toolkit_gui/config.py's
#     ACTIVATE_BAT/ENV_PATH/TOOLKIT_PY constants, which assume a real
#     Anaconda + toolkit-env installation today

block_cipher = None

a = Analysis(
    ['toolkit_gui/app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='TedToolkitGUI',
    console=False,
)
