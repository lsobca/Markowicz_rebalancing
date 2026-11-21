"""Universe parsing and deterministic selection; no network or import-time I/O.

Current membership and full-period availability are deliberately hindsight-biased.
Historical adapters are unavailable until a dated source is independently verified.
"""
from __future__ import annotations

from io import StringIO
import re

import numpy as np
import pandas as pd


class SourceUnavailableError(RuntimeError):
    """A required verified data source is unavailable; never switch tiers."""


class DataQualityError(ValueError):
    """Source schema or coverage cannot support the configured experiment."""


HISTORICAL_MODES = {"historical_top_cap_2010", "historical_roster_2010"}
BIAS_LABEL = "illustrative survivors-only"


def require_supported_mode(mode: str) -> None:
    if mode in HISTORICAL_MODES:
        raise SourceUnavailableError(
            f"{mode}: no verified historical source adapter is available. Obtain "
            "documented 2010-12-31 membership, contemporaneous identifiers and "
            "GICS sectors, complete 2005-2010 history and verified delisting "
            "returns/payouts (plus 2010 market caps for historical_top_cap_2010). "
            "Assess CRSP/WRDS or a licensed vendor, then implement a reviewed "
            "adapter. A configuration path alone is not verification. "
            "No automatic survivors-only fallback is permitted."
        )
    if mode != "current_survivors_only":
        raise ValueError(f"Unknown universe_mode: {mode!r}")


