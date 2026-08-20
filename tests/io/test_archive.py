'''Tests for tedtoolkit.io.archive's decompress_xml_archive()/xml_archive_import(), mirroring
test_xml.py's pattern: pure-core tests against small in-memory .tar.gz fixtures, wrapper
zero-prompt round-trip tests, and kwarg-baking regression tests.'''

import io
import os
import readline
import tarfile

import pytest

from tedtoolkit.history import _check_assignment
from tedtoolkit.io.archive import (decompress_xml_archive, xml_archive_import, _open_archive,
                                   _decompress_xml_archive_core, _xml_archive_import_core)
from tedtoolkit.io import archive as archive_module
from tedtoolkit.io import xml as xml_module  # _resolve_flatten_kwargs's prompts live here
from tedtoolkit import prompts as prompts_module

_FULLY_SPECIFIED = dict(list_strategy='explode', max_depth=None, namespace_mode='strip',
                        on_malformed='raise', low_memory=False, header_row=True)


def _build_tar_gz(members):
    '''members: dict[name] -> str content. Returns .tar.gz bytes with those members.'''
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for name, content in members.items():
            data = content.encode('utf-8')
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _open_archive - source normalization
# ---------------------------------------------------------------------------

def test_open_archive_from_bytes(orders_archive_bytes):
    with _open_archive(orders_archive_bytes) as tar:
        assert sorted(m.name for m in tar.getmembers()) == \
              ['a.xml', 'b.xml', 'readme.txt', 'sub/c.xml']


def test_open_archive_from_path(tmp_path, single_member_archive_bytes):
    path = tmp_path / 'bundle.tar.gz'
    path.write_bytes(single_member_archive_bytes)
    with _open_archive(str(path)) as tar:
        assert [m.name for m in tar.getmembers()] == ['only.xml']


def test_open_archive_from_file_like(single_member_archive_bytes):
    with _open_archive(io.BytesIO(single_member_archive_bytes)) as tar:
        assert [m.name for m in tar.getmembers()] == ['only.xml']


# ---------------------------------------------------------------------------
# _xml_archive_import_core
# ---------------------------------------------------------------------------

def test_core_flattens_every_xml_member(orders_archive_bytes):
    result = _xml_archive_import_core(orders_archive_bytes, record_path='Root.Rec',
                                      **_FULLY_SPECIFIED)
    assert set(result.keys()) == {'a.xml', 'b.xml', 'sub/c.xml'}
    assert result['a.xml'] == [['X'], ['1'], ['11']]
    assert result['b.xml'] == [['X', 'Y'], ['2', '9']]
    assert result['sub/c.xml'] == [['X'], ['3']]


def test_core_skips_non_xml_members_with_warning(orders_archive_bytes, capsys):
    result = _xml_archive_import_core(orders_archive_bytes, record_path='Root.Rec',
                                      **_FULLY_SPECIFIED)
    assert 'readme.txt' not in result
    assert 'skipping non-XML archive member: readme.txt' in capsys.readouterr().out


def test_core_no_xml_members_returns_empty_dict(no_xml_archive_bytes, capsys):
    result = _xml_archive_import_core(no_xml_archive_bytes, **_FULLY_SPECIFIED)
    assert result == {}
    assert 'no .xml members found' in capsys.readouterr().out


def test_core_column_order_stable_unifies_across_members(orders_archive_bytes):
    result = _xml_archive_import_core(orders_archive_bytes, record_path='Root.Rec',
                                      column_order='stable', **_FULLY_SPECIFIED)
    assert result['a.xml'][0] == ['X', 'Y']
    assert result['b.xml'][0] == ['X', 'Y']
    assert result['a.xml'][1] == ['1', '']
    assert result['sub/c.xml'][0] == ['X', 'Y']


def test_core_low_memory_matches_full_parse(orders_archive_bytes):
    full = _xml_archive_import_core(orders_archive_bytes, record_path='Root.Rec',
                                    **_FULLY_SPECIFIED)
    streaming = _xml_archive_import_core(orders_archive_bytes, record_path='Root.Rec',
                                        **{**_FULLY_SPECIFIED, 'low_memory': True})
    assert full == streaming


