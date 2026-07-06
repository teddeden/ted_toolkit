import os

from tedtoolkit.io.dispatch import data_import, data_export, _file_ext


def test_file_ext():
    assert _file_ext('/a/b/c.CSV') == 'csv'
    assert _file_ext('data.xlsx') == 'xlsx'
    assert _file_ext('noext') == ''


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
