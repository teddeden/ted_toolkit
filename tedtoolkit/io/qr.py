'''tedtoolkit.io.qr - visual-channel (QR code) encode/decode: turn arbitrary UTF-8 text or binary
content into one or more QR-code images (files on disk, or an in-memory GUI gallery - nothing
written to disk in that case), and reverse the process from one or more QR images back into the
original content, restoring the original filename when the source was a file.

Two new dependencies back this (see environment.yml): `qrcode` (pure-Python QR generation,
returns PIL images) and `opencv-python` (`cv2.QRCodeDetector` for image -> text decoding). Neither
touches the tabular list-of-lists data model this project avoids pandas/numpy for - `numpy` shows
up transitively via opencv-python's own wheel, purely as an internal detail of image-array
handling, not as a data-table representation.

Container format (every QR code we generate carries one of these, pipe-delimited; '|' never
appears in base64/uuencode output or in any header field we generate ourselves, so a fixed-count
str.split('|', maxsplit=5) safely separates header from payload on decode):

    TTKQR1|<session_id>|<seq>/<total>|<content_encoding>|<original_filename>|<payload_text>

- TTKQR1 (QR_MAGIC) - marks this as one of ours. A payload without this prefix is a foreign/
  generic QR code (e.g. a URL from some other app) - qr_decode() returns its raw text as-is, no
  chunk/session logic applied, for the "general-use QR decoding" requirement.
- session_id - random per-encode-call token so qr_decode() can group chunks that arrive mixed
  with unrelated codes or out of order.
- seq/total - 1-based chunk index and total chunk count.
- content_encoding - 'utf8' (payload_text IS the content, no binary-to-text step was needed),
  'base64', or 'uuencode'.
- original_filename - empty unless input_source_type='file'; os.path.basename(input_source).
- payload_text - this chunk's slice of the (optionally base64/uuencode'd) content.

Reliability note (why every generated image is self-verified before being accepted): OpenCV's
classical QRCodeDetector (no neural/contrib model involved) is measurably unreliable at high
QR versions/data density - empirically, dense codes near a given error_correction level's max
capacity often fail to decode with the FIRST rendering. QR's 8 standard mask patterns (0-7) are
an information-PRESERVING encoding choice - they don't change what the code contains, only which
of 8 fixed patterns XORs the data modules - and in practice at least one of the 8 decodes
reliably even when others don't. So _qr_encode_core() renders each chunk, decodes it right back
with the same cv2 detector qr_decode() uses, and only accepts the first mask pattern that
round-trips correctly; if genuinely none of the 8 do (not observed in testing even at max
version/H), it shrinks the per-chunk capacity and re-chunks, which always eventually succeeds
since small/low-version codes are reliable. This makes encoding slower than a naive
single-render approach (worst case up to 8x the QR render+decode cost per chunk) - noticeable for
large binary content at high error_correction levels - but guarantees qr_encode()'s own output is
actually decodable rather than merely well-formed.
'''

# pylint: disable=no-member
# cv2's C-extension bindings aren't statically introspectable by pylint - detectAndDecodeMulti(),
# cvtColor(), COLOR_RGB2BGR, imread(), and QRCodeDetector are all real, verified-at-runtime
# members; this is a well-known opencv-python/pylint false positive, not a defect.

import base64
import binascii
import glob
import os
import uuid

import cv2
import numpy as np
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from PIL import Image

from tedtoolkit.history import _add_kwarg_to_last_command, _check_assignment, _quoted
from tedtoolkit.prompts import _prompt_for_list_arg, _prompt_for_any_arg, _kwarg_parse_prompt_str
from tedtoolkit.gui.dialogs import g_sel_file, g_sel_folder, g_sel_files
from tedtoolkit.gui.image_viewer import g_show_image_gallery