def test_core_auto_detects_record_path():
    '''Uses a fixture where the member has a REPEATING <Rec> (auto-detect only picks 'Rec' as the
    record when it recurs - a single Rec per member falls back to treating root as the record,
    which is exercised separately/correctly elsewhere, e.g. orders_archive_bytes's single-Rec
    members).'''
    archive_bytes = _build_tar_gz({'a.xml': '<Root><Rec><X>1</X></Rec><Rec><X>2</X></Rec></Root>'})
    with_path = _xml_archive_import_core(archive_bytes, record_path='Root.Rec',
                                         **_FULLY_SPECIFIED)
    auto = _xml_archive_import_core(archive_bytes, record_path=None, **_FULLY_SPECIFIED)
    assert auto == with_path == {'a.xml': [['X'], ['1'], ['2']]}


def test_core_from_path(tmp_path, orders_archive_bytes):
    path = tmp_path / 'bundle.tar.gz'
    path.write_bytes(orders_archive_bytes)
    result = _xml_archive_import_core(str(path), record_path='Root.Rec', **_FULLY_SPECIFIED)
    assert result['a.xml'] == [['X'], ['1'], ['11']]


def test_core_from_file_like(orders_archive_bytes):
    result = _xml_archive_import_core(io.BytesIO(orders_archive_bytes), record_path='Root.Rec',
                                      **_FULLY_SPECIFIED)
    assert result['a.xml'] == [['X'], ['1'], ['11']]


def test_core_on_malformed_raise_raises(malformed_member_archive_bytes):
    from lxml import etree
    with pytest.raises(etree.XMLSyntaxError):
        _xml_archive_import_core(malformed_member_archive_bytes,
                                 **{**_FULLY_SPECIFIED, 'on_malformed': 'raise'})


def test_core_on_malformed_skip_skips_only_bad_member(malformed_member_archive_bytes):
    result = _xml_archive_import_core(malformed_member_archive_bytes, record_path='Root.Rec',
                                      **{**_FULLY_SPECIFIED, 'on_malformed': 'skip'})
    assert result['good.xml'] == [['X'], ['1']]
    assert result['bad.xml'] == [[]]


def test_core_return_metadata_shape(orders_archive_bytes):
    result = _xml_archive_import_core(orders_archive_bytes, record_path='Root.Rec',
                                      return_metadata=True, **_FULLY_SPECIFIED)
    table, metadata = result['a.xml']
    assert table == [['X'], ['1'], ['11']]
    assert metadata['record_count'] == 2


# ---------------------------------------------------------------------------
# _decompress_xml_archive_core
# ---------------------------------------------------------------------------

def test_decompress_core_extracts_everything_including_non_xml(tmp_path, orders_archive_bytes):
    dest = tmp_path / 'out'
    extracted = _decompress_xml_archive_core(orders_archive_bytes, str(dest))
    names = {os.path.relpath(p, dest).replace(os.sep, '/') for p in extracted}
    assert names == {'a.xml', 'b.xml', 'readme.txt', 'sub/c.xml'}
    assert (dest / 'readme.txt').read_text() == 'not xml'
    assert (dest / 'sub' / 'c.xml').is_file()


def test_decompress_core_returns_only_file_paths(tmp_path, orders_archive_bytes):
    dest = tmp_path / 'out'
    extracted = _decompress_xml_archive_core(orders_archive_bytes, str(dest))
    assert all(os.path.isfile(p) for p in extracted)


def test_decompress_core_creates_destination_folder(tmp_path, single_member_archive_bytes):
    dest = tmp_path / 'does' / 'not' / 'exist' / 'yet'
    assert not dest.exists()
    _decompress_xml_archive_core(single_member_archive_bytes, str(dest))
    assert dest.is_dir()
    assert (dest / 'only.xml').is_file()


