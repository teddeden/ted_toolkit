'''Pure unit tests for tedtoolkit.io.xml's small flattening-engine helpers, mirroring
test_csv_helpers.py's convention of testing pure logic directly (no prompting/history/GUI).'''

import json

from lxml import etree

from tedtoolkit.io.xml import (
    _join_path, _display_name, _cartesian_merge, _detect_record_tag, _tag_depth_pairs_full,
    _resolve_record_elements, _strip_namespaces_inplace, _apply_max_columns, _order_columns,
    _materialize_table, _serialize_residual, _aggregate_children, _element_to_jsonable,
    _flatten_children, _flatten_record, _build_ancestor_context, _as_parse_input,
    _is_raw_xml_text, _make_flatten_opts, _FlattenContext,
)


def _opts(**overrides):
    defaults = dict(max_depth=None, residual_format='xml', list_strategy='explode',
                    list_strategy_overrides=None, aggregate_format='json',
                    aggregate_delimiter=' | ', max_indexed_items=10, force_list=None,
                    path_separator='.', attribute_prefix='@', text_key='#text',
                    include_attributes=True, include_text=True, namespace_mode='strip')
    defaults.update(overrides)
    return _make_flatten_opts(**defaults)


def _parse(xml_text):
    return etree.fromstring(xml_text.encode('utf-8'))


# ---------------------------------------------------------------------------
# path building / naming
# ---------------------------------------------------------------------------

def test_join_path_empty_base():
    assert _join_path('', 'Order', '.') == 'Order'


def test_join_path_with_base():
    assert _join_path('Order', 'Customer', '.') == 'Order.Customer'
    assert _join_path('Order', 'Customer', '/') == 'Order/Customer'


def test_display_name_strip_mode_plain_tag():
    elem = _parse('<a/>')
    assert _display_name('a', elem, 'strip') == 'a'


def test_display_name_keep_mode_clark_notation():
    elem = _parse('<root xmlns:x="http://example.com/x"><x:a/></root>')[0]
    assert _display_name(elem.tag, elem, 'keep') == '{http://example.com/x}a'


def test_display_name_prefix_mode_uses_declared_prefix():
    elem = _parse('<root xmlns:x="http://example.com/x"><x:a/></root>')[0]
    assert _display_name(elem.tag, elem, 'prefix') == 'x:a'


def test_display_name_strip_mode_removes_namespace():
    elem = _parse('<root xmlns:x="http://example.com/x"><x:a/></root>')[0]
    assert _display_name(elem.tag, elem, 'strip') == 'a'


# ---------------------------------------------------------------------------
# cartesian merge (the trickiest piece: multiple independent exploded lists)
# ---------------------------------------------------------------------------

def test_cartesian_merge_single_by_single_is_plain_merge():
    rows = [{'a': 1}]
    sub_rows = [{'b': 2}]
    assert _cartesian_merge(rows, sub_rows) == [{'a': 1, 'b': 2}]


def test_cartesian_merge_empty_sub_rows_leaves_rows_unchanged():
    rows = [{'a': 1}]
    assert _cartesian_merge(rows, []) == rows


def test_cartesian_merge_multiplies_out():
    rows = [{'a': 1}]
    sub_rows = [{'b': 1}, {'b': 2}]
    assert _cartesian_merge(rows, sub_rows) == [{'a': 1, 'b': 1}, {'a': 1, 'b': 2}]


def test_cartesian_merge_two_independent_lists_sequentially():
    '''Applying _cartesian_merge once per child-group, in sequence, must fully cross-multiply
    two independent sibling lists (2 line items x 2 tags = 4 rows), not just concatenate them.'''
    rows = [{}]
    rows = _cartesian_merge(rows, [{'item': 'A'}, {'item': 'B'}])
    rows = _cartesian_merge(rows, [{'tag': 'x'}, {'tag': 'y'}])
    assert len(rows) == 4
    assert {'item': 'A', 'tag': 'x'} in rows
    assert {'item': 'A', 'tag': 'y'} in rows
    assert {'item': 'B', 'tag': 'x'} in rows
    assert {'item': 'B', 'tag': 'y'} in rows


