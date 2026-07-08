'''run_regression_tests.py - runs the full pytest regression suite and writes a
Markdown report, including an explicit list of functionality that cannot be
covered by the automated suite (real keystroke capture, GUI dialogs, Excel COM,
clipboard). See regression_test.bat for the normal way to invoke this, and
ABOUT.md for context on why these specific things can't be automated.
'''

import datetime
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
REPORT_DIR = REPO_ROOT / 'test_reports'

KNOWN_UNTESTABLE = [
    ('Real keystroke capture / up-arrow history recall',
     'pyreadline3 hooks the Windows console directly; there is no way to simulate real '
     'keystrokes from a non-interactive test process. Verify by hand: run '
     'start_ted_toolkit.bat, type a command, press Up, confirm it is recalled.'),
    ('tkinter file/folder picker dialogs (g_sel_file, g_sel_file_to_write, g_sel_folder)',
     'One-line wrappers around blocking native dialogs; not unit tested by design '
     '(see ABOUT.md). Verify by hand if changed.'),
    ('tkinter messagebox popups (g_ask_yn, g_ask_okcancel, g_conditional_stop, g_show_*)',
     'Same as above - thin wrappers around blocking native dialogs.'),
    ('Excel COM automation (view_in_excel=True opening a real Excel window)',
     'Requires a real Excel installation and a visible desktop session; not exercised by '
     'the automated suite.'),
    ('Windows clipboard I/O (win_copy / win_paste / win_copy_table / win_paste_table)',
     'Requires a real Windows clipboard and, for paste, pre-populated clipboard content.'),
    ('data_recon() col_select=\'LIST\' with no columns kwarg, or col_mode=\'NAME\'',
     'Known gap, not a test-coverage gap: calls _sel_compare_cols()/_check_convert_text_cols(), '
     'neither of which exist anywhere in the codebase. See ABOUT.md "Known gaps".'),
    ('toolkit_gui: real ConPTY spawn/timing (WinPtyBackend, env_resolve.build_spawn_argv)',
     'Requires actually launching python -i ted_toolkit.py inside a real Windows pseudo-console '
     'and conda activation; the pure argv-construction and pid-resolution logic is unit tested, '
     'but the live spawn itself is not. Verify by hand: open the GUI, confirm a new tab reaches '
     'the interactive prompt.'),
    ('toolkit_gui: TerminalWidget rendering, keystroke forwarding, and arrow-key history recall',
     'Requires a real Qt event loop, a live PtySession, and pyreadline3 running inside the child - '
     'the same fundamental limitation as plain-CLI keystroke capture above, just behind a GUI '
     'widget instead of a raw console. Verify by hand: type a command in a tab, press Up, confirm '
     'it is recalled exactly as it would be in start_ted_toolkit.bat.'),
    ('toolkit_gui: tkinter dialogs launched from a ConPTY-hosted, console-window-less process',
     'save_history()\'s Save-As dialog and any g_ask_*/g_show_* popup still work when triggered '
     'from a GUI tab (confirmed manually during development), but this cannot be asserted '
     'automatically for the same reasons as the plain-CLI tkinter dialogs above.'),
    ('toolkit_gui: Save/Restore Session\'s live process handshake (session_persistence.py)',
     'The .tedsession file format and the bridge RPC handlers are unit tested; the actual '
     'spawn-a-tab / wait-for-fresh-prompt / feed-transcript / restore-over-the-wire sequence '
     'requires a live ConPTY-hosted process and is verified manually. Verify by hand: save a '
     'session with a variable, restore it into a new tab, confirm the variable is usable '
     'without re-running any commands.'),
    ('toolkit_gui: CPU status bar sum and per-tab busy indicator',
     'Depends on real psutil.Process CPU sampling against live spawned processes over multiple '
     'poll ticks; verified manually by running a CPU-heavy command and watching the tab dot and '
     'status bar respond.'),
]


def run_pytest():
    REPORT_DIR.mkdir(exist_ok=True)
    junit_path = REPORT_DIR / '_last_run_junit.xml'
    log_path = REPORT_DIR / '_last_run_log.txt'

    cmd = [sys.executable, '-m', 'pytest', 'tests/', '-v',
           '--junitxml=' + str(junit_path)]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)

    log_path.write_text(proc.stdout + '\n' + proc.stderr, encoding='utf-8')
    return proc.returncode, junit_path, log_path


