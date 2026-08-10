'''Tests for tedtoolkit.io.xml's xml_import()/_xml_import_core(), mirroring test_csv.py's
pattern: pure-core tests against small XML fixtures, a wrapper round-trip test with fully-
specified kwargs asserting zero prompts, and a kwarg-baking regression test.'''

import os
import readline

import pytest

from tedtoolkit.io.xml import xml_import, _xml_import_core
from tedtoolkit.io import xml as xml_module
from tedtoolkit import prompts as prompts_module

# Every curated kwarg xml_import() may prompt for EXCEPT record_path (deliberately omitted here
# since almost every test below passes its own record_path - merging a second one via **kwargs
# would raise "multiple values for keyword argument"), fully specified so no test here ever
# blocks on stdin/hangs waiting for a prompt unless that's the exact thing under test.
_FULLY_SPECIFIED = dict(list_strategy='explode', max_depth=None, namespace_mode='strip',
                        on_malformed='raise', low_memory=False, header_row=True)


# ---------------------------------------------------------------------------
# _xml_import_core - single file / string / bytes source
# ---------------------------------------------------------------------------

def test_core_imports_from_raw_string_source(orders_xml):
    table = _xml_import_core(orders_xml, record_path='Orders.Order', **_FULLY_SPECIFIED)
    assert table[0] == ['@id', '@status', 'Customer', 'LineItems.LineItem.@sku',
                        'LineItems.LineItem.Qty', 'LineItems.LineItem.Price', 'Tags.Tag']
    assert len(table) - 1 == 5  # 2 line items x 2 tags for Order 1, 1 line item for Order 2


def test_core_imports_from_bytes_source(orders_xml):
    table = _xml_import_core(orders_xml.encode('utf-8'), record_path='Orders.Order',
                             **_FULLY_SPECIFIED)
    assert len(table) - 1 == 5


def test_core_imports_from_file_path(tmp_path, orders_xml):
    file_path = tmp_path / 'orders.xml'
    file_path.write_text(orders_xml, encoding='utf-8')
    table = _xml_import_core(str(file_path), record_path='Orders.Order', **_FULLY_SPECIFIED)
    assert len(table) - 1 == 5


def test_core_auto_detects_record_path(orders_xml):
    with_path = _xml_import_core(orders_xml, record_path='Orders.Order', **_FULLY_SPECIFIED)
    auto = _xml_import_core(orders_xml, record_path=None, **_FULLY_SPECIFIED)
    assert auto == with_path


def test_core_header_row_false_omits_header():
    # 2 <Rec> under root -> 'Rec' auto-detected as the repeating record element
    xml_text = '<Root><Rec><X>1</X></Rec><Rec><X>2</X></Rec></Root>'
    table = _xml_import_core(xml_text, record_path=None,
                             **{**_FULLY_SPECIFIED, 'header_row': False})
    assert table == [['1'], ['2']]


def test_core_empty_value_fills_missing_columns():
    xml_text = '<Root><Rec><X>1</X></Rec><Rec><Y>2</Y></Rec></Root>'
    table = _xml_import_core(xml_text, record_path=None, empty_value='<missing>',
                             **_FULLY_SPECIFIED)
    assert table[0] == ['X', 'Y']
    assert table[1] == ['1', '<missing>']
    assert table[2] == ['<missing>', '2']


def test_core_column_order_alpha(flat_records_xml):
    table = _xml_import_core(flat_records_xml, record_path=None, column_order='alpha',
                             **_FULLY_SPECIFIED)
    assert table[0] == ['X', 'Y']


def test_core_max_columns_truncates():
    xml_text = '<Root><Rec><A>1</A><B>2</B><C>3</C></Rec><Rec><A>4</A><B>5</B><C>6</C></Rec></Root>'
    table = _xml_import_core(xml_text, record_path=None, max_columns=2, **_FULLY_SPECIFIED)
    assert table[0] == ['A', 'B']


def test_core_max_rows_limits_output():
    xml_text = '<Root><Rec><X>1</X></Rec><Rec><X>2</X></Rec><Rec><X>3</X></Rec></Root>'
    table = _xml_import_core(xml_text, record_path=None, max_rows=2, **_FULLY_SPECIFIED)
    assert len(table) - 1 == 2


def test_core_return_metadata_shape(orders_xml):
    table, metadata = _xml_import_core(orders_xml, record_path='Orders.Order',
                                       return_metadata=True, **_FULLY_SPECIFIED)
    assert metadata['record_count'] == 5
    assert 'Customer' in metadata['discovered_paths']
    assert metadata['truncated_paths'] == []
    assert metadata['warnings'] == []


def test_core_context_xml_per_instance_ancestor_values(context_xml):
    table = _xml_import_core(context_xml, record_path='Group.Order', **_FULLY_SPECIFIED)
    header, *rows = table
    region_col = header.index('Group.@region')
    id_col = header.index('@id')
    by_id = {row[id_col]: row[region_col] for row in rows}
    assert by_id == {'1': 'west', '2': 'west', '3': 'east'}


def test_core_namespace_modes(namespaced_items_xml):
    strip_table = _xml_import_core(namespaced_items_xml, record_path='Item',
                                   **{**_FULLY_SPECIFIED, 'namespace_mode': 'strip'})
    prefix_table = _xml_import_core(namespaced_items_xml, record_path='Item',
                                    **{**_FULLY_SPECIFIED, 'namespace_mode': 'prefix'})
    assert strip_table[0] == ['@id', 'Name']
    assert prefix_table[0] == ['@x:id', 'x:Name']


