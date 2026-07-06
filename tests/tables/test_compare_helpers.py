import datetime

from tedtoolkit.tables.compare import _try_convert_date, _detect_blank


def test_try_convert_date_from_text():
    result = _try_convert_date('2024-01-15 00:00:00.000000', '%Y-%m-%d %H:%M:%S.%f')
    assert result == datetime.datetime(2024, 1, 15)


def test_try_convert_date_from_excel_serial():
    # Excel serial 44927 = 2023-01-01 (per Excel's 1900 date system, with the classic off-by-2)
    result = _try_convert_date(44927, '%Y-%m-%d')
    assert isinstance(result, datetime.datetime)
    assert result.year == 2023


def test_try_convert_date_passthrough_for_date_object():
    d = datetime.date(2024, 1, 1)
    assert _try_convert_date(d, '%Y-%m-%d') == d


def test_try_convert_date_unconvertible_returns_none():
    assert _try_convert_date('not a date', '%Y-%m-%d') is None


def test_detect_blank_none():
    assert _detect_blank(None) is True


def test_detect_blank_whitespace_string():
    assert _detect_blank('   ') is True


def test_detect_blank_empty_string():
    assert _detect_blank('') is True


def test_detect_blank_nonblank_string():
    assert _detect_blank('x') is False


def test_detect_blank_non_string_nonblank():
    assert _detect_blank(0) is False
    assert _detect_blank(False) is False
