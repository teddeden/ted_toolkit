'''toolkit_gui.session_persistence - GUI-side orchestration for Save Session
/ Restore Session, on top of session_bundle.py's file format and the
bridge's save_session/restore_session RPCs
(tedtoolkit.gui_bridge.rpc_save_session/rpc_restore_session - menu-only,
never imported into ted_toolkit.py, so structurally unreachable from the
plain CLI or help_all()'s listing).

Restore never replays/exec()s a single history line - it seeds the new
tab's terminal display directly from the saved transcript, then (once the
new tab's bridge connects) sends the saved history/variables over the wire
for pure readline.add_history()/namespace-injection, so a restored session
is usable with zero recomputation.
'''

import base64
import datetime
import getpass

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from toolkit_gui import session_bundle

TOOLKIT_VERSION_UNKNOWN = 'unknown'
_RESTORE_CONNECT_WAIT_ATTEMPTS = 40
_RESTORE_CONNECT_WAIT_INTERVAL_MS = 500
_RESTORE_STARTUP_WAIT_ATTEMPTS = 60
_RESTORE_STARTUP_WAIT_INTERVAL_MS = 500


def save_session(parent_widget, tab):
    '''Save `tab`'s session to a user-chosen .tedsession file. Returns True
    on success (even if some variables had to be skipped), False if the user
    canceled or the save failed outright.'''
    path, _filter = QFileDialog.getSaveFileName(
        parent_widget, 'Save Session', '', 'Ted Toolkit Session (*.tedsession)')
    if not path:
        return False
    if not path.lower().endswith('.tedsession'):
        path += '.tedsession'

    try:
        resp = tab.bridge_client.save_session()
    except (ConnectionError, OSError) as exc:
        QMessageBox.critical(parent_widget, 'Save Session',
                              f'Could not reach this session (bridge not connected yet?): {exc}')
        return False
    if not resp.get('ok'):
        error = resp.get('error')
        message = ('A script is currently running in this tab - wait for it to finish '
                   'before saving.' if error == 'script_running' else f'Save failed: {error}')
        QMessageBox.critical(parent_widget, 'Save Session', message)
        return False

    session_bundle.write_bundle(
        path,
        transcript_text=tab.terminal.screen_text_for_save(),
        history_lines=resp['history'],
        variables_pickle_bytes=base64.b64decode(resp['variables_pickle_b64']),
        variables_succeeded=resp['variables_succeeded'],
        variables_failed=resp['variables_failed'],
        toolkit_version=TOOLKIT_VERSION_UNKNOWN,
        saved_at_utc=datetime.datetime.utcnow().isoformat(),
        saved_by=getpass.getuser(),
    )

    if resp['variables_failed']:
        names = ', '.join(item['name'] for item in resp['variables_failed'])
        QMessageBox.warning(
            parent_widget, 'Save Session',
            f'Session saved, but {len(resp["variables_failed"])} variable(s) could not be '
            f'saved and were skipped: {names}')
    return True


def restore_session(main_window, parent_widget):
    '''Restore a previously saved session into a brand-new tab (restore
    never merges into an existing tab). Returns the new tab, or None if the
    user canceled or the file couldn't be read at all.'''
    path, _filter = QFileDialog.getOpenFileName(
        parent_widget, 'Restore Session', '', 'Ted Toolkit Session (*.tedsession)')
    if not path:
        return None

    try:
        bundle = session_bundle.read_bundle(path)
    except session_bundle.BundleError as exc:
        QMessageBox.critical(parent_widget, 'Restore Session', str(exc))
        return None
    if bundle['read_errors']:
        QMessageBox.warning(
            parent_widget, 'Restore Session',
            'Some parts of this session file could not be read and will be skipped:\n'
            + '\n'.join(bundle['read_errors']))

    tab = main_window.new_tab()
    tab.terminal.set_input_blocked(True)
    _wait_for_fresh_prompt_then_restore(tab, bundle, parent_widget, _RESTORE_STARTUP_WAIT_ATTEMPTS)
    return tab


