import pytest

from tedtoolkit.tables.reconcile import key_analysis, in_tolerance, _square_tables
from tedtoolkit.tables.preview import single_col_analysis


def test_single_col_analysis_basic():
    unique, non_unique = single_col_analysis([1, 1, 2, 3, 'four', 'four', 'five'])
    assert sorted(unique, key=str) == sorted([2, 3, 'five'], key=str)
    assert sorted(non_unique, key=str) == sorted([1, 'four'], key=str)


def test_in_tolerance_exact_match():
    assert in_tolerance(100, 100, 0.1) is True


def test_in_tolerance_within_band():
    assert in_tolerance(100, 105, 0.1) is True


def test_in_tolerance_outside_band():
    assert in_tolerance(100, 200, 0.1) is False


def test_in_tolerance_non_numeric_returns_false():
    assert in_tolerance('a', 'b', 0.1) is False


def test_in_tolerance_zero_handling():
    assert in_tolerance(0, 0, 0.1) is True
    assert in_tolerance(0, 5, 0.1) is False


def test_in_tolerance_rejects_bad_tolerance():
    with pytest.raises(Exception):
        in_tolerance(1, 1, 1.5)
    with pytest.raises(Exception):
        in_tolerance(1, 1, -0.1)


def test_key_analysis_categories():
    left = ['a', 'a', 'b', 'c']   # a: non-unique, b: unique, c: unique
    right = ['b', 'd', 'd', 'e']  # b: unique, d: non-unique, e: unique
    result = key_analysis(left, right)
    assert result['A'] == ['b']            # unique/unique
    assert set(result['C']) == {'e'}       # missing/unique (right only, unique)
    assert set(result['G']) == {'a'}       # non-unique/missing (left only)
    assert set(result['H']) == {'d'}       # missing/non-unique (right only)
    assert result['reverse']['b'] == 'A'
    assert result['reverse']['a'] == 'G'


def test_key_analysis_rejects_non_list():
    with pytest.raises(Exception):
        key_analysis('not a list', ['a'])


def test_key_analysis_rejects_empty():
    with pytest.raises(Exception):
        key_analysis([], ['a'])


def test_square_tables_pads_short_rows():
    left = [['a', 'b'], ['1']]
    right = [['x', 'y'], ['1', '2']]
    sq_left, sq_right = _square_tables(left, right)
    assert sq_left[1] == ['1', '']


def test_square_tables_trims_long_rows():
    left = [['a', 'b'], ['1', '2', '3']]
    right = [['x', 'y'], ['1', '2']]
    sq_left, sq_right = _square_tables(left, right)
    assert sq_left[1] == ['1', '2']
