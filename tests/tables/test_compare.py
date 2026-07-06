import importlib

from tedtoolkit.tables.compare import compare_columns, _compare_columns_core

compare_module = importlib.import_module('tedtoolkit.tables.compare')


def _defaults(**overrides):
    base = dict(header_row=True, require_nonblank=False, case_sensitive=True,
                strip_text_fields=False, convert_dates=False, first_date_format=None,
                second_date_format=None, require_nonzero=False, conv_text_to_num=False,
                first_col_conv=None, tolerance=0, pass_text='PASS', error_text='ERROR',
                fail_text='FAIL', fail_text_blank='FAIL_ALL_BLANK',
                fail_text_nonzero='FAIL_ALL_ZERO', fail_detail=False, new_col_name='COMPARE',
                error_condition='')
    base.update(overrides)
    return base


# --- text compare_type: pass / fail / error ---

def test_text_pass():
    data = [['Old', 'New'], ['abc', 'abc']]
    _compare_columns_core(data, [0, 1], 'text', **_defaults())
    assert data[1][-1] == 'PASS'


def test_text_fail():
    data = [['Old', 'New'], ['abc', 'xyz']]
    _compare_columns_core(data, [0, 1], 'text', **_defaults())
    assert data[1][-1] == 'FAIL'


def test_text_error_non_string_data():
    data = [['Old', 'New'], [1, 'a']]
    _compare_columns_core(data, [0, 1], 'text', **_defaults())
    assert data[1][-1] == 'ERROR'


def test_text_case_insensitive_and_strip():
    data = [['Old', 'New'], [' ABC ', 'abc']]
    _compare_columns_core(data, [0, 1], 'text',
                          **_defaults(case_sensitive=False, strip_text_fields=True))
    assert data[1][-1] == 'PASS'


def test_text_require_nonblank_fails_on_double_blank():
    data = [['Old', 'New'], ['', '']]
    _compare_columns_core(data, [0, 1], 'text', **_defaults(require_nonblank=True))
    assert data[1][-1] == 'FAIL_ALL_BLANK'


# --- numerical compare_type: pass / fail / error ---

def test_numerical_pass():
    data = [['Old', 'New'], [100, 100]]
    _compare_columns_core(data, [0, 1], 'numerical', **_defaults())
    assert data[1][-1] == 'PASS'


def test_numerical_fail():
    data = [['Old', 'New'], [100, 200]]
    _compare_columns_core(data, [0, 1], 'numerical', **_defaults())
    assert data[1][-1] == 'FAIL'


def test_numerical_error_on_text_without_conversion():
    data = [['Old', 'New'], ['abc', 100]]
    _compare_columns_core(data, [0, 1], 'numerical', **_defaults())
    assert data[1][-1] == 'ERROR'


def test_numerical_conv_text_to_num():
    data = [['Old', 'New'], ['100', 100]]
    _compare_columns_core(data, [0, 1], 'numerical', **_defaults(conv_text_to_num=True))
    assert data[1][-1] == 'PASS'


def test_numerical_tolerance_pass_within_band():
    data = [['Old', 'New'], [100, 104]]
    _compare_columns_core(data, [0, 1], 'numerical', **_defaults(tolerance=0.1))
    assert data[1][-1] == 'PASS (WITHIN TOLERANCE)'


def test_numerical_require_nonzero_fails_on_double_zero():
    data = [['Old', 'New'], [0, 0]]
    _compare_columns_core(data, [0, 1], 'numerical', **_defaults(require_nonzero=True))
    assert data[1][-1] == 'FAIL_ALL_ZERO'


# --- date compare_type: pass / fail / error ---

def test_date_pass_native_dates():
    import datetime
    data = [['Old', 'New'], [datetime.date(2024, 1, 1), datetime.date(2024, 1, 1)]]
    _compare_columns_core(data, [0, 1], 'date', **_defaults())
    assert data[1][-1] == 'PASS'


def test_date_fail_different_dates():
    import datetime
    data = [['Old', 'New'], [datetime.date(2024, 1, 1), datetime.date(2024, 1, 2)]]
    _compare_columns_core(data, [0, 1], 'date', **_defaults())
    assert data[1][-1] == 'FAIL'


