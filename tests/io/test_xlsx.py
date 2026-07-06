from tedtoolkit.io.xlsx import (_xlsx_export_core, _xlsx_import_core, xlsx_export, xlsx_import,
                                 _xlsx_data_check, ask_select_sheet, ALL_SHEETS_TEXT)


def test_xlsx_export_core_and_import_core_round_trip(tmp_path):
    file_path = str(tmp_path / 'out.xlsx')
    data_dict = {'Sheet1': [['id', 'name'], [1, 'a'], [2, 'b']]}
    _xlsx_export_core(data_dict, file_path, wb_filter=True, view_in_excel=False)
    result = _xlsx_import_core(file_path, include_formulas=False, override_ro=False)
    assert result['Sheet1'] == [['id', 'name'], [1, 'a'], [2, 'b']]


def test_xlsx_export_core_multiple_sheets(tmp_path):
    file_path = str(tmp_path / 'out.xlsx')
    data_dict = {'A': [['x'], [1]], 'B': [['y'], [2]]}
    _xlsx_export_core(data_dict, file_path, wb_filter=False, view_in_excel=False)
    result = _xlsx_import_core(file_path, include_formulas=False, override_ro=False)
    assert set(result.keys()) == {'A', 'B'}
    assert result['A'] == [['x'], [1]]
    assert result['B'] == [['y'], [2]]


def test_xlsx_data_check_single_table():
    single_sheet_mode = _xlsx_data_check([['a'], [1]])
    assert single_sheet_mode is True


def test_xlsx_data_check_dict_of_tables():
    single_sheet_mode = _xlsx_data_check({'Sheet1': [['a'], [1]]})
    assert single_sheet_mode is False


def test_xlsx_data_check_rejects_bad_shape():
    import pytest
    with pytest.raises(Exception):
        _xlsx_data_check('not a table')


def test_ask_select_sheet_single_sheet_no_prompt():
    result = ask_select_sheet({'OnlySheet': []}, include_all=False)
    assert result == 'OnlySheet'


def test_xlsx_wrapper_round_trip_no_prompts_when_fully_specified(tmp_path):
    file_path = str(tmp_path / 'wrapper_out.xlsx')
    data = [['id', 'name'], [1, 'a']]
    xlsx_export(data, file_path=file_path, sheet_name='Data', wb_filter=True, view_in_excel=False)
    result = xlsx_import(file_path=file_path)
    assert result['Data'] == [['id', 'name'], [1, 'a']]
