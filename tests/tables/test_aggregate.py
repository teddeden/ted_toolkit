import readline

import pytest

from tedtoolkit.tables import aggregate as aggregate_module
from tedtoolkit.tables.aggregate import (data_de_aggregate, _data_de_aggregate_core,
                                          data_aggregate, _data_aggregate_core)


def test_data_de_aggregate_core_basic():
    table = [['Client Name', 'Total Amount', 'Order IDs'],
             ['George', 340, '1,3,4'],
             ['Ben', 160, '2,5']]
    result = _data_de_aggregate_core(table, headers=True, agg_key_col=2, delim=',', strip=False)
    assert result == [
        ['Client Name', 'Total Amount', 'Order IDs'],
        ['George', 340, '1'],
        ['George', 340, '3'],
        ['George', 340, '4'],
        ['Ben', 160, '2'],
        ['Ben', 160, '5'],
    ]


def test_data_de_aggregate_core_strip():
    table = [['ID', 'Key'], ['x', ' 1 , 2 ']]
    result = _data_de_aggregate_core(table, headers=True, agg_key_col=1, delim=',', strip=True)
    assert result[1:] == [['x', '1'], ['x', '2']]


def test_data_de_aggregate_core_no_headers():
    table = [['a', '1,2']]
    result = _data_de_aggregate_core(table, headers=False, agg_key_col=1, delim=',', strip=False)
    assert result == [['a', '1'], ['a', '2']]


def test_data_de_aggregate_wrapper_no_prompts_when_fully_specified(no_prompts, seed_history):
    '''Fully-specified kwargs must delegate straight to the core with zero prompts -
    this is the load-bearing contract behind replaying a saved script non-interactively.'''
    no_prompts(aggregate_module, 'ask_yn', 'ask_select_column_index')
    seed_history("x = data_de_aggregate(table)")
    table = [['Client Name', 'Order IDs'], ['George', '1,3'], ['Ben', '2']]
    result = data_de_aggregate(table, headers=True, aggregation_key_col=1, delim=',', strip=True)
    assert result == [
        ['Client Name', 'Order IDs'],
        ['George', '1'],
        ['George', '3'],
        ['Ben', '2'],
    ]


def test_data_de_aggregate_wrapper_bakes_missing_kwarg_into_history(monkeypatch, seed_history):
    '''When aggregation_key_col is omitted, the wrapper prompts for it and bakes the
    resolved value into the readline history line - the core mechanism the whole
    toolkit's "guided call becomes a replayable script line" design depends on.'''
    seed_history("x = data_de_aggregate(table)")
    monkeypatch.setattr(aggregate_module, 'ask_select_column_index', lambda *a, **k: 1)
    table = [['Client Name', 'Order IDs'], ['George', '1,3'], ['Ben', '2']]
    data_de_aggregate(table, delim=',', strip=True, headers=True)
    rewritten = readline.get_history_item(1)
    assert 'aggregation_key_col=1' in rewritten
    assert 'data_de_aggregate(table' in rewritten


# ---------------------------------------------------------------------------
# _data_aggregate_core: one representative test per dispatch-branch *shape*
# ---------------------------------------------------------------------------

ORDERS = [
    ['Order ID', 'Client Name', 'Amount'],
    [1, 'George', 100],
    [2, 'Ben', 50],
    [3, 'George', 230],
    [4, 'George', 10],
    [5, 'Ben', 110],
]


def _spec(agg_type, agg_col, agg_name, **options):
    return {'agg_type': agg_type, 'agg_col': agg_col, 'agg_options': options, 'agg_name': agg_name}


