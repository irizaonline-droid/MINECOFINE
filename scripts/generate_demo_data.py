"""Create a deterministic, clearly labeled synthetic dataset for the rapid MVP."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from minicofin_pm.config import RANDOM_SEED, RAW_DIR, ensure_directories


CLASS_CONFIG = {
    "Sedan": {
        "models": ["Toyota Corolla", "Toyota RAV4", "Nissan Sunny"],
        "usage_range": (38_000, 185_000),
        "faults": ["brake wear", "cooling system", "battery", "suspension", "electrical"],
    },
    "Pickup": {
        "models": ["Toyota Hilux", "Ford Ranger", "Isuzu D-Max"],
        "usage_range": (52_000, 245_000),
        "faults": ["suspension", "brake wear", "drivetrain", "cooling system", "tyre wear"],
    },
    "Motorcycle": {
        "models": ["Yamaha AG125", "Honda XR150", "TVS HLX"],
        "usage_range": (18_000, 96_000),
        "faults": ["chain wear", "brake wear", "electrical", "tyre wear", "fuel system"],
    },
    "Generator": {
        "models": ["Perkins 45kVA", "Cummins 60kVA", "FG Wilson 50kVA"],
        "usage_range": (2_200, 14_500),
        "faults": ["fuel system", "cooling system", "alternator", "starter motor", "oil pressure"],
    },
}


def generate_assets(rng: np.random.Generator, count: int = 180) -> pd.DataFrame:
    classes = rng.choice(list(CLASS_CONFIG), size=count, p=[0.37, 0.31, 0.18, 0.14])
    acquisition_dates = pd.to_datetime(
        rng.integers(pd.Timestamp("2012-01-01").value // 10**9, pd.Timestamp("2024-06-01").value // 10**9, size=count),
        unit="s",
    ).normalize()
    records = []
    for index, (asset_class, acquisition_date) in enumerate(zip(classes, acquisition_dates), start=1):
        config = CLASS_CONFIG[asset_class]
        usage = float(rng.integers(*config["usage_range"]))
        if rng.random() < 0.045 or index == count:
            usage = np.nan
        records.append(
            {
                "asset_id": f"GOV-{index:04d}",
                "asset_class": asset_class,
                "make_model": rng.choice(config["models"]),
                "acquisition_date": acquisition_date.date().isoformat(),
                "usage_value": usage,
                "institution": "Demo Public Institution",
                "dataset_mode": "SIMULATED DEMO DATA",
                "latent_condition": round(float(rng.beta(2.2, 3.0)), 4),
            }
        )
    return pd.DataFrame(records)


def generate_history(assets: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    maintenance: list[dict[str, object]] = []
    inspections: list[dict[str, object]] = []
    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2026-09-20")
    maintenance_id = 1
    inspection_id = 1

    for asset in assets.itertuples(index=False):
        # Keep two assets deliberately sparse to exercise the manual-review safeguard.
        if asset.asset_id in {"GOV-0179", "GOV-0180"}:
            continue
        acquired = pd.Timestamp(asset.acquisition_date)
        active_start = max(start, acquired)
        age_years = max((end - acquired).days / 365.25, 0.5)
        latent = float(asset.latent_condition)
        class_multiplier = {"Sedan": 1.0, "Pickup": 1.18, "Motorcycle": 0.92, "Generator": 1.12}[asset.asset_class]

        service_interval = int(rng.integers(105, 170))
        service_date = active_start + pd.Timedelta(days=int(rng.integers(10, service_interval)))
        while service_date <= end:
            maintenance.append(
                {
                    "event_id": f"M-{maintenance_id:06d}",
                    "asset_id": asset.asset_id,
                    "event_date": service_date.date().isoformat(),
                    "event_type": "scheduled",
                    "fault_or_defect": "routine service",
                    "severity": "none",
                    "maintenance_cost": int(rng.integers(55_000, 175_000)),
                    "downtime_hours": int(rng.integers(2, 9)),
                    "dataset_mode": "SIMULATED DEMO DATA",
                }
            )
            maintenance_id += 1
            service_date += pd.Timedelta(days=service_interval + int(rng.integers(-18, 26)))

        months_active = max((end.year - active_start.year) * 12 + end.month - active_start.month, 1)
        base_rate = 0.035 + 0.055 * latent + 0.006 * max(age_years - 5, 0)
        expected_events = months_active * base_rate * class_multiplier
        corrective_count = int(rng.poisson(expected_events))
        corrective_dates: list[pd.Timestamp] = []
        for _ in range(corrective_count):
            day_offset = int(rng.integers(0, max((end - active_start).days, 1)))
            event_date = active_start + pd.Timedelta(days=day_offset)
            corrective_dates.append(event_date)
            if rng.random() < 0.24 + latent * 0.26:
                repeat_gap = int(rng.integers(14, 70))
                if event_date + pd.Timedelta(days=repeat_gap) <= end:
                    corrective_dates.append(event_date + pd.Timedelta(days=repeat_gap))

        last_fault = None
        for event_date in sorted(corrective_dates):
            faults = CLASS_CONFIG[asset.asset_class]["faults"]
            if last_fault and rng.random() < 0.38:
                fault = last_fault
            else:
                fault = str(rng.choice(faults))
            last_fault = fault
            breakdown_probability = min(0.08 + latent * 0.20 + max(age_years - 8, 0) * 0.015, 0.42)
            event_type = "breakdown" if rng.random() < breakdown_probability else "corrective"
            severity = rng.choice(
                ["low", "medium", "high", "critical"],
                p=[0.28, 0.40, 0.24, 0.08] if event_type == "corrective" else [0.05, 0.25, 0.45, 0.25],
            )
            severity_factor = {"low": 1, "medium": 1.8, "high": 3.3, "critical": 5.5}[severity]
            maintenance.append(
                {
                    "event_id": f"M-{maintenance_id:06d}",
                    "asset_id": asset.asset_id,
                    "event_date": event_date.date().isoformat(),
                    "event_type": event_type,
                    "fault_or_defect": fault,
                    "severity": severity,
                    "maintenance_cost": int(rng.integers(75_000, 260_000) * severity_factor),
                    "downtime_hours": int(rng.integers(4, 18) * severity_factor),
                    "dataset_mode": "SIMULATED DEMO DATA",
                }
            )
            maintenance_id += 1

        inspection_interval = int(rng.integers(95, 155))
        inspection_date = active_start + pd.Timedelta(days=int(rng.integers(5, inspection_interval)))
        while inspection_date <= end:
            nearby_failure = any(abs((date - inspection_date).days) <= 50 for date in corrective_dates)
            if nearby_failure:
                severity = str(rng.choice(["medium", "high", "critical"], p=[0.40, 0.45, 0.15]))
                outcome = "repair recommended"
                defect = str(rng.choice(CLASS_CONFIG[asset.asset_class]["faults"]))
            else:
                severity = str(rng.choice(["none", "low", "medium"], p=[0.62, 0.28, 0.10]))
                outcome = "serviceable" if severity == "none" else "monitor"
                defect = "none" if severity == "none" else str(rng.choice(CLASS_CONFIG[asset.asset_class]["faults"]))
            inspections.append(
                {
                    "inspection_id": f"I-{inspection_id:06d}",
                    "asset_id": asset.asset_id,
                    "inspection_date": inspection_date.date().isoformat(),
                    "defect": defect,
                    "severity": severity,
                    "outcome": outcome,
                    "dataset_mode": "SIMULATED DEMO DATA",
                }
            )
            inspection_id += 1
            inspection_date += pd.Timedelta(days=inspection_interval + int(rng.integers(-12, 22)))

    return pd.DataFrame(maintenance), pd.DataFrame(inspections)


def main() -> None:
    ensure_directories()
    rng = np.random.default_rng(RANDOM_SEED)
    assets = generate_assets(rng)
    events, inspections = generate_history(assets, rng)
    assets.drop(columns=["latent_condition"]).to_csv(RAW_DIR / "assets.csv", index=False)
    events.sort_values(["event_date", "asset_id"]).to_csv(RAW_DIR / "maintenance_events.csv", index=False)
    inspections.sort_values(["inspection_date", "asset_id"]).to_csv(RAW_DIR / "inspections.csv", index=False)
    print(
        f"Generated {len(assets)} assets, {len(events)} maintenance events, "
        f"and {len(inspections)} inspections in {RAW_DIR}."
    )


if __name__ == "__main__":
    main()

