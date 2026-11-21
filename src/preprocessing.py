"""Strict price validation and past-only risk-free alignment (phase 3).

No import-time I/O, downloads or automatic exports. Dates are daily session
labels, not intraday timestamps. Adjusted prices remain vendor-vintage proxies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import warnings

import exchange_calendars as xcals
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

from .universe import BIAS_LABEL, DataQualityError, require_supported_mode

if TYPE_CHECKING:
    from .download_data import DownloadBundle


class PriceValidationError(DataQualityError):
    """A selected asset failed validation; report is available even on failure."""
    def __init__(self, message: str, report: pd.DataFrame):
        super().__init__(message)
        self.report = report


@dataclass
class PreparedData:
    # Includes the final 2004 reference session; returns start in 2005.
    adjusted_prices: pd.DataFrame
    daily_returns: pd.DataFrame
    risk_free: pd.DataFrame
    quality_report: pd.DataFrame
    metadata: dict


def daily_index(index: pd.Index, name: str) -> pd.DatetimeIndex:
    """Require explicit unique, timezone-naive, midnight date labels."""
    if not isinstance(index, pd.DatetimeIndex):
        raise DataQualityError(f"{name}: expected DatetimeIndex")
    if index.tz is not None or index.hasnans or index.has_duplicates:
        raise DataQualityError(f"{name}: ambiguous timezone, missing or duplicate dates")
    if not index.equals(index.normalize()):
        raise DataQualityError(f"{name}: intraday timestamps are not daily labels")
    return index


def session_grid(config: dict) -> tuple[pd.DatetimeIndex, pd.Timestamp]:
    """Bound XNYS explicitly, including the pre-training reference session."""
    calendar_config = config["calendar"]
    if calendar_config["exchange"] != "XNYS":
        raise DataQualityError("Baseline requires XNYS")
    calendar = xcals.get_calendar("XNYS", start=calendar_config["start"],
                                 end=calendar_config["end"])
    for closure in calendar_config["required_exceptional_closures"]:
        if calendar.is_session(closure):
            raise DataQualityError(f"Calendar incorrectly includes exceptional closure {closure}")
    sessions = calendar.sessions_in_range(config["universe"]["coverage_start"],
                                         config["universe"]["coverage_end"]).tz_localize(None)
    if sessions.empty:
        raise DataQualityError("Empty requested trading calendar")
    reference = pd.Timestamp(calendar.previous_session(sessions[0])).tz_localize(None)
    if reference < pd.Timestamp(config["download_start"]):
        raise DataQualityError("Download start omits the required pre-training reference")
    return sessions, reference


def validate_prices(prices: pd.DataFrame, selected: pd.DataFrame, config: dict
                    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recheck selected holdings; never remove a failed holding or fill prices.

    Invalid dates/columns fail as schema errors. Value failures carry a per-asset
    report. Extra non-session rows inside the required interval fail explicitly;
    observations outside that interval are recorded and excluded deliberately.
    """
    require_supported_mode(config["universe_mode"])
    if config["universe"]["missing_trading_session_prices_tolerated"] != 0:
        raise DataQualityError("Baseline permits zero missing session prices")
    if config["universe"]["price_forward_fill"] or config["universe"]["price_backfill"]:
        raise DataQualityError("Price filling is forbidden")
    if config["prices"]["auto_adjust"] or config["prices"]["field"] != "Adj Close":
        raise DataQualityError("Expected explicit vendor Adj Close, auto_adjust=False")
    if config["prices"]["separate_dividend_credit"]:
        raise DataQualityError("Adjusted-price proxy must not credit dividends twice")
    if selected.empty or "original_ticker" not in selected:
        raise DataQualityError("Missing selected universe")
    symbols = selected["original_ticker"].tolist()
    if len(set(symbols)) != len(symbols) or any(not isinstance(s, str) or not s for s in symbols):
        raise DataQualityError("Selected tickers must be unique nonempty strings")
    if prices.columns.has_duplicates or set(prices.columns) != set(symbols):
        raise DataQualityError("Price columns must match the selected universe exactly")
    daily_index(prices.index, "prices")
    try:
        numeric = prices.loc[:, symbols].apply(pd.to_numeric, errors="raise").astype(float).sort_index()
    except (ValueError, TypeError) as exc:
        raise DataQualityError("Nonnumeric adjusted prices") from exc
    sessions, reference = session_grid(config)
    required = pd.DatetimeIndex([reference]).append(sessions)
    aligned = numeric.reindex(required)
    in_range = numeric.index[(numeric.index >= reference) & (numeric.index <= sessions[-1])]
    extra = in_range.difference(required)
    outside_count = int(((numeric.index < reference) | (numeric.index > sessions[-1])).sum())
    records = []
    for symbol in symbols:
        values = aligned[symbol]
        finite = pd.Series(np.isfinite(values.to_numpy()), index=required)
        good = values.notna() & finite & values.gt(0)
        training = good.loc[config["initial_training_start"]:config["initial_training_end"]]
        evaluation = good.loc["2011-01-01":config["backtest_end"]]
        bad_dates = required[~good]
        records.append({
            "original_ticker": symbol,
            "universe_mode": config["universe_mode"], "bias_label": BIAS_LABEL,
            "expected_sessions": len(sessions),
            "missing_session_prices": int(values.loc[sessions].isna().sum()),
            "nonfinite_nonmissing_prices": int((~finite & values.notna()).sum()),
            "nonpositive_prices": int((finite & values.le(0)).sum()),
            "reference_session": reference.date().isoformat(),
            "reference_price_available": bool(good.loc[reference]),
            "complete_2005_2010": bool(len(training) > 0 and training.all()),
            "complete_2011_2025": bool(len(evaluation) > 0 and evaluation.all()),
            "unexpected_in_range_dates": ";".join(d.date().isoformat() for d in extra),
            "outside_required_interval_rows": outside_count,
            "invalid_dates": ";".join(d.date().isoformat() for d in bad_dates),
            "price_fill_count": 0,
            "status": "passed" if good.all() and extra.empty else "failed",
            "corporate_action_verification": "vendor_proxy_not_independently_verified",
        })
    report = pd.DataFrame(records)
    if report.status.eq("failed").any():
        failed = report.loc[report.status.eq("failed"), "original_ticker"].tolist()
        raise PriceValidationError(
            f"Selected asset price failure: {failed}. Stop; no filling, zero returns, "
            "implicit delisting payout or silent universe change.", report,
        )
    aligned.index.name = "date"
    return aligned, report


def simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """First row is a reference price, not a synthetic return observation."""
    daily_index(prices.index, "prices")
    if len(prices) < 2 or prices.shape[1] == 0 or not prices.index.is_monotonic_increasing:
        raise DataQualityError("Returns require ordered reference and session prices")
    values = prices.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise DataQualityError("Returns require positive finite prices without gaps")
    returns = prices.pct_change(fill_method=None).iloc[1:]
    if not np.isfinite(returns.to_numpy()).all() or (returns.to_numpy() <= -1).any():
        raise DataQualityError("Invalid simple returns from adjusted prices")
    return returns


def annualized_estimates(returns: pd.DataFrame, sessions_per_year: int = 252
                         ) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    """Arithmetic mean, sample covariance and sample volatility, without filtering.

    Caller must supply its intended training window; this function never chooses
    a window or drops incomplete rows. It performs no optimization or PSD repair.
    """
    daily_index(returns.index, "returns")
    if sessions_per_year != 252:
        raise ValueError("The agreed annualization is 252 sessions")
    if len(returns) < 2 or returns.shape[1] == 0 or returns.columns.has_duplicates:
        raise DataQualityError("At least two observations and unique assets required")
    if not returns.index.is_monotonic_increasing:
        raise DataQualityError("Return dates must be ordered")
    values = returns.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= -1).any():
        raise DataQualityError("Invalid or missing returns; pairwise deletion is forbidden")
    mean = returns.mean() * sessions_per_year
    covariance = returns.cov(ddof=1) * sessions_per_year
    volatility = returns.std(ddof=1) * np.sqrt(sessions_per_year)
    if not all(np.isfinite(x.to_numpy()).all() for x in (mean, covariance, volatility)):
        raise DataQualityError("Nonfinite annualized estimates")
    return mean, covariance, volatility


