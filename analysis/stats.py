from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from analysis import settings
from analysis.formulas import (
    clopper_pearson,
    cochran_q,
    cohens_kappa,
    fisher_exact,
    gwet_ac1,
    holm,
    mcnemar_exact,
    mcnemar_midp,
    newcombe_paired,
    wilcoxon_signed_rank,
    wilson,
)
from experiment import datasets
from experiment.review_sheet import CONDITIONS as SHEET_CONDITIONS

OUT = Path(__file__).resolve().parent / "output"

SETS = datasets.SETS
DOMAINS = datasets.DOMAINS
CONDS = datasets.CONDITIONS
LAB = settings.CONDITION_LABELS
SHEETLAB = {label: cond for cond, label, _ in SHEET_CONDITIONS}


def pct(x):
    return round(100 * x, 1)


def load_set(name):
    rows = json.load(open(datasets.results_path(name)))
    scen = {}
    for dom in DOMAINS:
        for s in json.load(open(datasets.scenario_path(name, dom))):
            scen[s["id"]] = s
    by = defaultdict(dict)
    for r in rows:
        by[r["condition"]][r["scenario_id"]] = r
    return rows, scen, by


def called_tools(row):
    return {tc["tool"].rsplit(".", 1)[-1] for tc in row["tool_calls_made"]}


