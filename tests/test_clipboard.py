'''Tests for tedtoolkit.clipboard's pickled copy/paste: the pure _pickle_to_text()/
_text_from_pickle() cores, and the win_copy_pickle()/win_paste_pickle() wrappers with the
real Windows clipboard and file dialogs monkeypatched out.'''

import datetime
import readline

import pytest

from tedtoolkit import clipboard
from tedtoolkit.clipboard import _pickle_to_text, _text_from_pickle, PICKLE_TEXT_MAGIC


def _sample_tree():
    return {
        'root': {'children': [{'name': 'a', 'tags': {'x', 'y'}, 'pos': (1, 2)},
                              {'name': 'b', 'children': []}]},
        'table': [['h1', 'h2'], [1, 2.5], [None, 'ünïcødé']],
        'when': datetime.datetime(2026, 10, 28, 9, 30),
        'big': list(range(10_000)),
    }


@pytest.fixture
def fake_clipboard(monkeypatch):
    store = {'text': ''}
    monkeypatch.setattr(clipboard, 'win_copy', lambda text: store.__setitem__('text', str(text)))
    monkeypatch.setattr(clipboard, 'win_paste', lambda: store['text'])
    return store


# --- pure cores -----------------------------------------------------------------------

@pytest.mark.parametrize('value', [_sample_tree(), [], 0, 'text', {1, 2}, (None,), b'\x00\xff'])
def test_round_trip(value):
    assert _text_from_pickle(_pickle_to_text(value)) == value


def test_text_is_ascii_header_plus_wrapped_lines():
    text = _pickle_to_text(_sample_tree())
    lines = text.splitlines()
    assert lines[0].startswith(PICKLE_TEXT_MAGIC + ' ')
    assert all(len(line) <= 76 for line in lines[1:])
    text.encode('ascii')


def test_tolerates_crlf_rewrapping_and_leading_notes():
    text = _pickle_to_text(_sample_tree())
    header, *body = text.splitlines()
    mangled = 'my notes about this tree\r\n\r\n' + header + '\r\n' + '\r\n  '.join(
        ''.join(body)[pos:pos + 50] for pos in range(0, len(''.join(body)), 50)) + '  \r\n'
    assert _text_from_pickle(mangled) == _sample_tree()


def test_rejects_text_without_header():
    with pytest.raises(ValueError, match='header'):
        _text_from_pickle('just some text')


def test_rejects_truncated_payload():
    text = _pickle_to_text(_sample_tree())
    with pytest.raises(ValueError):
        _text_from_pickle(text[:len(text) // 2])


def test_rejects_checksum_mismatch():
    header, *body = _pickle_to_text([1, 2, 3]).splitlines()
    magic, _checksum, count = header.split()
    with pytest.raises(ValueError, match='checksum'):
        _text_from_pickle('\n'.join([f'{magic} 0000000000000000 {count}'] + body))


# --- wrappers -------------------------------------------------------------------------

def test_clipboard_round_trip(fake_clipboard, seed_history, capsys):
    clipboard.win_copy_pickle(_sample_tree())
    assert fake_clipboard['text'].startswith(PICKLE_TEXT_MAGIC)
    assert 'copied to clipboard' in capsys.readouterr().out
    seed_history('tree = win_paste_pickle()')
    assert clipboard.win_paste_pickle() == _sample_tree()


def test_file_round_trip(tmp_path, fake_clipboard, seed_history):
    path = str(tmp_path / 'tree.txt')
    clipboard.win_copy_pickle(_sample_tree(), file_path=path)
    assert fake_clipboard['text'] == ''
    seed_history(f'tree = win_paste_pickle(file_path={path!r})')
    assert clipboard.win_paste_pickle(file_path=path) == _sample_tree()


def test_file_read_tolerates_notepad_bom(tmp_path, seed_history):
    path = tmp_path / 'tree.txt'
    path.write_text(_pickle_to_text([1, 2]), encoding='utf-8-sig')
    seed_history('x = win_paste_pickle(file_path="...")')
    assert clipboard.win_paste_pickle(file_path=str(path)) == [1, 2]


def test_paste_requires_assignment(fake_clipboard, seed_history):
    fake_clipboard['text'] = _pickle_to_text([1])
    seed_history('win_paste_pickle()')
    with pytest.raises(Exception, match='assign'):
        clipboard.win_paste_pickle()


def test_empty_file_path_prompts_and_bakes_chosen_path(tmp_path, monkeypatch, seed_history):
    path = str(tmp_path / 'tree.txt')
    monkeypatch.setattr(clipboard, 'g_sel_file_to_write', lambda **kwargs: path)
    seed_history("win_copy_pickle(tree, file_path='')")
    clipboard.win_copy_pickle({'a': 1}, file_path='')
    assert readline.get_history_item(1) == f'win_copy_pickle(tree, file_path={path!r})'

    monkeypatch.setattr(clipboard, 'g_sel_file', lambda **kwargs: path)
    seed_history("t = win_paste_pickle(file_path='')")
    assert clipboard.win_paste_pickle(file_path='') == {'a': 1}
    assert readline.get_history_item(1) == f't = win_paste_pickle(file_path={path!r})'
