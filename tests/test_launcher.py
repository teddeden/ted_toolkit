'''Tests for the ted_toolkit.py launcher itself: help_all() coverage of the public namespace.'''

import inspect

import ted_toolkit


def test_every_public_function_has_a_help_all_category():
    # Regression: maybe_start_bridge() leaked into help_all() under "**no category**"
    namespace = vars(ted_toolkit)
    uncategorised = [name for name, value in namespace.items()
                     if inspect.isfunction(value) and not name.startswith('_')
                     and name not in ted_toolkit.FUNCTION_CATEGORIES]
    assert uncategorised == []
