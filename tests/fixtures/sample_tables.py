'''Shared list-of-lists table builders for tests.

Plain factory functions, not fixtures, and each returns a FRESH list on every
call - several cores under test (compare_columns, data_de_aggregate) mutate
their input, and a shared mutable object would leak mutation across tests.
'''


def orders_table(headers=True):
    '''Canonical small table mirroring data_aggregate()'s own docstring example.'''
    data = [
        ['Order ID', 'Client Name', 'Amount'],
        [1, 'George', 100],
        [2, 'Ben', 50],
        [3, 'George', 230],
        [4, 'George', 10],
        [5, 'Ben', 110],
    ]
    return data if headers else data[1:]


def ragged_table():
    '''Table with unequal row lengths - for exercising guard-rail exceptions.'''
    return [
        ['A', 'B', 'C'],
        [1, 2, 3],
        [4, 5],
    ]


def ambiguous_key_table():
    '''Table with a duplicate key value - for exercising key_analysis()'s A-H categories.'''
    return [
        ['Key', 'Value'],
        ['a', 1],
        ['a', 2],
        ['b', 3],
    ]


def two_col_table(rows):
    '''Build a simple two-column ['Old', 'New'] table from a list of (old, new) pairs.'''
    return [['Old', 'New']] + [[old, new] for (old, new) in rows]