def test_decompress_core_rejects_path_traversal_member(tmp_path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        data = b'evil'
        info = tarfile.TarInfo(name='../evil.txt')
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    dest = tmp_path / 'sub' / 'out'
    with pytest.raises(tarfile.OutsideDestinationError):
        _decompress_xml_archive_core(buf.getvalue(), str(dest))
    assert not (tmp_path / 'evil.txt').exists()


# ---------------------------------------------------------------------------
# xml_archive_import() wrapper: zero-prompt round trip + kwarg-baking
# ---------------------------------------------------------------------------

def test_xml_archive_import_wrapper_zero_prompts_when_fully_specified(no_prompts,
                                                                       orders_archive_bytes):
    # archive_path is supplied explicitly (no g_sel_file prompt); the curated flattening-kwarg
    # prompts (record_path/list_strategy/etc) are resolved by xml.py's shared
    # _resolve_flatten_kwargs(), so that's where ask_yn/_prompt_for_* must be patched, not
    # archive.py (which doesn't import ask_yn/those prompt helpers at all).
    no_prompts(xml_module, 'ask_yn', '_prompt_for_list_arg', '_prompt_for_bool_arg')
    result = xml_archive_import(archive_path=orders_archive_bytes, record_path='Root.Rec',
                                **_FULLY_SPECIFIED)
    assert result['a.xml'] == [['X'], ['1'], ['11']]


def test_xml_archive_import_bakes_prompted_kwargs_into_history(monkeypatch, seed_history,
                                                               orders_archive_bytes):
    monkeypatch.setattr(xml_module, 'ask_yn', lambda *a, **k: True)
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    seed_history('result = xml_archive_import(archive_path=archive_bytes)')
    xml_archive_import(archive_path=orders_archive_bytes)
    rewritten = readline.get_history_item(1)
    assert 'xml_archive_import(' in rewritten
    for kwarg in ('record_path=', 'list_strategy=', 'max_depth=', 'namespace_mode=',
                 'on_malformed=', 'low_memory=', 'header_row='):
        assert kwarg in rewritten, '{} missing from: {}'.format(kwarg, rewritten)


def test_xml_archive_import_wrapper_returns_none_when_selection_cancelled(monkeypatch):
    monkeypatch.setattr(archive_module, 'g_sel_file', lambda **k: '')
    result = xml_archive_import()
    assert result is None


# ---------------------------------------------------------------------------
# decompress_xml_archive() wrapper: check_assignment, zero-prompt round trip, kwarg-baking
# ---------------------------------------------------------------------------

def test_decompress_xml_archive_requires_assignment(seed_history):
    seed_history('decompress_xml_archive(archive_path="x", destination_folder="y")')
    with pytest.raises(Exception):
        _check_assignment(function_name='decompress_xml_archive')


def test_decompress_xml_archive_wrapper_zero_prompts_when_fully_specified(
        tmp_path, seed_history, orders_archive_bytes):
    dest = tmp_path / 'out'
    seed_history(f"result = decompress_xml_archive(archive_path=archive_bytes, "
                f"destination_folder='{dest}')")
    result = decompress_xml_archive(archive_path=orders_archive_bytes,
                                    destination_folder=str(dest))
    assert len(result) == 4


def test_decompress_xml_archive_bakes_prompted_kwargs_into_history(monkeypatch, seed_history,
                                                                    tmp_path,
                                                                    single_member_archive_bytes):
    dest = tmp_path / 'out'
    monkeypatch.setattr(archive_module, 'g_sel_file', lambda **k: str(tmp_path / 'archive.tar.gz'))
    monkeypatch.setattr(archive_module, 'g_sel_folder', lambda **k: str(dest))
    archive_path = tmp_path / 'archive.tar.gz'
    archive_path.write_bytes(single_member_archive_bytes)
    seed_history('result = decompress_xml_archive()')
    decompress_xml_archive()
    rewritten = readline.get_history_item(1)
    assert 'decompress_xml_archive(' in rewritten
    assert 'archive_path=' in rewritten
    assert 'destination_folder=' in rewritten
