'''Shared pytest fixtures for the tedtoolkit test suite.'''

import readline

import pytest

from tests.fixtures import sample_tables, xml_samples


@pytest.fixture(autouse=True)
def reset_readline_history():
    '''Clear readline history before and after every test so no test's history
    mutations leak into another test - critical given how much of this
    codebase's wrapper behavior is expressed as global readline state.'''
    readline.clear_history()
    yield
    readline.clear_history()


@pytest.fixture
def seed_history():
    '''Factory fixture: seed_history("x = foo(t)") clears history and adds one line,
    for tests exercising _add_kwarg_to_last_command()/_check_assignment() against a
    controlled "last typed command".'''
    def _seed(line):
        readline.clear_history()
        readline.add_history(line)
    return _seed


@pytest.fixture
def no_prompts(monkeypatch):
    '''Factory fixture: no_prompts(module, 'ask_yn', 'ask_num', ...) monkeypatches the
    named prompt functions on `module` to raise AssertionError if called - proves a
    wrapper's "fully-specified kwargs -> zero prompts" contract.'''
    def _raise(*args, **kwargs):
        raise AssertionError('Unexpected prompt call with fully-specified kwargs: '
                              f'args={args!r} kwargs={kwargs!r}')

    def _apply(module, *names):
        for name in names:
            monkeypatch.setattr(module, name, _raise)
    return _apply


@pytest.fixture
def recording_kwarg_adder(monkeypatch):
    '''Monkeypatches _add_kwarg_to_last_command (as imported into `module`) to record
    (keyword, value, fn_name) tuples instead of touching real readline history.
    Returns the list the calls are recorded into.'''
    calls = []

    def _record(keyword, value, fn_name=''):
        calls.append((keyword, value, fn_name))

    def _apply(module):
        monkeypatch.setattr(module, '_add_kwarg_to_last_command', _record)
        return calls
    return _apply


@pytest.fixture
def orders_table():
    return sample_tables.orders_table()


@pytest.fixture
def ragged_table():
    return sample_tables.ragged_table()


@pytest.fixture
def ambiguous_key_table():
    return sample_tables.ambiguous_key_table()


@pytest.fixture
def orders_xml():
    return xml_samples.orders_xml()


@pytest.fixture
def namespaced_items_xml():
    return xml_samples.namespaced_items_xml()


@pytest.fixture
def malformed_xml():
    return xml_samples.malformed_xml()


@pytest.fixture
def context_xml():
    return xml_samples.context_xml()


@pytest.fixture
def flat_records_xml():
    return xml_samples.flat_records_xml()
