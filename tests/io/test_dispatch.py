import io
import os
import readline
import tarfile

from tedtoolkit.io.dispatch import data_import, data_export, _file_ext, _detect_format
from tedtoolkit import prompts as prompts_module


def test_file_ext():
    assert _file_ext('/a/b/c.CSV') == 'csv'
    assert _file_ext('data.xlsx') == 'xlsx'
    assert _file_ext('noext') == ''


def test_file_ext_double_suffix_archive_extension_is_a_known_limitation():
    '''Pins the exact wrinkle _detect_format() exists to work around: os.path.splitext() only
    ever splits on the LAST dot, so _file_ext() alone can't recognize .tar.gz as one unit.'''
    assert _file_ext('bundle.tar.gz') == 'gz'


def test_detect_format_recognizes_tar_gz_and_tgz():
    assert _detect_format('bundle.tar.gz') == 'xml_archive'
    assert _detect_format('BUNDLE.TAR.GZ') == 'xml_archive'
    assert _detect_format('bundle.tgz') == 'xml_archive'
    assert _detect_format('data.xml') == 'xml'
    assert _detect_format('data.csv') == 'csv'


def _make_archive_bytes():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for name, text in {'a.xml': '<Root><Rec><X>1</X></Rec></Root>',
                           'b.xml': '<Root><Rec><X>2</X></Rec></Root>'}.items():
            data = text.encode('utf-8')
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_csv_round_trip(tmp_path):
    file_path = str(tmp_path / 'test.csv')
    table = [['id', 'name', 'amount'], [1, 'George', 100], [2, 'Ben', 50]]
    data_export(table, file_path=file_path, delim=',', quote_mark='"', encoding='utf_8',
                line_terminator='\n', quoting='QUOTE_MINIMAL', convert_dates=False,
                date_format=None)
    result = data_import(file_path=file_path, delim=',', quote_mark='"', encoding='utf_8',
                         line_terminator='\n', quoting='QUOTE_MINIMAL', convert_numbers=True,
                         convert_dates=False, date_format=None)
    assert result == table


def test_txt_round_trip(tmp_path):
    file_path = str(tmp_path / 'test.txt')
    table = [['id', 'name'], [1, 'a']]
    data_export(table, file_path=file_path, process_as='txt')
    result = data_import(file_path=file_path, process_as='txt')
    # Windows text-mode open() translates '\n' -> os.linesep on write; normalize before comparing.
    assert [line.replace('\r\n', '\n') for line in result] == ['id\tname\n', '1\ta\n']


def test_xlsx_round_trip(tmp_path):
    file_path = str(tmp_path / 'test.xlsx')
    table = [['id', 'name'], [1, 'George'], [2, 'Ben']]
    data_export(table, file_path=file_path, wb_filter=True, view_in_excel=False)
    result = data_import(file_path=file_path, selected_sheet='Sheet1')
    assert result == table


def test_data_export_appends_missing_extension(tmp_path):
    file_path_no_ext = str(tmp_path / 'test')
    table = [['a'], [1]]
    data_export(table, file_path=file_path_no_ext, process_as='csv', delim=',', quote_mark='"',
                encoding='utf_8', line_terminator='\n', quoting='QUOTE_MINIMAL',
                convert_dates=False, date_format=None)
    assert os.path.isfile(file_path_no_ext + '.csv')


def test_data_export_rejects_non_table_for_csv(tmp_path):
    import pytest
    file_path = str(tmp_path / 'bad.csv')
    with pytest.raises(Exception):
        data_export('not a table', file_path=file_path, process_as='csv', delim=',',
                    quote_mark='"', encoding='utf_8', line_terminator='\n',
                    quoting='QUOTE_MINIMAL', convert_dates=False, date_format=None)


_XML_FULLY_SPECIFIED = dict(record_path=None, list_strategy='explode', max_depth=None,
                           namespace_mode='strip', on_malformed='raise', low_memory=False,
                           header_row=True)


def test_data_import_xml_single_file(tmp_path):
    file_path = tmp_path / 'test.xml'
    file_path.write_text('<Root><Rec><X>1</X></Rec><Rec><X>2</X></Rec></Root>', encoding='utf-8')
    result = data_import(file_path=str(file_path), **_XML_FULLY_SPECIFIED)
    assert result == [['X'], ['1'], ['2']]


def test_data_import_xml_directory_bulk_mode(tmp_path):
    '''Regression test for the directory-path guard fix: a directory file_path must reach XML
    bulk mode, not be discarded by the "not os.path.isfile" GUI-fallback check.'''
    (tmp_path / 'a.xml').write_text('<Root><Rec><X>1</X></Rec></Root>', encoding='utf-8')
    (tmp_path / 'b.xml').write_text('<Root><Rec><X>2</X></Rec></Root>', encoding='utf-8')
    result = data_import(file_path=str(tmp_path), process_as='xml', record_path='Root.Rec',
                         **{k: v for k, v in _XML_FULLY_SPECIFIED.items() if k != 'record_path'})
    assert result == {'a.xml': [['X'], ['1']], 'b.xml': [['X'], ['2']]}


