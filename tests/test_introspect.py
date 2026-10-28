'''Tests for tedtoolkit.introspect._variable_snapshot_core() - the
namespace-explicit counterpart to help_vars()'s variable-listing filter, used
by the GUI bridge's Variables panel.'''

import datetime
import types

import collections
import time

import pytest

from tedtoolkit.introspect import _variable_snapshot_core, _preview_repr


def test_includes_common_types():
    namespace = {'a': 1, 'b': 2.5, 'c': True, 'd': 'text', 'e': [1, 2],
                 'f': {1, 2}, 'g': {'k': 'v'}, 'h': datetime.datetime(2026, 1, 1)}
    names = {item['name'] for item in _variable_snapshot_core(namespace)}
    assert names == set(namespace)


def test_excludes_underscore_prefixed_names():
    namespace = {'_private': 1, 'public': 2}
    names = {item['name'] for item in _variable_snapshot_core(namespace)}
    assert names == {'public'}


def test_excludes_functions_and_modules():
    namespace = {'fn': lambda: None, 'mod': types, 'data': [1, 2, 3]}
    names = {item['name'] for item in _variable_snapshot_core(namespace)}
    assert names == {'data'}


def test_excludes_all_caps_when_exclude_globals_true():
    namespace = {'VERSION': '0.72', 'data': [1]}
    names = {item['name'] for item in _variable_snapshot_core(namespace, exclude_globals=True)}
    assert names == {'data'}


def test_includes_all_caps_when_exclude_globals_false():
    namespace = {'VERSION': '0.72', 'data': [1]}
    names = {item['name'] for item in _variable_snapshot_core(namespace, exclude_globals=False)}
    assert names == {'VERSION', 'data'}


def test_result_shape():
    result = _variable_snapshot_core({'x': [1, 2, 3]})
    assert result == [{'name': 'x', 'type': 'list', 'preview': '[1, 2, 3]'}]


def test_preview_is_truncated_to_40_chars():
    long_string = 'a' * 100
    result = _variable_snapshot_core({'x': long_string})
    assert len(result[0]['preview']) == 40


# --- _preview_repr(): bounded preview, must equal repr(value)[:width] ---------------

def _self_ref_list():
    lst = [1, 2]
    lst.append(lst)
    return lst


def _self_ref_dict():
    dct = {'a': 1}
    dct['me'] = dct
    return dct


class _PlainListSubclass(list):
    pass


class _PlainSetSubclass(set):
    pass


PREVIEW_CASES = [
    0, -17, 3.25, float('inf'), True, None, 10**50,
    '', 'short', 'x' * 500, "it's", 'say "hi"', 'both \' and "' + 'z' * 80,
    "only ' quote here " + 'y' * 80, 'tab\tnew\nline\back' * 20, 'ünïcødé ✓ ' * 20,
    [], [[]], [1, 'two', 3.0, None], [[i, str(i)] for i in range(100)],
    (), (1,), ((1,),), (1, 2, 3) * 30,
    set(), {1}, set(range(200)), frozenset(), frozenset({'a'}),
    {}, {'k': 'v'}, {i: {'nested': [i] * 5} for i in range(100)},
    {(1, 2): {3, 4}, 'x': (5,)},
    datetime.datetime(2026, 1, 2, 3, 4, 5), datetime.date(2026, 1, 2),
    _self_ref_list(), _self_ref_dict(),
    _PlainListSubclass([1, 2, 3]), _PlainSetSubclass({1}), _PlainSetSubclass(),
    collections.OrderedDict([('a', 1), ('b', [2, 3])]),
]


@pytest.mark.parametrize('value', PREVIEW_CASES, ids=lambda v: type(v).__name__)
@pytest.mark.parametrize('width', [1, 5, 40, 200])
def test_preview_repr_matches_repr_prefix(value, width):
    assert _preview_repr(value, width) == repr(value)[:width]


def test_preview_repr_default_width_is_40():
    value = list(range(1000))
    assert _preview_repr(value) == repr(value)[:40]


def test_preview_repr_zero_width():
    assert _preview_repr([1, 2, 3], 0) == ''


def test_preview_repr_custom_repr_subclass_is_approximated():
    value = collections.defaultdict(list, {'a': [1]})
    assert _preview_repr(value) == "defaultdict({'a': [1]})"


def test_preview_repr_huge_int_does_not_raise():
    assert 'preview unavailable' in _preview_repr(10**5000)


def test_preview_repr_is_fast_on_large_objects():
    # Regression: help_vars() called repr() on the whole object before slicing 40 chars
    big_table = [[row, 'value', row * 1.5] for row in range(1_000_000)]
    big_tree = {i: {'children': list(range(50))} for i in range(100_000)}
    big_text = 'abc' * 10_000_000
    start = time.perf_counter()
    for value in (big_table, big_tree, big_text):
        _preview_repr(value)
    assert time.perf_counter() - start < 0.5


def test_snapshot_preview_uses_bounded_preview():
    namespace = {'big': [[i] * 10 for i in range(200_000)]}
    [item] = _variable_snapshot_core(namespace)
    assert item['preview'] == repr(namespace['big'])[:40]
