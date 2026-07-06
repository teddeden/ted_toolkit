from tedtoolkit.io.csv import _process_line


def test_process_line_convert_numbers_int():
    assert _process_line(['1', '2.5', 'abc'], convert_numbers=True, convert_dates=False) == \
        [1, 2.5, 'abc']


def test_process_line_no_conversion():
    assert _process_line(['1', '2.5'], convert_numbers=False, convert_dates=False) == ['1', '2.5']


def test_process_line_convert_dates():
    result = _process_line(['2024-01-15 00:00:00.000000'], convert_numbers=False,
                            convert_dates=True, date_format='%Y-%m-%d %H:%M:%S.%f')
    import datetime
    assert result == [datetime.datetime(2024, 1, 15)]


def test_process_line_unconvertible_date_passthrough():
    result = _process_line(['not a date'], convert_numbers=False, convert_dates=True)
    assert result == ['not a date']