def test_core_docstring_example_end_to_end():
    '''Reproduces data_aggregate()'s own docstring example exactly.'''
    specs = [
        _spec('sum', 2, 'Total Amount', ignore_non_numbers=False, non_numbers_text='-Non-numeric-',
              ignore_empty=True, empty_text='-All empty-'),
        _spec('concatenate_unique', 0, 'Order IDs', strip=True, link_text=','),
        _spec('count_all', 0, 'Number of Orders'),
    ]
    result = _data_aggregate_core(ORDERS, headers=True, agg_key_col=1,
                                   agg_key_name='Client Name', agg_specs=specs)
    lookup = {row[0]: row[1:] for row in result[1:]}
    assert lookup['George'] == [340, '1,3,4', 3]
    assert lookup['Ben'] == [160, '2,5', 2]


def test_core_sum_with_string_numbers_regression():
    '''Regression test for the _arithmetic_stats missing-continue bug: string-typed
    numbers (as commonly come from CSV/text imports) must sum correctly, not fall
    through to '-Non-numeric-'.'''
    table = [['Key', 'Amount'], ['a', '10'], ['a', '20'], ['b', '5']]
    specs = [_spec('sum', 1, 'Total', ignore_non_numbers=False, non_numbers_text='-Non-numeric-',
                    ignore_empty=True, empty_text='-All empty-')]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    lookup = {row[0]: row[1] for row in result[1:]}
    assert lookup['a'] == 30.0
    assert lookup['b'] == 5.0


def test_core_and_or_boolean_shape():
    table = [['Key', 'Flag'], ['a', True], ['a', True], ['b', True], ['b', False]]
    specs = [_spec('and', 1, 'AllTrue', allow_yn=True, allow_01=True, allow_tf=True,
                   ignore_blanks=False, invalid_text='-Non-boolean value found-')]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    lookup = {row[0]: row[1] for row in result[1:]}
    assert lookup['a'] is True
    assert lookup['b'] is False


def test_core_count_unique_shape():
    table = [['Key', 'Val'], ['a', 'x'], ['a', 'x'], ['a', 'y'], ['b', 'z']]
    specs = [_spec('count_unique', 1, 'UniqueCount', strip=True)]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    lookup = {row[0]: row[1] for row in result[1:]}
    assert lookup['a'] == 2
    assert lookup['b'] == 1


def test_core_are_same_shape():
    table = [['Key', 'Val'], ['a', 'x'], ['a', 'x'], ['b', 'x'], ['b', 'y']]
    specs = [_spec('are_same', 1, 'AllSame', strip=True)]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    lookup = {row[0]: row[1] for row in result[1:]}
    assert lookup['a'] is True
    assert lookup['b'] is False


def test_core_text_length_shape():
    table = [['Key', 'Val'], ['a', 'ab'], ['a', 'abcd'], ['b', 'x']]
    specs = [_spec('max_text_length', 1, 'MaxLen', strip=True,
                    non_text_message='-Field(s) without text data-', empty_text='-All empty-')]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    lookup = {row[0]: row[1] for row in result[1:]}
    assert lookup['a'] == 4
    assert lookup['b'] == 1


def test_core_filled_shape():
    table = [['Key', 'Val'], ['a', 'x'], ['a', ''], ['b', '']]
    specs = [_spec('some_filled', 1, 'AnyFilled', strip=True)]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    lookup = {row[0]: row[1] for row in result[1:]}
    assert lookup['a'] is True
    assert lookup['b'] is False


def test_core_category_pivot_shape():
    '''The plain 'category' aggregation: one output column per category value.'''
    table = [['Key', 'Category', 'Value'],
              ['a', 'X', 1], ['a', 'Y', 2],
              ['b', 'X', 3]]
    specs = [_spec('category', 2, 'Val', cat_key_col=1, allow_duplicates_if_equal=False,
                    duplicates_text='-Duplicate entries-')]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    header = result[0]
    lookup = {row[0]: dict(zip(header[1:], row[1:])) for row in result[1:]}
    assert lookup['a']['Val - X'] == 1
    assert lookup['a']['Val - Y'] == 2
    assert lookup['b']['Val - X'] == 3
    assert lookup['b']['Val - Y'] is None