def parse_junit(junit_path):
    tree = ET.parse(junit_path)
    root = tree.getroot()
    # pytest's junitxml root is <testsuites><testsuite ...>
    suite = root.find('testsuite') if root.tag == 'testsuites' else root
    summary = {
        'tests': int(suite.get('tests', 0)),
        'failures': int(suite.get('failures', 0)),
        'errors': int(suite.get('errors', 0)),
        'skipped': int(suite.get('skipped', 0)),
        'time': float(suite.get('time', 0)),
    }
    failed_cases = []
    for case in suite.findall('testcase'):
        failure = case.find('failure')
        error = case.find('error')
        if failure is not None or error is not None:
            node = failure if failure is not None else error
            failed_cases.append({
                'name': '{}::{}'.format(case.get('classname', ''), case.get('name', '')),
                'message': (node.get('message') or '').strip().splitlines()[0]
                           if node.get('message') else '(no message)',
            })
    return summary, failed_cases


def _find_git():
    import shutil
    found = shutil.which('git')
    if found:
        return found
    for candidate in (r'C:\Program Files\Git\bin\git.exe', r'C:\Program Files\Git\cmd\git.exe'):
        if Path(candidate).exists():
            return candidate
    return None


def get_git_info():
    git_exe = _find_git()

    def _run(args):
        if git_exe is None:
            return 'unknown'
        try:
            return subprocess.run([git_exe] + args, cwd=REPO_ROOT, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except Exception:
            return 'unknown'
    return _run(['rev-parse', '--abbrev-ref', 'HEAD']), _run(['rev-parse', '--short', 'HEAD'])


def build_report(summary, failed_cases, returncode):
    branch, commit = get_git_info()
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []
    lines.append('# Regression Test Report')
    lines.append('')
    lines.append('Generated: {}'.format(timestamp))
    lines.append('Git branch: `{}` @ `{}`'.format(branch, commit))
    lines.append('Python: {}'.format(sys.version.split()[0]))
    lines.append('')
    lines.append('## Automated Suite Result')
    lines.append('')
    status = 'PASSED' if returncode == 0 else 'FAILED'
    lines.append('**Overall: {}**'.format(status))
    lines.append('')
    lines.append('| Metric | Count |')
    lines.append('|---|---|')
    lines.append('| Tests run | {} |'.format(summary['tests']))
    lines.append('| Failures | {} |'.format(summary['failures']))
    lines.append('| Errors | {} |'.format(summary['errors']))
    lines.append('| Skipped | {} |'.format(summary['skipped']))
    lines.append('| Duration (s) | {:.2f} |'.format(summary['time']))
    lines.append('')
    if failed_cases:
        lines.append('### Failed / Errored Tests')
        lines.append('')
        for case in failed_cases:
            lines.append('- `{}` - {}'.format(case['name'], case['message']))
        lines.append('')
    else:
        lines.append('No failures or errors.')
        lines.append('')
    lines.append('## Functionality NOT Covered By This Automated Run')
    lines.append('')
    lines.append('The automated suite above only covers what can be exercised from a plain, '
                  'non-interactive Python process. The following require manual verification '
                  'and are NOT reflected in the pass/fail counts above:')
    lines.append('')
    for name, note in KNOWN_UNTESTABLE:
        lines.append('- **{}**: {}'.format(name, note))
    lines.append('')
    lines.append('If you changed any code related to the items above, verify them by hand '
                 'before merging - a green automated run does not cover them.')
    lines.append('')
    return '\n'.join(lines)


def main():
    returncode, junit_path, log_path = run_pytest()
    summary, failed_cases = parse_junit(junit_path)
    report_text = build_report(summary, failed_cases, returncode)

    report_path = REPORT_DIR / 'regression_report_{}.md'.format(
        datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    report_path.write_text(report_text, encoding='utf-8')
    latest_path = REPORT_DIR / 'regression_report_latest.md'
    latest_path.write_text(report_text, encoding='utf-8')

    print(report_text)
    print('\nFull pytest log: {}'.format(log_path))
    print('Report saved to: {}'.format(report_path))
    print('Latest report also at: {}'.format(latest_path))

    return returncode


if __name__ == '__main__':
    sys.exit(main())
