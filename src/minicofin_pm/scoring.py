from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from .config import RISK_THRESHOLDS


SEVERITY_MAP = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _safe_days(delta: pd.Series, default: int = 999) -> pd.Series:
    return delta.dt.days.fillna(default).clip(lower=0)


def build_features_at(
    assets: pd.DataFrame,
    events: pd.DataFrame,
    inspections: pd.DataFrame,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of).normalize()
    base = assets.copy()
    base["acquisition_date"] = pd.to_datetime(base["acquisition_date"], errors="coerce")
    base["asset_age_years"] = ((as_of - base["acquisition_date"]).dt.days / 365.25).clip(lower=0)

    past_events = events[pd.to_datetime(events["event_date"]) <= as_of].copy()
    past_events["event_date"] = pd.to_datetime(past_events["event_date"])
    corrective = past_events[past_events["event_type"].isin(["corrective", "breakdown"])].copy()
    scheduled = past_events[past_events["event_type"] == "scheduled"].copy()
    past_inspections = inspections[pd.to_datetime(inspections["inspection_date"]) <= as_of].copy()
    past_inspections["inspection_date"] = pd.to_datetime(past_inspections["inspection_date"])

    def last_date(frame: pd.DataFrame, date_col: str, name: str) -> pd.DataFrame:
        return frame.groupby("asset_id", as_index=False)[date_col].max().rename(columns={date_col: name})

    base = base.merge(last_date(scheduled, "event_date", "last_service_date"), on="asset_id", how="left")
    base = base.merge(last_date(corrective, "event_date", "last_corrective_date"), on="asset_id", how="left")
    base = base.merge(
        last_date(past_inspections, "inspection_date", "last_inspection_date"), on="asset_id", how="left"
    )
    base["days_since_service"] = _safe_days(as_of - base["last_service_date"])
    base["days_since_corrective"] = _safe_days(as_of - base["last_corrective_date"])
    base["days_since_inspection"] = _safe_days(as_of - base["last_inspection_date"])

    def window_aggregate(days: int) -> pd.DataFrame:
        cutoff = as_of - pd.Timedelta(days=days)
        window = corrective[corrective["event_date"] > cutoff].copy()
        if window.empty:
            return pd.DataFrame(columns=["asset_id"])
        aggregates = window.groupby("asset_id", as_index=False).agg(
            repairs=("event_id", "count"),
            corrective_cost=("maintenance_cost", "sum"),
            downtime_hours=("downtime_hours", "sum"),
        )
        repeat_fault = (
            window.groupby(["asset_id", "fault_or_defect"]).size().groupby("asset_id").max().rename("repeat_fault_count")
        )
        aggregates = aggregates.merge(repeat_fault, on="asset_id", how="left")
        return aggregates.rename(
            columns={
                "repairs": f"repairs_{days}d",
                "corrective_cost": f"corrective_cost_{days}d",
                "downtime_hours": f"downtime_hours_{days}d",
                "repeat_fault_count": f"repeat_fault_count_{days}d",
            }
        )

    for days in (90, 180):
        base = base.merge(window_aggregate(days), on="asset_id", how="left")

    severity_events = corrective[corrective["event_date"] > as_of - pd.Timedelta(days=180)].copy()
    severity_events["severity_value"] = severity_events["severity"].astype(str).str.lower().map(SEVERITY_MAP).fillna(0)
    severity_inspections = past_inspections[
        past_inspections["inspection_date"] > as_of - pd.Timedelta(days=180)
    ].copy()
    severity_inspections["severity_value"] = (
        severity_inspections["severity"].astype(str).str.lower().map(SEVERITY_MAP).fillna(0)
    )
    severity = pd.concat(
        [
            severity_events[["asset_id", "severity_value"]],
            severity_inspections[["asset_id", "severity_value"]],
        ],
        ignore_index=True,
    )
    severity_max = severity.groupby("asset_id", as_index=False)["severity_value"].max().rename(
        columns={"severity_value": "max_severity_180d"}
    )
    base = base.merge(severity_max, on="asset_id", how="left")

    event_counts = past_events.groupby("asset_id").size().rename("history_event_count")
    inspection_counts = past_inspections.groupby("asset_id").size().rename("inspection_count")
    base = base.merge(event_counts, on="asset_id", how="left").merge(inspection_counts, on="asset_id", how="left")

    age_days = ((as_of - base["acquisition_date"]).dt.days).clip(lower=1)
    estimated_usage_at_date = base["usage_value"] * (age_days / ((pd.Timestamp("2026-09-29") - base["acquisition_date"]).dt.days.clip(lower=1)))
    daily_usage = estimated_usage_at_date / age_days
    base["usage_since_service"] = (daily_usage * base["days_since_service"].clip(upper=730)).clip(lower=0)
    base["missing_usage_flag"] = base["usage_value"].isna().astype(int)
    base["stale_inspection_flag"] = (base["days_since_inspection"] > 180).astype(int)

    numeric_fill_zero = [
        "repairs_90d",
        "repairs_180d",
        "corrective_cost_90d",
        "corrective_cost_180d",
        "downtime_hours_90d",
        "downtime_hours_180d",
        "repeat_fault_count_90d",
        "repeat_fault_count_180d",
        "max_severity_180d",
        "history_event_count",
        "inspection_count",
    ]
    for column in numeric_fill_zero:
        if column not in base:
            base[column] = 0
        base[column] = pd.to_numeric(base[column], errors="coerce").fillna(0)
    base["usage_since_service"] = base["usage_since_service"].fillna(0)
    base["scoring_date"] = as_of
    return base


