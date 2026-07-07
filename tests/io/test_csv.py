import csv as csv_module
import readline

from tedtoolkit.io.csv import _csv_import_core, _csv_export_core, csv_export, csv_import
from tedtoolkit import prompts as prompts_module


def test_csv_export_core_writes_file(tmp_path):
    file_path = str(tmp_path / 'out.csv')
    data = [['id', 'name'], [1, 'a'], [2, 'b']]
    _csv_export_core(data, file_path, delim=',', quote_mark='"', encoding='utf_8',
                     line_terminator='\n', quoting='QUOTE_MINIMAL', convert_dates=False,
                     date_format=None)
    with open(file_path, encoding='utf_8') as f:
        rows = list(csv_module.reader(f))
    assert rows == [['id', 'name'], ['1', 'a'], ['2', 'b']]


def test_csv_export_core_converts_dates(tmp_path):
    import datetime
    file_path = str(tmp_path / 'out.csv')
    data = [['id', 'date'], [1, datetime.datetime(2024, 1, 15)]]
    _csv_export_core(data, file_path, delim=',', quote_mark='"', encoding='utf_8',
                     line_terminator='\n', quoting='QUOTE_MINIMAL', convert_dates=True,
                     date_format='%Y-%m-%d')
    with open(file_path, encoding='utf_8') as f:
        rows = list(csv_module.reader(f))
    assert rows[1] == ['1', '2024-01-15']


def test_csv_import_core_reads_file(tmp_path):
    file_path = tmp_path / 'in.csv'
    file_path.write_text('id,name\n1,a\n2,b\n', encoding='utf_8')
    result = _csv_import_core(str(file_path), delim=',', quote_mark='"', encoding='utf_8',
                              line_terminator='\n', quoting='QUOTE_MINIMAL',
                              convert_numbers=False, convert_dates=False, date_format=None)
    assert result == [['id', 'name'], ['1', 'a'], ['2', 'b']]


def test_csv_import_core_converts_numbers(tmp_path):
    file_path = tmp_path / 'in.csv'
    file_path.write_text('id,amount\n1,100.5\n', encoding='utf_8')
    result = _csv_import_core(str(file_path), delim=',', quote_mark='"', encoding='utf_8',
                              line_terminator='\n', quoting='QUOTE_MINIMAL',
                              convert_numbers=True, convert_dates=False, date_format=None)
    assert result == [['id', 'amount'], [1, 100.5]]


def test_csv_export_core_custom_delimiter(tmp_path):
    file_path = str(tmp_path / 'out.csv')
    data = [['a', 'b'], [1, 2]]
    _csv_export_core(data, file_path, delim=';', quote_mark='"', encoding='utf_8',
                     line_terminator='\n', quoting='QUOTE_MINIMAL', convert_dates=False,
                     date_format=None)
    content = open(file_path, encoding='utf_8').read()
    assert 'a;b' in content


def test_csv_wrapper_round_trip_no_prompts_when_fully_specified(tmp_path):
    '''Fully-specified kwargs must delegate straight to the core with zero prompts.'''
    file_path = str(tmp_path / 'roundtrip.csv')
    data = [['id', 'name'], [1, 'a'], [2, 'b']]
    csv_export(data, file_path=file_path, delim=',', quote_mark='"', encoding='utf_8',
               line_terminator='\n', quoting='QUOTE_MINIMAL', convert_dates=False,
               date_format=None)
    result = csv_import(file_path=file_path, delim=',', quote_mark='"', encoding='utf_8',
                        line_terminator='\n', quoting='QUOTE_MINIMAL', convert_numbers=True,
                        convert_dates=False, date_format=None)
    assert result == data


def test_csv_import_bakes_prompted_kwargs_into_history(monkeypatch, seed_history, tmp_path):
    '''Regression test: csv_import() only had file_path/etc pre-supplied here via kwargs
    is not the point - the point is that when delim/encoding/etc are *not* supplied and get
    prompted for internally (via _parse_csv_args), the resolved values must be baked into
    the history line, exactly like every other guided function's missing kwargs are.'''
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    file_path = tmp_path / 'in.csv'
    file_path.write_text('id,name\n1,a\n', encoding='utf_8')
    seed_history(f"result = csv_import(file_path='{file_path}')")
    csv_import(file_path=str(file_path))
    rewritten = readline.get_history_item(1)
    assert 'csv_import(' in rewritten
    assert 'delim=' in rewritten
    assert 'encoding=' in rewritten
    assert 'quoting=' in rewritten
    assert 'convert_numbers=' in rewritten
