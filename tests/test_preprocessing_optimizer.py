import numpy as np
import pandas as pd
import pytest

from src.preprocessing import (validate_prices, PriceValidationError, simple_returns,
                               annualized_estimates, align_risk_free)
from src.optimization import (training_returns, optimize_estimates, regularize_covariance,
                              filter_weights, concentration, signal_risk_free, OptimizationError)
from src.universe import DataQualityError


def test_price_coverage_reference_and_missing(config, synthetic_prices):
    selected = pd.DataFrame({'original_ticker': ['AAA', 'BBB']})
    prices, report = validate_prices(synthetic_prices, selected, config)
    assert report.complete_2011_2025.all()
    returns = simple_returns(prices)
    assert returns.index[0] == pd.Timestamp('2005-01-03')
    assert returns.iloc[0, 0] == pytest.approx(prices.iloc[1, 0] / prices.iloc[0, 0] - 1)
    for bad in [np.nan, np.inf, 0, -1]:
        broken = synthetic_prices.copy()
        broken.loc['2014-03-03', 'AAA'] = bad
        with pytest.raises(PriceValidationError) as error:
            validate_prices(broken, selected, config)
        assert error.value.report.set_index('original_ticker').loc['AAA', 'status'] == 'failed'
    with pytest.raises(PriceValidationError):
        validate_prices(synthetic_prices.iloc[1:], selected, config)
    with pytest.raises(PriceValidationError):
        validate_prices(synthetic_prices.loc[:'2024-12-31'], selected, config)


def test_annualization_sample_convention():
    returns = pd.DataFrame({'A': [0.01, -0.02, 0.03]}, index=pd.date_range('2020-01-01', periods=3))
    mean, covariance, volatility = annualized_estimates(returns)
    assert mean.A == pytest.approx(np.mean(returns.A) * 252)
    assert covariance.loc['A', 'A'] == pytest.approx(np.var(returns.A, ddof=1) * 252)
    assert volatility.A == pytest.approx(np.std(returns.A, ddof=1) * np.sqrt(252))


def test_exact_windows_and_future_independence(config, synthetic_prices):
    initial, initial_log = training_returns(synthetic_prices, '2010-12-31', config, initial=True)
    assert initial.index[0] == pd.Timestamp('2005-01-03')
    assert initial.index[-1] == pd.Timestamp('2010-12-31')
    rolling, log = training_returns(synthetic_prices, '2011-01-31', config)
    assert log['window_lower_bound'] == '2006-01-31'
    assert log['price_start'] == '2006-02-01'
    assert rolling.index[0] == pd.Timestamp('2006-02-02')
    assert initial_log['initial_reference_only']
    changed = synthetic_prices.copy()
    changed.loc[changed.index > '2011-01-31'] *= 100
    changed.loc['2006-01-31'] *= 10
    again, _ = training_returns(changed, '2011-01-31', config)
    pd.testing.assert_frame_equal(rolling, again)


def test_fred_lag_holiday_past_only(config):
    raw = pd.Series([4., 5., 99.], index=pd.to_datetime(['2024-07-02', '2024-07-03', '2024-07-05']))
    sessions = pd.to_datetime(['2024-07-03', '2024-07-05'])
    aligned = align_risk_free(raw, sessions, config)
    assert aligned.loc['2024-07-03', 'annual_rate'] == 0.04
    assert aligned.loc['2024-07-05', 'annual_rate'] == 0.05
    assert aligned.loc['2024-07-05', 'available_date'] == pd.Timestamp('2024-07-05')
    assert aligned.loc['2024-07-05', 'daily_rate'] == pytest.approx(1.05 ** (1 / 252) - 1)
    rate, _ = signal_risk_free(aligned, pd.Timestamp('2024-07-05'), config)
    assert rate == 0.05
    corrupted = aligned.copy()
    corrupted.loc['2024-07-05', 'available_date'] = pd.Timestamp('2024-07-08')
    with pytest.raises(DataQualityError):
        signal_risk_free(corrupted, pd.Timestamp('2024-07-05'), config)
    with pytest.raises(DataQualityError):
        align_risk_free(raw.iloc[1:], pd.to_datetime(['2024-07-03']), config)


def test_positive_excess_analytic_solution(config):
    mean = pd.Series([0.12, 0.08], index=['A', 'B'])
    covariance = pd.DataFrame(np.diag([0.04, 0.09]), index=mean.index, columns=mean.index)
    ids = pd.Series(['A', 'B'], index=mean.index)
    result = optimize_estimates(mean, covariance, 0.02, ids, config)
    expected = (mean - 0.02) / np.diag(covariance)
    expected /= expected.sum()
    np.testing.assert_allclose(result.weights, expected, atol=1e-5, rtol=0)
    assert result.diagnostics['optimizer_status'] == 'optimal'
    assert result.weights.sum() == pytest.approx(1)


def test_nonpositive_contingency_tie_and_invalid_volatility(config):
    mean = pd.Series([0.01, 0.01], index=['A', 'B'])
    covariance = pd.DataFrame(np.diag([0.04, 0.09]), index=mean.index, columns=mean.index)
    ids = pd.Series(['Z', 'A'], index=mean.index)
    with pytest.warns(UserWarning, match='not guaranteed'):
        result = optimize_estimates(mean, covariance, 0.02, ids, config)
    assert result.weights.B == 1 and result.weights.A == 0
    assert result.diagnostics['optimizer_status'] == 'nonpositive_excess_fallback'
    covariance.loc['B', 'B'] = 0
    with pytest.raises(OptimizationError):
        optimize_estimates(mean, covariance, 0.02, ids, config)


def test_covariance_repair_and_filter_boundary():
    matrix = pd.DataFrame([[1., 2.], [2., 1.]], index=['A', 'B'], columns=['A', 'B'])
    repaired, log = regularize_covariance(matrix, 1e-10)
    assert log['clipped_eigenvalues'] == 1
    assert np.linalg.eigvalsh(repaired).min() > 0
    weights = pd.Series([0.0001, 0.00009, 0.99981], index=['A', 'B', 'C'])
    filtered = filter_weights(weights)
    assert filtered.A > 0 and filtered.B == 0
    assert filtered.sum() == pytest.approx(1)
    report = concentration(filtered)
    assert report['holdings_count'] == 2
    assert report['hhi'] == pytest.approx((filtered ** 2).sum())
    assert report['largest_weight'] == filtered.max()


def test_solver_failure_does_not_make_equal_weights(config, monkeypatch):
    import cvxpy as cp
    mean = pd.Series([0.1], index=['A'])
    covariance = pd.DataFrame([[0.04]], index=['A'], columns=['A'])
    monkeypatch.setattr(cp, 'installed_solvers', lambda: [])
    with pytest.raises(OptimizationError, match='unavailable'):
        optimize_estimates(mean, covariance, 0, pd.Series(['A'], index=['A']), config)
