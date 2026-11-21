"""Phase 6: four static figures; functions do nothing until explicitly called."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, StrMethodFormatter
import numpy as np
import pandas as pd

from .backtest import BacktestResult, STRATEGIES
from .metrics import MetricsResult, wealth_matrix
from .universe import DataQualityError


LABELS = {"buy_and_hold": "Buy & Hold", "monthly": "Monthly", "quarterly": "Quarterly",
          "semiannual": "Semiannual", "annual": "Annual"}
COLORS = dict(zip(STRATEGIES, ["#264653", "#0077b6", "#2a9d8f", "#e9a23b", "#bc4749"]))


def subtitle(result: BacktestResult) -> str:
    return (f"{result.metadata['bias_label']} | fee {result.metadata['fee_rate']:.2%} | "
            f"RF: {result.metadata['rf_mode']}\n"
            "Target re-estimation and trading frequency change together")


def finish(fig, title: str, result: BacktestResult):
    fig.suptitle(title, fontsize=15, fontweight="bold")
    fig.text(0.5, 0.01, subtitle(result), ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.07, 1, 0.94))
    return fig


def plot_growth(result: BacktestResult):
    wealth = wealth_matrix(result)
    fig, ax = plt.subplots(figsize=(11, 6))
    for strategy in STRATEGIES:
        ax.plot(wealth.index, wealth[strategy], label=LABELS[strategy], color=COLORS[strategy])
    ax.axhline(result.metadata["initial_external_capital_usd"], color="gray", linestyle=":",
               linewidth=1, label="External initial capital")
    ax.set(ylabel="Account wealth (USD)", xlabel="Session close")
    ax.yaxis.set_major_formatter(StrMethodFormatter("${x:,.0f}"))
    ax.grid(alpha=0.2)
    ax.legend()
    return finish(fig, "Portfolio wealth after trading fees", result)


def plot_risk_return(result: BacktestResult, metrics: MetricsResult):
    table = metrics.portfolio_metrics.set_index("strategy")
    if table.index.has_duplicates or set(table.index) != set(STRATEGIES):
        raise DataQualityError("Risk-return plot requires exactly five strategy metrics")
    fig, ax = plt.subplots(figsize=(9, 6))
    for strategy in STRATEGIES:
        row = table.loc[strategy]
        x, y = float(row.annualized_volatility), float(row.cagr)
        if not np.isfinite([x, y]).all():
            raise DataQualityError("Nonfinite risk-return point")
        ax.scatter(x, y, s=70, color=COLORS[strategy], label=LABELS[strategy])
    ax.set(xlabel="Annualized daily-return volatility", ylabel="Net CAGR")
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(alpha=0.2)
    ax.legend()
    return finish(fig, "Risk versus return: 2011–2025", result)


def plot_drawdowns(result: BacktestResult, metrics: MetricsResult):
    curves = metrics.drawdowns.pivot(index="date", columns="strategy", values="drawdown").sort_index()
    if set(curves.columns) != set(STRATEGIES) or not np.isfinite(curves.to_numpy()).all():
        raise DataQualityError("Drawdown plot requires complete five-strategy curves")
    fig, ax = plt.subplots(figsize=(11, 6))
    for strategy in STRATEGIES:
        ax.plot(curves.index, curves[strategy], label=LABELS[strategy], color=COLORS[strategy])
    ax.set(xlabel="Session close", ylabel="Drawdown from running peak (initial peak USD 10,000)")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(alpha=0.2)
    ax.legend()
    return finish(fig, "Portfolio drawdowns including initial trading fees", result)


def plot_weight_evolution(result: BacktestResult, config: dict):
    """Common top assets by full-sample mean actual weight, solely for display.

    The retrospective ranking does not select the investable universe or targets.
    Other contains all remaining stock weights; residual cash is shown separately.
    """
    history = result.weight_history
    if (set(history.strategy) != set(STRATEGIES)
            or history.duplicated(["date", "strategy", "asset"]).any()):
        raise DataQualityError("Invalid five-strategy weight history")
    count = int(config["plots"]["influential_stocks_count"])
    if count < 1 or config["plots"]["remaining_holdings_label"] != "Other":
        raise ValueError("Expected positive top-stock count and Other label")
    ranking = (history.groupby("asset", sort=True).weight.mean().rename("mean_weight")
               .reset_index().sort_values(["mean_weight", "asset"], ascending=[False, True]))
    top = ranking.asset.iloc[:count].tolist()
    palette = plt.get_cmap("tab20")
    colors = [palette(i % 20) for i in range(len(top))] + ["#cccccc", "#ffffff"]
    fig, axes = plt.subplots(5, 1, figsize=(13, 16), sharex=True)
    wealth = wealth_matrix(result)
    for ax, strategy in zip(axes, STRATEGIES):
        frame = history.loc[history.strategy == strategy].pivot(index="date", columns="asset", values="weight").sort_index()
        if (not frame.index.equals(wealth.index) or not set(top).issubset(frame.columns)
                or not np.isfinite(frame.to_numpy()).all() or (frame < 0).any().any()):
            raise DataQualityError("Missing/invalid daily weights; no display filling")
        accounts = result.portfolio_values.loc[result.portfolio_values.strategy == strategy].set_index("date")
        cash = (accounts.cash / accounts.portfolio_value).reindex(frame.index)
        if not np.isfinite(cash.to_numpy()).all() or (cash < 0).any():
            raise DataQualityError("Invalid cash weight")
        if not np.allclose(frame.sum(axis=1) + cash, 1, atol=1e-10, rtol=0):
            raise DataQualityError("Stock plus cash weights do not sum to one")
        other = frame.drop(columns=top).sum(axis=1)
        ax.stackplot(frame.index, *[frame[t].to_numpy() for t in top], other.to_numpy(), cash.to_numpy(),
                     labels=top + ["Other", "Cash"], colors=colors)
        ax.set(ylabel=LABELS[strategy], ylim=(0, 1))
        ax.yaxis.set_major_formatter(PercentFormatter(1))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=6, fontsize=8)
    axes[-1].set_xlabel("Session close; common top stocks ranked by mean observed weight")
    fig.suptitle("Actual portfolio weights and drift", fontsize=15, fontweight="bold")
    fig.text(0.5, 0.01, subtitle(result), ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return fig


def export_figures(result: BacktestResult, metrics: MetricsResult, config: dict,
                   directory: str | Path) -> None:
    """Explicit future PNG export; close figures after each save."""
    if config["plots"]["format"] != "png" or int(config["plots"]["dpi"]) <= 0:
        raise ValueError("Expected PNG format and positive DPI")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    factories = {
        "portfolio_growth": lambda: plot_growth(result),
        "risk_return": lambda: plot_risk_return(result, metrics),
        "drawdowns": lambda: plot_drawdowns(result, metrics),
        "weight_evolution": lambda: plot_weight_evolution(result, config),
    }
    for name, factory in factories.items():
        fig = factory()
        try:
            fig.savefig(directory / f"{name}.png", dpi=int(config["plots"]["dpi"]),
                        bbox_inches="tight", facecolor="white")
        finally:
            plt.close(fig)
