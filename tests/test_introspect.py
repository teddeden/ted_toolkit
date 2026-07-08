'''Tests for tedtoolkit.introspect._variable_snapshot_core() - the
namespace-explicit counterpart to help_vars()'s variable-listing filter, used
by the GUI bridge's Variables panel.'''

import datetime
import types

from tedtoolkit.introspect import _variable_snapshot_core


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
