'''Tests for tedtoolkit.prompts's internal _prompt_for_*_arg helpers.

Regression coverage for a bug where these helpers prompted the user and used the
resolved value, but never called _add_kwarg_to_last_command() - so csv_import()/
csv_export() (the only callers) silently dropped delim/encoding/etc. from the
replayable history line while file_path (baked elsewhere, explicitly) survived.
'''

import tedtoolkit.prompts as prompts_module
from tedtoolkit.history import _quoted
from tedtoolkit.prompts import _prompt_for_any_arg, _prompt_for_bool_arg, _prompt_for_list_arg


def test_prompt_for_any_arg_bakes_accepted_default_into_history(monkeypatch, recording_kwarg_adder):
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    calls = recording_kwarg_adder(prompts_module)
    result = _prompt_for_any_arg('delim', ',', fn_name='csv_import')
    assert result == ','
    assert calls == [('delim', _quoted(','), 'csv_import')]


def test_prompt_for_any_arg_bakes_typed_value_into_history(monkeypatch, recording_kwarg_adder):
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: False)
    monkeypatch.setattr(prompts_module, 'input', lambda *a, **k: ';')
    calls = recording_kwarg_adder(prompts_module)
    result = _prompt_for_any_arg('delim', ',', fn_name='csv_import')
    assert result == ';'
    assert calls == [('delim', _quoted(';'), 'csv_import')]


def test_prompt_for_list_arg_bakes_accepted_default_into_history(monkeypatch, recording_kwarg_adder):
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    calls = recording_kwarg_adder(prompts_module)
    result = _prompt_for_list_arg('encoding', ['utf_8', 'ascii'], default_index=0, fn_name='csv_import')
    assert result == 'utf_8'
    assert calls == [('encoding', _quoted('utf_8'), 'csv_import')]


def test_prompt_for_list_arg_bakes_selected_choice_into_history(monkeypatch, recording_kwarg_adder):
    monkeypatch.setattr(prompts_module, 'input', lambda *a, **k: '1')
    calls = recording_kwarg_adder(prompts_module)
    result = _prompt_for_list_arg('encoding', ['utf_8', 'ascii'], fn_name='csv_import')
    assert result == 'ascii'
    assert calls == [('encoding', _quoted('ascii'), 'csv_import')]


def test_prompt_for_bool_arg_bakes_accepted_default_into_history(monkeypatch, recording_kwarg_adder):
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: True)
    calls = recording_kwarg_adder(prompts_module)
    result = _prompt_for_bool_arg('convert_dates', False, fn_name='csv_import')
    assert result is False
    assert calls == [('convert_dates', False, 'csv_import')]


def test_prompt_for_bool_arg_bakes_flipped_value_into_history(monkeypatch, recording_kwarg_adder):
    monkeypatch.setattr(prompts_module, 'ask_yn', lambda *a, **k: False)
    calls = recording_kwarg_adder(prompts_module)
    result = _prompt_for_bool_arg('convert_dates', False, fn_name='csv_import')
    assert result is True
    assert calls == [('convert_dates', True, 'csv_import')]
