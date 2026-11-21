"""Phase 5: explicitly invoked five-portfolio engine; no import-time execution.

Shares are fractional units of the vendor's adjusted total-return price proxy,
not a reconstruction of legal share counts/dividend cash flows. No extra dividends,
interest on residual cash, taxes, spread or slippage are credited or charged.
"""
from __future__ import annotations

from dataclasses import dataclass

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from .optimization import optimize_signal
from .preprocessing import PreparedData, daily_index, session_grid
from .universe import DataQualityError


STRATEGIES = {
    "buy_and_hold": [], "monthly": list(range(1, 13)),
    "quarterly": [3, 6, 9, 12], "semiannual": [6, 12], "annual": [12],
}


class AccountingError(RuntimeError):
    """An allocation cannot be reconciled without borrowing or invented cash."""


@dataclass
class Execution:
    shares: pd.Series
    cash: float
    signed_notionals: pd.Series
    fees: pd.Series
    pre_trade_wealth: float
    post_trade_wealth: float
    gross_notional: float
    turnover: float
    equation_residual_usd: float


@dataclass
class BacktestResult:
    portfolio_values: pd.DataFrame
    initial_weights: pd.DataFrame
    weight_history: pd.DataFrame
    trades: pd.DataFrame
    events: pd.DataFrame
    optimization_log: pd.DataFrame
    schedule: pd.DataFrame
    metadata: dict


def execute_target(shares: pd.Series, cash: float, prices: pd.Series,
                   weights: pd.Series, fee_rate: float, tolerance: float = 1e-8,
                   max_iterations: int = 200) -> Execution:
    """Solve X = V - c*sum(abs(w*X-h)) using the feasible bisection endpoint.

    No order-size threshold: every nonzero executed notional incurs a fee.
    An exactly unchanged target at zero cash returns unchanged shares and zero
    fees. Tiny numerical residual cash is retained, never borrowed or fabricated.
    """
    if (shares.empty or shares.index.has_duplicates
            or not shares.index.equals(prices.index) or not shares.index.equals(weights.index)):
        raise DataQualityError("Execution asset axes must match exactly")
    arrays = [s.to_numpy(dtype=float) for s in (shares, prices, weights)]
    q, p, w = arrays
    if (not all(np.isfinite(a).all() for a in arrays) or (q < 0).any()
            or (p <= 0).any() or (w < 0).any()
            or not np.isfinite(cash) or cash < 0):
        raise AccountingError("Invalid positions, cash, prices or weights")
    if not np.isclose(w.sum(), 1, rtol=0, atol=1e-12):
        raise AccountingError("Target must sum to one")
    if not np.isfinite(fee_rate) or not 0 <= fee_rate < 1:
        raise ValueError("Fee rate must be in [0, 1)")
    if not np.isfinite(tolerance) or tolerance <= 0 or max_iterations < 1:
        raise ValueError("Invalid accounting solver settings")
    h = q * p
    wealth = float(h.sum() + cash)
    if not np.isfinite(wealth) or wealth <= 0:
        raise AccountingError("Nonpositive or nonfinite pre-trade wealth")
    if cash == 0 and np.array_equal(h / wealth, w):
        zeros = pd.Series(0.0, index=shares.index)
        return Execution(shares.copy(), 0.0, zeros, zeros.copy(), wealth, wealth, 0.0, 0.0, 0.0)

    def residual(x: float) -> float:
        return x + fee_rate * float(np.abs(w * x - h).sum()) - wealth

    low, high = 0.0, wealth
    if residual(high) == 0:
        low = high
    else:
        for _ in range(max_iterations):
            middle = (low + high) / 2
            if residual(middle) <= 0:
                low = middle
            else:
                high = middle
            if high - low <= tolerance and abs(residual(low)) <= tolerance:
                break
        else:
            raise AccountingError("Post-fee wealth bisection did not converge")
    # Use actual representable share changes for fees and cash. If floating point
    # rounding makes the endpoint unaffordable, move toward zero, not into debt.
    x = low
    for _ in range(max_iterations):
        new_q = w * x / p
        notional = (new_q - q) * p
        fees = fee_rate * np.abs(notional)
        new_cash = float(cash - notional.sum() - fees.sum())
        if new_cash >= 0:
            break
        x = float(np.nextafter(x, 0.0))
    else:
        raise AccountingError("Cannot construct a nonnegative-cash execution")
    post = float((new_q * p).sum() + new_cash)
    equation_error = abs(residual(x))
    if (not np.isfinite(post) or new_cash > tolerance or equation_error > tolerance
            or abs(post + fees.sum() - wealth) > tolerance):
        raise AccountingError("Post-fee accounting failed absolute-dollar reconciliation")
    gross = float(np.abs(notional).sum())
    return Execution(pd.Series(new_q, index=shares.index), new_cash,
                     pd.Series(notional, index=shares.index), pd.Series(fees, index=shares.index),
                     wealth, post, gross, gross / wealth, equation_error)