# ---------------------------------------------------------------------------
# record-tag auto-detection
# ---------------------------------------------------------------------------

def test_detect_record_tag_picks_shallowest_repeating_tag():
    pairs = [('Order', 1), ('Customer', 2), ('Order', 1)]
    assert _detect_record_tag(iter(pairs)) == 'Order'


def test_detect_record_tag_returns_none_when_nothing_repeats():
    pairs = [('A', 1), ('B', 1)]
    assert _detect_record_tag(iter(pairs)) is None


def test_detect_record_tag_prefers_shallower_over_more_frequent():
    # 'Deep' recurs more often but at depth 3; 'Shallow' recurs at depth 1 - shallow wins.
    pairs = [('Shallow', 1), ('Shallow', 1), ('Deep', 3), ('Deep', 3), ('Deep', 3)]
    assert _detect_record_tag(iter(pairs)) == 'Shallow'


def test_tag_depth_pairs_full_excludes_root_and_computes_depth():
    root = _parse('<root><a><b/></a></root>')
    pairs = dict(_tag_depth_pairs_full(root))
    assert 'root' not in pairs
    assert pairs['a'] == 1
    assert pairs['b'] == 2


# ---------------------------------------------------------------------------
# record_path / XPath resolution
# ---------------------------------------------------------------------------

def test_resolve_record_elements_strips_leading_root_segment():
    root = _parse('<Orders><Order id="1"/><Order id="2"/></Orders>')
    elements = _resolve_record_elements(root, 'Orders.Order', _opts())
    assert [e.get('id') for e in elements] == ['1', '2']


def test_resolve_record_elements_matches_by_local_name_ignoring_namespace():
    root = _parse('<root xmlns:x="http://example.com/x"><x:Item x:id="1"/></root>')
    elements = _resolve_record_elements(root, 'Item', _opts(namespace_mode='keep'))
    assert len(elements) == 1


def test_resolve_record_elements_raises_on_no_match():
    import pytest
    root = _parse('<root><a/></root>')
    with pytest.raises(ValueError):
        _resolve_record_elements(root, 'NoSuchTag', _opts())


def test_resolve_record_elements_auto_detects_when_record_path_none():
    root = _parse('<Root><Rec><X>1</X></Rec><Rec><X>2</X></Rec></Root>')
    elements = _resolve_record_elements(root, None, _opts())
    assert len(elements) == 2


def test_resolve_record_elements_returns_root_when_nothing_repeats():
    root = _parse('<Root><A/><B/></Root>')
    elements = _resolve_record_elements(root, None, _opts())
    assert elements == [root]


def test_strip_namespaces_inplace_rewrites_tags_and_attrs():
    root = _parse('<root xmlns:x="http://example.com/x"><x:a x:id="1">text</x:a></root>')
    _strip_namespaces_inplace(root)
    child = root[0]
    assert child.tag == 'a'
    assert child.get('id') == '1'


# ---------------------------------------------------------------------------
# column ordering / max_columns / materialize
# ---------------------------------------------------------------------------

def test_order_columns_discovery_preserves_order():
    assert _order_columns(['b', 'a', 'c'], 'discovery') == ['b', 'a', 'c']


def test_order_columns_alpha_sorts():
    assert _order_columns(['b', 'a', 'c'], 'alpha') == ['a', 'b', 'c']


def test_apply_max_columns_truncates_and_flags():
    columns, truncated = _apply_max_columns(['a', 'b', 'c'], 2)
    assert columns == ['a', 'b']
    assert truncated is True


def test_apply_max_columns_none_is_unlimited():
    columns, truncated = _apply_max_columns(['a', 'b'], None)
    assert columns == ['a', 'b']
    assert truncated is False


def test_materialize_table_fills_missing_with_empty_value():
    table = _materialize_table([{'a': 1}, {'b': 2}], ['a', 'b'], header_row=True, empty_value='')
    assert table == [['a', 'b'], [1, ''], ['', 2]]