def add_future_label(features: pd.DataFrame, events: pd.DataFrame, horizon_days: int = 60) -> pd.DataFrame:
    result = features.copy()
    as_of = pd.Timestamp(result["scoring_date"].iloc[0])
    future = events[
        (pd.to_datetime(events["event_date"]) > as_of)
        & (pd.to_datetime(events["event_date"]) <= as_of + pd.Timedelta(days=horizon_days))
        & (events["event_type"].isin(["corrective", "breakdown"]))
    ]
    positive_assets = set(future["asset_id"])
    result["corrective_event_next_60d"] = result["asset_id"].isin(positive_assets).astype(int)
    return result


def weighted_rule_score(features: pd.DataFrame) -> np.ndarray:
    frame = features.copy()
    class_group = frame.groupby("asset_class", dropna=False)
    usage_pct = class_group["usage_since_service"].rank(pct=True).fillna(0.5)
    cost_pct = class_group["corrective_cost_180d"].rank(pct=True).fillna(0.5)
    age_pct = class_group["asset_age_years"].rank(pct=True).fillna(0.5)

    score = (
        frame["repairs_90d"].clip(0, 3) * 10
        + (frame["repeat_fault_count_180d"] >= 2).astype(float) * 10
        + frame["max_severity_180d"].clip(0, 4) * 7
        + usage_pct * 10
        + cost_pct * 8
        + age_pct * 6
        + frame["stale_inspection_flag"].astype(float) * 8
    )
    return np.clip(score, 0, 100).to_numpy(dtype=float)


def assign_risk_band(score: float, manual_review: bool = False) -> str:
    if manual_review or math.isnan(float(score)):
        return "Manual review"
    for band in ("Critical", "High", "Watch", "Normal"):
        if score >= RISK_THRESHOLDS[band]:
            return band
    return "Normal"


def build_reason_codes(row: pd.Series) -> list[str]:
    reasons: list[tuple[float, str]] = []
    if row.get("repairs_90d", 0) > 0:
        value = int(row["repairs_90d"])
        reasons.append((30 + value, f"{value} corrective repair{'s' if value != 1 else ''} in 90 days"))
    if row.get("repeat_fault_count_180d", 0) >= 2:
        reasons.append((29, "Repeated fault pattern in the last 180 days"))
    severity = int(row.get("max_severity_180d", 0))
    if severity >= 3:
        label = "Critical" if severity >= 4 else "High"
        reasons.append((28 + severity, f"{label.lower()} defect severity recorded recently"))
    if row.get("corrective_cost_180d", 0) >= 350_000:
        reasons.append((24, "Corrective maintenance cost is rising"))
    if row.get("usage_since_service", 0) >= 6_000:
        reasons.append((22, "Usage since last service is high"))
    if row.get("days_since_service", 0) >= 180:
        reasons.append((20, f"Last recorded service was {int(row['days_since_service'])} days ago"))
    if row.get("downtime_hours_180d", 0) >= 24:
        reasons.append((18, "Recent downtime exceeds 24 hours"))
    if row.get("asset_age_years", 0) >= 8:
        reasons.append((12, "Asset age is above eight years"))
    if row.get("stale_inspection_flag", 0) == 1:
        reasons.append((10, "Inspection record is older than 180 days"))
    if row.get("missing_usage_flag", 0) == 1:
        reasons.append((9, "Usage reading is missing"))
    if not reasons:
        reasons.append((1, "No elevated maintenance signal detected"))
    return [reason for _, reason in sorted(reasons, reverse=True)[:3]]


def recommended_action(band: str, reasons: Iterable[str]) -> str:
    reason_text = " ".join(reasons).lower()
    if band == "Manual review":
        return "Verify asset identity and missing records before scoring"
    if band == "Critical":
        return "Inspect within 24 hours; restrict use if a safety defect is confirmed"
    if band == "High":
        if "usage" in reason_text:
            return "Inspect within 48 hours and verify the current usage reading"
        return "Inspect within 48 hours and verify the reported fault"
    if band == "Watch":
        return "Review within 7 days and monitor the next inspection cycle"
    return "Continue scheduled maintenance and monitor monthly"


def explain_scores(scored: pd.DataFrame) -> pd.DataFrame:
    output = scored.copy()
    manual_review = (output["history_event_count"] == 0) & (output["inspection_count"] == 0)
    output["risk_band"] = [
        assign_risk_band(score, bool(review)) for score, review in zip(output["risk_score"], manual_review)
    ]
    reason_lists = [build_reason_codes(row) for _, row in output.iterrows()]
    for idx in range(3):
        output[f"reason_{idx + 1}"] = [reasons[idx] if len(reasons) > idx else "" for reasons in reason_lists]
    output["recommended_action"] = [
        recommended_action(band, reasons) for band, reasons in zip(output["risk_band"], reason_lists)
    ]
    output.loc[manual_review, "risk_score"] = np.nan
    return output

