"""Phase 6: descriptive metrics, explicit opening marks and optional CSV export.

No inference of statistical superiority, no downloads and no import-time I/O.
Returns/volatility exclude a synthetic initial fee return; wealth and drawdown
include the initial fee against the external capital baseline.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import BacktestResult, STRATEGIES
from .preprocessing import daily_index, session_grid
from .universe import DataQualityError


@dataclass
class MetricsResult:
    portfolio_metrics: pd.DataFrame
    subperiod_metrics: pd.DataFrame
    drawdowns: pd.DataFrame


def wealth_matrix(result: BacktestResult) -> pd.DataFrame:
    values = result.portfolio_values
    if values.duplicated(["date", "strategy"]).any() or set(values.strategy) != set(STRATEGIES):
        raise DataQualityError("Expected unique dates for exactly five strategies")
    matrix = values.pivot(index="date", columns="strategy", values="portfolio_value").sort_index()
    daily_index(matrix.index, "portfolio dates")
    matrix = matrix.loc[:, list(STRATEGIES)]
    if matrix.empty or not np.isfinite(matrix.to_numpy()).all() or (matrix <= 0).any().any():
        raise DataQualityError("Missing/nonpositive portfolio wealth; no filling is allowed")
    return matrix


def drawdown_curve(wealth: pd.Series, opening_wealth: float) -> pd.Series:
    daily_index(wealth.index, "drawdown dates")
    if (wealth.empty or not wealth.index.is_monotonic_increasing
            or not np.isfinite(opening_wealth) or opening_wealth <= 0
            or not np.isfinite(wealth.to_numpy()).all() or (wealth <= 0).any()):
        raise DataQualityError("Invalid drawdown wealth or baseline")
    peak = np.maximum.accumulate(np.r_[opening_wealth, wealth.to_numpy()])[1:]
    return pd.Series(wealth.to_numpy() / peak - 1, index=wealth.index, name="drawdown")


def performance(wealth: pd.Series, opening_wealth: float, opening_date: pd.Timestamp,
                risk_free: pd.DataFrame, *, initial_period: bool) -> dict:
    """Later periods prepend the previous-year close for returns and drawdown.

    For the initial period, the opening mark is external cash on the SAME close
    as the first purchase: it is included in net return but not as a daily return.
    """
    drawdown = drawdown_curve(wealth, opening_wealth)
    if initial_period:
        if opening_date != wealth.index[0]:
            raise DataQualityError("Initial time origin must equal the first execution close")
        returns = wealth.pct_change(fill_method=None).iloc[1:]
    else:
        if opening_date >= wealth.index[0]:
            raise DataQualityError("Subperiod opening mark must precede its first session")
        with_opening = pd.concat([pd.Series([opening_wealth], index=[opening_date]), wealth])
        returns = with_opening.pct_change(fill_method=None).iloc[1:]
    if len(returns) < 2 or not np.isfinite(returns.to_numpy()).all():
        raise DataQualityError("Insufficient/invalid daily portfolio returns")
    daily_index(risk_free.index, "metric risk-free dates")
    rf = risk_free["daily_rate"].reindex(returns.index)
    if not np.isfinite(rf.to_numpy()).all():
        raise DataQualityError("Missing daily risk-free rates; no implicit fallback")
    excess = returns - rf
    volatility = float(returns.std(ddof=1) * np.sqrt(252))
    excess_std = float(excess.std(ddof=1))
    sharpe = float(excess.mean() / excess_std * np.sqrt(252)) if excess_std > 0 else np.nan
    years = (wealth.index[-1] - opening_date).days / 365.25
    if years <= 0:
        raise DataQualityError("CAGR requires positive elapsed calendar time")
    terminal = float(wealth.iloc[-1])
    return {
        "opening_date": opening_date, "opening_wealth": opening_wealth,
        "ending_date": wealth.index[-1], "terminal_value": terminal,
        "total_net_return": terminal / opening_wealth - 1,
        "cagr": (terminal / opening_wealth) ** (1 / years) - 1,
        "annualized_volatility": volatility, "realized_sharpe": sharpe,
        "sharpe_status": "defined" if excess_std > 0 else "undefined_zero_excess_volatility",
        "maximum_drawdown": float(-drawdown.min()),
        "daily_return_observations": len(returns),
        "sharpe_convention": "mean_daily_excess_over_sample_std_daily_excess_times_sqrt252",
        "drawdown_convention": "positive_loss_magnitude; curves_are_nonpositive",
    }


def trading_metrics(result: BacktestResult, strategy: str,
                    start: pd.Timestamp, end: pd.Timestamp) -> dict:
    events = result.events.loc[(result.events.strategy == strategy)
                               & result.events.execution_date.between(start, end)]
    schedule = result.schedule
    scheduled = schedule.loc[(schedule.strategy == strategy) & ~schedule.is_initial
                             & schedule.within_sample & schedule.execution_date.between(start, end)]
    post = events.loc[~events.is_initial]
    initial = events.loc[events.is_initial]
    if (post.execution_date.duplicated().any()
            or set(post.execution_date) != set(scheduled.execution_date)):
        raise DataQualityError("Scheduled execution and event records disagree")
    numbers = events[["fees", "gross_notional", "gross_two_sided_turnover", "pre_trade_wealth"]]
    if not np.isfinite(numbers.to_numpy()).all() or (numbers < 0).any().any():
        raise DataQualityError("Invalid accounting event values")
    if (events.pre_trade_wealth <= 0).any():
        raise DataQualityError("Nonpositive wealth before orders")
    if not np.allclose(events.gross_notional / events.pre_trade_wealth,
                       events.gross_two_sided_turnover, rtol=1e-12, atol=1e-12):
        raise DataQualityError("Turnover does not reconcile with executed notionals")
    trade_rows = result.trades.loc[(result.trades.strategy == strategy)
                                   & result.trades.execution_date.between(start, end)]
    for column, event_column in (("fee", "fees"), ("gross_notional", "gross_notional")):
        if not np.isclose(trade_rows[column].sum(), events[event_column].sum(), rtol=0, atol=1e-8):
            raise DataQualityError("Trade ledger and event totals do not reconcile")
    return {
        "scheduled_rebalance_count": len(scheduled),
        "any_trade_rebalance_count": int((post.gross_notional > 0).sum()),
        "material_rebalance_count": int((post.gross_two_sided_turnover > 0.0001).sum()),
        "initial_gross_two_sided_turnover": float(initial.gross_two_sided_turnover.sum()),
        "post_initial_gross_two_sided_turnover": float(post.gross_two_sided_turnover.sum()),
        "gross_two_sided_turnover": float(events.gross_two_sided_turnover.sum()),
        "initial_fees": float(initial.fees.sum()),
        "post_initial_fees": float(post.fees.sum()), "total_trading_fees": float(events.fees.sum()),
    }


def concentration_metrics(result: BacktestResult, strategy: str,
                          start: pd.Timestamp, end: pd.Timestamp,
                          *, include_initial: bool) -> dict:
    daily = result.portfolio_values.loc[(result.portfolio_values.strategy == strategy)
                                        & result.portfolio_values.date.between(start, end)].sort_values("date")
    signals = result.optimization_log.loc[result.optimization_log.strategy == strategy].copy()
    dates = pd.to_datetime(signals.signal_date, errors="raise")
    mask = dates.between(start, end)
    if include_initial:
        mask |= signals.initial.eq(True)
    signals = signals.loc[mask]
    output = {"concentration_signal_count": len(signals)}
    for field in ("holdings_count", "largest_weight", "hhi"):
        for name, table in (("daily", daily), ("signal", signals)):
            values = pd.to_numeric(table[field], errors="raise")
            if not np.isfinite(values.to_numpy()).all():
                raise DataQualityError("Invalid concentration values")
            for statistic in ("mean", "min", "max"):
                output[f"{name}_{field}_{statistic}"] = float(getattr(values, statistic)()) if len(values) else np.nan
        output[f"terminal_{field}"] = float(daily[field].iloc[-1])
    return output


def calculate_metrics(result: BacktestResult, risk_free: pd.DataFrame, config: dict) -> MetricsResult:
    matrix = wealth_matrix(result)
    expected, _ = session_grid(config)
    first = pd.Timestamp(config["initial_execution_date"])
    expected = expected[(expected >= first) & (expected <= pd.Timestamp(config["backtest_end"]))]
    if not matrix.index.equals(expected):
        raise DataQualityError("Metrics require every expected backtest session")
    if (config["metrics"]["annualization_sessions"] != 252
            or config["metrics"]["volatility_ddof"] != 1
            or config["metrics"]["cagr_days_per_year"] != 365.25):
        raise ValueError("Unsupported metric annualization convention")
    fixed_periods = [
        {"start": "2011-01-03", "end": "2015-12-31", "baseline": "external_capital_before_initial_purchase"},
        {"start": "2016-01-01", "end": "2020-12-31", "baseline": "2015-12-31"},
        {"start": "2021-01-01", "end": "2025-12-31", "baseline": "2020-12-31"},
    ]
    if config["metrics"]["subperiods"] != fixed_periods:
        raise ValueError("Preserve the three agreed subperiod baselines")
    capital = float(result.metadata["initial_external_capital_usd"])
    if capital != 10000 or config["metrics"]["initial_drawdown_peak_usd"] != capital:
        raise ValueError("Expected original USD 10000 baseline")
    full_rows, sub_rows, curves = [], [], []
    labels = {k: result.metadata[k] for k in ("universe_mode", "bias_label", "rf_mode", "fee_rate")}
    for strategy in STRATEGIES:
        wealth = matrix[strategy]
        full_rows.append({"strategy": strategy, **labels,
                          **performance(wealth, capital, first, risk_free, initial_period=True),
                          **trading_metrics(result, strategy, first, wealth.index[-1]),
                          **concentration_metrics(result, strategy, first, wealth.index[-1], include_initial=True)})
        curve = drawdown_curve(wealth, capital)
        curves.append(pd.DataFrame({"date": curve.index, "strategy": strategy,
                                    "drawdown": curve.to_numpy(), **labels}))
        for period in fixed_periods:
            start, end = pd.Timestamp(period["start"]), pd.Timestamp(period["end"])
            initial = period is fixed_periods[0]
            baseline_date = first if initial else pd.Timestamp(period["baseline"])
            if not initial and baseline_date not in wealth.index:
                raise DataQualityError(f"Missing exact subperiod opening close {baseline_date}")
            opening = capital if initial else float(wealth.loc[baseline_date])
            subset = wealth.loc[start:end]
            sub_rows.append({"strategy": strategy, "period": f"{start.year}-{end.year}", **labels,
                             **performance(subset, opening, baseline_date, risk_free, initial_period=initial),
                             **trading_metrics(result, strategy, start, end),
                             **concentration_metrics(result, strategy, start, end, include_initial=initial)})
    return MetricsResult(pd.DataFrame(full_rows), pd.DataFrame(sub_rows), pd.concat(curves, ignore_index=True))


def export_metrics(metrics: MetricsResult, directory: str | Path) -> None:
    """Write only on an explicit later call; decimal fractions, ISO dates, NA blanks."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in (("portfolio_metrics", metrics.portfolio_metrics),
                        ("subperiod_metrics", metrics.subperiod_metrics)):
        frame.to_csv(directory / f"{name}.csv", index=False, encoding="utf-8",
                     float_format="%.12g", date_format="%Y-%m-%d", na_rep="")