def test_core_on_malformed_raise_raises(malformed_xml):
    from lxml import etree
    with pytest.raises(etree.XMLSyntaxError):
        _xml_import_core(malformed_xml, **{**_FULLY_SPECIFIED, 'on_malformed': 'raise'})


def test_core_on_malformed_skip_returns_empty(malformed_xml):
    table = _xml_import_core(malformed_xml, **{**_FULLY_SPECIFIED, 'on_malformed': 'skip'})
    assert table == [[]]


def test_core_on_malformed_recover_salvages_partial_tree(malformed_xml):
    table = _xml_import_core(malformed_xml, **{**_FULLY_SPECIFIED, 'on_malformed': 'recover'})
    assert len(table) >= 1  # at least the header/root-derived row survives


def test_core_low_memory_matches_full_parse(orders_xml):
    full = _xml_import_core(orders_xml, record_path='Orders.Order', **_FULLY_SPECIFIED)
    streaming = _xml_import_core(orders_xml, record_path='Orders.Order',
                                 **{**_FULLY_SPECIFIED, 'low_memory': True})
    assert full == streaming


# ---------------------------------------------------------------------------
# _xml_import_core - bulk/folder mode
# ---------------------------------------------------------------------------

def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return path


def test_core_bulk_folder_returns_dict_keyed_by_filename(tmp_path):
    _write(tmp_path, 'a.xml', '<Root><Rec><X>1</X></Rec></Root>')
    _write(tmp_path, 'b.xml', '<Root><Rec><X>2</X></Rec></Root>')
    result = _xml_import_core(str(tmp_path), record_path='Root.Rec', **_FULLY_SPECIFIED)
    assert set(result.keys()) == {'a.xml', 'b.xml'}
    assert result['a.xml'] == [['X'], ['1']]
    assert result['b.xml'] == [['X'], ['2']]


def test_core_bulk_folder_skips_non_xml_files(tmp_path, capsys):
    _write(tmp_path, 'a.xml', '<Root><Rec><X>1</X></Rec></Root>')
    _write(tmp_path, 'notes.txt', 'not xml')
    result = _xml_import_core(str(tmp_path), record_path='Root.Rec', **_FULLY_SPECIFIED)
    assert list(result.keys()) == ['a.xml']
    assert 'skipping non-XML file' in capsys.readouterr().out


def test_core_bulk_folder_stable_order_unifies_columns_across_files(tmp_path):
    _write(tmp_path, 'a.xml', '<Root><Rec><X>1</X></Rec></Root>')
    _write(tmp_path, 'b.xml', '<Root><Rec><X>2</X><Y>9</Y></Rec></Root>')
    result = _xml_import_core(str(tmp_path), record_path='Root.Rec', column_order='stable',
                              **_FULLY_SPECIFIED)
    assert result['a.xml'][0] == ['X', 'Y']
    assert result['b.xml'][0] == ['X', 'Y']
    assert result['a.xml'][1] == ['1', '']


def test_core_bulk_folder_no_xml_files_returns_empty_dict(tmp_path, capsys):
    _write(tmp_path, 'notes.txt', 'not xml')
    result = _xml_import_core(str(tmp_path), record_path='Root.Rec', **_FULLY_SPECIFIED)
    assert result == {}
    assert 'no .xml files found' in capsys.readouterr().out


# ---------------------------------------------------------------------------
# wrapper: zero-prompt round trip
# ---------------------------------------------------------------------------

def test_xml_import_wrapper_zero_prompts_when_fully_specified(no_prompts, orders_xml):
    no_prompts(xml_module, 'ask_yn', '_prompt_for_list_arg', '_prompt_for_bool_arg')
    result = xml_import(source=orders_xml, record_path='Orders.Order', **_FULLY_SPECIFIED)
    assert len(result) - 1 == 5


def test_xml_import_wrapper_returns_none_when_source_selection_cancelled(monkeypatch):
    monkeypatch.setattr(xml_module, 'ask_yn', lambda *a, **k: False)
    monkeypatch.setattr(xml_module, 'g_sel_file', lambda **k: '')
    result = xml_import()
    assert result is None


# ---------------------------------------------------------------------------
# kwarg-baking regression test
# ---------------------------------------------------------------------------

def test_xml_import_bakes_prompted_kwargs_into_history(monkeypatch, seed_history, orders_xml):
    '''When the curated kwargs are *not* supplied and get prompted for internally, the resolved
    values must be baked into the history line, exactly like csv_import's equivalent test.'''
    monkeypatch.setattr(xml_module, 'ask_yn', lambda *a, **k: True)
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    seed_history("result = xml_import(source={!r})".format(orders_xml))
    xml_import(source=orders_xml)
    rewritten = readline.get_history_item(1)
    assert 'xml_import(' in rewritten
    for kwarg in ('record_path=', 'list_strategy=', 'max_depth=', 'namespace_mode=',
                  'on_malformed=', 'low_memory=', 'header_row='):
        assert kwarg in rewritten, '{} missing from: {}'.format(kwarg, rewritten)