def analyze_set(name):
    rows, scen, by = load_set(name)
    out = {"n_rows": len(rows), "n_scenarios": len(scen)}
    out["errors"] = {LAB[c]: sum(1 for r in by[c].values() if r.get("grounded") is None) for c in CONDS}

    rates = {}
    for c in CONDS:
        vals = [r["grounded"] for r in by[c].values() if r.get("grounded") is not None]
        k, n = sum(vals), len(vals)
        lo, hi = wilson(k, n)
        rates[LAB[c]] = {"k": k, "n": n, "rate": pct(k / n), "wilson": [pct(lo), pct(hi)], "failures": n - k}
    out["rates"] = rates

    for key, groups in (("by_domain", DOMAINS), ("by_difficulty", settings.DIFFICULTIES)):
        tab = {}
        for g in groups:
            tab[g] = {}
            for c in CONDS:
                vals = [r["grounded"] for sid, r in by[c].items() if r.get("grounded") is not None
                        and (scen[sid]["domain"] if key == "by_domain" else scen[sid].get("difficulty")) == g]
                tab[g][LAB[c]] = {"k": sum(vals), "n": len(vals), "rate": pct(sum(vals) / len(vals)) if vals else None}
        out[key] = tab

    out["failure_reasons"] = {
        LAB[c]: dict(Counter(r["failure_reason"].split(":")[0] for r in by[c].values() if r.get("grounded") is False))
        for c in CONDS
    }
    out["failure_reasons_by_domain"] = {
        LAB[c]: dict(Counter(f"{scen[s]['domain']}|{r['failure_reason'].split(':')[0]}"
                             for s, r in by[c].items() if r.get("grounded") is False))
        for c in CONDS
    }
    out["failed_ids"] = {LAB[c]: sorted(s for s, r in by[c].items() if r.get("grounded") is False) for c in CONDS}

    sids = sorted(s for s in scen if all(by[c].get(s, {}).get("grounded") is not None for c in CONDS))
    matrix = [[int(by[c][s]["grounded"]) for c in CONDS] for s in sids]
    q, qp = cochran_q(matrix)
    out["cochran_q"] = {"n": len(sids), "Q": round(q, 3), "df": 2, "p": qp}

    pairs, raw_p = {}, {}
    for c1, c2 in combinations(CONDS, 2):
        a = sum(1 for s in sids if by[c1][s]["grounded"] and by[c2][s]["grounded"])
        d = sum(1 for s in sids if not by[c1][s]["grounded"] and not by[c2][s]["grounded"])
        only1 = sum(1 for s in sids if by[c1][s]["grounded"] and not by[c2][s]["grounded"])
        only2 = sum(1 for s in sids if not by[c1][s]["grounded"] and by[c2][s]["grounded"])
        p = mcnemar_exact(only1, only2)
        key = f"{LAB[c1]}_vs_{LAB[c2]}"
        raw_p[key] = p
        theta, lo, hi = newcombe_paired(a, only2, only1, d)
        cp = clopper_pearson(only2, only1 + only2) if only1 + only2 else (0, 1)
        or_ = (only2 / only1) if only1 else float("inf")
        or_ci = (cp[0] / (1 - cp[0]) if cp[0] < 1 else float("inf"), cp[1] / (1 - cp[1]) if cp[1] < 1 else float("inf"))
        pairs[key] = {
            "n": len(sids), "both_right": a, "both_wrong": d,
            f"only_{LAB[c1]}_right": only1, f"only_{LAB[c2]}_right": only2,
            "discordant": only1 + only2, "p_exact": p, "p_midp": mcnemar_midp(only1, only2),
            "risk_diff_pp": round(100 * theta, 1), "risk_diff_ci_pp": [round(100 * lo, 1), round(100 * hi, 1)],
            "cond_odds_ratio": None if or_ == float("inf") else round(or_, 2),
            "cond_or_ci": [round(x, 2) if x != float("inf") else None for x in or_ci],
        }
    adj = holm(raw_p)
    for k in pairs:
        pairs[k]["p_holm"] = adj[k]
    out["pairwise"] = pairs

    p1f = [s for s in sids if not by["before"][s]["grounded"]]
    p1s = [s for s in sids if by["before"][s]["grounded"]]
    fixed = [s for s in p1f if by["after_verified"][s]["grounded"]]
    broken = [s for s in p1s if not by["after_verified"][s]["grounded"]]
    out["p3_vs_p1_fix_break"] = {
        "p1_failures": len(p1f), "fixed": len(fixed), "fix_rate": pct(len(fixed) / len(p1f)) if p1f else None,
        "p1_successes": len(p1s), "broken": len(broken), "break_rate": pct(len(broken) / len(p1s)) if p1s else None,
        "fixed_ids": fixed, "broken_ids": broken,
    }
    p2f = [s for s in sids if not by["after"][s]["grounded"]]
    p2s = [s for s in sids if by["after"][s]["grounded"]]
    out["p3_vs_p2_fix_break"] = {
        "p2_failures": len(p2f), "fixed": sum(1 for s in p2f if by["after_verified"][s]["grounded"]),
        "p2_successes": len(p2s), "broken": sum(1 for s in p2s if not by["after_verified"][s]["grounded"]),
    }

    dom_tests = {}
    for dom in DOMAINS:
        ds = [s for s in sids if scen[s]["domain"] == dom]
        only1 = sum(1 for s in ds if by["before"][s]["grounded"] and not by["after_verified"][s]["grounded"])
        only3 = sum(1 for s in ds if not by["before"][s]["grounded"] and by["after_verified"][s]["grounded"])
        dom_tests[dom] = {"only_P1": only1, "only_P3": only3, "p_exact": mcnemar_exact(only1, only3)}
    out["p1_vs_p3_by_domain"] = dom_tests
    diff_tests = {}
    for band in settings.DIFFICULTIES:
        ds = [s for s in sids if scen[s].get("difficulty") == band]
        only1 = sum(1 for s in ds if by["before"][s]["grounded"] and not by["after_verified"][s]["grounded"])
        only3 = sum(1 for s in ds if not by["before"][s]["grounded"] and by["after_verified"][s]["grounded"])
        diff_tests[band] = {"n": len(ds), "only_P1": only1, "only_P3": only3, "p_exact": mcnemar_exact(only1, only3)}
    out["p1_vs_p3_by_difficulty"] = diff_tests

    lat = {}
    for c in CONDS:
        v = [r["latency_ms"] for r in by[c].values() if r.get("latency_ms")]
        v_sorted = sorted(v)
        lat[LAB[c]] = {
            "mean": round(statistics.mean(v)), "median": round(statistics.median(v)),
            "p90": round(v_sorted[int(settings.LATENCY_PERCENTILE * (len(v) - 1))]), "sd": round(statistics.stdev(v)),
            "min": round(min(v)), "max": round(max(v)),
        }
    out["latency"] = lat
    lat_s = [s for s in sids if all(by[c][s].get("latency_ms") for c in CONDS)]
    out["latency_tests"] = {
        "P3_vs_P1": wilcoxon_signed_rank([by["after_verified"][s]["latency_ms"] - by["before"][s]["latency_ms"] for s in lat_s]),
        "P2_vs_P1": wilcoxon_signed_rank([by["after"][s]["latency_ms"] - by["before"][s]["latency_ms"] for s in lat_s]),
        "median_ratio_P3_P1": round(statistics.median(by["after_verified"][s]["latency_ms"] / by["before"][s]["latency_ms"] for s in lat_s), 2),
        "n": len(lat_s),
        "P3_slower_than_P1": sum(1 for s in lat_s if by["after_verified"][s]["latency_ms"] > by["before"][s]["latency_ms"]),
        "P2_slower_than_P1": sum(1 for s in lat_s if by["after"][s]["latency_ms"] > by["before"][s]["latency_ms"]),
    }

    tools = {}
    for c in CONDS:
        rs = [r for r in by[c].values() if r.get("grounded") is not None]
        ncalls = [len(r["tool_calls_made"]) for r in rs]
        needs = [r for r in rs if scen[r["scenario_id"]].get("expects_tool_call", True)]
        tools[LAB[c]] = {
            "mean_calls": round(statistics.mean(ncalls), 2),
            "share_with_call": pct(sum(1 for x in ncalls if x) / len(ncalls)),
            "no_call_when_expected": sum(1 for r in needs if not r["tool_calls_made"]),
            "expected_n": len(needs),
            "hallucinated_id_attempts": sum(1 for r in rs if r.get("hallucinated_id_attempt")),
            "tool_names": dict(Counter(tc["tool"] for r in rs for tc in r["tool_calls_made"]).most_common(8)),
        }
    out["tool_use"] = tools

    out["mutating_calls"] = {
        LAB[c]: dict(Counter(tc["tool"] for r in by[c].values() for tc in r["tool_calls_made"] if tc["tool"] in settings.MUTATING_TOOLS))
        for c in CONDS
    }
    out["slot_mutating_calls_detail"] = [
        {"cond": LAB[c], "sid": r["scenario_id"], "tool": tc["tool"], "args": tc["arguments"], "result": tc["result"][:160]}
        for c in CONDS for r in by[c].values() for tc in r["tool_calls_made"] if tc["tool"] in settings.SLOT_MUTATING_TOOLS
    ]

    claims = {}
    for c in CONDS[1:]:
        rs = [r for r in by[c].values() if r.get("grounded") is not None]
        allc = [(r, cl) for r in rs for cl in (r.get("claims") or [])]
        fabricated = [(r["scenario_id"], cl.get("source_tool_call")) for r, cl in allc
                      if cl.get("source_tool_call") and cl["source_tool_call"].rsplit(".", 1)[-1] not in called_tools(r)]
        claims[LAB[c]] = {
            "replies": len(rs), "replies_with_claims": sum(1 for r in rs if r.get("claims")),
            "total_claims": len(allc), "mean_claims": round(len(allc) / len(rs), 2),
            "null_source": sum(1 for _, cl in allc if not cl.get("source_tool_call")),
            "fabricated_citations": len(fabricated), "fabricated_rows": sorted({s for s, _ in fabricated}),
            "fabricated_examples": fabricated[:6],
            "claims_in_no_tool_rows": sum(len(r.get("claims") or []) for r in rs if not r["tool_calls_made"]),
        }
    out["claims"] = claims

    safety_ids = [s for s in sids if scen[s]["ground_truth_facts"].get("must_direct_to_112")
                  or scen[s]["ground_truth_facts"].get("must_not_answer")]
    out["safety"] = {LAB[c]: {"k": sum(1 for s in safety_ids if by[c][s]["grounded"]), "n": len(safety_ids)} for c in CONDS}
    return out, rows, scen, by


