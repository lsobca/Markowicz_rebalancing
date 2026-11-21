"""Explicitly invoked phase-2 downloads, immutable source snapshots and manifests.

Importing this module does not download anything. No prices are filled, no returns
are calculated, and no optimization/backtest is run. API compatibility is untested.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
from pathlib import Path
import time
from typing import Callable
from uuid import uuid4
import warnings

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import requests
import yfinance as yf

from .universe import (
    BIAS_LABEL, DataQualityError, SourceUnavailableError, coverage_record,
    parse_current_roster, require_supported_mode, select_survivors,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class SnapshotStore:
    """Cache payloads are reusable only when request and SHA-256 both match.

    Bytes are content-addressed, so refreshed vintages do not overwrite old data.
    Sidecars contain actual retrieval timestamps, never the cache reuse time.
    """
    def __init__(self, root: Path, enabled: bool):
        self.root, self.enabled = root, enabled

    def key(self, request: dict) -> str:
        return sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

    def read(self, request: dict) -> tuple[bytes, dict] | None:
        if not self.enabled:
            return None
        sidecar = self.root / "index" / (self.key(request) + ".json")
        try:
            record = json.loads(sidecar.read_text(encoding="utf-8"))
            if record["request"] != request:
                raise ValueError("Request mismatch")
            payload = (self.root / "objects" / record["sha256"]).read_bytes()
            if sha256(payload).hexdigest() != record["sha256"]:
                raise ValueError("Checksum mismatch")
            datetime.fromisoformat(record["retrieved_at_utc"])
            return payload, record
        except FileNotFoundError:
            return None
        except (ValueError, KeyError, TypeError) as exc:
            warnings.warn(f"Ignoring invalid cached snapshot: {exc}")
            return None

    def write(self, request: dict, payload: bytes, source: str) -> dict:
        digest = sha256(payload).hexdigest()
        path = self.root / "objects" / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(payload)
        record = {"request": request, "sha256": digest,
                  "retrieved_at_utc": utc_now(), "source": source,
                  "raw_object": str(path), "byte_count": len(payload)}
        save_json(self.root / "index" / (self.key(request) + ".json"), record)
        return record


class Downloader:
    def __init__(self, config: dict, root: Path, *, refresh: bool = False,
                 sleep: Callable[[float], None] = time.sleep):
        self.config, self.root, self.refresh, self.sleep = config, root, refresh, sleep
        self.settings = config["download"]
        self.attempts = int(self.settings["max_attempts"])
        if self.attempts < 1 or not 1 <= int(self.settings["ticker_batch_size"]) <= 10:
            raise ValueError("Invalid retry count or Yahoo batch size (maximum 10)")
        self.store = SnapshotStore(root / self.settings["cache_directory"],
                                   self.settings["cache_enabled"])
        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.settings["user_agent"]
        self.records: list[dict] = []
        self.events: list[dict] = []

    def pause(self, attempt: int, retry_after: str | None = None) -> None:
        delay = min(self.settings["exponential_backoff_max_seconds"],
                    self.settings["exponential_backoff_initial_seconds"]
                    * self.settings["exponential_backoff_multiplier"] ** attempt)
        if retry_after and self.settings["respect_retry_after"]:
            try:
                server_delay = float(retry_after)
            except ValueError:
                try:
                    server_delay = (parsedate_to_datetime(retry_after)
                                    - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    server_delay = 0
            delay = max(delay, server_delay)
        self.sleep(max(0, delay))

    def note(self, record: dict, *, cached: bool, purpose: str) -> None:
        self.records.append({**record, "cache_reused": cached, "purpose": purpose})

    def http(self, url: str, validator: Callable[[bytes], object],
             purpose: str) -> tuple[bytes, dict]:
        request = {"url": url, "transport": "http", "schema_version": 1}
        cached = self.store.read(request)
        if cached:
            try:
                validator(cached[0])
            except (ValueError, KeyError) as exc:
                self.events.append({"source": url, "cache_rejected": str(exc)})
                cached = None
        if cached and not self.refresh:
            self.note(cached[1], cached=True, purpose=purpose)
            return cached
        errors = []
        for attempt in range(self.attempts):
            retry_after = None
            try:
                with self.session.get(url, timeout=self.settings["timeout_seconds"]) as response:
                    retry_after = response.headers.get("Retry-After")
                    response.raise_for_status()
                    payload = response.content
                validator(payload)
                record = self.store.write(request, payload, url)
                self.note(record, cached=False, purpose=purpose)
                return payload, record
            except (requests.RequestException, ValueError, KeyError) as exc:
                errors.append(str(exc))
                if attempt + 1 < self.attempts:
                    self.pause(attempt, retry_after)
        self.events.append({"source": url, "download_errors": errors})
        if cached:
            warnings.warn(f"Download failed; using validated cache for {purpose}")
            self.note(cached[1], cached=True, purpose=purpose)
            return cached
        raise SourceUnavailableError(f"{purpose}: download failed and no valid cache: {errors}")

    def yahoo_request(self, ticker: str) -> dict:
        return {"provider": "yfinance", "ticker": ticker,
                "start": self.config["download_start"],
                "end_exclusive": self.config["yahoo_end_exclusive"],
                "auto_adjust": False, "interval": "1d", "schema_version": 1}

    def fetch_prices(self, tickers: list[str], sessions: pd.DatetimeIndex,
                     reference: pd.Timestamp) -> tuple[dict[str, pd.Series], dict[str, list[str]]]:
        prices: dict[str, pd.Series] = {}
        errors: dict[str, list[str]] = {t: [] for t in tickers}
        cached_good: dict[str, pd.Series] = {}
        pending = []
        for ticker in tickers:
            cached = self.store.read(self.yahoo_request(ticker))
            if cached:
                try:
                    series = decode_price(cached[0])
                    complete = coverage_record(series, sessions, reference)["eligible_history"]
                    self.note(cached[1], cached=True, purpose=f"price:{ticker}")
                    prices[ticker] = series
                    if complete:
                        cached_good[ticker] = series
                        if not self.refresh:
                            continue
                except (ValueError, KeyError) as exc:
                    errors[ticker].append(f"Invalid cache: {exc}")
            pending.append(ticker)
        batch_size = int(self.settings["ticker_batch_size"])
        for attempt in range(self.attempts):
            if not pending:
                break
            if attempt:
                self.pause(attempt - 1)
            retry = []
            # First pass batches; subsequent attempts isolate every unresolved ticker.
            size = batch_size if attempt == 0 else 1
            for offset in range(0, len(pending), size):
                batch = pending[offset:offset + size]
                try:
                    frame = yf.download(
                        tickers=batch, start=self.config["download_start"],
                        end=self.config["yahoo_end_exclusive"], auto_adjust=False,
                        actions=True, interval="1d", threads=False, progress=False,
                        timeout=self.settings["timeout_seconds"], group_by="column",
                    )
                    if frame.empty:
                        raise DataQualityError("Empty Yahoo response (possibly rate limited)")
                    # Retain the unmodified returned table as well as per-ticker cache.
                    batch_request = {"provider": "yfinance_batch", "tickers": batch,
                                     "start": self.config["download_start"],
                                     "end_exclusive": self.config["yahoo_end_exclusive"],
                                     "auto_adjust": False, "actions": True}
                    record = self.store.write(batch_request, frame.to_csv().encode(),
                                              "https://finance.yahoo.com/")
                    self.note(record, cached=False, purpose="raw_yahoo_batch")
                except Exception as exc:
                    # yfinance may raise provider-specific errors, or swallow 429 and
                    # return an empty frame. Both get bounded, rate-aware backoff.
                    retry.extend(batch)
                    for ticker in batch:
                        errors[ticker].append(f"Attempt {attempt + 1}: {type(exc).__name__}: {exc}")
                    response = getattr(exc, "response", None)
                    headers = getattr(response, "headers", {})
                    self.pause(attempt, headers.get("Retry-After"))
                    continue
                for ticker in batch:
                    try:
                        series = extract_adjusted_close(frame, ticker, len(batch))
                        complete = coverage_record(series, sessions, reference)["eligible_history"]
                        # Never stitch observations from different retrieval vintages.
                        if not (ticker in cached_good and not complete):
                            prices[ticker] = series
                            record = self.store.write(
                                self.yahoo_request(ticker),
                                series.rename("adj_close").to_csv(index_label="date").encode(),
                                f"https://finance.yahoo.com/quote/{ticker}/history/",
                            )
                            self.note(record, cached=False, purpose=f"price:{ticker}")
                        if not complete:
                            errors[ticker].append(f"Attempt {attempt + 1}: incomplete/invalid coverage")
                            retry.append(ticker)
                    except (ValueError, KeyError) as exc:
                        errors[ticker].append(f"Attempt {attempt + 1}: {exc}")
                        retry.append(ticker)
                self.sleep(self.settings["pause_between_batches_seconds"])
            pending = retry
        for ticker in pending:
            if ticker in cached_good:
                prices[ticker] = cached_good[ticker]
                warnings.warn(f"Using complete cached vintage after refresh failure: {ticker}")
        return prices, errors


def normalize_dates(series: pd.Series) -> pd.Series:
    result = series.copy()
    index = pd.DatetimeIndex(pd.to_datetime(result.index, errors="raise"))
    if index.tz is not None:
        index = index.tz_localize(None)
    if not index.equals(index.normalize()) or index.has_duplicates or index.hasnans:
        raise DataQualityError("Expected unique daily date labels")
    result.index = index
    return pd.to_numeric(result, errors="raise").sort_index()


def extract_adjusted_close(frame: pd.DataFrame, ticker: str, batch_count: int) -> pd.Series:
    if isinstance(frame.columns, pd.MultiIndex):
        matches = [c for c in frame.columns if "Adj Close" in c and ticker in c]
        if len(matches) != 1:
            raise DataQualityError(f"Missing/ambiguous Adj Close for {ticker}")
        series = frame[matches[0]]
    else:
        if batch_count != 1 or "Adj Close" not in frame:
            raise DataQualityError("Missing Adj Close; unadjusted Close is not a substitute")
        series = frame["Adj Close"]
    return normalize_dates(series)


def decode_price(payload: bytes) -> pd.Series:
    frame = pd.read_csv(BytesIO(payload), index_col="date")
    if list(frame.columns) != ["adj_close"]:
        raise DataQualityError("Unexpected price cache schema")
    return normalize_dates(frame["adj_close"])


def parse_fred(payload: bytes, start: str, end: str) -> pd.Series:
    """Validate raw annual percentage yields; publication lag belongs to phase 3."""
    frame = pd.read_csv(BytesIO(payload), na_values=["."])
    if len(frame.columns) != 2 or frame.columns[0] not in {"DATE", "observation_date"}:
        raise DataQualityError("Unexpected FRED date schema")
    if frame.columns[1] != "DGS3MO":
        raise DataQualityError("Expected FRED DGS3MO series")
    rates = normalize_dates(frame.set_index(frame.columns[0])["DGS3MO"])
    observed = rates.dropna()
    if observed.empty or not np.isfinite(observed).all():
        raise DataQualityError("Empty or nonfinite FRED yields")
    if (observed / 100 <= -1).any():
        raise DataQualityError("FRED yield cannot support daily-rate transformation")
    if observed.index.min() > pd.Timestamp(start):
        raise DataQualityError("FRED lacks pre-sample rate history")
    # The final NYSE session must have a recent past observation; never fabricate it.
    if observed.loc[:end].empty or observed.loc[:end].index.max() < pd.Timestamp(end) - pd.Timedelta(days=7):
        raise DataQualityError("FRED cache/source does not cover the requested end")
    return rates.rename("DGS3MO_percent")


@dataclass
class DownloadBundle:
    selected_universe: pd.DataFrame
    adjusted_prices: pd.DataFrame
    fred_annual_percent: pd.Series | None
    manifest_path: Path


def download_inputs(config: dict, root: str | Path, *, refresh: bool = False) -> DownloadBundle:
    """Future explicit entry point; creates only download artifacts, not results.

    Call only after separate permission to download. root is the repository root.
    A refresh retrieves new vintages; otherwise checksum-validated cache is reused.
    """
    require_supported_mode(config["universe_mode"])
    if config["rf_mode"] not in {"fred_dgs3mo", "zero-sensitivity"}:
        raise ValueError("Unsupported rf_mode; no implicit risk-free fallback")
    root = Path(root).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    manifest_path = root / "data/manifests" / f"{run_id}.json"
    universe_dir = root / "data/universe" / run_id
    client = Downloader(config, root, refresh=refresh)
    manifest = {"schema_version": 1, "run_id": run_id, "status": "started",
                "started_at_utc": utc_now(), "universe_mode": config["universe_mode"],
                "bias_label": BIAS_LABEL, "rf_mode": config["rf_mode"],
                "configuration": config, "artifacts": [], "sources": client.records,
                "events": client.events,
                "limitations": ["future-survivor selection", "post-2005 IPO exclusion",
                                "retrieval-date adjusted-price vintage",
                                "unverified delisting and corporate-action treatment"]}
    save_json(manifest_path, manifest)
    try:
        manifest["package_versions"] = {p: version(p) for p in
                                        ("pandas", "numpy", "yfinance", "exchange_calendars", "requests")}
        calendar = xcals.get_calendar(config["calendar"]["exchange"],
                                     start=config["calendar"]["start"], end=config["calendar"]["end"])
        sessions = calendar.sessions_in_range(config["universe"]["coverage_start"],
                                             config["universe"]["coverage_end"]).tz_localize(None)
        earlier = calendar.sessions_in_range(config["download_start"],
                                             config["initial_training_start"]).tz_localize(None)
        reference = earlier[earlier < sessions[0]][-1]
        url = config["universe"]["current_roster_url"]
        expected_sectors = config["universe"]["current_sector_count"]
        def validate_roster(payload: bytes) -> pd.DataFrame:
            return parse_current_roster(payload.decode("utf-8"), url, "validation_only", expected_sectors)
        payload, source = client.http(url, validate_roster, "current_sp500_roster")
        roster = parse_current_roster(payload.decode("utf-8"), url,
                                      source["retrieved_at_utc"], expected_sectors)
        universe_dir.mkdir(parents=True, exist_ok=True)
        def save_table(name: str, frame: pd.DataFrame) -> None:
            path = universe_dir / name
            frame.to_csv(path, index=False)
            manifest["artifacts"].append({"path": str(path.relative_to(root)),
                                           "sha256": sha256(path.read_bytes()).hexdigest()})
        save_table("roster_before.csv", roster)
        prices, failures = client.fetch_prices(roster.yahoo_ticker.tolist(), sessions, reference)
        availability = []
        for row in roster.itertuples():
            series = prices.get(row.yahoo_ticker, pd.Series(dtype=float, index=pd.DatetimeIndex([])))
            availability.append({"original_ticker": row.original_ticker,
                                 **coverage_record(series, sessions, reference),
                                 "retrieval_errors": json.dumps(failures[row.yahoo_ticker])})
        availability = pd.DataFrame(availability)
        save_table("availability.csv", availability)
        selected, audit, counts = select_survivors(
            roster, availability, config["universe"]["maximum_per_sector"],
            config["universe"]["maximum_total"],
        )
        save_table("roster_after.csv", selected)
        save_table("selection_audit.csv", audit)
        save_table("exclusions.csv", audit.loc[~audit.selected])
        save_table("sector_counts.csv", counts)
        fred = None
        if config["rf_mode"] == "fred_dgs3mo":
            def validate_fred(payload: bytes) -> pd.Series:
                return parse_fred(payload, config["download_start"], config["backtest_end"])
            payload, _ = client.http(config["risk_free"]["url"], validate_fred, "fred_dgs3mo")
            fred = validate_fred(payload)
        else:
            warnings.warn("Explicit zero-sensitivity: no FRED rates downloaded; not the primary experiment")
        matrix = pd.DataFrame({r.original_ticker: prices[r.yahoo_ticker]
                               for r in selected.itertuples()}).sort_index()
        manifest["status"] = "downloads_complete_not_backtested"
        manifest["selected_count"] = len(selected)
        return DownloadBundle(selected, matrix, fred, manifest_path)
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["finished_at_utc"] = utc_now()
        save_json(manifest_path, manifest)
        client.session.close()