QR_MAGIC = 'TTKQR1'
ERROR_CORRECTION_LEVELS = {'L': ERROR_CORRECT_L, 'M': ERROR_CORRECT_M,
                           'Q': ERROR_CORRECT_Q, 'H': ERROR_CORRECT_H}
# Real byte-mode capacity (chars) at QR version 40 (the largest) for mixed-case/base64-like
# content, one entry per error_correction level - measured directly against this project's
# `qrcode` version via binary search while catching qrcode.exceptions.DataOverflowError at a
# fixed version=40/fit=False (see git history for the probe script). box_size/border only affect
# the rendered image's pixel size, not data capacity, so they don't factor in here.
QR_MAX_CHARS_V40 = {'L': 2953, 'M': 2331, 'Q': 1663, 'H': 1273}

IMAGE_EXTENSIONS = ('*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif')
IMAGE_FILETYPES = [('Images', IMAGE_EXTENSIONS), ('All files', ('*.*'))]


# ---------------------------------------------------------------------------
# Binary <-> text (only used when source content isn't valid UTF-8)
# ---------------------------------------------------------------------------

def _encode_binary_to_text(content_bytes, encoding_type):
    if encoding_type == 'base64':
        return base64.b64encode(content_bytes).decode('ascii')
    if encoding_type == 'uuencode':
        return ''.join(binascii.b2a_uu(content_bytes[i:i + 45]).decode('ascii')
                       for i in range(0, len(content_bytes), 45))
    raise ValueError("qr_encode(): unknown encoding_type {!r}; must be 'base64' or "
                     "'uuencode'.".format(encoding_type))


def _decode_text_to_binary(payload_text, content_encoding):
    if content_encoding == 'base64':
        return base64.b64decode(payload_text)
    if content_encoding == 'uuencode':
        out = bytearray()
        for line in payload_text.splitlines(keepends=True):
            if line.strip():
                out += binascii.a2b_uu(line)
        return bytes(out)
    raise ValueError("qr_decode(): unknown content_encoding {!r} in QR payload.".format(
        content_encoding))


# ---------------------------------------------------------------------------
# Envelope (header) format
# ---------------------------------------------------------------------------

def _build_envelope(session_id, seq, total, content_encoding, filename, payload_text):
    return '|'.join([QR_MAGIC, session_id, '{}/{}'.format(seq, total), content_encoding,
                     filename, payload_text])


def _parse_envelope(text):
    '''Returns a parsed-fields dict, or None if text isn't one of our envelopes (a foreign/
    generic QR code).'''
    parts = text.split('|', 5)
    if len(parts) != 6 or parts[0] != QR_MAGIC:
        return None
    _, session_id, seq_total, content_encoding, filename, payload_text = parts
    try:
        seq_str, total_str = seq_total.split('/')
        seq, total = int(seq_str), int(total_str)
    except ValueError:
        return None
    return {'session_id': session_id, 'seq': seq, 'total': total,
           'content_encoding': content_encoding, 'filename': filename,
           'payload_text': payload_text}


# ---------------------------------------------------------------------------
# qr_encode() - content -> one or more QR-code images
# ---------------------------------------------------------------------------

def _max_payload_chars(error_correction, total_guess, session_id, filename, cap):
    '''cap is the current (possibly shrunk) capacity ceiling in chars; 'uuencode' (the longest
    content_encoding value) is used for the header-overhead estimate so the real header (whatever
    content_encoding turns out to be) never exceeds the reserved space.'''
    header_len = len(_build_envelope(session_id, total_guess, total_guess, 'uuencode',
                                     filename, ''))
    return min(cap, QR_MAX_CHARS_V40[error_correction]) - header_len


