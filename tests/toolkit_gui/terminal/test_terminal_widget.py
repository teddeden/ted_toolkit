'''Tests for toolkit_gui.terminal.terminal_widget's pure helper logic.

TerminalWidget itself (real Qt painting, a live PtySession, keyboard-event
handling) is not exercised here - that requires a real ConPTY-hosted session
and a visible Qt event loop, verified manually instead (see Phase 3's
screenshot-based verification and regression_test.bat's KNOWN_UNTESTABLE
list), consistent with this codebase's existing precedent for tkinter
dialogs/Excel COM/clipboard.
'''

import pyte

from toolkit_gui.terminal.terminal_widget import _row_to_text


def test_row_to_text_flattens_pyte_scrollback_row_in_column_order():
    screen = pyte.HistoryScreen(10, 3, history=50)
    stream = pyte.Stream(screen)
    stream.feed('hello\r\n')
    for _ in range(5):
        stream.feed('x\r\n')
    assert len(screen.history.top) > 0
    row = screen.history.top[0]
    assert _row_to_text(row).rstrip() == 'hello'
