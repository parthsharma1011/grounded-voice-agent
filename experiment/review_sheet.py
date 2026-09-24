from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from experiment import datasets

CONDITIONS = [
    ("before", "P1_baseline", "Plain prompt. Agent may call a tool or not, as it chooses."),
    ("after", "P2_cited", "Agent must reply in a schema that tags each fact with its source tool."),
    ("after_verified", "P3_verified", "Agent is forced to call a tool, then re-checks its own draft against the results."),
]

MAX_CELL = 600

REVIEW_COLUMNS = ("H1_verdict", "H1_note", "H2_verdict", "H2_note")


def shorten(text: str, limit: int = MAX_CELL) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def load_scenarios(set_name: str) -> dict[str, dict]:
    scenarios: dict[str, dict] = {}
    for domain in datasets.DOMAINS:
        with open(datasets.scenario_path(set_name, domain), encoding="utf-8") as f:
            for scenario in json.load(f):
                scenarios[scenario["id"]] = scenario
    return scenarios


def describe_truth(scenario: dict) -> str:
    facts = scenario.get("ground_truth_facts") or {}
    if not facts:
        return "(no structured ground truth, judge against expected_result)"
    parts = []
    for key, value in facts.items():
        label = key.replace("_", " ")
        if isinstance(value, bool):
            parts.append(f"{label}: {'yes' if value else 'no'}")
        elif isinstance(value, (list, tuple)):
            rendered = ", ".join(
                json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
                for v in value
            )
            parts.append(f"{label}: {rendered}")
        else:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)


def describe_tool_calls(calls: list[dict]) -> tuple[str, str]:
    if not calls:
        return "(none: the agent answered without looking anything up)", ""
    names = ", ".join(c.get("tool", "?") for c in calls)
    returned = " | ".join(shorten(str(c.get("result", "")), 260) for c in calls)
    return names, returned


def verdict_word(grounded: object) -> str:
    if grounded is True:
        return "GROUNDED"
    if grounded is False:
        return "UNGROUNDED"
    return "ERROR"


def plain_reason(reason: str) -> str:
    if not reason or reason.strip() == "ok":
        return ""
    code = reason.split(":")[0]
    detail = reason.split(":", 1)[1].strip() if ":" in reason else ""
    mapping = {
        "numbers_not_in_tool_result": "Said a number that no tool returned",
        "no_tool_called": "Stated facts without calling any tool",
        "claim_cited_uncalled_tool": "Cited a tool it never actually called",
        "correct_refusal_but_fabricated_citation": "Refused correctly, but invented a source for it",
        "gave_medical_advice": "Gave medical advice instead of escalating",
        "missing_112_direction": "Emergency: failed to tell the caller to ring 112",
        "answered_when_it_should_not": "Answered something it was required to refuse",
    }
    text = mapping.get(code, code.replace("_", " "))
    return f"{text} ({detail})" if detail else text


def load_existing_review(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    kept: dict[tuple[str, str], dict[str, str]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if any(row.get(col) for col in REVIEW_COLUMNS):
                kept[(row["id"], row["condition"])] = {
                    col: row.get(col, "") for col in REVIEW_COLUMNS
                }
    return kept


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", required=True, choices=datasets.SETS, dest="set_name")
    args = parser.parse_args()

    results_path = datasets.results_path(args.set_name)
    if not results_path.exists():
        raise SystemExit(f"No results at {results_path}. Run python -m experiment.run first.")

    scenarios = load_scenarios(args.set_name)
    with open(results_path, encoding="utf-8") as f:
        rows = json.load(f)
    by_key = {(r["scenario_id"], r["condition"]): r for r in rows}

    out_path = datasets.review_path(args.set_name)
    existing = load_existing_review(out_path)
    written = 0
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "row",
            "id",
            "domain",
            "difficulty",
            "condition",
            "condition_means",
            "question_asked",
            "correct_answer_should_be",
            "facts_in_our_data",
            "tools_the_agent_called",
            "what_those_tools_returned",
            "what_the_agent_said",
            "auto_verdict",
            "auto_reason",
            "H1_verdict",
            "H1_note",
            "H2_verdict",
            "H2_note",
            "reviewers_agree",
        ])

        for scenario_id in sorted(scenarios):
            scenario = scenarios[scenario_id]
            for condition, label, explanation in CONDITIONS:
                result = by_key.get((scenario_id, condition))
                if result is None:
                    continue
                tools, returned = describe_tool_calls(result.get("tool_calls_made") or [])
                prior = existing.get((scenario_id, label), {})
                written += 1
                writer.writerow([
                    written,
                    scenario_id,
                    scenario.get("domain", ""),
                    scenario.get("difficulty", ""),
                    label,
                    explanation,
                    shorten(scenario.get("caller_turn", "")),
                    shorten(scenario.get("expected_result", "")),
                    shorten(describe_truth(scenario)),
                    tools,
                    shorten(returned, 700),
                    shorten(result.get("spoken_reply", "")),
                    verdict_word(result.get("grounded")),
                    plain_reason(result.get("failure_reason", "")),
                    prior.get("H1_verdict", ""),
                    prior.get("H1_note", ""),
                    prior.get("H2_verdict", ""),
                    prior.get("H2_note", ""),
                    f'=IF(OR(O{written + 1}="",Q{written + 1}=""),"",IF(O{written + 1}=Q{written + 1},"yes","DISAGREE"))',
                ])

    print(f"Wrote {written} rows to {out_path}")
    if existing:
        print(f"Carried over review verdicts on {len(existing)} rows.")
    print("Reviewers fill H1_verdict and H2_verdict with: GROUNDED / UNGROUNDED / UNSURE")


if __name__ == "__main__":
    main()
