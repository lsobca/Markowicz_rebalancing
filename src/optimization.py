"""Phase 4: lagged max-Sharpe targets only; no trading or backtest execution."""
from __future__ import annotations

from dataclasses import dataclass
import warnings

import cvxpy as cp
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

from .preprocessing import (
    PreparedData, annualized_estimates, daily_index, session_grid, simple_returns,
)
from .universe import DataQualityError


class OptimizationError(RuntimeError):
    """No valid portfolio can be produced; never silently replace the strategy."""


@dataclass
class OptimizationResult:
    weights: pd.Series
    annual_mean: pd.Series
    sample_covariance: pd.DataFrame
    regularized_covariance: pd.DataFrame
    diagnostics: dict


def training_returns(prices: pd.DataFrame, signal_date: str | pd.Timestamp,
                     config: dict, *, initial: bool = False
                     ) -> tuple[pd.DataFrame, dict]:
    """Initial six-year returns versus strictly bounded five-year PRICE windows.

    Initial: prepend the last 2004 session solely to calculate the first 2005
    return. Later: exclude all prices on/before D - five years, then compute
    returns within that price window. Thus the first retained rolling price is
    a reference, not a return using an excluded boundary price.
    """
    daily_index(prices.index, "training prices")
    if not prices.index.is_monotonic_increasing:
        raise DataQualityError("Training prices must be ordered")
    signal = pd.Timestamp(signal_date)
    daily_index(pd.DatetimeIndex([signal]), "signal")
    sessions, reference = session_grid(config)
    if signal not in sessions or signal not in prices.index:
        raise DataQualityError("Signal must be an available XNYS session")
    if config["rolling_window_years"] != 5 or config["initial_training_calendar_years"] != 6:
        raise DataQualityError("Preserve the six-year initial / five-year rolling asymmetry")
    if (config["rolling_window_left_boundary"] != "exclusive"
            or config["rolling_window_right_boundary"] != "inclusive"):
        raise DataQualityError("Rolling price window must be left-exclusive, right-inclusive")
    if initial:
        if (signal != pd.Timestamp(config["initial_signal_date"])
                or config["initial_training_start"] != "2005-01-01"
                or config["initial_training_end"] != "2010-12-31"
                or signal != pd.Timestamp("2010-12-31")):
            raise DataQualityError("Initial training must cover 2005-2010 through the initial signal")
        lower = pd.Timestamp(config["initial_training_start"])
        expected = pd.DatetimeIndex([reference]).append(sessions[(sessions >= lower) & (sessions <= signal)])
    else:
        if signal <= pd.Timestamp(config["initial_signal_date"]):
            raise DataQualityError("Rolling signals must follow the initial signal")
        lower = signal - pd.DateOffset(years=5)
        expected = sessions[(sessions > lower) & (sessions <= signal)]
    if len(expected) < 3 or not expected.isin(prices.index).all():
        raise DataQualityError("Incomplete training session window")
    window = prices.loc[expected]
    returns = simple_returns(window)
    return returns, {
        "signal_date": signal.date().isoformat(), "initial": initial,
        "window_lower_bound": lower.date().isoformat(),
        "window_left_inclusive": initial, "window_right_inclusive": True,
        "price_start": expected[0].date().isoformat(),
        "price_end": expected[-1].date().isoformat(),
        "first_return_date": returns.index[0].date().isoformat(),
        "last_return_date": returns.index[-1].date().isoformat(),
        "price_observations": len(window), "return_observations": len(returns),
        "initial_reference_only": initial,
    }


