from tedtoolkit.tables.columns import excel_column, _decimate


def test_excel_column_basic():
    assert excel_column(0) == 'A'
    assert excel_column(1) == 'B'
    assert excel_column(25) == 'Z'
    assert excel_column(26) == 'AA'
    assert excel_column(27) == 'AB'


def test_excel_column_rejects_non_integer():
    import pytest
    with pytest.raises(TypeError):
        excel_column(1.5)


def test_excel_column_rejects_out_of_range():
    import pytest
    with pytest.raises(IndexError):
        excel_column(-1)
    with pytest.raises(IndexError):
        excel_column(16384)


def test_decimate_short_list():
    assert list(_decimate(list(range(5)))) == [1, 2, 3, 4]


def test_decimate_long_list():
    result = _decimate(list(range(100)))
    assert len(result) == 10
    assert result[0] < result[-1]
