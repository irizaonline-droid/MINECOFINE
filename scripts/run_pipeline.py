from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from minicofin_pm.pipeline import run_pipeline


if __name__ == "__main__":
    result = run_pipeline()
    metrics = result["metrics"]
    print(
        f"Scored {metrics['assets_scored']} assets with {metrics['selected_model']} "
        f"using {metrics['dataset_mode'].lower()}."
    )

