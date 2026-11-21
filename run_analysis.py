"""Explicit future entry point: download, prepare, backtest and export.

Nothing runs on import. This source was written without executing the workflow.
"""
from __future__ import annotations

import argparse
import gzip
import shutil
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
import sys
from uuid import uuid4

import numpy as np
import pandas as pd
import yaml


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8", float_format="%.12g",
                 date_format="%Y-%m-%d", na_rep="")


def compress_weight_history(directory: Path) -> Path:
    """Retain the local CSV and create a deterministic Git-friendly gzip copy."""
    source = directory / "weight_history.csv"
    destination = source.with_suffix(".csv.gz")
    with source.open("rb") as incoming, destination.open("wb") as outgoing:
        with gzip.GzipFile(filename="", mode="wb", fileobj=outgoing, mtime=0) as compressed:
            shutil.copyfileobj(incoming, compressed)
    return destination


def generate_conclusions(metrics, result, download_manifest: dict) -> str:
    """Generate only from completed in-memory results; no prewritten winners."""
    full = metrics.portfolio_metrics.set_index("strategy")
    sub = metrics.subperiod_metrics
    if len(full) != 5 or full.index.has_duplicates or len(sub) != 15:
        raise ValueError("Conclusions require all five strategies and three subperiods")

    def leaders(table, column, *, maximum=True, percent=False):
        values = table[column].dropna()
        values = values[np.isfinite(values)]
        if values.empty:
            return "nedefinované (žiadna konečná hodnota)"
        best = values.max() if maximum else values.min()
        names = ", ".join(str(x) for x in values.index[values == best])
        formatted = f"{best:.2%}" if percent else f"{best:,.4f}"
        return f"{names}: {formatted}"

    lines = ["# Závery z uskutočneného behu", "",
             f"Režim: **{result.metadata['universe_mode']} — {result.metadata['bias_label']}**.",
             f"Poplatok: {result.metadata['fee_rate']:.2%}; RF: {result.metadata['rf_mode']}.",
             f"Dátový manifest: `{download_manifest['run_id']}`.", "",
             "Experiment súčasne mení frekvenciu odhadovania Markowitzových cieľových váh "
             "aj obchodovania. Neizoluje rebalansovanie k jednému fixnému vektoru váh.", "",
             "## Celkové výsledky", "",
             f"- Najvyššia konečná hodnota (USD): {leaders(full, 'terminal_value')}.",
             f"- Najvyšší realizovaný Sharpe: {leaders(full, 'realized_sharpe')}.",
             f"- Najmenší maximálny drawdown: {leaders(full, 'maximum_drawdown', maximum=False, percent=True)}.",
             f"- Najnižšie celkové poplatky (USD): {leaders(full, 'total_trading_fees', maximum=False)}.",
             f"- Najnižší post-initial hrubý obojstranný obrat: {leaders(full, 'post_initial_gross_two_sided_turnover', maximum=False)}.",
             "", "Obrat je súčet pomerov nominálov k hodnote účtu, nie anualizované percento.", "",
             "| Stratégia | Čistý výnos | CAGR | Volatilita | Poplatky USD | Post-initial obrat |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for strategy, row in full.iterrows():
        lines.append(f"| {strategy} | {row.total_net_return:.2%} | {row.cagr:.2%} | "
                     f"{row.annualized_volatility:.2%} | {row.total_trading_fees:.2f} | "
                     f"{row.post_initial_gross_two_sided_turnover:.4f} |")
    lines += ["", "## Podperiódy", "",
              "2011–2015 začína externými 10 000 USD pred úvodným nákupom; "
              "2016–2020 od close 2015-12-31 a 2021–2025 od close 2020-12-31."]
    winners = []
    for period, rows in sub.groupby("period", sort=True):
        table = rows.set_index("strategy")
        best = table.total_net_return.max()
        winners.append(tuple(sorted(table.index[table.total_net_return == best])))
        lines += ["", f"**{period}**: najvyšší čistý výnos: {leaders(table, 'total_net_return', percent=True)}; "
                  f"najvyšší Sharpe: {leaders(table, 'realized_sharpe')}; "
                  f"najmenší drawdown: {leaders(table, 'maximum_drawdown', maximum=False, percent=True)}."]
    lines += ["", "Poradie lídrov podľa čistého výnosu sa medzi podperiódami "
              + ("menilo." if len(set(winners)) > 1 else "nemenilo."),
              "", "## Koncentrácia a odhady", "",
              "| Stratégia | Priemerný denný počet pozícií | Najvyššia denná váha | Priemerný denný HHI | Max. signálový HHI |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for strategy, row in full.iterrows():
        lines.append(f"| {strategy} | {row.daily_holdings_count_mean:.2f} | "
                     f"{row.daily_largest_weight_max:.2%} | {row.daily_hhi_mean:.4f} | {row.signal_hhi_max:.4f} |")
    logs = result.optimization_log
    fallback_count = int(logs.optimizer_status.eq("nonpositive_excess_fallback").sum())
    repaired_count = int(logs.clipped_eigenvalues.gt(0).sum())
    lines += ["", f"Záznamy signálov s núdzovým pravidlom: {fallback_count}; "
              f"s orezaním vlastných čísel kovariancie: {repaired_count}. "
              "Počty sú po stratégiách, vrátane spoločného úvodného odhadu a záverečných signálov bez exekúcie.",
              "Núdzové pravidlo nie je garantovaným maximom Sharpe pri nekladných excess výnosoch. "
              "Nestabilné priemery a šum bez limitu maximálnej váhy môžu viesť ku koncentrácii, "
              "najmä pri mesačnom preodhadovaní. Úvodné šesťročné a ďalšie päťročné okná "
              "sú zámerne asymetrické a obmedzujú porovnateľnosť.", "", "## Zdroje a obmedzenia", ""]
    sources: dict[str, list[str]] = {}
    for record in download_manifest["sources"]:
        source = record["source"]
        provider = "Yahoo Finance / yfinance" if "finance.yahoo.com" in source else source
        sources.setdefault(provider, []).append(record["retrieved_at_utc"])
    for provider, dates in sorted(sources.items()):
        lines.append(f"- {provider}: získané od {min(dates)} do {max(dates)}.")
    lines.append("Úplné URL, jednotlivé dátové verzie a SHA-256 sú v uvedenom dátovom manifeste.")
    lines += ["", "Vzorka je silne skreslená dnešným členstvom a dostupnosťou až do 2025 "
              "(survivorship a look-ahead selection bias). Podmienka histórie od 2005 vylučuje neskoršie IPO. "
              "Časovanie signálov bez budúcich výnosov toto výberové skreslenie neodstraňuje.",
              "Yahoo Adj Close je retrieval-date verzia spätne upraveného total-return proxy, "
              "nie dobový archív. Korporátne udalosti, delistingy a revízie môžu byť neúplné. "
              "FRED používa predpoklad jedného amerického pracovného dňa oneskorenia, "
              "nie overené historické release timestamps. DGS3MO je výnosová sadzba, nie investovateľný realizovaný výnos.",
              "Modelovaný poplatok nezahŕňa spread, sklz, trhový dopad ani financovanie. "
              "Dane z dividend a realizovaných ziskov sa nemodelujú; celkové náklady môžu byť podhodnotené.",
              "Jedna realizovaná trajektória 2011–2025 nepreukazuje štatistickú významnosť "
              "ani budúcu prevahu. Porovnanie je opisné, bez inferenčného testu. "
              "Benchmark je vynechaný: závery porovnávajú päť stratégií, netvrdia prevahu nad širokým trhom."]
    if result.metadata["fee_rate"] == 0 or result.metadata["rf_mode"] == "zero-sensitivity":
        lines += ["", "**Toto je citlivostná analýza; nenahrádza hlavný experiment s 0,1 % poplatkom a FRED sadzbou.**"]
    return "\n".join(lines) + "\n"


def run(config_path: str | Path, *, output: str | Path | None = None,
        fee_rate: float | None = None, rf_mode: str | None = None,
        refresh: bool = False) -> Path:
    """Execute only after separate authorization; refuse existing output files."""
    from src.download_data import download_inputs, save_json, utc_now
    from src.preprocessing import prepare_data, PriceValidationError
    from src.backtest import run_backtest
    from src.metrics import calculate_metrics, export_metrics
    import matplotlib
    matplotlib.use("Agg")
    from src.plotting import export_figures

    config_path = Path(config_path).resolve()
    root = config_path.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a mapping")
    if fee_rate is not None:
        config["fee_rate"] = fee_rate
    if rf_mode is not None:
        config["rf_mode"] = rf_mode
    if not np.isfinite(config["fee_rate"]) or not 0 <= config["fee_rate"] < 1:
        raise ValueError("Fee rate must be finite and in [0, 1)")
    sensitivity = config["fee_rate"] != 0.001 or config["rf_mode"] != "fred_dgs3mo"
    if output is None and sensitivity:
        raise ValueError("Sensitivity runs require a separate --output directory")
    destination = Path(output) if output is not None else Path(config["paths"]["results"])
    if not destination.is_absolute():
        destination = root / destination
    destination = destination.resolve()
    if destination.exists() and any(p.is_file() and p.name != ".gitkeep" for p in destination.rglob("*")):
        raise FileExistsError("Output contains existing files; choose a new --output directory")
    destination.mkdir(parents=True, exist_ok=True)
    state = {"run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8],
             "status": "started", "started_at_utc": utc_now(), "configuration": config,
             "config_source_sha256": sha256(config_path.read_bytes()).hexdigest(),
             "sensitivity": sensitivity, "output": str(destination), "artifacts": []}
    state_path = destination / "run_manifest.json"
    save_json(state_path, state)
    try:
        logging.info("Downloading and selecting universe")
        bundle = download_inputs(config, root, refresh=refresh)
        state["download_manifest"] = str(bundle.manifest_path)
        download_manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
        logging.info("Preparing %s selected stocks", len(bundle.selected_universe))
        data = prepare_data(bundle, config)
        ids = pd.Series(data.adjusted_prices.columns, index=data.adjusted_prices.columns, dtype=str)
        logging.info("Running five-strategy backtest")
        result = run_backtest(data, ids, config)
        logging.info("Calculating metrics and exporting figures")
        metrics = calculate_metrics(result, data.risk_free, config)
        export_metrics(metrics, destination)
        tables = {"portfolio_values": result.portfolio_values, "initial_weights": result.initial_weights,
                  "weight_history": result.weight_history, "trades": result.trades,
                  "optimization_log": result.optimization_log, "data_quality_report": data.quality_report,
                  "events": result.events, "schedule": result.schedule,
                  "drawdown_curves": metrics.drawdowns,
                  "risk_free_alignment": data.risk_free.rename_axis("date").reset_index()}
        for name, table in tables.items():
            write_csv(table, destination / f"{name}.csv")
        compress_weight_history(destination)
        export_figures(result, metrics, config, destination / "graphs")
        (destination / "conclusions.md").write_text(
            generate_conclusions(metrics, result, download_manifest), encoding="utf-8")
        state["status"] = "completed"
        state["metadata"] = result.metadata
    except KeyboardInterrupt:
        state["status"] = "interrupted"
        raise
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, PriceValidationError):
            write_csv(exc.report, destination / "data_quality_report.csv")
        raise
    finally:
        state["finished_at_utc"] = utc_now()
        state["artifacts"] = [{"path": str(p.relative_to(destination)),
                                "sha256": sha256(p.read_bytes()).hexdigest()}
                               for p in sorted(destination.rglob("*"))
                               if p.is_file() and p != state_path and p.name != ".gitkeep"]
        save_json(state_path, state)
    return destination


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Download and run the five-strategy research workflow")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fee-rate", type=float)
    parser.add_argument("--rf-mode", choices=["fred_dgs3mo", "zero-sensitivity"])
    parser.add_argument("--refresh", action="store_true", help="Request new source vintages instead of reusing valid cache")
    args = parser.parse_args()
    try:
        destination = run(args.config, output=args.output, fee_rate=args.fee_rate,
                          rf_mode=args.rf_mode, refresh=args.refresh)
    except Exception as exc:
        print(f"Analysis failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Completed analysis: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
