from __future__ import annotations

import pandas as pd

from minicofin_pm.pipeline import load_outputs
from minicofin_pm.scoring import assign_risk_band, build_reason_codes, explain_scores


def test_risk_band_boundaries() -> None:
    assert assign_risk_band(80) == "Critical"
    assert assign_risk_band(60) == "High"
    assert assign_risk_band(35) == "Watch"
    assert assign_risk_band(34.9) == "Normal"
    assert assign_risk_band(50, manual_review=True) == "Manual review"


def test_reasons_match_visible_features() -> None:
    row = pd.Series(
        {
            "repairs_90d": 3,
            "repeat_fault_count_180d": 2,
            "max_severity_180d": 4,
            "corrective_cost_180d": 500_000,
            "usage_since_service": 8_500,
            "days_since_service": 220,
            "downtime_hours_180d": 30,
            "asset_age_years": 9,
            "stale_inspection_flag": 1,
            "missing_usage_flag": 0,
        }
    )
    reasons = build_reason_codes(row)
    assert len(reasons) == 3
    assert any("corrective" in reason.lower() for reason in reasons)
    assert any("severity" in reason.lower() for reason in reasons)


def test_published_scores_are_bounded_and_explained() -> None:
    scores, _ = load_outputs()
    scored = scores["risk_score"].dropna()
    assert scored.between(0, 100).all()
    assert scores["reason_1"].fillna("").str.len().gt(0).all()
    assert scores["recommended_action"].fillna("").str.len().gt(0).all()
    assert scores["risk_score"].dropna().is_monotonic_decreasing


def test_no_history_forces_manual_review() -> None:
    frame = pd.DataFrame(
        [
            {
                "risk_score": 82.0,
                "history_event_count": 0,
                "inspection_count": 0,
                "repairs_90d": 0,
                "repeat_fault_count_180d": 0,
                "max_severity_180d": 0,
                "corrective_cost_180d": 0,
                "usage_since_service": 0,
                "days_since_service": 999,
                "downtime_hours_180d": 0,
                "asset_age_years": 2,
                "stale_inspection_flag": 1,
                "missing_usage_flag": 1,
            }
        ]
    )
    result = explain_scores(frame)
    assert result.loc[0, "risk_band"] == "Manual review"
    assert pd.isna(result.loc[0, "risk_score"])
    assert "Verify" in result.loc[0, "recommended_action"]

