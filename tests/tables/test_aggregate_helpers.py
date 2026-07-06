import pytest

from tedtoolkit.tables.aggregate import (_bool_calc, _arithmetic_stats, _text_length_stats,
                                          _filled_stats, _get_float, _get_type, _add_values)


BOOL_OPTIONS = {'allow_yn': True, 'allow_01': True, 'allow_tf': True, 'ignore_blanks': False,
                'invalid_text': '-Non-boolean value found-'}


def test_bool_calc_and_all_true():
    assert _bool_calc([True, 'y', 1, 'T'], 'and', BOOL_OPTIONS) is True


def test_bool_calc_and_one_false():
    assert _bool_calc([True, 'n', True], 'and', BOOL_OPTIONS) is False


def test_bool_calc_or_one_true():
    assert _bool_calc([False, 'yes', False], 'or', BOOL_OPTIONS) is True


def test_bool_calc_invalid_value():
    assert _bool_calc(['maybe'], 'and', BOOL_OPTIONS) == '-Non-boolean value found-'


def test_bool_calc_ignores_blanks():
    options = dict(BOOL_OPTIONS, ignore_blanks=True)
    assert _bool_calc(['', True, True], 'and', options) is True


def test_bool_calc_all_blank_returns_empty_string():
    options = dict(BOOL_OPTIONS, ignore_blanks=True)
    assert _bool_calc(['', ''], 'and', options) == ''


ARITH_OPTIONS = {'ignore_non_numbers': False, 'non_numbers_text': '-Non-numeric-',
                  'ignore_empty': True, 'empty_text': '-All empty-'}


def test_arithmetic_stats_sum():
    assert _arithmetic_stats([1, 2, '3'], 'sum', ARITH_OPTIONS) == 6


def test_arithmetic_stats_min_max_average():
    values = [1, 5, 3]
    assert _arithmetic_stats(values, 'min', ARITH_OPTIONS) == 1
    assert _arithmetic_stats(values, 'max', ARITH_OPTIONS) == 5
    assert _arithmetic_stats(values, 'average', ARITH_OPTIONS) == 3


def test_arithmetic_stats_non_numeric_text():
    assert _arithmetic_stats(['abc'], 'sum', ARITH_OPTIONS) == '-Non-numeric-'


def test_arithmetic_stats_all_empty():
    assert _arithmetic_stats([], 'sum', ARITH_OPTIONS) == '-All empty-'


TEXT_LEN_OPTIONS = {'non_text_message': '-Field(s) without text data-', 'empty_text': '-All empty-'}


def test_text_length_stats():
    values = ['a', 'abc', 'ab']
    assert _text_length_stats(values, 'min_text_length', TEXT_LEN_OPTIONS) == 1
    assert _text_length_stats(values, 'max_text_length', TEXT_LEN_OPTIONS) == 3
    assert _text_length_stats(values, 'avg_text_length', TEXT_LEN_OPTIONS) == 2


def test_text_length_stats_non_text():
    assert _text_length_stats([1, 2], 'min_text_length', TEXT_LEN_OPTIONS) == \
        '-Field(s) without text data-'


def test_filled_stats_all_filled():
    assert _filled_stats(['a', 'b'], 'all_filled') is True
    assert _filled_stats(['a', 'b'], 'some_filled') is True
    assert _filled_stats(['a', 'b'], 'none_filled') is False


def test_filled_stats_none_filled():
    assert _filled_stats(['', None, 0], 'all_filled') is False
    assert _filled_stats(['', None, 0], 'some_filled') is False
    assert _filled_stats(['', None, 0], 'none_filled') is True


def test_filled_stats_some_filled():
    assert _filled_stats(['a', ''], 'all_filled') is False
    assert _filled_stats(['a', ''], 'some_filled') is True
    assert _filled_stats(['a', ''], 'none_filled') is False


def test_get_float_valid():
    assert _get_float('3.14') == 3.14


def test_get_float_invalid_returns_default():
    assert _get_float('abc') == 'NaN'
    assert _get_float('abc', default_val=0) == 0


def test_get_type_blank():
    assert _get_type(['', 'x'], 0) == 'BLANK'
    assert _get_type(['x'], 5) == 'BLANK'  # index out of range


def test_get_type_number():
    assert _get_type(['42.5'], 0) == 'NUMBER'


def test_get_type_text():
    assert _get_type(['hello'], 0) == 'TEXT'


def test_get_type_date():
    assert _get_type(['2024-01-15'], 0) == 'DATE'


def test_add_values():
    ret_table = [['Key', 'ExistingCol'], ['a', 1], ['b', 2]]
    _add_values(ret_table, {'a': 100, 'b': 200}, 'NewCol')
    assert ret_table == [['Key', 'ExistingCol', 'NewCol'], ['a', 1, 100], ['b', 2, 200]]


def test_add_values_missing_key_defaults_to_empty_string():
    ret_table = [['Key'], ['a'], ['missing']]
    _add_values(ret_table, {'a': 1}, 'NewCol')
    assert ret_table[2] == ['missing', '']
