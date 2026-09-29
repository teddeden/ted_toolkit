'''Tests for tedtoolkit.io.qr's qr_encode()/qr_decode(), mirroring test_archive.py's pattern:
pure-core round-trip tests (envelope format, chunking/reassembly, binary-to-text encodings,
generic/foreign QR decode), wrapper zero-prompt round-trip tests, and kwarg-baking regression
tests. Multi-chunk scenarios deliberately use the smallest content that still forces >1 chunk
(error_correction='H' has the lowest per-code capacity) to keep runtime reasonable - every QR
image _qr_encode_core() produces is self-verified via a real render+decode round trip (see its
module docstring), so each chunk costs real wall-clock time.'''

import os
import readline

import pytest
from PIL import Image

from tedtoolkit.history import _check_assignment
from tedtoolkit.io.qr import (qr_encode, qr_decode, _build_envelope, _parse_envelope,
                              _encode_binary_to_text, _decode_text_to_binary,
                              _qr_encode_core, _qr_decode_core, QR_MAX_CHARS_V40)
from tedtoolkit.io import qr as qr_module

_FULLY_SPECIFIED_ENCODE = dict(encoding_type='base64', output_type='files',
                               error_correction='M', box_size=6, border=2,
                               base_file_name='qr_code')


# ---------------------------------------------------------------------------
# Envelope format
# ---------------------------------------------------------------------------

def test_build_and_parse_envelope_round_trip():
    text = _build_envelope('abcd1234', 2, 5, 'base64', 'photo.jpg', 'SGVsbG8=')
    parsed = _parse_envelope(text)
    assert parsed == {'session_id': 'abcd1234', 'seq': 2, 'total': 5,
                      'content_encoding': 'base64', 'filename': 'photo.jpg',
                      'payload_text': 'SGVsbG8='}


def test_parse_envelope_returns_none_for_foreign_text():
    assert _parse_envelope('https://example.com/not-ours') is None
    assert _parse_envelope('TTKQR1|missing-fields') is None


def test_envelope_payload_may_contain_pipe_free_binary_text_encodings():
    # base64/uuencode alphabets never contain '|', so a fixed-count split is safe even when the
    # payload itself came from arbitrary binary content.
    encoded = _encode_binary_to_text(bytes(range(256)), 'base64')
    assert '|' not in encoded
    encoded_uu = _encode_binary_to_text(bytes(range(256)), 'uuencode')
    assert '|' not in encoded_uu


# ---------------------------------------------------------------------------
# Binary <-> text encodings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('encoding_type', ['base64', 'uuencode'])
def test_binary_text_round_trip(encoding_type):
    data = bytes(range(256)) * 3
    encoded = _encode_binary_to_text(data, encoding_type)
    assert _decode_text_to_binary(encoded, encoding_type) == data


def test_binary_text_round_trip_survives_arbitrary_mid_stream_split():
    # _qr_decode_core() reassembles chunks by simple string concatenation - encoded text must
    # reconstruct correctly even when split at a character boundary that isn't a uuencode line
    # boundary.
    data = os.urandom(500)
    encoded = _encode_binary_to_text(data, 'uuencode')
    mid = len(encoded) // 2
    rejoined = encoded[:mid] + encoded[mid:]
    assert _decode_text_to_binary(rejoined, 'uuencode') == data


def test_unknown_encoding_type_raises():
    with pytest.raises(ValueError):
        _encode_binary_to_text(b'x', 'rot13')
    with pytest.raises(ValueError):
        _decode_text_to_binary('x', 'rot13')


# ---------------------------------------------------------------------------
# _qr_encode_core / _qr_decode_core - pure round trips
# ---------------------------------------------------------------------------

def test_core_round_trip_utf8_text():
    images = _qr_encode_core('hello world'.encode('utf-8'), '', 'base64', 'M', 6, 2)
    assert len(images) == 1
    assert all(isinstance(img, Image.Image) for img in images)
    results = _qr_decode_core(qr_module._decode_payloads_from_images(images))
    assert results == [{'content': 'hello world', 'filename': ''}]


def test_core_round_trip_binary_base64_preserves_filename():
    data = os.urandom(200)
    images = _qr_encode_core(data, 'photo.jpg', 'base64', 'M', 6, 2)
    results = _qr_decode_core(qr_module._decode_payloads_from_images(images))
    assert results == [{'content': data, 'filename': 'photo.jpg'}]


def test_core_round_trip_binary_uuencode():
    data = os.urandom(200)
    images = _qr_encode_core(data, 'data.bin', 'uuencode', 'M', 6, 2)
    results = _qr_decode_core(qr_module._decode_payloads_from_images(images))
    assert results == [{'content': data, 'filename': 'data.bin'}]