def analyze_sheet(name, by):
    path = datasets.review_path(name)
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))
    out = {"rows": len(rows)}
    filled = [r for r in rows if r["H1_verdict"] and r["H2_verdict"]]
    out["filled"] = len(filled)
    out["H1_dist"] = dict(Counter(r["H1_verdict"] for r in filled))
    out["H2_dist"] = dict(Counter(r["H2_verdict"] for r in filled))

    pairs = [(r["H1_verdict"], r["H2_verdict"]) for r in filled]
    k_all = cohens_kappa(pairs)
    labels3 = ["GROUNDED", "UNGROUNDED", "UNSURE"]
    out["h1_h2_all"] = {**k_all, "pabak_k3": (3 * k_all["po"] - 1) / 2, "gwet_ac1_k3": gwet_ac1(pairs, labels3)}
    binpairs = [p for p in pairs if "UNSURE" not in p]
    k_bin = cohens_kappa(binpairs)
    out["h1_h2_binary"] = {**k_bin, "pabak": 2 * k_bin["po"] - 1,
                           "gwet_ac1": gwet_ac1(binpairs, ["GROUNDED", "UNGROUNDED"])}
    out["h1_h2_binary_table"] = dict(Counter(f"{a}|{b}" for a, b in binpairs))

    settled = [r for r in filled if r["H1_verdict"] == r["H2_verdict"]]
    usable = [r for r in settled if r["H1_verdict"] in ("GROUNDED", "UNGROUNDED")]
    disputed = [r for r in filled if r["H1_verdict"] != r["H2_verdict"]]
    out["settled"], out["usable"], out["disputed"] = len(settled), len(usable), len(disputed)
    out["both_unsure"] = len(settled) - len(usable)

    mism = []
    for r in filled:
        cond = SHEETLAB[r["condition"]]
        g = by[cond][r["id"]]["grounded"]
        auto = "GROUNDED" if g is True else "UNGROUNDED" if g is False else "ERROR"
        if auto != r["auto_verdict"]:
            mism.append((r["id"], r["condition"], r["auto_verdict"], auto))
    out["auto_verdict_mismatch_vs_raw"] = mism

    out["disputed_rows"] = [(r["id"], r["condition"], r["H1_verdict"], r["H2_verdict"]) for r in disputed]
    out["both_unsure_rows"] = [(r["id"], r["condition"]) for r in settled if r["H1_verdict"] == "UNSURE"]
    return out