def test_date_error_unconvertible():
    data = [['Old', 'New'], ['not a date', 'also not a date']]
    _compare_columns_core(data, [0, 1], 'date', **_defaults())
    assert data[1][-1] == 'ERROR'


def test_date_convert_from_text():
    data = [['Old', 'New'], ['2024-01-15 00:00:00.000000', '2024-01-15 00:00:00.000000']]
    _compare_columns_core(data, [0, 1], 'date',
                          **_defaults(convert_dates=True,
                                      first_date_format='%Y-%m-%d %H:%M:%S.%f',
                                      second_date_format='%Y-%m-%d %H:%M:%S.%f'))
    assert data[1][-1] == 'PASS'


# --- first_col_conv (eval()-based user transform) ---

def test_first_col_conv_success():
    '''The eval()-based transform-expression feature must remain fully functional -
    this is an intentional power-user capability, not something to remove.'''
    data = [['Old', 'New'], [10, -10]]
    _compare_columns_core(data, [0, 1], 'numerical', **_defaults(first_col_conv='{x}*-1'))
    assert data[1][-1] == 'PASS'


def test_first_col_conv_malformed_degrades_to_error_text():
    data = [['Old', 'New'], [10, -10]]
    _compare_columns_core(data, [0, 1], 'numerical',
                          **_defaults(first_col_conv='{x}++invalid', fail_detail=False))
    assert data[1][-1] == 'ERROR'


def test_first_col_conv_malformed_fail_detail_includes_exception_text():
    data = [['Old', 'New'], [10, -10]]
    _compare_columns_core(data, [0, 1], 'numerical',
                          **_defaults(first_col_conv='{x}++invalid', fail_detail=True))
    assert data[1][-1].startswith('ERROR: first_col_conv failure:')


# --- mutate-in-place contract + rollback on exception ---

def test_core_mutates_and_returns_same_object():
    data = [['Old', 'New'], ['a', 'a']]
    result = _compare_columns_core(data, [0, 1], 'text', **_defaults())
    assert result is data
    assert data[0][-1] == 'COMPARE'


def test_core_rolls_back_partial_mutation_on_fatal_error():
    '''If a row is too short to read the compare columns (a "should never happen" guard),
    the exception must be re-raised, but any header/row cells already appended before the
    fatal row must be rolled back so `data` is left exactly as it started.'''
    data = [['Old', 'New'], ['a', 'a'], ['b']]  # second row too short for column index 1
    original_widths = [len(row) for row in data]
    try:
        _compare_columns_core(data, [0, 1], 'text', **_defaults())
        assert False, 'expected an exception'
    except Exception:
        pass
    assert [len(row) for row in data] == original_widths


def test_error_condition_short_circuits_every_row():
    '''When error_condition is set (a specification error found during kwarg resolution),
    every row gets that message instead of being compared - this is a deliberate design
    (report errors as part of results rather than crash), not something this refactor
    should change.'''
    data = [['Old', 'New'], ['a', 'a'], ['b', 'c']]
    _compare_columns_core(data, [0, 1], 'text', **_defaults(error_condition='SPEC ERROR'))
    assert data[1][-1] == 'SPEC ERROR'
    assert data[2][-1] == 'SPEC ERROR'


# --- wrapper contract ---

def test_compare_columns_wrapper_no_prompts_when_fully_specified(no_prompts, seed_history):
    no_prompts(compare_module, 'ask_select_column_index')
    seed_history("compare_columns(table)")
    table = [['Old', 'New'], ['a', 'a'], ['a', 'b']]
    compare_columns(table, header_row=True, header_row_index=0, column_select_mode='index',
                    first_col=0, second_col=1, compare_type='text', require_nonblank=False,
                    case_sensitive=True, strip_text_fields=False, pass_text='PASS',
                    error_text='ERROR', fail_text='FAIL', fail_detail=False,
                    new_col_name='COMPARE')
    assert table[1][-1] == 'PASS'
    assert table[2][-1] == 'FAIL'