def _wait_for_fresh_prompt_then_restore(tab, bundle, parent_widget, attempts_left):
    '''A brand-new interactive session unconditionally clears its screen
    (os.system('cls')) before printing its own banner and title prompt -
    existing, protected ted_toolkit.py startup behavior that a restore must
    work AROUND, not race: feeding the old transcript before that cls
    happens just gets wiped (confirmed: pyte does not preserve erased
    content in scrollback, matching real terminal semantics). So this waits
    for the fresh session's own "Title for this session" prompt first,
    auto-answers it with a blank Enter (exactly what a user pressing Enter
    there gets - the toolkit's own default title), waits for the resulting
    stable prompt, and only THEN seeds the old transcript and fires the
    actual restore RPC.'''
    if 'Title for this session' in tab.terminal.display_text():
        tab.session.write(b'\r\n')
        # Wait a beat before the first stable-prompt check: checking on the
        # same tick would still see the stale, unanswered "Title for this
        # session: >>>" line, which (being a longer line that happens to
        # also end in ">>>") would satisfy a naive suffix check and fire the
        # restore one full round-trip too early.
        QTimer.singleShot(
            _RESTORE_STARTUP_WAIT_INTERVAL_MS,
            lambda: _wait_for_stable_prompt_then_restore(tab, bundle, parent_widget,
                                                          _RESTORE_STARTUP_WAIT_ATTEMPTS))
        return
    if attempts_left <= 0:
        QMessageBox.critical(parent_widget, 'Restore Session',
                              'Timed out waiting for the new session to start - restore aborted.')
        tab.terminal.set_input_blocked(False)
        return
    QTimer.singleShot(
        _RESTORE_STARTUP_WAIT_INTERVAL_MS,
        lambda: _wait_for_fresh_prompt_then_restore(tab, bundle, parent_widget, attempts_left - 1))


def _wait_for_stable_prompt_then_restore(tab, bundle, parent_widget, attempts_left):
    if _is_bare_prompt_line(tab.terminal.display_text()):
        tab.terminal.feed_text(bundle['transcript_text'])
        variables_pickle_b64 = (
            base64.b64encode(bundle['variables_pickle_bytes']).decode('ascii')
            if bundle['variables_pickle_bytes'] is not None else '')
        _restore_once_connected(tab, bundle['history_lines'], variables_pickle_b64, parent_widget,
                                 _RESTORE_CONNECT_WAIT_ATTEMPTS)
        return
    if attempts_left <= 0:
        QMessageBox.critical(parent_widget, 'Restore Session',
                              'Timed out waiting for the new session to be ready - restore aborted.')
        tab.terminal.set_input_blocked(False)
        return
    QTimer.singleShot(
        _RESTORE_STARTUP_WAIT_INTERVAL_MS,
        lambda: _wait_for_stable_prompt_then_restore(tab, bundle, parent_widget, attempts_left - 1))


def _is_bare_prompt_line(display_text):
    '''True only for a genuine idle ">>> " prompt line with nothing else on
    it - NOT merely a line that happens to end with ">>>", which the
    unanswered "Title for this session: >>>" line also does (that ambiguity
    previously caused the transcript to be fed one round-trip too early,
    landing on the same line as the still-unprocessed title prompt).'''
    non_empty_lines = [line.strip() for line in display_text.split('\n') if line.strip()]
    return bool(non_empty_lines) and non_empty_lines[-1] == '>>>'


def _restore_once_connected(tab, history_lines, variables_pickle_b64, parent_widget, attempts_left):
    if tab.bridge_client.is_connected():
        try:
            resp = tab.bridge_client.restore_session(history_lines, variables_pickle_b64)
        except (ConnectionError, OSError) as exc:
            QMessageBox.critical(parent_widget, 'Restore Session', f'Restore failed: {exc}')
        else:
            if not resp.get('ok'):
                QMessageBox.critical(parent_widget, 'Restore Session',
                                      f"Restore failed: {resp.get('error')}")
            elif resp.get('variables_error'):
                QMessageBox.warning(
                    parent_widget, 'Restore Session',
                    f"History restored, but variables could not be loaded: {resp['variables_error']}")
        tab.terminal.set_input_blocked(False)
        return
    if attempts_left <= 0:
        QMessageBox.critical(parent_widget, 'Restore Session',
                              'Timed out waiting for the new session to start - restore aborted.')
        tab.terminal.set_input_blocked(False)
        return
    QTimer.singleShot(
        _RESTORE_CONNECT_WAIT_INTERVAL_MS,
        lambda: _restore_once_connected(tab, history_lines, variables_pickle_b64, parent_widget,
                                         attempts_left - 1))
