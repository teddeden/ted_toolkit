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


# --- delimited-text detection for non-.csv files (_sniff_delimited + data_import) -----

import pytest

from tedtoolkit import history as history_module
from tedtoolkit.io import dispatch as dispatch_module
from tedtoolkit.io.dispatch import _sniff_delimited


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding='utf-8', newline='')
    return str(path)


@pytest.mark.parametrize('delim', [',', '\t', ';', '|'])
def test_sniff_detects_common_delimiters(tmp_path, delim):
    rows = [['id', 'name', 'amount']] + [[str(i), f'n{i}', str(i * 1.5)] for i in range(10)]
    path = _write(tmp_path, 'd.txt', '\n'.join(delim.join(row) for row in rows) + '\n')
    assert _sniff_delimited(path) == (delim, 3)


def test_sniff_handles_quoted_fields(tmp_path):
    path = _write(tmp_path, 'q.txt', 'id,comment\n1,"hello, world"\n2,"a, b, c"\n3,plain\n')
    assert _sniff_delimited(path) == (',', 2)


@pytest.mark.parametrize('text', [
    'This is a normal text file.\nIt has sentences, and the odd comma.\nNothing tabular here at all\n',
    'one\ntwo\nthree\nfour\n',
    'a,b,c\nd\ne,f\ng,h,i,j,k\nl\n',
    '',
    'single,line,only\n',
])
def test_sniff_rejects_non_tabular_text(tmp_path, text):
    assert _sniff_delimited(_write(tmp_path, 'p.txt', text)) is None


def test_sniff_rejects_binary(tmp_path):
    path = tmp_path / 'b.dat'
    path.write_bytes(b'\x00\x01\x02,\x03\n' * 50)
    assert _sniff_delimited(str(path)) is None


def test_sniff_rejects_missing_file(tmp_path):
    assert _sniff_delimited(str(tmp_path / 'nope.txt')) is None


@pytest.fixture
def recorded_yn(monkeypatch):
    '''Answer every ask_yn() with its default-accepting "yes" and record the prompts.'''
    prompts = []
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda default='no', prompt='': prompts.append(prompt) or True)
    return prompts


def test_delimited_txt_offers_csv_with_detected_delimiter(tmp_path, seed_history, recorded_yn, capsys):
    path = _write(tmp_path, 'tab.txt', 'id\tname\n1\ta\n2\tb\n')
    seed_history(f'data = data_import(file_path={path!r})')
    result = data_import(file_path=path)
    assert result == [['id', 'name'], ['1', 'a'], ['2', 'b']]
    assert r"looks like delimited data (delimiter '\t', 2 columns)" in capsys.readouterr().out
    assert recorded_yn[0] == 'The argument <process_as> is set to <csv>. Is this ok?'
    assert r"The argument <delim> is set to <'\t'>. Is this ok?" in recorded_yn
    rewritten = readline.get_history_item(1)
    assert "process_as='csv'" in rewritten and r"delim='\t'" in rewritten


def test_delimited_txt_can_still_be_read_as_plain_text(tmp_path, seed_history, monkeypatch):
    path = _write(tmp_path, 'tab.txt', 'id\tname\n1\ta\n')
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: False)   # "not ok" -> choose
    monkeypatch.setattr(prompts_module, 'input', lambda prompt: '1')      # index 1 = 'txt'
    seed_history(f'data = data_import(file_path={path!r})')
    result = data_import(file_path=path)
    assert [line.rstrip('\r\n') for line in result] == ['id\tname', '1\ta']
    assert "process_as='txt'" in readline.get_history_item(1)


def test_no_sniff_prompt_for_plain_text_or_explicit_process_as_or_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: pytest.fail('unexpected prompt'))
    prose = _write(tmp_path, 'notes.txt', 'just some notes\nmore notes\n')
    assert [line.rstrip('\r\n') for line in data_import(file_path=prose)] == ['just some notes', 'more notes']
    tabular = _write(tmp_path, 'tab.txt', 'a\tb\n1\t2\n')
    assert len(data_import(file_path=tabular, process_as='txt')) == 2
    semicolon_csv = _write(tmp_path, 'x.csv', 'a;b\n1;2\n')
    assert data_import(file_path=semicolon_csv, delim=';', quote_mark='"', quoting='QUOTE_MINIMAL',
                       encoding='utf_8', line_terminator='\n', convert_numbers=False,
                       convert_dates=False, date_format=None) == [['a', 'b'], ['1', '2']]


def test_no_sniff_prompt_while_replaying_a_saved_script(tmp_path, monkeypatch):
    '''Old saved scripts' data_import(file_path='x.txt') lines (no process_as) must keep reading
    the file as plain text with no new prompt.'''
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: pytest.fail('unexpected prompt'))
    monkeypatch.setattr(history_module, 'REPLAY_ACTIVE', True)
    path = _write(tmp_path, 'tab.txt', 'a\tb\n1\t2\n')
    assert [line.rstrip('\r\n') for line in data_import(file_path=path)] == ['a\tb', '1\t2']


def test_unknown_extension_defaults_ambiguous_picker_to_csv_when_delimited(tmp_path, monkeypatch, seed_history):
    seen = []

    def _fake_select(var_in, prompt='', orig_out=False, default_val=None, **kwargs):
        seen.append(default_val)
        return 'txt'
    monkeypatch.setattr(dispatch_module, 'ask_select', _fake_select)
    delimited = _write(tmp_path, 'export.tsv', 'a\tb\n1\t2\n')
    seed_history(f'd = data_import(file_path={delimited!r})')
    data_import(file_path=delimited)
    prose = _write(tmp_path, 'readme.log', 'hello\nworld\n')
    seed_history(f'd = data_import(file_path={prose!r})')
    data_import(file_path=prose)
    assert seen == ['csv', None]


def test_plain_csv_import_keeps_comma_default(tmp_path, seed_history, recorded_yn):
    path = _write(tmp_path, 'in.csv', 'a\tb\n1\t2\n')
    seed_history(f'd = data_import(file_path={path!r})')
    data_import(file_path=path)
    assert "The argument <delim> is set to <','>. Is this ok?" in recorded_yn