def _chunk_payload(encoded_text, error_correction, session_id, filename, cap):
    '''Split encoded_text into as many chunks as fit under `cap` chars (plus header overhead) per
    QR code, converging total_guess/header-length (header length depends on total's digit count,
    which depends on how many chunks there are - a small fixed-point iteration).'''
    total_guess = 1
    for _ in range(12):
        capacity = _max_payload_chars(error_correction, total_guess, session_id, filename, cap)
        if capacity <= 0:
            raise ValueError('qr_encode(): header overhead exceeds the code capacity for this '
                             'error_correction level (original_filename may be too long).')
        needed = max(1, -(-len(encoded_text) // capacity)) if encoded_text else 1
        if needed == total_guess:
            return ([encoded_text[i:i + capacity] for i in range(0, len(encoded_text), capacity)]
                   or [''])
        total_guess = needed
    raise RuntimeError('qr_encode(): could not converge on a stable QR chunk count.')


def _render_chunk_reliably(envelope_text, error_correction, box_size, border, detector):
    '''Try each of the 8 QR mask patterns until one round-trips through the same cv2 detector
    qr_decode() uses; returns the accepted PIL.Image.Image, or None if none of the 8 verified
    (the caller then shrinks capacity and re-chunks).'''
    for mask_pattern in range(8):
        qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECTION_LEVELS[error_correction],
                           box_size=box_size, border=border, mask_pattern=mask_pattern)
        qr.add_data(envelope_text)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white').get_image()
        arr = cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2BGR)
        retval, decoded_info, _points, _straight = detector.detectAndDecodeMulti(arr)
        if retval and envelope_text in decoded_info:
            return img
    return None


def _qr_encode_core(content_bytes, original_filename, encoding_type, error_correction,
                    box_size, border):
    '''Pure encode logic (no GUI/prompting/history side effects). Returns a list of
    PIL.Image.Image, one per QR code, in chunk order. See the module docstring for the container
    format and the self-verifying render strategy.'''
    try:
        text = content_bytes.decode('utf-8', errors='strict')
        content_encoding, encoded_text = 'utf8', text
    except UnicodeDecodeError:
        content_encoding = encoding_type
        encoded_text = _encode_binary_to_text(content_bytes, encoding_type)

    session_id = uuid.uuid4().hex[:8]
    filename = original_filename or ''
    detector = cv2.QRCodeDetector()
    cap = QR_MAX_CHARS_V40[error_correction]

    for _attempt in range(6):
        chunk_texts = _chunk_payload(encoded_text, error_correction, session_id, filename, cap)
        total = len(chunk_texts)
        images = []
        for seq, chunk_text in enumerate(chunk_texts, start=1):
            envelope = _build_envelope(session_id, seq, total, content_encoding, filename,
                                       chunk_text)
            img = _render_chunk_reliably(envelope, error_correction, box_size, border, detector)
            if img is None:
                images = None
                break
            images.append(img)
        if images is not None:
            return images
        cap = max(40, int(cap * 0.6))
    raise RuntimeError('qr_encode(): could not generate reliably-decodable QR code(s) for this '
                       'content; try a lower error_correction level.')


def _read_source_bytes(input_source_type, input_source):
    if input_source_type == 'file':
        with open(input_source, 'rb') as fil:
            return fil.read()
    if input_source_type == 'stream':
        data = input_source.read()
        return data.encode('utf-8') if isinstance(data, str) else data
    if input_source_type == 'string':
        return input_source.encode('utf-8') if isinstance(input_source, str) else input_source
    raise ValueError('qr_encode(): unknown input_source_type {!r}.'.format(input_source_type))


