'''tedtoolkit - Ted's Toolkit as an installable package.

Aggregates every submodule's public API here so that the interactive
session launcher (root ted_toolkit.py) can do `from tedtoolkit import *`
and get the same flat, bare-callable namespace the original single-file
toolkit provided. Only non-underscore names are re-exported by wildcard
import (consistent with the original design: underscore-prefixed helpers
are internal and are imported explicitly by name where needed, never
typed directly by a user at the interactive prompt).

Phase 1 note: only history/validation/prompts have been migrated so far.
Later phases add more submodules here as they're migrated out of
ted_toolkit.py / load_save.py.
'''

from .history import *
from .validation import *
from .prompts import *
from .util import *
from .clipboard import *
from .introspect import *
from .gui.dialogs import *
from .io.xlsx import *
from .io.csv import *
from .io.txt import *
from .tables.columns import *
from .tables.preview import *
from .tables.reconcile import *
from .tables.join import *
from .tables.aggregate import *