def signal_risk_free(risk_free: pd.DataFrame, signal: pd.Timestamp,
                     config: dict) -> tuple[float, dict]:
    """Require the exact signal row, with documented past publication availability."""
    daily_index(risk_free.index, "risk-free dates")
    if signal not in risk_free.index:
        raise DataQualityError("No aligned risk-free rate on signal date")
    row = risk_free.loc[signal]
    rate = float(row["annual_rate"])
    if not np.isfinite(rate) or rate <= -1 or row["rf_mode"] != config["rf_mode"]:
        raise DataQualityError("Invalid annual risk-free rate or mode mismatch")
    if config["rf_mode"] == "zero-sensitivity":
        if rate != 0:
            raise DataQualityError("Zero sensitivity requires a zero rate")
        return rate, {"rf_mode": "zero-sensitivity", "annual_rf": rate,
                      "rf_observation_date": None, "rf_available_date": None}
    if config["rf_mode"] != "fred_dgs3mo":
        raise DataQualityError("Unknown risk-free mode")
    observation = pd.Timestamp(row["observation_date"])
    available = pd.Timestamp(row["available_date"])
    daily_index(pd.DatetimeIndex([observation]), "FRED observation date")
    daily_index(pd.DatetimeIndex([available]), "FRED availability date")
    lag = CustomBusinessDay(n=1, calendar=USFederalHolidayCalendar())
    if available < observation + lag or available > signal:
        raise DataQualityError("Risk-free input violates the one-US-business-day publication lag")
    return rate, {"rf_mode": "fred_dgs3mo", "annual_rf": rate,
                  "rf_observation_date": observation.date().isoformat(),
                  "rf_available_date": available.date().isoformat()}