def qr_encode(**kwargs):
    '''Encode UTF-8 text or binary content into one or more QR-code images, splitting across
    multiple codes automatically when the content doesn't fit in one at the chosen
    error_correction level.
    kwargs:
      input_source_type - 'file' | 'string' | 'stream' (prompted, default 'file')
      input_source - a file path (input_source_type='file'; prompts via GUI if not given), a
        str/bytes value (input_source_type='string'), or an open file-like/stream object
        (input_source_type='stream', read via .read()). For 'string'/'stream' this must be
        supplied directly - there's no GUI prompt for an in-memory Python value.
      encoding_type - 'base64' | 'uuencode': binary-to-text encoding used only when the source
        content isn't valid UTF-8 text (prompted, default 'base64')
      output_type - 'files' | 'gui' (prompted, default 'files')
      save_location - destination folder; only used when output_type='files' (prompts via GUI
        if not given)
      base_file_name - filename stem; only used when output_type='files' - images are saved as
        '<base_file_name>_001.png', '_002.png', ... (prompted, default 'qr_code')
      error_correction - 'L' | 'M' | 'Q' | 'H' QR error-correction level, low to high redundancy
        (prompted, default 'M')
      box_size - pixel size of each QR module (prompted, default 10)
      border - QR quiet-zone border width in modules (prompted, default 4)

    If input_source_type='file', the original file name is embedded in every generated QR code
    so qr_decode() can reconstruct it later.

    Returns the list of saved file paths (output_type='files') or the list of in-memory
    PIL.Image.Image objects (output_type='gui' - nothing is written to disk in that case; the
    images are also displayed in a resizable gallery window with Prev/Next navigation).
    '''
    ass_var = _check_assignment(function_name='qr_encode')

    input_source_type = kwargs.get('input_source_type', None)
    if input_source_type not in ('file', 'string', 'stream'):
        input_source_type = _prompt_for_list_arg('input_source_type', ['file', 'string', 'stream'],
                                                  default_index=0, fn_name='qr_encode')

    input_source = kwargs.get('input_source', None)
    if input_source is None:
        if input_source_type != 'file':
            raise ValueError("qr_encode(): input_source must be supplied directly when "
                             "input_source_type is 'string' or 'stream' (there is no GUI prompt "
                             "for an in-memory value).")
        input_source = g_sel_file(title='qr_encode(): select file to encode')
        if not input_source:
            print('No file selected: qr_encode() cancelled.\n')
            return None
        if 'input_source' not in kwargs:
            _add_kwarg_to_last_command('input_source', _quoted(input_source), fn_name='qr_encode')

    encoding_type = kwargs.get('encoding_type', None)
    if encoding_type not in ('base64', 'uuencode'):
        encoding_type = _prompt_for_list_arg('encoding_type', ['base64', 'uuencode'],
                                             default_index=0, fn_name='qr_encode')

    output_type = kwargs.get('output_type', None)
    if output_type not in ('files', 'gui'):
        output_type = _prompt_for_list_arg('output_type', ['files', 'gui'],
                                           default_index=0, fn_name='qr_encode')

    error_correction = kwargs.get('error_correction', None)
    if error_correction not in ERROR_CORRECTION_LEVELS:
        error_correction = _prompt_for_list_arg('error_correction', ['L', 'M', 'Q', 'H'],
                                                default_index=1, fn_name='qr_encode')

    box_size = _prompt_for_any_arg('box_size', 10, numeric=True, fn_name='qr_encode') \
              if 'box_size' not in kwargs else kwargs['box_size']
    border = _prompt_for_any_arg('border', 4, numeric=True, fn_name='qr_encode') \
            if 'border' not in kwargs else kwargs['border']

    save_location = kwargs.get('save_location', None)
    base_file_name = 'qr_code'
    if output_type == 'files':
        if save_location is None:
            save_location = g_sel_folder(title='qr_encode(): select folder to save QR image(s)')
            if not save_location:
                print('No destination folder selected: qr_encode() cancelled.\n')
                return None
            if 'save_location' not in kwargs:
                _add_kwarg_to_last_command('save_location', _quoted(save_location),
                                           fn_name='qr_encode')
        base_file_name = _kwarg_parse_prompt_str('base_file_name', default_val='qr_code', **kwargs)

    original_filename = os.path.basename(input_source) if input_source_type == 'file' else ''
    content_bytes = _read_source_bytes(input_source_type, input_source)

    images = _qr_encode_core(content_bytes, original_filename, encoding_type, error_correction,
                             int(box_size), int(border))
    print('qr_encode(): {} QR code(s) generated.\n'.format(len(images)))

    if output_type == 'files':
        os.makedirs(save_location, exist_ok=True)
        result = []
        for index, img in enumerate(images, start=1):
            path = os.path.join(save_location, '{}_{:03d}.png'.format(base_file_name, index))
            img.save(path)
            result.append(path)
    else:
        g_show_image_gallery(images, window_title='qr_encode() preview')
        result = images

    if ass_var:
        print('Assigning result to variable <{}>.'.format(ass_var))
    return result
