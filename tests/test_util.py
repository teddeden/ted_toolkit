'''Tests for tedtoolkit.util: elapsed(), timer_start()/timer_elapsed() and their
shared timedelta formatting.'''

import datetime

import pytest

from tedtoolkit import util


class _FrozenDatetime(datetime.datetime):
    '''datetime subclass whose now() returns a controllable instant.'''
    current = datetime.datetime(2026, 1, 1, 12, 0, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.current


@pytest.fixture
def frozen_now(monkeypatch):
    '''Freeze util's view of datetime.datetime.now(); returns a setter.'''
    monkeypatch.setattr(util.datetime, 'datetime', _FrozenDatetime)
    monkeypatch.setattr(util, 'TIMER_START', util.TIMER_START)
    monkeypatch.setattr(util, 'START_TIME', util.START_TIME)

    def _set(value):
        _FrozenDatetime.current = value
    return _set


def test_format_timedelta_drops_microseconds():
    assert util._format_timedelta(datetime.timedelta(seconds=5, microseconds=123456)) == '0:00:05'


def test_format_timedelta_whole_seconds_not_truncated():
    # Regression: str(delta)[:str(delta).find('.')] chopped the last char when microseconds == 0
    assert util._format_timedelta(datetime.timedelta(seconds=5)) == '0:00:05'


def test_format_timedelta_multi_day():
    assert util._format_timedelta(datetime.timedelta(days=2, hours=3, microseconds=1)) == '2 days, 3:00:00'


def test_elapsed_whole_seconds(frozen_now):
    frozen_now(datetime.datetime(2026, 1, 1, 12, 0, 0))
    util.START_TIME = datetime.datetime(2026, 1, 1, 11, 58, 55)
    assert util.elapsed() == '0:01:05'


def test_timer_start_resets_timer_and_prints(frozen_now, capsys):
    start = datetime.datetime(2026, 1, 1, 12, 0, 0, 250000)
    frozen_now(start)
    util.timer_start()
    assert util.TIMER_START == start
    assert 'Timer start at 2026-01-01 12:00:00.250000' in capsys.readouterr().out


def test_timer_elapsed_number_and_string(frozen_now):
    frozen_now(datetime.datetime(2026, 1, 1, 12, 0, 0))
    util.timer_start()
    frozen_now(datetime.datetime(2026, 1, 1, 12, 1, 2, 500000))
    assert util.timer_elapsed() == 62.5
    assert util.timer_elapsed(output_format='number') == 62.5
    assert util.timer_elapsed(output_format='string') == '0:01:02'


def test_timer_elapsed_independent_of_elapsed(frozen_now):
    util.START_TIME = datetime.datetime(2026, 1, 1, 10, 0, 0)
    frozen_now(datetime.datetime(2026, 1, 1, 12, 0, 0))
    util.timer_start()
    frozen_now(datetime.datetime(2026, 1, 1, 12, 0, 10))
    assert util.timer_elapsed() == 10.0
    assert util.elapsed() == '2:00:10'


def test_timer_elapsed_rejects_unknown_format():
    with pytest.raises(ValueError, match='output_format'):
        util.timer_elapsed(output_format='hours')


def test_desc_attributes_are_distinct():
    # Regression: timer_elapsed's desc was mistakenly assigned to elapsed.desc
    assert util.elapsed.desc == 'Returns time (str) since start'
    assert util.timer_start.desc
    assert util.timer_elapsed.desc
    assert util.timer_elapsed.desc != util.elapsed.desc
