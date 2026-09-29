from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import RAW_DIR


REQUIRED_ASSET_COLUMNS = {
    "asset_id",
    "asset_class",
    "make_model",
    "acquisition_date",
    "usage_value",
}
REQUIRED_EVENT_COLUMNS = {
    "event_id",
    "asset_id",
    "event_date",
    "event_type",
    "fault_or_defect",
    "severity",
    "maintenance_cost",
    "downtime_hours",
}
REQUIRED_INSPECTION_COLUMNS = {
    "inspection_id",
    "asset_id",
    "inspection_date",
    "defect",
    "severity",
    "outcome",
}


@dataclass(frozen=True)
class DataBundle:
    assets: pd.DataFrame
    events: pd.DataFrame
    inspections: pd.DataFrame


@dataclass(frozen=True)
class ValidationResult:
    checks: pd.DataFrame
    warnings: tuple[str, ...]
    is_usable: bool


def _read_csv(path: Path, date_columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    return pd.read_csv(path, parse_dates=date_columns)


def load_demo_bundle(raw_dir: Path = RAW_DIR) -> DataBundle:
    return DataBundle(
        assets=_read_csv(raw_dir / "assets.csv", ["acquisition_date"]),
        events=_read_csv(raw_dir / "maintenance_events.csv", ["event_date"]),
        inspections=_read_csv(raw_dir / "inspections.csv", ["inspection_date"]),
    )


def _missing_columns(frame: pd.DataFrame, required: set[str]) -> set[str]:
    return required - set(frame.columns)


def validate_bundle(bundle: DataBundle) -> ValidationResult:
    rows: list[dict[str, object]] = []
    warnings: list[str] = []

    schemas = (
        ("Asset schema", bundle.assets, REQUIRED_ASSET_COLUMNS),
        ("Maintenance schema", bundle.events, REQUIRED_EVENT_COLUMNS),
        ("Inspection schema", bundle.inspections, REQUIRED_INSPECTION_COLUMNS),
    )
    blocker = False
    for name, frame, required in schemas:
        missing = _missing_columns(frame, required)
        passed = not missing
        blocker = blocker or not passed
        rows.append(
            {
                "check": name,
                "status": "Pass" if passed else "Blocker",
                "detail": "Required fields present" if passed else f"Missing: {', '.join(sorted(missing))}",
            }
        )

    if blocker:
        return ValidationResult(pd.DataFrame(rows), tuple(warnings), False)

    duplicate_ids = int(bundle.assets["asset_id"].duplicated().sum())
    rows.append(
        {
            "check": "Unique asset IDs",
            "status": "Pass" if duplicate_ids == 0 else "Blocker",
            "detail": f"{duplicate_ids} duplicate asset IDs",
        }
    )
    blocker = blocker or duplicate_ids > 0

    known_assets = set(bundle.assets["asset_id"])
    event_linkage = float(bundle.events["asset_id"].isin(known_assets).mean()) if len(bundle.events) else 0.0
    inspection_linkage = (
        float(bundle.inspections["asset_id"].isin(known_assets).mean()) if len(bundle.inspections) else 0.0
    )
    for name, value in (("Maintenance linkage", event_linkage), ("Inspection linkage", inspection_linkage)):
        passed = value >= 0.95
        rows.append(
            {
                "check": name,
                "status": "Pass" if passed else "Blocker",
                "detail": f"{value:.1%} linked to a valid asset ID",
            }
        )
        blocker = blocker or not passed

    allowed_event_types = {"scheduled", "corrective", "inspection", "breakdown"}
    invalid_types = sorted(set(bundle.events["event_type"].dropna()) - allowed_event_types)
    rows.append(
        {
            "check": "Event codebook",
            "status": "Pass" if not invalid_types else "Blocker",
            "detail": "Event types valid" if not invalid_types else f"Unsupported: {', '.join(invalid_types)}",
        }
    )
    blocker = blocker or bool(invalid_types)

    impossible_usage = int((bundle.assets["usage_value"].dropna() < 0).sum())
    impossible_cost = int((bundle.events["maintenance_cost"].dropna() < 0).sum())
    plausible = impossible_usage == 0 and impossible_cost == 0
    rows.append(
        {
            "check": "Plausibility",
            "status": "Pass" if plausible else "Blocker",
            "detail": f"{impossible_usage} invalid usage values; {impossible_cost} invalid costs",
        }
    )
    blocker = blocker or not plausible

    critical_fields = ["asset_class", "acquisition_date", "usage_value"]
    completeness = 1.0 - float(bundle.assets[critical_fields].isna().mean().mean())
    rows.append(
        {
            "check": "Critical completeness",
            "status": "Pass" if completeness >= 0.90 else "Manage",
            "detail": f"{completeness:.1%} complete across critical asset fields",
        }
    )
    if completeness < 0.90:
        warnings.append("Critical field completeness is below the 90% prototype target.")

    corrective_share = float(bundle.events["event_type"].isin(["corrective", "breakdown"]).mean())
    rows.append(
        {
            "check": "Corrective label signal",
            "status": "Pass" if corrective_share >= 0.05 else "Manage",
            "detail": f"{corrective_share:.1%} of events are corrective or breakdown",
        }
    )
    if corrective_share < 0.05:
        warnings.append("Corrective outcomes are rare; prefer transparent rule scoring.")

    return ValidationResult(pd.DataFrame(rows), tuple(warnings), not blocker)


def completeness_by_column(bundle: DataBundle) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for source, frame in (
        ("Assets", bundle.assets),
        ("Maintenance", bundle.events),
        ("Inspections", bundle.inspections),
    ):
        for column in frame.columns:
            records.append(
                {
                    "source": source,
                    "field": column,
                    "complete_pct": round(100 * (1 - frame[column].isna().mean()), 1),
                }
            )
    return pd.DataFrame(records)


def normalize_uploaded_frame(uploaded_file, expected: str) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(uploaded_file)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(uploaded_file)
    else:
        raise ValueError("Use CSV or Excel (.xlsx/.xls) files.")
    frame.columns = [str(c).strip().lower().replace(" ", "_") for c in frame.columns]
    required = {
        "assets": REQUIRED_ASSET_COLUMNS,
        "events": REQUIRED_EVENT_COLUMNS,
        "inspections": REQUIRED_INSPECTION_COLUMNS,
    }[expected]
    missing = _missing_columns(frame, required)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
    return frame