qr_encode.desc = 'Encode text/binary content into one or more QR-code images'


# ---------------------------------------------------------------------------
# qr_decode() - one or more QR-code images -> content
# ---------------------------------------------------------------------------

def _cv2_array_from_source(item):
    '''item: path/Path str, PIL.Image.Image, or numpy array. Returns a BGR numpy array for cv2.'''
    if isinstance(item, Image.Image):
        return cv2.cvtColor(np.array(item.convert('RGB')), cv2.COLOR_RGB2BGR)
    if isinstance(item, np.ndarray):
        return item
    path = os.fspath(item)
    img = cv2.imread(path)
    if img is None:
        raise ValueError('qr_decode(): could not read image at <{}>.'.format(path))
    return img


def _resolve_image_source(image_source):
    '''Normalizes image_source into a list of items _cv2_array_from_source() can read: a single
    path/PIL.Image, a list/tuple of paths/PIL.Images, or a folder path (globbed for common image
    extensions).'''
    if isinstance(image_source, Image.Image):
        return [image_source]
    if isinstance(image_source, (list, tuple)):
        return list(image_source)
    if isinstance(image_source, str) and os.path.isdir(image_source):
        found = []
        for ext in IMAGE_EXTENSIONS:
            found.extend(glob.glob(os.path.join(image_source, ext)))
        return sorted(found)
    return [image_source]


def _decode_payloads_from_images(items):
    '''items: list of path/PIL.Image/ndarray. Returns every decoded QR payload string found
    across all images (image order, then in-image detection order).'''
    detector = cv2.QRCodeDetector()
    payloads = []
    for item in items:
        arr = _cv2_array_from_source(item)
        retval, decoded_info, _points, _straight = detector.detectAndDecodeMulti(arr)
        if retval:
            payloads.extend(text for text in decoded_info if text)
    return payloads


def _qr_decode_core(payloads):
    '''Pure decode/reassembly logic (no GUI/prompting/history side effects). Returns a list of
    {'content': bytes-or-str, 'filename': str} dicts - one per reconstructed original (chunks of
    one of our envelopes, grouped by session_id, reassembled and reversed through
    content_encoding), plus one per foreign/generic QR payload (raw text, filename='').
    Raises ValueError if a session's chunks are incomplete - no silent partial reconstruction.'''
    ours = {}
    generic = []
    for text in payloads:
        parsed = _parse_envelope(text)
        if parsed is None:
            generic.append(text)
            continue
        ours.setdefault(parsed['session_id'], {})[parsed['seq']] = parsed

    results = []
    for session_id, by_seq in ours.items():
        total = next(iter(by_seq.values()))['total']
        missing = [seq for seq in range(1, total + 1) if seq not in by_seq]
        if missing:
            raise ValueError('qr_decode(): incomplete QR code set for session <{}>: missing '
                             'chunk(s) {} of {}.'.format(session_id, missing, total))
        encoded_text = ''.join(by_seq[seq]['payload_text'] for seq in range(1, total + 1))
        content_encoding = by_seq[1]['content_encoding']
        content = encoded_text if content_encoding == 'utf8' else \
                 _decode_text_to_binary(encoded_text, content_encoding)
        results.append({'content': content, 'filename': by_seq[1]['filename']})

    for text in generic:
        results.append({'content': text, 'filename': ''})
    return results


