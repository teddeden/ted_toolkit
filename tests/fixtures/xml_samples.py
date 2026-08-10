'''Shared small XML string fixtures for the xml_import test suite.

Plain factory functions, not fixtures (consistent with sample_tables.py) - each returns a fresh
string constant.
'''


def orders_xml():
    '''Two <Order> records under an <Orders> root, each with attributes, a nested scalar element,
    and two independent repeated child groups (LineItems.LineItem, Tags.Tag) - exercises the
    cartesian explode of multiple sibling lists under one parent.'''
    return '''<?xml version="1.0"?>
<Orders>
  <Order id="1" status="open">
    <Customer>Alice</Customer>
    <LineItems>
      <LineItem sku="A1"><Qty>2</Qty><Price>9.99</Price></LineItem>
      <LineItem sku="A2"><Qty>1</Qty><Price>4.50</Price></LineItem>
    </LineItems>
    <Tags>
      <Tag>rush</Tag>
      <Tag>gift</Tag>
    </Tags>
  </Order>
  <Order id="2" status="closed">
    <Customer>Bob</Customer>
    <LineItems>
      <LineItem sku="B1"><Qty>5</Qty><Price>1.00</Price></LineItem>
    </LineItems>
  </Order>
</Orders>
'''


def namespaced_items_xml():
    '''A default-namespaced document with a declared prefix - exercises namespace_mode.'''
    return '''<root xmlns:x="http://example.com/x">
  <x:Item x:id="1"><x:Name>foo</x:Name></x:Item>
  <x:Item x:id="2"><x:Name>bar</x:Name></x:Item>
</root>'''


def malformed_xml():
    '''Mismatched closing tag - exercises on_malformed='raise'/'recover'/'skip'.'''
    return '<root><a>1</a><b>2</root>'


def context_xml():
    '''Records nested two levels deep under distinct parent instances with their own attributes -
    exercises per-instance ancestor context (each Order's rows must get ITS OWN Group's
    attributes, not the first Group seen in the document).'''
    return '''<Root>
  <Group region="west">
    <Order id="1"><Amount>10</Amount></Order>
    <Order id="2"><Amount>20</Amount></Order>
  </Group>
  <Group region="east">
    <Order id="3"><Amount>30</Amount></Order>
  </Group>
</Root>'''


def flat_records_xml():
    '''Simple, uniform records with no lists/attributes - the baseline "just works" case.'''
    return '<Root><Rec><X>1</X><Y>9</Y></Rec><Rec><X>2</X><Y>8</Y></Rec></Root>'