def test_materialize_table_without_header_row():
    table = _materialize_table([{'a': 1}], ['a'], header_row=False, empty_value='')
    assert table == [[1]]


# ---------------------------------------------------------------------------
# residual / aggregate serialization
# ---------------------------------------------------------------------------

def test_serialize_residual_xml_format():
    elem = _parse('<a><b>1</b></a>')
    assert _serialize_residual(elem, 'xml', _opts()) == '<a><b>1</b></a>'


def test_serialize_residual_json_format():
    elem = _parse('<a id="1"><b>text</b></a>')
    result = json.loads(_serialize_residual(elem, 'json', _opts()))
    assert result == {'@id': '1', 'b': 'text'}


def test_serialize_residual_dict_format_is_repr():
    elem = _parse('<a><b>1</b></a>')
    result = _serialize_residual(elem, 'dict', _opts())
    assert eval(result) == {'b': '1'}


def test_serialize_residual_unknown_format_raises():
    import pytest
    elem = _parse('<a/>')
    with pytest.raises(ValueError):
        _serialize_residual(elem, 'bogus', _opts())


def test_aggregate_children_delimited_scalars():
    root = _parse('<r><t>rush</t><t>gift</t></r>')
    children = list(root)
    value = _aggregate_children(children, _opts(aggregate_format='delimited'))
    assert value == 'rush | gift'


def test_aggregate_children_json_format():
    root = _parse('<r><t sku="A1"><q>2</q></t><t sku="A2"><q>1</q></t></r>')
    children = list(root)
    value = json.loads(_aggregate_children(children, _opts(aggregate_format='json')))
    assert value == [{'@sku': 'A1', 'q': '2'}, {'@sku': 'A2', 'q': '1'}]


def test_aggregate_children_xml_format():
    root = _parse('<r><t>1</t><t>2</t></r>')
    children = list(root)
    value = _aggregate_children(children, _opts(aggregate_format='xml'))
    assert value == '<t>1</t><t>2</t>'


def test_element_to_jsonable_pure_leaf_returns_text():
    elem = _parse('<a>hello</a>')
    assert _element_to_jsonable(elem, _opts()) == 'hello'


def test_element_to_jsonable_repeated_children_become_list():
    elem = _parse('<a><b>1</b><b>2</b></a>')
    assert _element_to_jsonable(elem, _opts()) == {'b': ['1', '2']}


# ---------------------------------------------------------------------------
# the flattening engine itself
# ---------------------------------------------------------------------------

def test_flatten_children_scalar_and_attribute():
    elem = _parse('<Order id="1"><Customer>Alice</Customer></Order>')
    ctx = _FlattenContext()
    rows = _flatten_children(elem, '', 0, _opts(), ctx)
    assert rows == [{'@id': '1', 'Customer': 'Alice'}]


def test_flatten_children_text_and_attributes_uses_text_key():
    elem = _parse('<Note lang="en">hello</Note>')
    ctx = _FlattenContext()
    rows = _flatten_children(elem, 'Note', 0, _opts(), ctx)
    assert rows == [{'Note.@lang': 'en', 'Note.#text': 'hello'}]


def test_flatten_children_explode_cartesian_product():
    elem = _parse('<Order><LineItems><LineItem>A</LineItem><LineItem>B</LineItem></LineItems>'
                  '<Tags><Tag>x</Tag><Tag>y</Tag></Tags></Order>')
    ctx = _FlattenContext()
    rows = _flatten_children(elem, '', 0, _opts(), ctx)
    assert len(rows) == 4
    values = {(r['LineItems.LineItem'], r['Tags.Tag']) for r in rows}
    assert values == {('A', 'x'), ('A', 'y'), ('B', 'x'), ('B', 'y')}


def test_flatten_children_force_list_treats_single_occurrence_as_list():
    elem = _parse('<Order><LineItem>A</LineItem></Order>')
    ctx = _FlattenContext()
    rows = _flatten_children(elem, '', 0, _opts(force_list=['LineItem']), ctx)
    # explode strategy on a forced single-item list still yields exactly one row
    assert rows == [{'LineItem': 'A'}]