def qr_decode(**kwargs):
    '''Decode one or more QR-code images back into their original text/binary content, restoring
    the original file name when the images came from qr_encode(input_source_type='file', ...).
    Also supports general-use QR decoding of foreign/generic QR codes (returned as raw text).
    kwargs:
      image_source - a single image path, a list/tuple of image paths or in-memory
        PIL.Image.Image objects, or a folder path (globbed for common image extensions);
        prompts via a GUI multi-file picker if not given
      output_type - 'file' | 'variable' (prompted; defaults to 'file' when the reconstructed
        result carries an embedded filename, else 'variable')
      save_location - destination folder; only used when output_type='file' (prompts via GUI
        if not given)
      output_file_name - override the reconstructed file name; only prompted when needed (a
        single reconstructed result with no embedded filename) - a foreign/generic QR code, or a
        source that wasn't originally a file

    Returns the reconstructed content directly (output_type='variable': a single value, or a
    list if the given images decode to more than one distinct original) or the list of saved
    file paths (output_type='file').
    '''
    ass_var = _check_assignment(function_name='qr_decode')

    image_source = kwargs.get('image_source', None)
    if image_source is None:
        image_source = g_sel_files(title='qr_decode(): select QR code image(s)',
                                   filetypes=IMAGE_FILETYPES)
        if not image_source:
            print('No image(s) selected: qr_decode() cancelled.\n')
            return None
        if 'image_source' not in kwargs:
            _add_kwarg_to_last_command('image_source', list(image_source), fn_name='qr_decode')

    items = _resolve_image_source(image_source)
    payloads = _decode_payloads_from_images(items)
    if not payloads:
        print('qr_decode(): no QR codes could be decoded from the given image(s).\n')
        return None

    results = _qr_decode_core(payloads)
    print('qr_decode(): reconstructed {} item(s) from {} decoded QR code(s).\n'.format(
        len(results), len(payloads)))

    default_output_type = 'file' if any(r['filename'] for r in results) else 'variable'
    output_type = kwargs.get('output_type', None)
    if output_type not in ('file', 'variable'):
        output_type = _prompt_for_list_arg('output_type', ['file', 'variable'],
            default_index=['file', 'variable'].index(default_output_type), fn_name='qr_decode')

    if output_type == 'variable':
        content = [r['content'] for r in results]
        result = content[0] if len(content) == 1 else content
        if ass_var:
            print('Assigning result to variable <{}>.'.format(ass_var))
        return result

    save_location = kwargs.get('save_location', None)
    if save_location is None:
        save_location = g_sel_folder(
            title='qr_decode(): select folder to save reconstructed file(s)')
        if not save_location:
            print('No destination folder selected: qr_decode() cancelled.\n')
            return None
        if 'save_location' not in kwargs:
            _add_kwarg_to_last_command('save_location', _quoted(save_location),
                                       fn_name='qr_decode')

    os.makedirs(save_location, exist_ok=True)
    saved_paths = []
    for index, result_item in enumerate(results, start=1):
        filename = result_item['filename']
        is_text = isinstance(result_item['content'], str)
        if not filename:
            if len(results) == 1:
                filename = kwargs.get('output_file_name', None)
                if filename is None:
                    filename = _kwarg_parse_prompt_str('output_file_name',
                        default_val='qr_decoded.txt' if is_text else 'qr_decoded.bin', **kwargs)
            else:
                filename = 'qr_decoded_{:03d}.{}'.format(index, 'txt' if is_text else 'bin')
        path = os.path.join(save_location, filename)
        if is_text:
            with open(path, 'w', encoding='utf-8') as fil:
                fil.write(result_item['content'])
        else:
            with open(path, 'wb') as fil:
                fil.write(result_item['content'])
        saved_paths.append(path)

    if ass_var:
        print('Assigning list of saved file path(s) to variable <{}>.'.format(ass_var))
    return saved_paths
qr_decode.desc = 'Decode one or more QR-code images back into text/binary content'