def build_schedule(config: dict) -> pd.DataFrame:
    """Calendar period-end signals and actual next-session executions.

    Keep final signals whose next close lies outside the sample as unexecuted
    rows. They are not counted as within-sample scheduled execution events.
    """
    if (config["signal_convention"] != "period_last_session_close"
            or config["execution_convention"] != "next_session_close"):
        raise ValueError("Unsupported signal/execution convention")
    if set(config["strategies"]) != set(STRATEGIES):
        raise ValueError("Exactly the five agreed strategies are required")
    for strategy, months in STRATEGIES.items():
        if config["strategies"][strategy]["rebalance_months"] != months:
            raise ValueError(f"Unexpected schedule for {strategy}")
    sessions, _ = session_grid(config)
    initial_signal = pd.Timestamp(config["initial_signal_date"])
    first = pd.Timestamp(config["initial_execution_date"])
    end = pd.Timestamp(config["backtest_end"])
    calendar = xcals.get_calendar("XNYS", start=config["calendar"]["start"],
                                 end=config["calendar"]["end"])
    if pd.Timestamp(calendar.next_session(initial_signal)).tz_localize(None) != first:
        raise DataQualityError("Initial execution must be the next session after the initial signal")
    # Use full calendar months rather than treating a truncated final month as end.
    all_sessions = calendar.sessions.tz_localize(None)
    month_ends = pd.Series(all_sessions, index=all_sessions).groupby(all_sessions.to_period("M")).max()
    rows = []
    for strategy, months in STRATEGIES.items():
        rows.append({"strategy": strategy, "signal_date": initial_signal,
                     "execution_date": first, "is_initial": True, "within_sample": True})
        for signal in month_ends:
            if signal <= first or signal > end or signal.month not in months:
                continue
            execution = pd.Timestamp(calendar.next_session(signal)).tz_localize(None)
            rows.append({"strategy": strategy, "signal_date": signal,
                         "execution_date": execution, "is_initial": False,
                         "within_sample": execution <= end})
    if first not in sessions or first > end:
        raise DataQualityError("Invalid sample execution bounds")
    return pd.DataFrame(rows).sort_values(["signal_date", "strategy"]).reset_index(drop=True)


