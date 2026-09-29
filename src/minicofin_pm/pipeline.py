from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import MODEL_DIR, MODEL_FEATURES, PROCESSED_DIR, SCORING_DATE, ensure_directories
from .data import DataBundle, load_demo_bundle, validate_bundle
from .scoring import add_future_label, build_features_at, explain_scores, weighted_rule_score


@dataclass(frozen=True)
class ModelMetric:
    model: str
    recall: float
    precision: float
    pr_auc: float
    alert_rate: float
    threshold: float


def _snapshot_dates() -> list[pd.Timestamp]:
    return list(pd.date_range("2025-01-31", "2026-07-31", freq="ME"))


def build_training_table(bundle: DataBundle) -> pd.DataFrame:
    snapshots = []
    for snapshot_date in _snapshot_dates():
        features = build_features_at(bundle.assets, bundle.events, bundle.inspections, snapshot_date)
        snapshots.append(add_future_label(features, bundle.events))
    return pd.concat(snapshots, ignore_index=True)


def _threshold_for_recall(y_true: pd.Series, probabilities: np.ndarray, target: float = 0.80) -> float:
    candidates = np.linspace(0.15, 0.80, 66)
    accepted = [t for t in candidates if recall_score(y_true, probabilities >= t, zero_division=0) >= target]
    return float(max(accepted)) if accepted else 0.35


def _metric(name: str, y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> ModelMetric:
    predictions = probabilities >= threshold
    return ModelMetric(
        model=name,
        recall=float(recall_score(y_true, predictions, zero_division=0)),
        precision=float(precision_score(y_true, predictions, zero_division=0)),
        pr_auc=float(average_precision_score(y_true, probabilities)),
        alert_rate=float(np.mean(predictions)),
        threshold=float(threshold),
    )


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        steps=[("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
    )
    categories = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric, MODEL_FEATURES),
            ("category", categories, ["asset_class"]),
        ]
    )


def _model_pipeline(estimator) -> Pipeline:
    return Pipeline(steps=[("prepare", _preprocessor()), ("model", estimator)])


def train_and_select(training: pd.DataFrame) -> tuple[Pipeline, ModelMetric, list[ModelMetric]]:
    split_date = pd.Timestamp("2026-03-31")
    train = training[pd.to_datetime(training["scoring_date"]) < split_date]
    holdout = training[pd.to_datetime(training["scoring_date"]) >= split_date]
    feature_columns = MODEL_FEATURES + ["asset_class"]
    target = "corrective_event_next_60d"

    candidates: dict[str, Pipeline] = {
        "Logistic regression": _model_pipeline(
            LogisticRegression(max_iter=1500, class_weight="balanced", random_state=42)
        ),
        "Random forest": _model_pipeline(
            RandomForestClassifier(
                n_estimators=220,
                max_depth=8,
                min_samples_leaf=4,
                class_weight="balanced_subsample",
                random_state=42,
                n_jobs=-1,
            )
        ),
    }
    metrics: list[ModelMetric] = []
    fitted: dict[str, Pipeline] = {}

    rule_prob = weighted_rule_score(holdout) / 100
    rule_threshold = _threshold_for_recall(holdout[target], rule_prob)
    metrics.append(_metric("Weighted rules", holdout[target], rule_prob, rule_threshold))

    for name, model in candidates.items():
        model.fit(train[feature_columns], train[target])
        probabilities = model.predict_proba(holdout[feature_columns])[:, 1]
        threshold = _threshold_for_recall(holdout[target], probabilities)
        metrics.append(_metric(name, holdout[target], probabilities, threshold))
        fitted[name] = model

    model_metrics = [metric for metric in metrics if metric.model in fitted]
    selected_metric = max(model_metrics, key=lambda item: (item.pr_auc, item.precision, item.recall))
    selected_model = fitted[selected_metric.model]
    selected_model.fit(training[feature_columns], training[target])
    return selected_model, selected_metric, metrics


def run_pipeline(bundle: DataBundle | None = None) -> dict[str, object]:
    ensure_directories()
    bundle = bundle or load_demo_bundle()
    validation = validate_bundle(bundle)
    if not validation.is_usable:
        blockers = validation.checks[validation.checks["status"] == "Blocker"]
        raise ValueError(f"Data validation failed: {blockers.to_dict(orient='records')}")

    training = build_training_table(bundle)
    model, selected_metric, metrics = train_and_select(training)
    feature_columns = MODEL_FEATURES + ["asset_class"]
    current = build_features_at(bundle.assets, bundle.events, bundle.inspections, pd.Timestamp(SCORING_DATE))
    model_probability = model.predict_proba(current[feature_columns])[:, 1]
    rule_probability = weighted_rule_score(current) / 100
    current["model_probability"] = model_probability
    current["rule_score"] = np.round(rule_probability * 100, 1)
    blended_probability = np.clip(0.72 * model_probability + 0.28 * rule_probability, 0, 1)
    # Stretch the center of the demo score while preserving rank. This makes fixed
    # operational bands useful without presenting the value as a calibrated failure probability.
    current["risk_score"] = np.round(100 / (1 + np.exp(-7 * (blended_probability - 0.36))), 1)
    scored = explain_scores(current).sort_values("risk_score", ascending=False, na_position="last")

    generated_at = datetime.now(timezone.utc).isoformat()
    metrics_payload = {
        "dataset_mode": "SIMULATED DEMO DATA",
        "generated_at_utc": generated_at,
        "scoring_date": SCORING_DATE,
        "selected_model": selected_metric.model,
        "selected_threshold": selected_metric.threshold,
        "holdout_strategy": "Time-based: snapshots from 2026-03-31 onward",
        "metrics": [asdict(metric) for metric in metrics],
        "training_rows": int(len(training)),
        "assets_scored": int(len(scored)),
        "positive_rate": float(training["corrective_event_next_60d"].mean()),
        "data_quality_warnings": list(validation.warnings),
    }

    current.to_csv(PROCESSED_DIR / "asset_features.csv", index=False)
    scored.to_csv(PROCESSED_DIR / "risk_scores.csv", index=False)
    training.to_csv(PROCESSED_DIR / "training_snapshots.csv", index=False)
    validation.checks.to_csv(PROCESSED_DIR / "data_quality_checks.csv", index=False)
    with (PROCESSED_DIR / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics_payload, handle, indent=2)
    joblib.dump(
        {"model": model, "feature_columns": feature_columns, "metadata": metrics_payload},
        MODEL_DIR / "risk_model.joblib",
    )
    return {"scores": scored, "metrics": metrics_payload, "validation": validation.checks}


def load_outputs() -> tuple[pd.DataFrame, dict[str, object]]:
    scores_path = PROCESSED_DIR / "risk_scores.csv"
    metrics_path = PROCESSED_DIR / "metrics.json"
    if not scores_path.exists() or not metrics_path.exists():
        run_pipeline()
    scores = pd.read_csv(
        scores_path,
        parse_dates=["acquisition_date", "last_service_date", "last_corrective_date", "last_inspection_date", "scoring_date"],
    )
    with metrics_path.open("r", encoding="utf-8") as handle:
        metrics = json.load(handle)
    return scores, metrics