def parse_current_roster(html: str, source_url: str, retrieved_at: str,
                         expected_sectors: int = 11) -> pd.DataFrame:
    """Parse the current constituent table, preserving original symbols and CIK.

    CIK is used only as a current issuer key, never a historical security ID.
    The Wikipedia 'Founded' and 'Date added' fields are NOT IPO dates.
    """
    required = {"Symbol", "Security", "GICS Sector", "CIK"}
    tables = pd.read_html(StringIO(html), converters={"CIK": str})
    matching = [t for t in tables if required.issubset(t.columns)]
    if len(matching) != 1:
        raise DataQualityError("Expected exactly one current S&P 500 constituent table")
    roster = matching[0].rename(columns={
        "Symbol": "original_ticker", "Security": "security_name",
        "GICS Sector": "sector", "CIK": "issuer_id",
    })[["original_ticker", "security_name", "sector", "issuer_id"]].copy()
    if roster.empty or roster.isna().any().any():
        raise DataQualityError("Empty roster or missing required constituent fields")
    for column in roster:
        roster[column] = roster[column].astype(str).str.strip()
        if roster[column].eq("").any():
            raise DataQualityError(f"Empty constituent field: {column}")
    if not roster["original_ticker"].map(
        lambda s: bool(re.fullmatch(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*", s))
    ).all():
        raise DataQualityError("Unexpected ticker syntax; review source schema")
    if not roster["issuer_id"].str.fullmatch(r"\d{1,10}").all():
        raise DataQualityError("Invalid current CIK issuer identifiers")
    roster["issuer_id"] = roster["issuer_id"].str.zfill(10)
    roster["yahoo_ticker"] = roster["original_ticker"].str.replace(".", "-", regex=False)
    if (roster["original_ticker"].duplicated().any()
            or roster["yahoo_ticker"].duplicated().any()):
        raise DataQualityError("Duplicate or colliding ticker mapping")
    if roster["sector"].nunique() != expected_sectors:
        raise DataQualityError("Unexpected current GICS sector count; review source")
    if (roster.groupby("issuer_id")["sector"].nunique() > 1).any():
        raise DataQualityError("Conflicting sectors for a current issuer")
    roster["source_url"] = source_url
    roster["retrieved_at_utc"] = retrieved_at
    roster["universe_mode"] = "current_survivors_only"
    roster["bias_label"] = BIAS_LABEL
    return roster.sort_values("original_ticker").reset_index(drop=True)


def coverage_record(prices: pd.Series, sessions: pd.DatetimeIndex,
                    reference_session: pd.Timestamp) -> dict:
    """Availability screening only; cleaning/returns belong to phase 3.

    No IPO or delisting is inferred as a fact from a short price history.
    Reference coverage is required to obtain the first 2005 daily return.
    """
    if prices.index.has_duplicates:
        raise DataQualityError("Duplicate daily price observations")
    numeric = pd.to_numeric(prices, errors="raise")
    valid = numeric.notna() & np.isfinite(numeric) & numeric.gt(0)
    available = numeric.loc[valid]
    expected = numeric.reindex(sessions)
    good = expected.notna() & np.isfinite(expected) & expected.gt(0)
    reference = numeric.get(reference_session, float("nan"))
    reference_ok = bool(pd.notna(reference) and np.isfinite(reference) and reference > 0)
    first = available.index.min() if not available.empty else None
    last = available.index.max() if not available.empty else None
    training = good.loc[:"2010-12-31"]
    evaluation = good.loc["2011-01-01":]
    return {
        "first_valid_date": first.date().isoformat() if first is not None else None,
        "last_valid_date": last.date().isoformat() if last is not None else None,
        "missing_or_invalid_sessions": int((~good).sum()),
        "complete_2005_2010": bool(training.all()),
        "complete_2011_2025": bool(evaluation.all()),
        "reference_price_available": reference_ok,
        "eligible_history": bool(good.all() and reference_ok),
        "late_start_or_missing_early_history": first is None or first > sessions[0],
        "early_end_or_missing_recent_history": last is None or last < sessions[-1],
        "ipo_status": "unknown_not_verified",
        "delisting_status": "unknown_not_verified",
        "corporate_action_status": "vendor_adjusted_not_independently_verified",
    }


def select_survivors(roster: pd.DataFrame, availability: pd.DataFrame,
                     per_sector: int = 10, maximum_total: int = 100
                     ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Screen the ENTIRE roster before issuer deduplication and round-robin."""
    if not 0 < per_sector <= 10 or not 0 < maximum_total <= 100:
        raise ValueError("Selection limits must be positive and at most 10/100")
    if availability["original_ticker"].duplicated().any():
        raise DataQualityError("Duplicate availability records")
    if set(roster.original_ticker) != set(availability.original_ticker):
        raise DataQualityError("Availability must cover exactly the entire roster")
    audit = roster.merge(availability, on="original_ticker", validate="one_to_one")
    if not audit["eligible_history"].map(lambda v: isinstance(v, (bool, np.bool_))).all():
        raise DataQualityError("Eligibility must contain explicit booleans")
    audit = audit.sort_values("original_ticker").reset_index(drop=True)
    audit["selection_reason"] = "incomplete_or_invalid_history"
    eligible = audit.loc[audit.eligible_history].copy()
    # Keep the alphabetically first fully covered share class for each issuer.
    duplicates = eligible.issuer_id.duplicated(keep="first")
    audit.loc[eligible.index, "selection_reason"] = "sector_or_global_limit"
    audit.loc[eligible.index[duplicates], "selection_reason"] = "duplicate_issuer_share_class"
    eligible = eligible.loc[~duplicates]
    groups = {s: g.index.tolist() for s, g in eligible.groupby("sector", sort=True)}
    chosen: list[int] = []
    for rank in range(per_sector):
        for sector in sorted(groups):
            if len(chosen) == maximum_total:
                break
            if rank < len(groups[sector]):
                chosen.append(groups[sector][rank])
    if not chosen:
        raise DataQualityError("No eligible issuers after full-history screening")
    audit["selected"] = audit.index.isin(chosen)
    audit.loc[chosen, "selection_reason"] = "selected"
    selected = audit.loc[chosen].reset_index(drop=True)
    counts = (audit.groupby("sector", sort=True)["selected"].sum()
              .astype(int).rename("selected_count").reset_index())
    return selected, audit, counts
