import numpy as np
import pandas as pd
import pytest
import exchange_calendars as xcals

from src.backtest import execute_target, build_schedule, AccountingError


def test_initial_fee_and_cash_use():
    prices = pd.Series([100., 50.], index=['A', 'B'])
    weights = pd.Series([0.6, 0.4], index=prices.index)
    executions = [execute_target(weights * 0, 10000, prices, weights, 0.001) for _ in range(5)]
    for execution in executions:
        assert execution.gross_notional == pytest.approx(10000 / 1.001, abs=1e-8)
        assert execution.fees.sum() == pytest.approx(execution.gross_notional * 0.001)
        assert execution.cash >= 0
        assert execution.post_trade_wealth + execution.fees.sum() == pytest.approx(10000, abs=1e-8)
        pd.testing.assert_series_equal(execution.shares, executions[0].shares)


def test_sell_buy_fees_and_small_orders():
    prices = pd.Series([1., 1.], index=['A', 'B'])
    shares = pd.Series([5000., 5000.], index=prices.index)
    target = pd.Series([0.50000001, 0.49999999], index=prices.index)
    execution = execute_target(shares, 0, prices, target, 0.001)
    assert 0 < execution.turnover < 0.0001
    assert execution.fees.sum() > 0
    assert execution.signed_notionals.min() < 0 < execution.signed_notionals.max()
    assert execution.fees.sum() == pytest.approx(execution.gross_notional * 0.001)
    assert execution.post_trade_wealth + execution.fees.sum() == pytest.approx(10000, abs=1e-8)


def test_no_trade_and_zero_fee():
    prices = pd.Series([1., 1.])
    shares = pd.Series([5000., 5000.])
    same = execute_target(shares, 0, prices, pd.Series([0.5, 0.5]), 0.001)
    assert same.gross_notional == same.fees.sum() == 0
    changed = execute_target(shares, 0, prices, pd.Series([0.25, 0.75]), 0)
    assert changed.post_trade_wealth == 10000
    assert changed.fees.sum() == 0
    assert changed.gross_notional == 5000


def test_negative_cash_rejected():
    with pytest.raises(AccountingError):
        execute_target(pd.Series([1.]), -1, pd.Series([1.]), pd.Series([1.]), 0.001)


def test_closures_and_first_events(config):
    calendar = xcals.get_calendar('XNYS', start='2004-12-01', end='2026-12-31')
    for date in ['2012-10-29', '2012-10-30', '2018-12-05', '2025-01-09']:
        assert not calendar.is_session(date)
    assert calendar.is_session('2005-01-03')
    schedule = build_schedule(config)
    expected = {'monthly': ('2011-01-31', '2011-02-01'),
                'quarterly': ('2011-03-31', '2011-04-01'),
                'semiannual': ('2011-06-30', '2011-07-01'),
                'annual': ('2011-12-30', '2012-01-03')}
    assert len(schedule[schedule.is_initial]) == 5
    assert len(schedule[(schedule.strategy == 'buy_and_hold') & ~schedule.is_initial]) == 0
    for strategy, dates in expected.items():
        rows = schedule[(schedule.strategy == strategy) & ~schedule.is_initial]
        first = rows.iloc[0]
        assert first.signal_date == pd.Timestamp(dates[0])
        assert first.execution_date == pd.Timestamp(dates[1])
        final = rows.iloc[-1]
        assert not final.within_sample
        assert final.execution_date.year == 2026
    assert (schedule.execution_date > schedule.signal_date).all()
    for row in schedule.itertuples():
        assert pd.Timestamp(calendar.next_session(row.signal_date)).tz_localize(None) == row.execution_date
