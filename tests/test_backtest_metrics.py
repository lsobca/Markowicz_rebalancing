from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.backtest import run_backtest, STRATEGIES
from src.preprocessing import PreparedData, align_risk_free, simple_returns
from src.metrics import calculate_metrics, performance, drawdown_curve, trading_metrics


def test_five_accounts_timing_and_subperiods(config, synthetic_prices, monkeypatch):
    import src.backtest as engine
    config['rf_mode'] = 'zero-sensitivity'
    returns = simple_returns(synthetic_prices)
    with pytest.warns(UserWarning):
        rf = align_risk_free(None, returns.index, config)
    data = PreparedData(synthetic_prices, returns, rf, pd.DataFrame(),
                        {'universe_mode': 'current_survivors_only',
                         'bias_label': 'illustrative survivors-only', 'rf_mode': 'zero-sensitivity'})
    calls = []
    def target(data, date, ids, config, initial=False):
        date = pd.Timestamp(date)
        calls.append((date, initial))
        weights = pd.Series([1., 0.] if initial else [0., 1.], index=synthetic_prices.columns)
        return SimpleNamespace(weights=weights, diagnostics={
            'signal_date': date.date().isoformat(), 'initial': initial,
            'holdings_count': 1, 'largest_weight': 1., 'hhi': 1.,
            'optimizer_status': 'synthetic_test_stub', 'clipped_eigenvalues': 0})
    monkeypatch.setattr(engine, 'optimize_signal', target)
    ids = pd.Series(synthetic_prices.columns, index=synthetic_prices.columns)
    result = run_backtest(data, ids, config)
    assert sum(initial for _, initial in calls) == 1
    opening = result.portfolio_values[result.portfolio_values.date == pd.Timestamp('2011-01-03')]
    assert len(opening) == 5 and opening.portfolio_value.nunique() == 1
    assert opening.portfolio_value.iloc[0] == pytest.approx(10000 / 1.001, abs=1e-8)
    assert (result.portfolio_values.cash >= 0).all()
    monthly = result.weight_history[result.weight_history.strategy == 'monthly']
    # New target is not applied on the signal close.
    assert monthly[(monthly.date == pd.Timestamp('2011-01-31')) & (monthly.asset == 'BBB')].shares.iloc[0] == 0
    assert monthly[(monthly.date == pd.Timestamp('2011-02-01')) & (monthly.asset == 'BBB')].shares.iloc[0] > 0
    buy_hold = result.weight_history[result.weight_history.strategy == 'buy_and_hold']
    assert (buy_hold.groupby('asset').shares.nunique() == 1).all()
    assert not ((result.events.strategy == 'buy_and_hold') & ~result.events.is_initial).any()
    assert (result.trades.execution_date > result.trades.signal_date).all()
    assert result.trades.execution_date.max() <= pd.Timestamp('2025-12-31')
    metrics = calculate_metrics(result, rf, config)
    assert len(metrics.portfolio_metrics) == 5 and len(metrics.subperiod_metrics) == 15
    for strategy in STRATEGIES:
        values = result.portfolio_values[result.portfolio_values.strategy == strategy].set_index('date')
        full = metrics.portfolio_metrics.set_index('strategy').loc[strategy]
        assert full.opening_wealth == 10000
        assert full.total_net_return == pytest.approx(values.portfolio_value.iloc[-1] / 10000 - 1)
        assert full.total_trading_fees == pytest.approx(values.fees_cumulative.iloc[-1], abs=1e-8)
        for period, baseline in [('2016-2020', '2015-12-31'), ('2021-2025', '2020-12-31')]:
            row = metrics.subperiod_metrics[(metrics.subperiod_metrics.strategy == strategy)
                                            & (metrics.subperiod_metrics.period == period)].iloc[0]
            assert row.opening_date == pd.Timestamp(baseline)
            assert row.opening_wealth == values.loc[baseline, 'portfolio_value']


def test_initial_loss_and_later_opening_mark():
    dates = pd.to_datetime(['2011-01-03', '2011-01-04', '2011-01-05'])
    wealth = pd.Series([9990., 10000., 9900.], index=dates)
    rf = pd.DataFrame({'daily_rate': 0.}, index=dates)
    report = performance(wealth, 10000, dates[0], rf, initial_period=True)
    assert report['daily_return_observations'] == 2
    assert report['total_net_return'] == pytest.approx(-0.01)
    assert drawdown_curve(wealth, 10000).iloc[0] == pytest.approx(-0.001)
    later_dates = pd.to_datetime(['2016-01-04', '2016-01-05', '2016-01-06'])
    later = pd.Series([90., 95., 92.], index=later_dates)
    later_rf = pd.DataFrame({'daily_rate': 0.}, index=later_dates)
    report = performance(later, 100, pd.Timestamp('2015-12-31'), later_rf, initial_period=False)
    assert report['daily_return_observations'] == 3
    assert report['maximum_drawdown'] == pytest.approx(0.1)
    assert report['annualized_volatility'] == pytest.approx(np.std([-0.1, 95/90-1, 92/95-1], ddof=1)*np.sqrt(252))


def test_strict_material_threshold():
    dates = pd.to_datetime(['2020-01-02', '2020-02-03', '2020-03-02'])
    turnover = np.array([0.000099, 0.0001, 0.000101])
    events = pd.DataFrame({'strategy': 'monthly', 'execution_date': dates,
                           'is_initial': False, 'pre_trade_wealth': 10000.,
                           'gross_two_sided_turnover': turnover,
                           'gross_notional': turnover * 10000,
                           'fees': turnover * 10})
    schedule = events[['strategy', 'execution_date', 'is_initial']].copy()
    schedule['within_sample'] = True
    trades = events.rename(columns={'fees': 'fee'})
    result = SimpleNamespace(events=events, schedule=schedule, trades=trades)
    metrics = trading_metrics(result, 'monthly', dates[0], dates[-1])
    assert metrics['scheduled_rebalance_count'] == 3
    assert metrics['any_trade_rebalance_count'] == 3
    assert metrics['material_rebalance_count'] == 1
    assert metrics['total_trading_fees'] == pytest.approx(sum(turnover) * 10)


def test_undefined_sharpe():
    dates = pd.date_range('2020-01-01', periods=3)
    wealth = pd.Series(100., index=dates)
    rf = pd.DataFrame({'daily_rate': 0.}, index=dates)
    metrics = performance(wealth, 100, dates[0], rf, initial_period=True)
    assert np.isnan(metrics['realized_sharpe'])
    assert metrics['sharpe_status'] == 'undefined_zero_excess_volatility'
