import importlib

from tedtoolkit.tables.reconcile import reconcile, data_recon

# `import tedtoolkit.tables.reconcile as x` / `from tedtoolkit.tables import reconcile as x`
# both resolve via attribute access on the tedtoolkit.tables package, which tedtoolkit/tables/
# __init__.py's `from .reconcile import *` has already shadowed with the reconcile() function
# itself (same name as the submodule). importlib.import_module bypasses that by going straight
# to sys.modules.
reconcile_module = importlib.import_module('tedtoolkit.tables.reconcile')


def test_reconcile_basic_match_and_change():
    orig = [['ID', 'Name', 'Amount'], [1, 'George', 100], [2, 'Ben', 50]]
    new = [['ID', 'Name', 'Amount'], [1, 'George', 100], [2, 'Ben', 75]]
    result = reconcile(orig, new, key_indices=(0, 0))
    detail = result['detail']
    names_row = detail[1]  # detail[0] is column-info comments; detail[1] is the header names
    name_col = names_row.index('Name')
    amount_col = names_row.index('Amount')
    rows_by_key = {row[0]: row for row in detail[2:]}
    assert rows_by_key[1][name_col] == '-'   # unchanged -> match_text default
    assert rows_by_key[2][amount_col] == '50 --> 75'  # changed -> transition_text format


def test_reconcile_added_and_removed_records():
    orig = [['ID', 'Val'], [1, 'a'], [2, 'b']]
    new = [['ID', 'Val'], [1, 'a'], [3, 'c']]
    result = reconcile(orig, new, key_indices=(0, 0))
    keys_present = {row[0] for row in result['detail'][2:]}
    assert 2 in keys_present  # removed (missing from new)
    assert 3 in keys_present  # added (missing from orig)


def test_reconcile_duplicate_keys_reported():
    orig = [['ID', 'Val'], [1, 'a'], [1, 'b'], [2, 'c']]
    new = [['ID', 'Val'], [1, 'a'], [2, 'c']]
    result = reconcile(orig, new, key_indices=(0, 0))
    assert len(result['duplicates in original']) == 3  # header + 2 duplicate rows for key 1


def test_reconcile_autogen_key_when_no_key_column():
    orig = [['Val'], ['a'], ['b']]
    new = [['Val'], ['a'], ['b']]
    result = reconcile(orig, new)  # default key_indices=(-1,-1) -> row index used as key
    assert len(result['detail']) == 4  # 2 header rows + 2 data rows


def test_reconcile_tolerance():
    orig = [['ID', 'Amt'], [1, 100]]
    new = [['ID', 'Amt'], [1, 104]]
    result = reconcile(orig, new, key_indices=(0, 0), columns=[(0, 0, 0), (1, 1, 1)], tolerance=0.1)
    row = result['detail'][2]
    assert row[-1] == '--'  # in_tolerance_text default


def test_reconcile_summary_includes_header_uniqueness():
    orig = [['ID', 'ID', 'Val'], [1, 1, 'a']]
    new = [['ID', 'Val'], [1, 'b']]
    result = reconcile(orig, new, key_indices=(0, 0))
    summary_text = str(result['summary'])
    assert 'non-unique' in summary_text.lower()


def test_reconcile_excludes_source_data_when_requested():
    orig = [['ID', 'Val'], [1, 'a']]
    new = [['ID', 'Val'], [1, 'a']]
    result = reconcile(orig, new, key_indices=(0, 0), include_source_data_in_output=False)
    assert 'original' not in result
    assert 'new' not in result


def test_data_recon_wrapper_no_prompts_when_fully_specified(no_prompts, seed_history):
    '''Fully-specified kwargs (AUTO-OR path, which is fully functional) must delegate
    straight to reconcile() with zero prompts.'''
    no_prompts(reconcile_module, 'ask_yn', 'ask_select', 'ask_num')
    seed_history("x = data_recon(orig, new)")
    orig = [['ID', 'Val'], [1, 'a'], [2, 'b']]
    new = [['ID', 'Val'], [1, 'a'], [2, 'c']]
    result = data_recon(orig, new, strip=True, include_source_data_in_output=True,
                        match_text='-', empty_text='<blank>', missing_col_text='<missing_col>',
                        missing_record_text='<missing_rec>', ambiguous_record_text='<ambig rec>',
                        transition_text=' --> ', col_mode='POSITION', col_select='AUTO-OR',
                        key_indices=(0, 0), numeric_key=True)
    assert 'detail' in result