def main():
    stats = {}
    for name in SETS:
        s, rows, scen, by = analyze_set(name)
        s["sheet"] = analyze_sheet(name, by)
        stats[name] = s

    pooled = {}
    by_all = defaultdict(dict)
    for name in SETS:
        _, _, by = load_set(name)
        for c in CONDS:
            by_all[c].update(by[c])
    sids = sorted(s for s in by_all["before"] if all(by_all[c][s].get("grounded") is not None for c in CONDS))
    for c in CONDS:
        k = sum(by_all[c][s]["grounded"] for s in sids)
        lo, hi = wilson(k, len(sids))
        pooled[LAB[c]] = {"k": k, "n": len(sids), "rate": pct(k / len(sids)), "wilson": [pct(lo), pct(hi)]}
    q, qp = cochran_q([[int(by_all[c][s]["grounded"]) for c in CONDS] for s in sids])
    pooled["cochran_q"] = {"Q": round(q, 3), "p": qp}
    raw_p, pw = {}, {}
    for c1, c2 in combinations(CONDS, 2):
        a = sum(1 for s in sids if by_all[c1][s]["grounded"] and by_all[c2][s]["grounded"])
        d = sum(1 for s in sids if not by_all[c1][s]["grounded"] and not by_all[c2][s]["grounded"])
        o1 = sum(1 for s in sids if by_all[c1][s]["grounded"] and not by_all[c2][s]["grounded"])
        o2 = sum(1 for s in sids if not by_all[c1][s]["grounded"] and by_all[c2][s]["grounded"])
        key = f"{LAB[c1]}_vs_{LAB[c2]}"
        raw_p[key] = mcnemar_exact(o1, o2)
        theta, lo, hi = newcombe_paired(a, o2, o1, d)
        pw[key] = {"both_right": a, "both_wrong": d, "only_first": o1, "only_second": o2, "p_exact": raw_p[key],
                   "risk_diff_pp": round(100 * theta, 1), "ci_pp": [round(100 * lo, 1), round(100 * hi, 1)]}
    adj = holm(raw_p)
    for k in pw:
        pw[k]["p_holm"] = adj[k]
    pooled["pairwise"] = pw
    stats["pooled"] = pooled
    stats["safety_pooled"] = {
        LAB[c]: {k: stats["golden"]["safety"][LAB[c]][k] + stats["hard"]["safety"][LAB[c]][k] for k in ("k", "n")}
        for c in CONDS
    }

    g = stats["golden"]["pairwise"]["P1_vs_P3"]
    h = stats["hard"]["pairwise"]["P1_vs_P3"]
    stats["moderation"] = {
        "golden_split_P3_P1": [g["only_P3_right"], g["only_P1_right"]],
        "hard_split_P3_P1": [h["only_P3_right"], h["only_P1_right"]],
        "fisher_homogeneity_p": fisher_exact(g["only_P3_right"], g["only_P1_right"], h["only_P3_right"], h["only_P1_right"]),
        "golden_fix_break": stats["golden"]["p3_vs_p1_fix_break"],
        "hard_fix_break": stats["hard"]["p3_vs_p1_fix_break"],
    }

    share = settings.POWER_WIN_SHARE
    floor = next(n for n in range(1, settings.POWER_SEARCH_LIMIT)
                 if mcnemar_exact(round(n * share), n - round(n * share)) < settings.ALPHA)
    stats["power_floor_80pct"] = floor
    stats["power_floor_all_one_way"] = next(n for n in range(1, settings.POWER_SEARCH_LIMIT) if mcnemar_exact(n, 0) < settings.ALPHA)

    json.dump(stats, open(OUT / "stats.json", "w"), indent=1, default=str)
    print(json.dumps(stats, indent=1, default=str))


if __name__ == "__main__":
    main()
