'''tedtoolkit.tables.snapshot - pure, structured table-preview helper for the
GUI bridge (see tedtoolkit/gui_bridge.py). Unlike data_preview() (which only
prints a column-header summary for interactive use), this returns a bounded,
JSON-serializable slice of a list-of-lists table suitable for rendering in a
GUI grid widget, capped at max_rows x max_cols for performance.
'''

from tedtoolkit.tables.columns import excel_column
from tedtoolkit.validation import _is_list_of_lists


def _table_snapshot_core(table, max_rows=250, max_cols=250):
    '''Return a bounded, JSON-serializable snapshot of a list-of-lists table:
        {
            'row_count': total rows in table,
            'col_count': widest row's length,
            'truncated_rows': bool - True if row_count > max_rows,
            'truncated_cols': bool - True if col_count > max_cols,
            'column_labels': excel_column() label for each included column,
            'rows': at most max_rows rows, each at most max_cols cells,
        }
    Cell values are stringified so the result is safely JSON-serializable
    regardless of what a cell actually holds.'''
    if not _is_list_of_lists(table):
        raise TypeError('table must be a list of lists')
    row_count = len(table)
    col_count = max((len(row) for row in table), default=0)
    included_cols = min(col_count, max_cols)
    rows = [[str(value) for value in row[:included_cols]] for row in table[:max_rows]]
    return {
        'row_count': row_count,
        'col_count': col_count,
        'truncated_rows': row_count > max_rows,
        'truncated_cols': col_count > max_cols,
        'column_labels': [excel_column(index) for index in range(included_cols)],
        'rows': rows,
    }
