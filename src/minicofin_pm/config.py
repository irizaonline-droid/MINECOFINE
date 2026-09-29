from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "demo"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = PROJECT_ROOT / "models"
ASSET_DIR = PROJECT_ROOT / "assets"
OUTPUT_DIR = PROJECT_ROOT / "output"

SCORING_DATE = "2026-09-29"
RANDOM_SEED = 42

RISK_THRESHOLDS = {
    "Critical": 80,
    "High": 60,
    "Watch": 35,
    "Normal": 0,
}

RISK_COLORS = {
    "Critical": "#DC4C64",
    "High": "#F59E0B",
    "Watch": "#0F8C7C",
    "Normal": "#2C6E9E",
    "Manual review": "#74839A",
}

MODEL_FEATURES = [
    "asset_age_years",
    "days_since_service",
    "days_since_corrective",
    "repairs_90d",
    "repairs_180d",
    "repeat_fault_count_180d",
    "max_severity_180d",
    "corrective_cost_180d",
    "downtime_hours_180d",
    "usage_since_service",
    "missing_usage_flag",
    "stale_inspection_flag",
]


def ensure_directories() -> None:
    for directory in (RAW_DIR, PROCESSED_DIR, MODEL_DIR, ASSET_DIR, OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

