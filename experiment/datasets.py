from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT / "experiment" / "scenarios"
RESULTS_DIR = ROOT / "experiment" / "results"

SETS = ["golden", "hard"]
DOMAINS = ["real_estate", "restaurant", "healthcare"]
CONDITIONS = ["before", "after", "after_verified"]


def scenario_path(set_name: str, domain: str) -> Path:
    return SCENARIOS_DIR / set_name / f"{domain}.json"


def results_path(set_name: str) -> Path:
    return RESULTS_DIR / f"{set_name}_results.json"


def review_path(set_name: str) -> Path:
    return RESULTS_DIR / f"{set_name}_review.csv"


def load_scenarios(set_name: str, domain: str) -> list[dict]:
    with open(scenario_path(set_name, domain)) as f:
        return json.load(f)