def regularize_covariance(covariance: pd.DataFrame, eigenvalue_floor: float
                          ) -> tuple[pd.DataFrame, dict]:
    if not np.isfinite(eigenvalue_floor) or eigenvalue_floor <= 0:
        raise ValueError("Covariance floor must be finite and strictly positive")
    matrix = covariance.to_numpy(dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[0] != matrix.shape[1]:
        raise DataQualityError("Expected nonempty square covariance")
    if not covariance.index.equals(covariance.columns) or covariance.index.has_duplicates:
        raise DataQualityError("Covariance axes must have identical unique asset labels")
    if not np.isfinite(matrix).all():
        raise DataQualityError("Nonfinite covariance")
    symmetric = (matrix + matrix.T) / 2
    try:
        eigenvalues, vectors = np.linalg.eigh(symmetric)
    except np.linalg.LinAlgError as exc:
        raise OptimizationError("Covariance eigendecomposition failed") from exc
    clipped = np.maximum(eigenvalues, eigenvalue_floor)
    repaired = (vectors * clipped) @ vectors.T
    repaired = (repaired + repaired.T) / 2
    minimum_after = float(np.linalg.eigvalsh(repaired).min())
    if not np.isfinite(repaired).all() or minimum_after <= 0:
        raise OptimizationError("Covariance repair failed to produce positive definiteness")
    diagnostics = {
        "covariance_asymmetry_max": float(np.max(np.abs(matrix - matrix.T))),
        "minimum_eigenvalue_before": float(eigenvalues.min()),
        "minimum_eigenvalue_after": minimum_after,
        "eigenvalue_floor_annual": eigenvalue_floor,
        "clipped_eigenvalues": int((eigenvalues < eigenvalue_floor).sum()),
        "covariance_adjustment_frobenius": float(np.linalg.norm(repaired - matrix)),
    }
    return pd.DataFrame(repaired, index=covariance.index, columns=covariance.columns), diagnostics


def filter_weights(weights: pd.Series, threshold: float = 0.0001) -> pd.Series:
    """Strict '<' filter: a weight exactly 0.0001 survives, then renormalize."""
    if threshold != 0.0001:
        raise ValueError("The agreed stock-weight threshold is exactly 0.0001")
    if (weights.empty or weights.index.has_duplicates
            or not np.isfinite(weights.to_numpy()).all() or (weights < 0).any()):
        raise OptimizationError("Invalid weights before filtering")
    if not np.isclose(weights.sum(), 1, rtol=0, atol=1e-8):
        raise OptimizationError("Filter expects already normalized weights")
    result = weights.mask(weights < threshold, 0.0)
    if result.sum() <= 0:
        raise OptimizationError("Weight filtering removed every asset")
    return result / result.sum()


def concentration(weights: pd.Series) -> dict:
    if (weights.empty or not np.isfinite(weights.to_numpy()).all()
            or (weights < 0).any() or not np.isclose(weights.sum(), 1, rtol=0, atol=1e-8)):
        raise OptimizationError("Concentration requires valid fully invested weights")
    return {"holdings_count": int((weights > 0).sum()),
            "largest_weight": float(weights.max()), "hhi": float((weights ** 2).sum())}


def optimize_estimates(mean: pd.Series, covariance: pd.DataFrame, annual_rf: float,
                       stable_ids: pd.Series, config: dict) -> OptimizationResult:
    """Convex positive-excess transformation, or explicitly disclosed contingency.

    stable_ids maps each asset label to a unique stable identifier. For the
    survivors-only baseline, consistently preserved original symbols can be used;
    they are not asserted to be historical permanent security identifiers.
    """
    settings = config["optimization"]
    if (settings["solver"] != "CLARABEL" or settings["solver_fallback"]
            or config["allow_shorting"] or config["maximum_stock_weight"] is not None
            or not config["fully_invested"] or not settings["normalize_after_weight_filter"]):
        raise ValueError("Unsupported optimizer constraints or solver configuration")
    if (mean.empty or mean.index.has_duplicates or not covariance.index.equals(mean.index)
            or not covariance.columns.equals(mean.index) or not stable_ids.index.equals(mean.index)):
        raise DataQualityError("Mean, covariance and ID axes must match exactly")
    if (not stable_ids.map(lambda x: isinstance(x, str) and bool(x)).all()
            or stable_ids.duplicated().any()):
        raise DataQualityError("Stable identifiers must be unique nonempty strings")
    mu = mean.to_numpy(dtype=float)
    if not np.isfinite(mu).all() or not np.isfinite(annual_rf) or annual_rf <= -1:
        raise DataQualityError("Invalid mean or annual risk-free input")
    tolerance = float(settings["feasibility_absolute_tolerance"])
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("Feasibility tolerance must be positive and finite")
    repaired, diagnostics = regularize_covariance(
        covariance, float(settings["covariance_eigenvalue_floor_annual"]),
    )
    sigma = repaired.to_numpy()
    excess = mu - annual_rf
    diagnostics.update({"annual_rf": float(annual_rf), "solver": None,
                        "positive_excess_assets": int((excess > 0).sum())})
    if not (excess > 0).any():
        if settings["nonpositive_excess_policy"] != "largest_excess_return_single_stock":
            raise ValueError("Unsupported nonpositive-excess contingency")
        candidates = np.flatnonzero(excess == excess.max())
        chosen = min(candidates, key=lambda i: stable_ids.iloc[i])
        # Check RAW variance: regularization must not conceal a zero-volatility asset.
        raw_variance = float(covariance.iloc[chosen, chosen])
        if not np.isfinite(raw_variance) or raw_variance <= 0:
            raise OptimizationError("Nonpositive-excess contingency has zero/invalid asset volatility")
        weights = pd.Series(0.0, index=mean.index)
        weights.iloc[chosen] = 1.0
        warning = "Largest-excess single-stock contingency is not guaranteed max-Sharpe for nonpositive excess returns"
        warnings.warn(warning)
        diagnostics.update({"optimizer_status": "nonpositive_excess_fallback",
                            "fallback_stable_id": stable_ids.iloc[chosen], "warning": warning})
    else:
        if "CLARABEL" not in cp.installed_solvers():
            raise OptimizationError("Required CLARABEL solver is unavailable")
        x = cp.Variable(len(mean))
        problem = cp.Problem(cp.Minimize(cp.quad_form(x, cp.psd_wrap(sigma))),
                             [excess @ x == 1, x >= 0])
        try:
            objective = problem.solve(
                solver="CLARABEL", max_iter=int(settings["solver_max_iterations"]),
                tol_gap_abs=tolerance, tol_gap_rel=tolerance, tol_feas=tolerance,
            )
        except cp.error.SolverError as exc:
            raise OptimizationError("CLARABEL failed; no substitute portfolio") from exc
        if problem.status != cp.OPTIMAL or x.value is None or objective is None:
            raise OptimizationError(f"CLARABEL did not reach optimal status: {problem.status}")
        solution = np.asarray(x.value, dtype=float).reshape(-1)
        if not np.isfinite(solution).all() or not np.isfinite(objective):
            raise OptimizationError("Nonfinite solver solution or objective")
        residual = abs(float(excess @ solution) - 1)
        if residual > tolerance or solution.min() < -tolerance:
            raise OptimizationError("Solver equality/nonnegativity constraints failed verification")
        calculated = float(solution @ sigma @ solution)
        if calculated <= 0 or abs(calculated - objective) > tolerance * max(1, abs(calculated)):
            raise OptimizationError("Solver objective failed independent verification")
        # Only numerical negatives within the verified tolerance can be clipped.
        nonnegative = np.maximum(solution, 0)
        if nonnegative.sum() <= 0 or abs(float(excess @ nonnegative) - 1) > tolerance:
            raise OptimizationError("Numerical clipping invalidated transformed constraints")
        weights = pd.Series(nonnegative / nonnegative.sum(), index=mean.index)
        diagnostics.update({"optimizer_status": "optimal", "solver": "CLARABEL",
                            "solver_status": problem.status, "objective": calculated,
                            "equality_residual": residual,
                            "numerical_negative_components_clipped": int((solution < 0).sum()),
                            "solver_iterations": problem.solver_stats.num_iters})
    pre_filter = weights.copy()
    weights = filter_weights(weights, config["weight_filter_threshold"])
    variance = float(weights.to_numpy() @ sigma @ weights.to_numpy())
    if not np.isfinite(variance) or variance <= 0:
        raise OptimizationError("Invalid final portfolio variance")
    diagnostics.update(concentration(weights))
    diagnostics.update({"pre_filter_holdings_count": int((pre_filter > 0).sum()),
                        "filtered_weight_mass": float(pre_filter[pre_filter < 0.0001].sum()),
                        "estimated_annual_return": float(mean @ weights),
                        "estimated_regularized_volatility": float(np.sqrt(variance)),
                        "estimated_regularized_sharpe": float((mean @ weights - annual_rf) / np.sqrt(variance)),
                        "post_filter_optimality_guaranteed": False})
    return OptimizationResult(weights, mean.copy(), covariance.copy(), repaired, diagnostics)


def optimize_signal(data: PreparedData, signal_date: str | pd.Timestamp,
                    stable_ids: pd.Series, config: dict, *, initial: bool = False
                    ) -> OptimizationResult:
    """Estimate one completed signal close; execution is a later phase's concern."""
    signal = pd.Timestamp(signal_date)
    returns, window = training_returns(data.adjusted_prices, signal, config, initial=initial)
    mean, covariance, _ = annualized_estimates(returns, config["metrics"]["annualization_sessions"])
    rf, rf_details = signal_risk_free(data.risk_free, signal, config)
    result = optimize_estimates(mean, covariance, rf, stable_ids, config)
    result.diagnostics.update(window)
    result.diagnostics.update(rf_details)
    result.diagnostics["universe_mode"] = data.metadata["universe_mode"]
    result.diagnostics["bias_label"] = data.metadata["bias_label"]
    return result


def summarize_concentration(diagnostics: pd.DataFrame) -> pd.DataFrame:
    """Summarize saved signal diagnostics for one strategy, without inventing events."""
    columns = ["holdings_count", "largest_weight", "hhi"]
    if diagnostics.empty or not set(columns).issubset(diagnostics.columns):
        raise DataQualityError("Signal concentration diagnostics are required")
    values = diagnostics[columns].astype(float)
    if not np.isfinite(values.to_numpy()).all():
        raise DataQualityError("Nonfinite concentration diagnostics")
    return values.agg(["count", "mean", "min", "max"]).T