def align_risk_free(raw_percent: pd.Series | None, sessions: pd.DatetimeIndex,
                    config: dict) -> pd.DataFrame:
    """Annual decimal and daily rates known by each session close.

    Availability = observation date + one US federal-calendar business day.
    Backward as-of matching on AVAILABILITY dates implements past-only filling.
    The recorded observation/availability dates expose every alignment decision.
    This is an assumed publication lag, not verified historical release timestamps
    or a vintage database. Daily rates are labelled by the session ending a return.
    """
    daily_index(sessions, "risk-free target sessions")
    if sessions.empty or not sessions.is_monotonic_increasing:
        raise DataQualityError("Risk-free target sessions must be nonempty and ordered")
    settings = config["risk_free"]
    if (settings["publication_lag_us_business_days"] != 1
            or settings["business_day_calendar"] != "USFederalHolidayCalendar"
            or settings["fill_policy"] != "past_only_forward_fill"
            or settings["future_backfill"]
            or settings["percent_to_decimal_divisor"] != 100
            or config["metrics"]["annualization_sessions"] != 252):
        raise DataQualityError("Unsupported risk-free convention; preserve the agreed lag and units")
    mode = config["rf_mode"]
    if mode == "zero-sensitivity":
        if settings["zero_sensitivity_annual_rate"] != 0:
            raise DataQualityError("Zero sensitivity must use exactly zero")
        warnings.warn("Explicit 0% risk-free sensitivity; not the primary FRED experiment")
        return pd.DataFrame({"annual_rate": 0.0, "daily_rate": 0.0,
                             "observation_date": pd.NaT, "available_date": pd.NaT,
                             "age_calendar_days": np.nan, "rf_mode": mode}, index=sessions)
    if mode != "fred_dgs3mo":
        raise ValueError(f"Unsupported rf_mode: {mode}")
    if raw_percent is None:
        raise DataQualityError("Primary experiment requires validated FRED observations")
    daily_index(raw_percent.index, "FRED observations")
    try:
        raw = pd.to_numeric(raw_percent, errors="raise").astype(float).sort_index()
    except (ValueError, TypeError) as exc:
        raise DataQualityError("Nonnumeric FRED rates") from exc
    # Missing source observations have no availability event; no future backfill.
    observed = raw.dropna()
    if observed.empty or not np.isfinite(observed.to_numpy()).all():
        raise DataQualityError("Empty or nonfinite FRED observations")
    annual = observed / 100
    if (annual <= -1).any():
        raise DataQualityError("Annual rate must exceed -100% for compounding")
    business_day = CustomBusinessDay(n=1, calendar=USFederalHolidayCalendar())
    available = pd.DatetimeIndex([date + business_day for date in observed.index])
    events = pd.DataFrame({"observation_date": observed.index,
                           "available_date": available,
                           "annual_rate": annual.to_numpy()})
    # If unexpected weekend/holiday observations share an availability date,
    # use the latest observation among those already available at that date.
    events = events.sort_values(["available_date", "observation_date"])
    aligned = pd.merge_asof(pd.DataFrame({"date": sessions}), events,
                            left_on="date", right_on="available_date",
                            direction="backward", allow_exact_matches=True).set_index("date")
    if aligned.annual_rate.isna().any():
        first = aligned.index[aligned.annual_rate.isna()][0]
        raise DataQualityError(f"No previously available FRED rate at {first.date()}; no backfill")
    if ((aligned.available_date > aligned.index).any()
            or (aligned.observation_date >= aligned.available_date).any()):
        raise DataQualityError("Risk-free availability invariant violated")
    aligned["daily_rate"] = np.expm1(np.log1p(aligned.annual_rate) / 252)
    aligned["age_calendar_days"] = (aligned.index.to_series() - aligned.observation_date).dt.days
    aligned["rf_mode"] = mode
    return aligned


def daily_excess_returns(returns: pd.DataFrame, risk_free: pd.DataFrame) -> pd.DataFrame:
    """Subtract the aligned daily proxy; never use pandas' implicit union/fill."""
    daily_index(returns.index, "excess-return dates")
    daily_index(risk_free.index, "risk-free dates")
    if not returns.index.equals(risk_free.index):
        raise DataQualityError("Return and risk-free dates must match exactly")
    rates = risk_free["daily_rate"]
    if not np.isfinite(rates.to_numpy()).all() or not np.isfinite(returns.to_numpy()).all():
        raise DataQualityError("Missing/nonfinite inputs to daily excess returns")
    return returns.sub(rates, axis=0)


def prepare_data(bundle: DownloadBundle, config: dict) -> PreparedData:
    """Pure in-memory preparation of the phase-2 bundle; no export or execution."""
    prices, report = validate_prices(bundle.adjusted_prices, bundle.selected_universe, config)
    returns = simple_returns(prices)
    risk_free = align_risk_free(bundle.fred_annual_percent, returns.index, config)
    metadata = {
        "universe_mode": config["universe_mode"], "bias_label": BIAS_LABEL,
        "download_manifest": str(bundle.manifest_path), "rf_mode": config["rf_mode"],
        "annualization_sessions": 252, "covariance_ddof": 1, "volatility_ddof": 1,
        "price_interpretation": "retrieval_vintage_backward_adjusted_total_return_proxy",
        "reference_date": prices.index[0].date().isoformat(),
        "first_return_date": returns.index[0].date().isoformat(),
        "last_return_date": returns.index[-1].date().isoformat(),
        "rf_publication_convention": "observation_plus_one_US_federal_business_day",
        "rf_vintage_limitation": "download_vintage_not_historical_release_archive",
        "price_fill_count": 0,
    }
    report["rf_mode"] = config["rf_mode"]
    report["rf_missing_aligned_sessions"] = int(risk_free.annual_rate.isna().sum())
    report["rf_max_observation_age_calendar_days"] = risk_free.age_calendar_days.max()
    return PreparedData(prices, returns, risk_free, report, metadata)
