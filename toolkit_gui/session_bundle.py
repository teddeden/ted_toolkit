'''toolkit_gui.session_bundle - the .tedsession zip bundle format for
Save Session / Restore Session.

A zip (not a single pickle-of-everything) so a corrupt/unreadable member
never destroys the rest: pickle is a sequential stream, so if one embedded
object failed to unpickle, the decoder would have no way to skip past it and
recover the transcript/history that came after it in the same stream. A
zip's central directory makes each member independently readable.

Bundle layout:
    manifest.json   - format/version metadata, save stats, failure list
    transcript.txt  - GUI-side: plain-text scrollback dump
    history.json    - bridge-side: canonical list[str] of raw history lines
    history.py      - bridge-side: human-readable copy (matches
                       save_history()'s own header template)
    variables.pkl   - bridge-side: pickle.dumps() of one {name: value} dict
'''

import json
import zipfile

FORMAT_VERSION = 1


class BundleError(Exception):
    '''Raised for a corrupted/unreadable/incompatible .tedsession file -
    specifically for problems bad enough that nothing in the bundle can be
    safely interpreted (not a valid zip, or missing/unsupported manifest).'''


def write_bundle(path, *, transcript_text, history_lines, variables_pickle_bytes,
                  variables_succeeded, variables_failed, toolkit_version, saved_at_utc, saved_by):
    manifest = {
        'format_version': FORMAT_VERSION,
        'toolkit_version': toolkit_version,
        'saved_at_utc': saved_at_utc,
        'saved_by': saved_by,
        'variables': {'succeeded': variables_succeeded, 'failed': variables_failed},
    }
    history_py = _render_history_py(history_lines, toolkit_version, saved_by, saved_at_utc)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('manifest.json', json.dumps(manifest, indent=2))
        zip_file.writestr('transcript.txt', transcript_text)
        zip_file.writestr('history.json', json.dumps(history_lines))
        zip_file.writestr('history.py', history_py)
        zip_file.writestr('variables.pkl', variables_pickle_bytes)


def read_bundle(path):
    '''Read a .tedsession bundle. Returns a dict with whatever members were
    readable; per-member read failures are collected into 'read_errors'
    rather than aborting the whole read (e.g. a corrupt variables.pkl still
    allows the transcript/history to be restored). Raises BundleError only
    when the file itself isn't a valid zip, or manifest.json/format_version
    is missing/unsupported - those are needed to safely interpret anything
    else in the archive.'''
    try:
        zip_file = zipfile.ZipFile(path, 'r')
    except (zipfile.BadZipFile, OSError) as exc:
        raise BundleError(f'Not a valid .tedsession file: {exc}') from exc
    with zip_file:
        bad_member = zip_file.testzip()
        try:
            manifest = json.loads(zip_file.read('manifest.json'))
        except (KeyError, json.JSONDecodeError) as exc:
            raise BundleError(f'Missing or corrupt manifest.json: {exc}') from exc
        if manifest.get('format_version') != FORMAT_VERSION:
            raise BundleError(
                f"Unsupported .tedsession format_version: {manifest.get('format_version')!r}")
        result = {
            'manifest': manifest,
            'transcript_text': '',
            'history_lines': [],
            'variables_pickle_bytes': None,
            'read_errors': [],
        }
        if bad_member:
            result['read_errors'].append(f'Corrupt member in archive: {bad_member}')
        try:
            result['transcript_text'] = zip_file.read('transcript.txt').decode('utf-8')
        except (KeyError, UnicodeDecodeError) as exc:
            result['read_errors'].append(f'Could not read transcript.txt: {exc}')
        try:
            result['history_lines'] = json.loads(zip_file.read('history.json'))
        except (KeyError, json.JSONDecodeError) as exc:
            result['read_errors'].append(f'Could not read history.json: {exc}')
        try:
            result['variables_pickle_bytes'] = zip_file.read('variables.pkl')
        except KeyError as exc:
            result['read_errors'].append(f'Could not read variables.pkl: {exc}')
        return result


def _render_history_py(history_lines, toolkit_version, saved_by, saved_at_utc):
    header = (f'# TED_TOOLKIT-based (v{toolkit_version}) session, '
              f'autogen by {saved_by} at UTC:{saved_at_utc}\n\n')
    return header + '\n'.join(history_lines) + '\n'
