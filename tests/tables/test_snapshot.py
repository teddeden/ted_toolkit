'''Tests for tedtoolkit.tables.snapshot._table_snapshot_core() - the bounded,
structured table preview used by the GUI's Data Preview panel.'''

import pytest

from tedtoolkit.tables.snapshot import _table_snapshot_core


def test_small_table_is_not_truncated(orders_table):
    result = _table_snapshot_core(orders_table)
    assert result['row_count'] == 6
    assert result['col_count'] == 3
    assert result['truncated_rows'] is False
    assert result['truncated_cols'] is False
    assert result['column_labels'] == ['A', 'B', 'C']
    assert result['rows'][0] == ['Order ID', 'Client Name', 'Amount']
    assert len(result['rows']) == 6


def test_truncates_rows_and_reports_true_dimensions():
    table = [['H']] + [[str(i)] for i in range(300)]
    result = _table_snapshot_core(table, max_rows=250, max_cols=250)
    assert result['row_count'] == 301
    assert result['truncated_rows'] is True
    assert len(result['rows']) == 250


def test_truncates_columns_and_reports_true_dimensions():
    table = [[str(i) for i in range(300)]]
    result = _table_snapshot_core(table, max_rows=250, max_cols=250)
    assert result['col_count'] == 300
    assert result['truncated_cols'] is True
    assert len(result['rows'][0]) == 250
    assert len(result['column_labels']) == 250


def test_cell_values_are_stringified():
    result = _table_snapshot_core([[1, 2.5, None, True]])
    assert result['rows'][0] == ['1', '2.5', 'None', 'True']


def test_ragged_table_col_count_uses_widest_row(ragged_table):
    result = _table_snapshot_core(ragged_table)
    assert result['col_count'] == 3
    assert result['rows'][-1] == ['4', '5']


def test_rejects_non_table_input():
    with pytest.raises(TypeError):
        _table_snapshot_core([1, 2, 3])


def test_empty_table():
    result = _table_snapshot_core([])
    assert result == {
        'row_count': 0,
        'col_count': 0,
        'truncated_rows': False,
        'truncated_cols': False,
        'column_labels': [],
        'rows': [],
    }
