from __future__ import annotations

import pandas as pd

from minicofin_pm.data import load_demo_bundle, validate_bundle
from minicofin_pm.scoring import build_features_at


def test_demo_bundle_passes_blocking_checks() -> None:
    result = validate_bundle(load_demo_bundle())
    assert result.is_usable
    assert "Blocker" not in set(result.checks["status"])


def test_feature_builder_excludes_future_events() -> None:
    bundle = load_demo_bundle()
    as_of = pd.Timestamp("2025-06-30")
    features = build_features_at(bundle.assets, bundle.events, bundle.inspections, as_of)
    future_only_assets = set(
        bundle.events.loc[
            (bundle.events["event_date"] > as_of)
            & (~bundle.events["asset_id"].isin(bundle.events.loc[bundle.events["event_date"] <= as_of, "asset_id"])),
            "asset_id",
        ]
    )
    for asset_id in future_only_assets:
        row = features.loc[features["asset_id"] == asset_id].iloc[0]
        assert row["history_event_count"] == 0


def test_sparse_assets_are_detectable() -> None:
    bundle = load_demo_bundle()
    features = build_features_at(bundle.assets, bundle.events, bundle.inspections, pd.Timestamp("2026-09-29"))
    sparse = features[(features["history_event_count"] == 0) & (features["inspection_count"] == 0)]
    assert len(sparse) >= 1

