'''Tests for toolkit_gui.session_bundle's .tedsession zip format - the
pure, testable core of Save/Restore Session (the bridge RPC handlers this
builds on, rpc_save_session/rpc_restore_session, are already covered by
tests/test_gui_bridge.py; this file covers only the GUI-side file format).
'''

import zipfile

import pytest

from toolkit_gui import session_bundle


def _write_sample(path):
    session_bundle.write_bundle(
        path,
        transcript_text='>>> x = 1\n',
        history_lines=['x = 1', 'y = 2'],
        variables_pickle_bytes=b'\x80\x04fake-pickle-bytes',
        variables_succeeded=['x', 'y'],
        variables_failed=[],
        toolkit_version='0.72',
        saved_at_utc='2026-07-08T00:00:00',
        saved_by='theo',
    )


def test_round_trip(tmp_path):
    path = tmp_path / 'session.tedsession'
    _write_sample(path)
    bundle = session_bundle.read_bundle(path)
    assert bundle['transcript_text'] == '>>> x = 1\n'
    assert bundle['history_lines'] == ['x = 1', 'y = 2']
    assert bundle['variables_pickle_bytes'] == b'\x80\x04fake-pickle-bytes'
    assert bundle['manifest']['toolkit_version'] == '0.72'
    assert bundle['manifest']['format_version'] == session_bundle.FORMAT_VERSION
    assert bundle['read_errors'] == []


def test_history_py_member_is_human_readable(tmp_path):
    path = tmp_path / 'session.tedsession'
    _write_sample(path)
    with zipfile.ZipFile(path) as zip_file:
        history_py = zip_file.read('history.py').decode('utf-8')
    assert 'TED_TOOLKIT-based (v0.72) session' in history_py
    assert 'x = 1' in history_py
    assert 'y = 2' in history_py


def test_manifest_records_failed_variables(tmp_path):
    path = tmp_path / 'session.tedsession'
    session_bundle.write_bundle(
        path, transcript_text='', history_lines=[], variables_pickle_bytes=b'',
        variables_succeeded=['a'],
        variables_failed=[{'name': 'mymod', 'type': 'module', 'reason': 'cannot pickle'}],
        toolkit_version='0.72', saved_at_utc='now', saved_by='theo',
    )
    bundle = session_bundle.read_bundle(path)
    assert bundle['manifest']['variables']['failed'] == [
        {'name': 'mymod', 'type': 'module', 'reason': 'cannot pickle'}]


def test_rejects_non_zip_file(tmp_path):
    path = tmp_path / 'not_a_zip.tedsession'
    path.write_text('this is not a zip file')
    with pytest.raises(session_bundle.BundleError):
        session_bundle.read_bundle(path)


def test_rejects_missing_manifest(tmp_path):
    path = tmp_path / 'no_manifest.tedsession'
    with zipfile.ZipFile(path, 'w') as zip_file:
        zip_file.writestr('transcript.txt', 'hello')
    with pytest.raises(session_bundle.BundleError):
        session_bundle.read_bundle(path)


def test_rejects_unsupported_format_version(tmp_path):
    path = tmp_path / 'future.tedsession'
    with zipfile.ZipFile(path, 'w') as zip_file:
        zip_file.writestr('manifest.json', '{"format_version": 999}')
    with pytest.raises(session_bundle.BundleError):
        session_bundle.read_bundle(path)


def test_degraded_read_when_variables_pkl_missing(tmp_path):
    '''A corrupt/missing variables.pkl must not prevent restoring the
    transcript and history - the whole point of using a zip instead of one
    pickle-of-everything.'''
    path = tmp_path / 'no_vars.tedsession'
    with zipfile.ZipFile(path, 'w') as zip_file:
        zip_file.writestr('manifest.json', f'{{"format_version": {session_bundle.FORMAT_VERSION}}}')
        zip_file.writestr('transcript.txt', 'some transcript')
        zip_file.writestr('history.json', '["a = 1"]')
    bundle = session_bundle.read_bundle(path)
    assert bundle['transcript_text'] == 'some transcript'
    assert bundle['history_lines'] == ['a = 1']
    assert bundle['variables_pickle_bytes'] is None
    assert len(bundle['read_errors']) == 1
