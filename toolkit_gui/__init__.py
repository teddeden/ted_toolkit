'''toolkit_gui - desktop GUI shell for Ted's Toolkit.

A separate top-level package from tedtoolkit/ (the toolkit itself, which
stays runnable exactly as before via start_ted_toolkit.bat). This package
hosts each GUI tab's interactive session as its own real
`python -i ted_toolkit.py` OS process, so the pyreadline3-based
history/guided-function mechanism keeps working completely unmodified - see
ABOUT.md for the full architecture writeup.
'''
