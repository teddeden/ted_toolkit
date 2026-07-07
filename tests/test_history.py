'''Tests for tedtoolkit.history's readline-history-rewrite primitives.

Regression coverage for a bug where _quoted() naively wrapped text in quote
characters without escaping it, so a string containing a newline (e.g.
line_terminator='\\n', an actual newline character) got spliced into history as
a literal newline - corrupting the single-line replayable command and breaking
subsequent exec()-based replay with a SyntaxError.
'''

import readline

from tedtoolkit.history import _quoted, _add_kwarg_to_last_command


def test_quoted_round_trips_plain_string():
    assert eval(_quoted('hello')) == 'hello'


def test_quoted_round_trips_string_with_single_quote():
    assert eval(_quoted("it's a test")) == "it's a test"


def test_quoted_round_trips_string_with_double_quote():
    assert eval(_quoted('say "hi"')) == 'say "hi"'


def test_quoted_round_trips_string_with_both_quote_styles():
    assert eval(_quoted('''both ' and " quotes''')) == '''both ' and " quotes'''


def test_quoted_round_trips_newline():
    '''The exact bug reported: line_terminator='\\n' is a single newline character.'''
    assert eval(_quoted('\n')) == '\n'


def test_quoted_round_trips_tab_and_backslash():
    assert eval(_quoted('a\tb\\c')) == 'a\tb\\c'


def test_quoted_output_has_no_raw_control_characters():
    '''The whole point: the literal must stay on one line so it can be spliced into
    a single readline history entry / single exec()'d script line.'''
    quoted = _quoted('\n')
    assert '\n' not in quoted
    assert '\r' not in quoted


def test_add_kwarg_to_last_command_with_newline_value_replays_correctly(seed_history):
    '''End-to-end proof: the rewritten history line must be valid, single-line,
    exec()-able Python that reconstructs the original newline value - this is
    what save_history()/_run_script() depend on for every saved session.'''
    captured = {}
    def fake_csv_import(**kwargs):
        captured.update(kwargs)
    seed_history("result = fake_csv_import(file_path='in.csv')")
    _add_kwarg_to_last_command('line_terminator', _quoted('\n'), fn_name='fake_csv_import')
    rewritten = readline.get_history_item(1)
    assert '\n' not in rewritten
    exec(rewritten, {'fake_csv_import': fake_csv_import})
    assert captured['line_terminator'] == '\n'
