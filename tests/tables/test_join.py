import importlib

from tedtoolkit.tables.join import data_join, _data_join_core

join_module = importlib.import_module('tedtoolkit.tables.join')


def _core(base, ext, join_type, **overrides):
    defaults = dict(neg_list=None, neg_key_col=-1, headers=True, base_hdr_tag='', ext_hdr_tag='',
                    suppress_key_table_return=False, no_match_text='-no match-',
                    ambiguous_text='-ambiguous-', join_error_text='-join error-',
                    include_unmatched_ext_in_ret_val=False, unmatched_ext_sheet_name='unmatched')
    defaults.update(overrides)
    return _data_join_core(base, ext, join_type, 0, 0, **defaults)


def test_restrictive_join_only_unambiguous_matches():
    base = [['ID', 'Name'], [1, 'a'], [2, 'b'], [3, 'c']]
    ext = [['ID', 'Val'], [1, 'x'], [2, 'y'], [4, 'z']]
    result = _core(base, ext, 'restrictive')
    joined_keys = {row[0] for row in result['joined'][1:]}
    assert joined_keys == {1, 2}  # only category A (unique/unique) rows


def test_base_join_includes_unmatched_base_records():
    base = [['ID', 'Name'], [1, 'a'], [2, 'b'], [3, 'c']]
    ext = [['ID', 'Val'], [1, 'x'], [2, 'y'], [4, 'z']]
    result = _core(base, ext, 'base')
    joined_keys = {row[0] for row in result['joined'][1:]}
    assert joined_keys == {1, 2, 3}  # base records always present, no-match filled with dummy
    row3 = next(row for row in result['joined'][1:] if row[0] == 3)
    assert row3[-1] == '-no match-'


def test_promiscuous_join_includes_all_records():
    base = [['ID', 'Name'], [1, 'a'], [2, 'b'], [3, 'c']]
    ext = [['ID', 'Val'], [1, 'x'], [2, 'y'], [4, 'z']]
    result = _core(base, ext, 'promiscuous')
    joined_keys = {row[0] for row in result['joined'][1:]}
    assert joined_keys == {1, 2, 3, 4}


def test_join_include_unmatched_ext_table():
    base = [['ID', 'Name'], [1, 'a'], [2, 'b']]
    ext = [['ID', 'Val'], [1, 'x'], [4, 'z']]
    result = _core(base, ext, 'base', include_unmatched_ext_in_ret_val=True,
                    unmatched_ext_sheet_name='leftover')
    assert result['leftover'] == [['ID', 'Val'], [4, 'z']]


def test_join_suppress_key_table_return():
    base = [['ID', 'Name'], [1, 'a']]
    ext = [['ID', 'Val'], [1, 'x']]
    with_keys = _core(base, ext, 'restrictive', suppress_key_table_return=False)
    without_keys = _core(base, ext, 'restrictive', suppress_key_table_return=True)
    assert 'all_keys' in with_keys
    assert 'all_keys' not in without_keys


def test_join_header_tags_applied():
    base = [['ID', 'Name'], [1, 'a']]
    ext = [['ID', 'Val'], [1, 'x']]
    result = _core(base, ext, 'restrictive', base_hdr_tag='ORIG_', ext_hdr_tag='NEW_')
    assert result['joined'][0] == ['Key', 'Key Code', 'ORIG_ID', 'ORIG_Name', 'NEW_ID', 'NEW_Val']


def test_data_join_wrapper_no_prompts_when_fully_specified(no_prompts, seed_history):
    no_prompts(join_module, 'ask_select', 'ask_select_column_index')
    seed_history("result = data_join(base, ext)")
    base = [['ID', 'Name'], [1, 'a'], [2, 'b']]
    ext = [['ID', 'Val'], [1, 'x'], [2, 'y']]
    result = data_join(base, ext, join_type='restrictive', base_key_col=0, ext_key_col=0,
                       headers=True, base_hdr_tag='', ext_hdr_tag='')
    assert len(result['joined']) == 3  # header + 2 matched rows
