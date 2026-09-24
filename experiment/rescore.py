from __future__ import annotations

import argparse
import json

from experiment import datasets
from experiment.scorer import score_after, score_before


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", required=True, choices=datasets.SETS, dest="set_name")
    args = parser.parse_args()

    src = datasets.results_path(args.set_name)
    with open(src) as f:
        rows = json.load(f)

    scenarios: dict[str, dict] = {}
    for domain in datasets.DOMAINS:
        for s in datasets.load_scenarios(args.set_name, domain):
            scenarios[s["id"]] = s

    changed = 0
    for r in rows:
        scenario = scenarios.get(r["scenario_id"])
        if scenario is None or r.get("grounded") is None:
            continue
        old = r["grounded"]
        if r["condition"] == "before":
            grounded, reason, hid = score_before(
                scenario, r["spoken_reply"], r["tool_calls_made"]
            )
        else:
            grounded, reason, hid = score_after(
                scenario, r["spoken_reply"], r["tool_calls_made"], r.get("claims", [])
            )
        r["grounded"] = grounded
        r["failure_reason"] = reason
        r["hallucinated_id_attempt"] = hid
        if old != grounded:
            changed += 1

    with open(src, "w") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"Re-scored {len(rows)} results ({changed} verdicts changed) -> {src}")


if __name__ == "__main__":
    main()