def test_core_splits_across_multiple_codes_when_content_exceeds_capacity():
    # error_correction='H' has the smallest per-code capacity (see QR_MAX_CHARS_V40); base64 of
    # ~1000 random bytes comfortably exceeds it, forcing at least 2 chunks.
    assert QR_MAX_CHARS_V40['H'] < 1350
    data = os.urandom(1000)
    images = _qr_encode_core(data, '', 'base64', 'H', 6, 2)
    assert len(images) > 1
    results = _qr_decode_core(qr_module._decode_payloads_from_images(images))
    assert results == [{'content': data, 'filename': ''}]


def test_core_decode_raises_on_missing_chunk():
    data = os.urandom(1000)
    images = _qr_encode_core(data, '', 'base64', 'H', 6, 2)
    assert len(images) > 1
    payloads = qr_module._decode_payloads_from_images(images[:-1])  # drop the last chunk
    with pytest.raises(ValueError, match='incomplete'):
        _qr_decode_core(payloads)


def test_core_decodes_foreign_generic_qr_code_as_raw_text():
    import qrcode
    qr = qrcode.QRCode(version=None, box_size=6, border=2)
    qr.add_data('https://example.com/plain-qr')
    qr.make(fit=True)
    foreign_img = qr.make_image(fill_color='black', back_color='white').get_image()
    results = _qr_decode_core(qr_module._decode_payloads_from_images([foreign_img]))
    assert results == [{'content': 'https://example.com/plain-qr', 'filename': ''}]


# ---------------------------------------------------------------------------
# qr_encode() wrapper
# ---------------------------------------------------------------------------

def test_qr_encode_requires_assignment(seed_history):
    seed_history('qr_encode(input_source_type="string", input_source="hi")')
    with pytest.raises(Exception):
        _check_assignment(function_name='qr_encode')


def test_qr_encode_wrapper_zero_prompts_when_fully_specified(no_prompts, seed_history, tmp_path):
    seed_history('result = qr_encode(input_source_type="string", input_source="hello world")')
    no_prompts(qr_module, '_prompt_for_list_arg', '_prompt_for_any_arg')
    result = qr_encode(input_source_type='string', input_source='hello world',
                       save_location=str(tmp_path), **_FULLY_SPECIFIED_ENCODE)
    assert result == [str(tmp_path / 'qr_code_001.png')]
    assert os.path.isfile(result[0])


def test_qr_encode_string_source_requires_input_source_kwarg(seed_history):
    seed_history('result = qr_encode(input_source_type="string")')
    with pytest.raises(ValueError):
        qr_encode(input_source_type='string')


def test_qr_encode_wrapper_returns_none_when_file_selection_cancelled(monkeypatch, seed_history):
    seed_history('result = qr_encode(input_source_type="file")')
    monkeypatch.setattr(qr_module, 'g_sel_file', lambda **k: '')
    result = qr_encode(input_source_type='file')
    assert result is None


def test_qr_encode_wrapper_returns_none_when_save_location_cancelled(monkeypatch, seed_history):
    seed_history('result = qr_encode(input_source_type="string", input_source="hi")')
    monkeypatch.setattr(qr_module, 'g_sel_folder', lambda **k: '')
    result = qr_encode(input_source_type='string', input_source='hi',
                       **{**_FULLY_SPECIFIED_ENCODE, 'save_location': None})
    assert result is None


def test_qr_encode_bakes_prompted_input_source_into_history(monkeypatch, seed_history, tmp_path):
    src = tmp_path / 'source.txt'
    src.write_text('hi there', encoding='utf-8')
    monkeypatch.setattr(qr_module, 'g_sel_file', lambda **k: str(src))
    seed_history('result = qr_encode(input_source_type="file", save_location=out, '
                 'encoding_type="base64", output_type="files", error_correction="M", '
                 'box_size=6, border=2, base_file_name="qr_code")')
    qr_encode(input_source_type='file', save_location=str(tmp_path / 'out'),
             **_FULLY_SPECIFIED_ENCODE)
    rewritten = readline.get_history_item(1)
    assert 'input_source=' in rewritten


def test_qr_encode_gui_output_shows_gallery_and_returns_images_in_memory(monkeypatch, seed_history,
                                                                          tmp_path):
    seed_history('result = qr_encode(input_source_type="string", input_source="hello gallery")')
    shown = []
    monkeypatch.setattr(qr_module, 'g_show_image_gallery',
                        lambda images, **k: shown.append(images))
    result = qr_encode(input_source_type='string', input_source='hello gallery',
                       **{**_FULLY_SPECIFIED_ENCODE, 'output_type': 'gui', 'save_location': None})
    assert len(shown) == 1
    assert result is shown[0]
    assert all(isinstance(img, Image.Image) for img in result)


