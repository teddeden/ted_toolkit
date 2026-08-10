'''Tests for toolkit_gui.session_persistence's pure logic.'''

from toolkit_gui.session_persistence import _is_bare_prompt_line


def test_bare_prompt_line_is_recognized():
    assert _is_bare_prompt_line('some banner text\n\n>>> ')


def test_unanswered_title_prompt_is_not_a_bare_prompt():
    '''Regression guard: this line also ends with ">>>", but it is NOT a
    genuine idle prompt - restoring must not fire while this is the last
    visible line, or the fed transcript lands on the same line as it.'''
    assert not _is_bare_prompt_line('Title for this session: >>> ')


def test_empty_screen_is_not_a_bare_prompt():
    assert not _is_bare_prompt_line('\n\n\n')


def test_prompt_with_partial_typed_input_is_not_bare():
    assert not _is_bare_prompt_line('>>> some_partial_inp')