def test_flatten_children_list_strategy_overrides_takes_precedence():
    elem = _parse('<Order><Tags><Tag>x</Tag><Tag>y</Tag></Tags></Order>')
    ctx = _FlattenContext()
    opts = _opts(list_strategy='explode', list_strategy_overrides={'Tags.Tag': 'aggregate'})
    rows = _flatten_children(elem, '', 0, opts, ctx)
    assert len(rows) == 1
    assert json.loads(rows[0]['Tags.Tag']) == ['x', 'y']


def test_flatten_children_max_depth_produces_residual():
    # Order=depth0 (the record itself), LineItems=depth1, LineItem=depth2 - max_depth=1 means
    # depth2 (LineItem, a grandchild of the record) is "deeper than max_depth" and gets truncated.
    elem = _parse('<Order><LineItems><LineItem><Qty>2</Qty></LineItem></LineItems></Order>')
    ctx = _FlattenContext()
    rows = _flatten_children(elem, '', 0, _opts(max_depth=1), ctx)
    assert len(rows) == 1
    assert 'LineItems.LineItem.residual' in rows[0]
    assert '<LineItem><Qty>2</Qty></LineItem>' in rows[0]['LineItems.LineItem.residual']
    assert 'LineItems.LineItem' in ctx.truncated_paths


def test_flatten_children_indexed_strategy_caps_and_warns():
    elem = _parse('<Order><Tag>a</Tag><Tag>b</Tag><Tag>c</Tag></Order>')
    ctx = _FlattenContext()
    rows = _flatten_children(elem, '', 0, _opts(list_strategy='indexed', max_indexed_items=2), ctx)
    assert rows == [{'Tag.0': 'a', 'Tag.1': 'b'}]
    assert len(ctx.warnings) == 1


def test_flatten_record_merges_discovered_paths_into_context():
    elem = _parse('<Rec><X>1</X></Rec>')
    ctx = _FlattenContext()
    rows = _flatten_record(elem, {}, _opts(), ctx)
    assert rows == [{'X': '1'}]
    assert 'X' in ctx.discovered_paths


def test_flatten_record_merges_ancestor_context_into_every_row():
    elem = _parse('<Rec><X>1</X></Rec>')
    ctx = _FlattenContext()
    rows = _flatten_record(elem, {'Group.@region': 'west'}, _opts(), ctx)
    assert rows == [{'Group.@region': 'west', 'X': '1'}]


# ---------------------------------------------------------------------------
# per-instance ancestor context
# ---------------------------------------------------------------------------

def test_build_ancestor_context_is_specific_to_each_instance():
    root = _parse('''<Root>
        <Group region="west"><Order id="1"/></Group>
        <Group region="east"><Order id="2"/></Group>
    </Root>''')
    order1, order2 = root.xpath("//*[local-name()='Order']")
    ctx1 = _build_ancestor_context(order1, root, _opts())
    ctx2 = _build_ancestor_context(order2, root, _opts())
    assert ctx1['Group.@region'] == 'west'
    assert ctx2['Group.@region'] == 'east'


def test_build_ancestor_context_empty_for_direct_root_child():
    root = _parse('<Root region="global"><Order id="1"/></Root>')
    order = root[0]
    # root itself is intentionally excluded from context (see module design notes)
    assert _build_ancestor_context(order, root, _opts()) == {}


# ---------------------------------------------------------------------------
# source normalization
# ---------------------------------------------------------------------------

def test_is_raw_xml_text_detects_markup():
    assert _is_raw_xml_text('  <root/>') is True
    assert _is_raw_xml_text('C:/some/path.xml') is False


def test_as_parse_input_wraps_raw_string_as_bytesio():
    import io
    result = _as_parse_input('<a/>')
    assert isinstance(result, io.BytesIO)


def test_as_parse_input_passes_through_path_string():
    result = _as_parse_input('C:/some/path.xml')
    assert result == 'C:/some/path.xml'


def test_as_parse_input_wraps_bytes():
    import io
    result = _as_parse_input(b'<a/>')
    assert isinstance(result, io.BytesIO)