def run_backtest(data: PreparedData, stable_ids: pd.Series, config: dict) -> BacktestResult:
    """Future explicit call: independent accounts, common initial allocation.

    A signal is computed only after that day's holdings have been valued and
    pending trades executed. The new target is held pending until the NEXT close.
    No CSVs or plots are written here; future orchestration controls export.
    """
    if (not config["initial_purchase_fee"]
            or config["initial_fee_policy"] != "charge_all_portfolios"
            or not config["fractional_shares"] or config["post_fee_solver"] != "bisection"
            or config["material_rebalance_turnover_threshold"] != 0.0001):
        raise ValueError("Unsupported fee, share or reporting convention")
    capital = float(config["initial_capital_usd"])
    if capital != 10000:
        raise ValueError("The agreed external initial capital is USD 10000")
    if config["post_fee_absolute_tolerance_usd"] != 1e-8:
        raise ValueError("The agreed absolute reconciliation tolerance is USD 1e-8")
    daily_index(data.adjusted_prices.index, "backtest prices")
    if not data.adjusted_prices.index.is_monotonic_increasing:
        raise DataQualityError("Prices must be ordered")
    assets = data.adjusted_prices.columns
    if assets.has_duplicates or not stable_ids.index.equals(assets):
        raise DataQualityError("Asset/ID axes must match")
    sessions, _ = session_grid(config)
    first = pd.Timestamp(config["initial_execution_date"])
    sessions = sessions[(sessions >= first) & (sessions <= pd.Timestamp(config["backtest_end"]))]
    if not sessions.isin(data.adjusted_prices.index).all():
        raise DataQualityError("Missing selected-asset trading session; stop backtest")
    schedule = build_schedule(config)
    initial = optimize_signal(data, config["initial_signal_date"], stable_ids, config, initial=True)
    # All five use the exact same target and initial execution computation.
    zero_shares = pd.Series(0.0, index=assets)
    common = execute_target(zero_shares, capital, data.adjusted_prices.loc[first],
                            initial.weights, config["fee_rate"],
                            config["post_fee_absolute_tolerance_usd"], config["post_fee_max_iterations"])
    values, weights_log, trades, events, optimizations, initial_rows = [], [], [], [], [], []
    for strategy in STRATEGIES:
        shares, cash = zero_shares.copy(), capital
        pending: tuple[pd.Timestamp, pd.Timestamp, pd.Series] | None = None
        strategy_schedule = schedule.loc[(schedule.strategy == strategy) & ~schedule.is_initial]
        by_signal = {row.signal_date: row for row in strategy_schedule.itertuples()}
        cumulative_fees = initial_turnover = rebalance_turnover = 0.0
        scheduled_count = any_trade_count = material_count = 0
        for date in sessions:
            prices = data.adjusted_prices.loc[date]
            if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any():
                raise DataQualityError(f"Invalid selected-asset price at {date}; no implicit delisting handling")
            pre_trade_wealth = float(shares @ prices + cash)
            execution = None
            signal_date = None
            is_initial = date == first
            if is_initial:
                execution = common
                signal_date = pd.Timestamp(config["initial_signal_date"])
                optimizations.append({"strategy": strategy, **initial.diagnostics})
                for asset in assets:
                    initial_rows.append({"strategy": strategy, "asset": asset,
                                         "weight": float(initial.weights[asset]),
                                         "shares": float(common.shares[asset]),
                                         "execution_date": date})
            elif pending is not None and date == pending[0]:
                _, signal_date, target = pending
                execution = execute_target(shares, cash, prices, target, config["fee_rate"],
                                           config["post_fee_absolute_tolerance_usd"],
                                           config["post_fee_max_iterations"])
                pending = None
            if execution is not None:
                old_shares = shares.copy()
                shares, cash = execution.shares.copy(), execution.cash
                fee = float(execution.fees.sum())
                cumulative_fees += fee
                any_trade = execution.gross_notional > 0
                material = not is_initial and execution.turnover > 0.0001
                if is_initial:
                    initial_turnover += execution.turnover
                else:
                    scheduled_count += 1
                    any_trade_count += int(any_trade)
                    material_count += int(material)
                    rebalance_turnover += execution.turnover
                events.append({"strategy": strategy, "signal_date": signal_date,
                               "execution_date": date, "is_initial": is_initial,
                               "pre_trade_wealth": execution.pre_trade_wealth,
                               "post_trade_wealth": execution.post_trade_wealth,
                               "cash_after": cash, "fees": fee,
                               "gross_notional": execution.gross_notional,
                               "gross_two_sided_turnover": execution.turnover,
                               "any_trade": any_trade, "material_rebalance": material,
                               "equation_residual_usd": execution.equation_residual_usd})
                for asset in assets:
                    notional = float(execution.signed_notionals[asset])
                    if notional != 0:
                        trades.append({"strategy": strategy, "signal_date": signal_date,
                                       "execution_date": date, "is_initial": is_initial,
                                       "asset": asset, "side": "buy" if notional > 0 else "sell",
                                       "adjusted_proxy_price": float(prices[asset]),
                                       "shares_before": float(old_shares[asset]),
                                       "shares_after": float(shares[asset]),
                                       "signed_notional": notional, "gross_notional": abs(notional),
                                       "fee": float(execution.fees[asset])})
            wealth = float(shares @ prices + cash)
            if not np.isfinite(wealth) or wealth <= 0 or cash < 0:
                raise AccountingError(f"Invalid account value for {strategy} at {date}")
            actual_weights = shares * prices / wealth
            values.append({"date": date, "strategy": strategy, "portfolio_value": wealth,
                           "pre_trade_wealth": pre_trade_wealth, "cash": cash,
                           "fees_cumulative": cumulative_fees,
                           "initial_gross_turnover": initial_turnover,
                           "post_initial_gross_turnover": rebalance_turnover,
                           "scheduled_rebalance_count": scheduled_count,
                           "any_trade_rebalance_count": any_trade_count,
                           "material_rebalance_count": material_count,
                           "holdings_count": int((shares > 0).sum()),
                           "largest_weight": float(actual_weights.max()),
                           "hhi": float((actual_weights ** 2).sum())})
            for asset in assets:
                weights_log.append({"date": date, "strategy": strategy, "asset": asset,
                                    "shares": float(shares[asset]), "weight": float(actual_weights[asset])})
            # Estimate after the close accounting above, never apply to this day's return.
            if date in by_signal:
                scheduled = by_signal[date]
                target = optimize_signal(data, date, stable_ids, config)
                optimizations.append({"strategy": strategy, **target.diagnostics,
                                      "execution_within_sample": scheduled.within_sample})
                if scheduled.within_sample:
                    if pending is not None:
                        raise AccountingError("Overlapping pending allocations")
                    pending = (scheduled.execution_date, date, target.weights.copy())
        if pending is not None:
            raise AccountingError("Scheduled within-sample execution was not processed")
    metadata = {**data.metadata, "initial_external_capital_usd": capital,
                "initial_execution_date": first.date().isoformat(),
                "fee_rate": config["fee_rate"],
                "fee_scenario": "zero-fee sensitivity" if config["fee_rate"] == 0 else "configured trading fee",
                "turnover_convention": "gross_two_sided",
                "scheduled_count_definition": "post-initial executions within sample; final unexecuted signals excluded",
                "share_convention": "fractional adjusted-total-return proxy units",
                "cash_interest_rate": 0.0,
                "experiment": "joint target re-estimation and trading frequency"}
    tables = [pd.DataFrame(rows) for rows in
              (values, initial_rows, weights_log, trades, events, optimizations)]
    for table in tables:
        table["universe_mode"] = data.metadata["universe_mode"]
        table["bias_label"] = data.metadata["bias_label"]
    return BacktestResult(*tables, schedule, metadata)