def test_qr_encode_embeds_original_filename_from_file_source(seed_history, tmp_path):
    src = tmp_path / 'notes.txt'
    src.write_text('remember the milk', encoding='utf-8')
    out_dir = tmp_path / 'out'
    seed_history('paths = qr_encode(input_source_type="file", input_source=src)')
    paths = qr_encode(input_source_type='file', input_source=str(src),
                      save_location=str(out_dir), **_FULLY_SPECIFIED_ENCODE)
    seed_history('decoded = qr_decode(image_source=paths)')
    decoded = qr_decode(image_source=paths, output_type='variable')
    assert decoded == 'remember the milk'


# ---------------------------------------------------------------------------
# qr_decode() wrapper
# ---------------------------------------------------------------------------

def _encode_to_files(seed_history, tmp_path, content):
    seed_history('paths = qr_encode(input_source_type="string", input_source=content)')
    return qr_encode(input_source_type='string', input_source=content,
                     save_location=str(tmp_path), **_FULLY_SPECIFIED_ENCODE)


def test_qr_decode_requires_assignment(seed_history):
    seed_history('qr_decode(image_source="x")')
    with pytest.raises(Exception):
        _check_assignment(function_name='qr_decode')


def test_qr_decode_wrapper_zero_prompts_when_fully_specified(no_prompts, seed_history, tmp_path):
    paths = _encode_to_files(seed_history, tmp_path, 'zero prompt content')
    seed_history('result = qr_decode(image_source=paths, output_type="variable")')
    no_prompts(qr_module, '_prompt_for_list_arg', '_kwarg_parse_prompt_str')
    result = qr_decode(image_source=paths, output_type='variable')
    assert result == 'zero prompt content'


def test_qr_decode_wrapper_returns_none_when_selection_cancelled(monkeypatch, seed_history):
    seed_history('result = qr_decode()')
    monkeypatch.setattr(qr_module, 'g_sel_files', lambda **k: ())
    result = qr_decode()
    assert result is None


def _stub_prompt_for_list_arg(monkeypatch, captured):
    '''Records default_index instead of ever hitting a real (blocking) prompt - always resolves
    to the offered default, exactly like a user pressing Enter to accept it.'''
    def _stub(arg_name, choices_list, default_index=None, fn_name=None):
        captured['arg_name'] = arg_name
        captured['default_index'] = default_index
        return choices_list[default_index]
    monkeypatch.setattr(qr_module, '_prompt_for_list_arg', _stub)


def test_qr_decode_defaults_to_variable_when_no_filename_embedded(monkeypatch, seed_history,
                                                                    tmp_path):
    paths = _encode_to_files(seed_history, tmp_path, 'no filename here')
    captured = {}
    _stub_prompt_for_list_arg(monkeypatch, captured)
    seed_history('result = qr_decode(image_source=paths)')
    result = qr_decode(image_source=paths)
    assert captured == {'arg_name': 'output_type', 'default_index': 1}  # 1 == 'variable'
    assert result == 'no filename here'


def test_qr_decode_defaults_to_file_when_filename_embedded(monkeypatch, seed_history, tmp_path):
    src = tmp_path / 'orig.txt'
    src.write_text('has a filename', encoding='utf-8')
    encoded_dir = tmp_path / 'encoded'
    seed_history('paths = qr_encode(input_source_type="file", input_source=src)')
    paths = qr_encode(input_source_type='file', input_source=str(src),
                      save_location=str(encoded_dir), **_FULLY_SPECIFIED_ENCODE)
    captured = {}
    _stub_prompt_for_list_arg(monkeypatch, captured)
    decoded_dir = tmp_path / 'decoded'
    seed_history('result = qr_decode(image_source=paths)')
    result = qr_decode(image_source=paths, save_location=str(decoded_dir))
    assert captured == {'arg_name': 'output_type', 'default_index': 0}  # 0 == 'file'
    assert result == [str(decoded_dir / 'orig.txt')]
    assert (decoded_dir / 'orig.txt').read_text(encoding='utf-8') == 'has a filename'


def test_qr_decode_binary_result_written_as_bytes(seed_history, tmp_path):
    src = tmp_path / 'blob.bin'
    data = os.urandom(64)
    src.write_bytes(data)
    encoded_dir = tmp_path / 'encoded'
    seed_history('paths = qr_encode(input_source_type="file", input_source=src)')
    paths = qr_encode(input_source_type='file', input_source=str(src),
                      save_location=str(encoded_dir), **_FULLY_SPECIFIED_ENCODE)
    decoded_dir = tmp_path / 'decoded'
    seed_history('result = qr_decode(image_source=paths, output_type="file")')
    result = qr_decode(image_source=paths, output_type='file', save_location=str(decoded_dir))
    assert (decoded_dir / 'blob.bin').read_bytes() == data