def test_data_export_xml_extension_still_prompts_among_non_xml_formats(monkeypatch, seed_history,
                                                                        tmp_path):
    '''data_export() must NOT gain 'xml' as a resolvable process_as (no XML export exists) - a
    .xml path stays ambiguous and falls back to the xlsx/csv/txt selection prompt, exactly as
    before this feature was added.'''
    from tedtoolkit.io import dispatch as dispatch_module

    def fake_ask_select(choices, **kwargs):
        assert 'xml' not in choices  # the whole point of this test
        return 'csv'
    monkeypatch.setattr(dispatch_module, 'ask_select', fake_ask_select)
    file_path = str(tmp_path / 'out.xml')
    seed_history(f"result = data_export(data, file_path='{file_path}')")
    data_export([['a'], [1]], file_path=file_path, delim=',', quote_mark='"', encoding='utf_8',
                line_terminator='\n', quoting='QUOTE_MINIMAL', convert_dates=False,
                date_format=None)
    # .xml path resolved to 'csv' by the forced choice; data_export() then appends the correct
    # .csv extension since the given path didn't already end with it (same as
    # test_data_export_appends_missing_extension above).
    assert os.path.isfile(file_path + '.csv')


def test_data_import_xml_archive_auto_detected_from_tar_gz_extension(tmp_path):
    archive_path = tmp_path / 'bundle.tar.gz'
    archive_path.write_bytes(_make_archive_bytes())
    result = data_import(file_path=str(archive_path), record_path='Root.Rec',
                         **{k: v for k, v in _XML_FULLY_SPECIFIED.items() if k != 'record_path'})
    assert result == {'a.xml': [['X'], ['1']], 'b.xml': [['X'], ['2']]}


def test_data_export_tar_gz_extension_still_prompts_among_non_archive_formats(monkeypatch,
                                                                              seed_history,
                                                                              tmp_path):
    '''data_export() must NOT gain 'xml_archive' as a resolvable process_as (no archive export
    exists) - a .tar.gz path stays ambiguous and falls back to the xlsx/csv/txt selection prompt,
    exactly like the equivalent .xml test above.'''
    from tedtoolkit.io import dispatch as dispatch_module

    def fake_ask_select(choices, **kwargs):
        assert 'xml_archive' not in choices  # the whole point of this test
        return 'csv'
    monkeypatch.setattr(dispatch_module, 'ask_select', fake_ask_select)
    file_path = str(tmp_path / 'out.tar.gz')
    seed_history(f"result = data_export(data, file_path='{file_path}')")
    data_export([['a'], [1]], file_path=file_path, delim=',', quote_mark='"', encoding='utf_8',
                line_terminator='\n', quoting='QUOTE_MINIMAL', convert_dates=False,
                date_format=None)
    assert os.path.isfile(file_path + '.csv')


def test_data_import_xml_archive_route_bakes_prompted_kwargs_onto_data_import_line(
        monkeypatch, seed_history, tmp_path):
    '''Same regression as the xml/csv equivalents, for the xml_archive route: prompted values
    must be baked onto the data_import(...) line, not a nonexistent xml_archive_import(...)
    line.'''
    # The curated flattening-kwarg prompts are resolved by xml.py's shared
    # _resolve_flatten_kwargs(), so that's where ask_yn must be patched (archive.py doesn't
    # import ask_yn at all - it has no folder-vs-file ambiguity to prompt about).
    from tedtoolkit.io import xml as xml_module
    monkeypatch.setattr(xml_module, 'ask_yn', lambda *a, **k: True)
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    archive_path = tmp_path / 'bundle.tar.gz'
    archive_path.write_bytes(_make_archive_bytes())
    seed_history(f"result = data_import(file_path='{archive_path}')")
    data_import(file_path=str(archive_path))
    rewritten = readline.get_history_item(1)
    assert 'data_import(' in rewritten
    assert 'xml_archive_import(' not in rewritten
    assert 'record_path=' in rewritten
    assert 'list_strategy=' in rewritten


def test_data_import_xml_route_bakes_prompted_kwargs_onto_data_import_line(monkeypatch,
                                                                           seed_history, tmp_path):
    '''Same regression as the csv equivalent below, for the xml route: prompted values must be
    baked onto the data_import(...) line, not a nonexistent xml_import(...) line.'''
    from tedtoolkit.io import xml as xml_module
    monkeypatch.setattr(xml_module, 'ask_yn', lambda *a, **k: True)
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    file_path = tmp_path / 'in.xml'
    file_path.write_text('<Root><Rec><X>1</X></Rec></Root>', encoding='utf-8')
    seed_history(f"result = data_import(file_path='{file_path}')")
    data_import(file_path=str(file_path))
    rewritten = readline.get_history_item(1)
    assert 'data_import(' in rewritten
    assert 'xml_import(' not in rewritten
    assert 'record_path=' in rewritten
    assert 'list_strategy=' in rewritten


def test_data_import_csv_route_bakes_prompted_kwargs_onto_data_import_line(monkeypatch, seed_history,
                                                                           tmp_path):
    '''Regression test: when data_import() routes to csv_import() for a missing
    delim/encoding/etc, the resolved values must be baked onto the *data_import(...)*
    history line (what the user actually typed) - not onto a nonexistent
    "csv_import(...)" line, which never appears in history when reached via the
    dispatcher.'''
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    file_path = tmp_path / 'in.csv'
    file_path.write_text('id,name\n1,a\n', encoding='utf_8')
    seed_history(f"result = data_import(file_path='{file_path}')")
    data_import(file_path=str(file_path))
    rewritten = readline.get_history_item(1)
    assert 'data_import(' in rewritten
    assert 'csv_import(' not in rewritten
    assert 'delim=' in rewritten
    assert 'encoding=' in rewritten