def test_core_category_sum_shape():
    table = [['Key', 'Category', 'Amount'],
              ['a', 'X', 10], ['a', 'X', 5], ['a', 'Y', 1],
              ['b', 'X', 2]]
    specs = [_spec('category-sum', 2, 'Total', cat_key_col=1, ignore_non_numbers=False,
                    non_numbers_text='-Non-numeric-')]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    header = result[0]
    lookup = {row[0]: dict(zip(header[1:], row[1:])) for row in result[1:]}
    assert lookup['a']['Total - X'] == 15.0
    assert lookup['a']['Total - Y'] == 1.0
    assert lookup['b']['Total - X'] == 2.0


def test_core_category_and_shape():
    '''Represents the shared cat_data dispatch loop (category-and/or/min/max/average/
    count/text-length/filled/are-same all funnel through this one branch).'''
    table = [['Key', 'Category', 'Flag'],
              ['a', 'X', True], ['a', 'X', True],
              ['a', 'Y', False]]
    specs = [_spec('category-and', 2, 'AllTrue', cat_key_col=1, allow_yn=True, allow_01=True,
                    allow_tf=True, ignore_blanks=False, invalid_text='-Non-boolean value found-',
                    strip=True)]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    header = result[0]
    lookup = {row[0]: dict(zip(header[1:], row[1:])) for row in result[1:]}
    assert lookup['a']['AllTrue - X'] is True
    assert lookup['a']['AllTrue - Y'] is False


def test_core_category_concat_unique_shape():
    table = [['Key', 'Category', 'Tag'],
              ['a', 'X', 'p'], ['a', 'X', 'p'], ['a', 'X', 'q']]
    specs = [_spec('category-concat-unique', 2, 'Tags', cat_key_col=1, link_text=',')]
    result = _data_aggregate_core(table, headers=True, agg_key_col=0, agg_key_name='Key',
                                   agg_specs=specs)
    header = result[0]
    lookup = {row[0]: dict(zip(header[1:], row[1:])) for row in result[1:]}
    assert lookup['a']['Tags - X'] == 'p,q'


def test_default_options_category_shared_branch_all_have_strip():
    '''Regression test: the shared category dispatch branch in _data_aggregate_core does
    an unguarded options['strip'] lookup for category-and/or/min/max/average/count-*/
    text-length/*filled/are-same. Every one of those types' default options dict must
    include 'strip', or picking that type via the interactive default-options flow
    raises KeyError.'''
    from tedtoolkit.tables.aggregate import ATT_AGG_DEFAULT_OPTIONS
    shared_branch_types = ['category-and', 'category-or', 'category-min', 'category-max',
                           'category-average', 'category-count-nonempty', 'category-count-all',
                           'category-count-unique', 'category-are-same',
                           'category-min-text-length', 'category-max-text-length',
                           'category-avg-text-length', 'category-all-filled',
                           'category-some-filled', 'category-none-filled']
    for agg_type in shared_branch_types:
        assert 'strip' in ATT_AGG_DEFAULT_OPTIONS[agg_type], \
            f'{agg_type} default options missing required "strip" key'


def test_data_aggregate_wrapper_no_prompts_when_fully_specified(no_prompts, seed_history):
    '''Fully-specified kwargs (including agg_specs) must delegate straight to the core
    with zero prompts.'''
    no_prompts(aggregate_module, 'ask_yn', 'ask_select', 'ask_select_column_index', 'input')
    seed_history("x = data_aggregate(table)")
    specs = [_spec('sum', 2, 'Total Amount', ignore_non_numbers=False,
                    non_numbers_text='-Non-numeric-', ignore_empty=True, empty_text='-All empty-')]
    result = data_aggregate(ORDERS, headers=True, aggregation_key_col=1, agg_key_name='Client Name',
                            agg_specs=specs)
    lookup = {row[0]: row[1] for row in result[1:]}
    assert lookup['George'] == 340
    assert lookup['Ben'] == 160
