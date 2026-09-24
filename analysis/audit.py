from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from analysis import settings
from analysis.formulas import mcnemar_exact, wilson
from experiment import datasets

OUTDIR = Path(__file__).resolve().parent / "output"
OUTDIR.mkdir(exist_ok=True)

L = settings.CONDITION_LABELS
CODES = Path(__file__).resolve().parent / "audit_codes.csv"


def load_codes():
    tables = {
        "no_lookup": defaultdict(dict), "number_flag": defaultdict(dict), "non_answer": defaultdict(list),
        "trap_invented": {c: {} for c in settings.LABELS}, "trap_no_answer": {c: [] for c in settings.LABELS},
        "p1_vs_p3_fixed": {}, "p1_vs_p3_broken": {},
    }
    with open(CODES, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table, key, sid = row["table"], (row["set"], row["condition"]), row["scenario"]
            if table in ("no_lookup", "number_flag"):
                tables[table][key][sid] = (row["code"], row["note"])
            elif table == "non_answer":
                tables[table][key].append(sid)
            elif table == "trap_invented":
                tables[table][row["condition"]][sid] = row["note"]
            elif table == "trap_no_answer":
                tables[table][row["condition"]].append(sid)
            else:
                tables[table][sid] = (row["code"], row["note"])
    return tables


CODED = load_codes()
NO_LOOKUP = CODED["no_lookup"]
NUMBER_FLAGS = CODED["number_flag"]
NON_ANSWERS = CODED["non_answer"]
TRAP_INV = CODED["trap_invented"]
TRAP_NOANSWER = CODED["trap_no_answer"]
DISCORDANT_FIX = CODED["p1_vs_p3_fixed"]
DISCORDANT_BREAK = CODED["p1_vs_p3_broken"]


def wilson_percent(k, n):
    lo, hi = wilson(k, n)
    return round(100 * lo, 1), round(100 * hi, 1)


def load(setname):
    rows = json.load(open(datasets.results_path(setname)))
    sc = {}
    for d in datasets.DOMAINS:
        for s in json.load(open(datasets.scenario_path(setname, d))):
            sc[s["id"]] = s
    by = {(r["scenario_id"], L[r["condition"]]): r for r in rows}
    return sc, by


def main():
    out = {}
    csv_rows = []

    for setname in datasets.SETS:
        sc, by = load(setname)
        sids = sorted(sc)
        for cond in settings.LABELS:
            flagged = {s for s in sids if by[(s, cond)]["grounded"] is False}
            nl = {s for s in flagged if by[(s, cond)]["failure_reason"] == "no_tool_called"}
            num = {s for s in flagged if by[(s, cond)]["failure_reason"].startswith("numbers")}
            assert nl == set(NO_LOOKUP.get((setname, cond), {})), (setname, cond, nl ^ set(NO_LOOKUP.get((setname, cond), {})))
            assert num == set(NUMBER_FLAGS.get((setname, cond), {})), (setname, cond, num ^ set(NUMBER_FLAGS.get((setname, cond), {})))
            for s in sorted(nl):
                cls, note = NO_LOOKUP[(setname, cond)][s]
                csv_rows.append([setname, s, cond, "scorer_flag", "skipped_lookup", cls, note])
            for s in sorted(num):
                cls, note = NUMBER_FLAGS[(setname, cond)][s]
                csv_rows.append([setname, s, cond, "scorer_flag", by[(s, cond)]["failure_reason"], cls, note])
            for s in NON_ANSWERS.get((setname, cond), []):
                assert by[(s, cond)]["spoken_reply"].startswith("[no final reply")
                csv_rows.append([setname, s, cond, "scorer_pass", "ok", "non_answer", "no reply after four tool rounds"])

        def corrected(s, cond, lenient_derived):
            r = by[(s, cond)]
            if s in NON_ANSWERS.get((setname, cond), []):
                return False
            if r["grounded"]:
                return True
            if r["failure_reason"] == "no_tool_called":
                return False
            cls = NUMBER_FLAGS[(setname, cond)][s][0]
            if cls in ("time_format", "caller_echo"):
                return True
            return lenient_derived

        sens = {}
        for label, lenient in (("conservative", False), ("lenient", True)):
            v = {c: {s: corrected(s, c, lenient) for s in sids} for c in settings.LABELS}
            res = {c: {"k": sum(v[c].values()), "n": len(sids), "rate": round(100 * sum(v[c].values()) / len(sids), 1),
                       "wilson": wilson_percent(sum(v[c].values()), len(sids))} for c in v}
            for a, b in settings.AUDIT_COMPARISONS:
                ob = sum(1 for s in sids if v[a][s] and not v[b][s])
                oc = sum(1 for s in sids if not v[a][s] and v[b][s])
                res[f"{a}_vs_{b}"] = {f"only_{a}": ob, f"only_{b}": oc, "p": mcnemar_exact(ob, oc)}
            sens[label] = res
        out[f"{setname}_sensitivity"] = sens

        comp = {}
        for cond in settings.LABELS:
            c = {}
            for s, (cls, _) in NO_LOOKUP.get((setname, cond), {}).items():
                c[f"skip:{cls}"] = c.get(f"skip:{cls}", 0) + 1
            for s, (cls, _) in NUMBER_FLAGS.get((setname, cond), {}).items():
                c[f"num:{cls}"] = c.get(f"num:{cls}", 0) + 1
            comp[cond] = c
        out[f"{setname}_flag_composition"] = comp

    sc, by = load(settings.AUDITED_SET)
    trap = sorted(s for s in sc if settings.TRAP_PATTERN.search(sc[s]["expected_result"]) or settings.TRAP_PATTERN.search(sc[s].get("notes", "")))
    assert len(trap) == settings.EXPECTED_TRAP_QUESTIONS
    audit = {}
    for cond in settings.LABELS:
        inv_set = set(TRAP_INV[cond])
        assert inv_set <= set(trap)
        skipped = {s for s in trap if by[(s, cond)]["failure_reason"] == "no_tool_called"}
        noans = set(TRAP_NOANSWER[cond])
        scorer_pass_inv = {s for s in inv_set if by[(s, cond)]["grounded"]}
        fail_set = skipped | inv_set | noans
        audit[cond] = {
            "n": len(trap), "invented": len(inv_set), "invented_missed_by_scorer": len(scorer_pass_inv),
            "invented_caught_by_scorer": len(inv_set) - len(scorer_pass_inv),
            "skipped_lookup": len(skipped), "non_answer": len(noans),
            "audited_clean": len(trap) - len(fail_set), "audited_clean_rate": round(100 * (len(trap) - len(fail_set)) / len(trap), 1),
            "scorer_pass": sum(1 for s in trap if by[(s, cond)]["grounded"]),
            "missed_ids": sorted(scorer_pass_inv), "fail_ids": sorted(fail_set),
        }
        for s in trap:
            code = "invented" if s in inv_set else "non_answer" if s in noans else "clean"
            note = TRAP_INV[cond].get(s, "")
            csv_rows.append([settings.AUDITED_SET, s, cond, "trap_audit",
                             "scorer_pass" if by[(s, cond)]["grounded"] else by[(s, cond)]["failure_reason"],
                             code, note])

    def fails(cond):
        return set(audit[cond]["fail_ids"])

    def inv(cond):
        return set(TRAP_INV[cond])
    tests = {}
    for a, b in settings.AUDIT_COMPARISONS:
        ob = len(fails(b) - fails(a))
        oc = len(fails(a) - fails(b))
        tests[f"audited_{a}_vs_{b}"] = {f"only_{a}_clean": ob, f"only_{b}_clean": oc, "p": mcnemar_exact(ob, oc)}
        ib = len(inv(a) - inv(b))
        ic = len(inv(b) - inv(a))
        tests[f"invented_{a}_vs_{b}"] = {f"only_{a}_invented": ib, f"only_{b}_invented": ic,
                                          "both": len(inv(a) & inv(b)), "p": mcnemar_exact(ib, ic)}
    audit["tests"] = tests
    out["trap_audit"] = audit

    out["p3_invented_claim_tags"] = {s: by[(s, "P3")].get("claims") for s in TRAP_INV["P3"]}

    fixed = {s for s in sc if not by[(s, "P1")]["grounded"] and by[(s, "P3")]["grounded"]}
    broken = {s for s in sc if by[(s, "P1")]["grounded"] and not by[(s, "P3")]["grounded"]}
    assert fixed == set(DISCORDANT_FIX) and broken == set(DISCORDANT_BREAK)
    for s_, (c_, n_) in sorted(DISCORDANT_FIX.items()):
        csv_rows.append([settings.AUDITED_SET, s_, "P3 vs P1", "p1_vs_p3_discordant", "P3 grounded, P1 failed", c_, n_])
    for s_, (c_, n_) in sorted(DISCORDANT_BREAK.items()):
        csv_rows.append([settings.AUDITED_SET, s_, "P3 vs P1", "p1_vs_p3_discordant", "P1 grounded, P3 failed", c_, n_])
    out["discordant_composition"] = dict(Counter(c for c, _ in DISCORDANT_FIX.values()))

    conf = {"pass_clean": 0, "pass_fail": 0, "fail_fail": 0, "fail_clean": 0}
    right_reason = 0
    for cond in settings.LABELS:
        for s_ in trap:
            r_ = by[(s_, cond)]
            audit_fail = s_ in audit[cond]["fail_ids"]
            scorer_fail = not r_["grounded"]
            conf[("fail" if scorer_fail else "pass") + "_" + ("fail" if audit_fail else "clean")] += 1
            if scorer_fail and audit_fail and r_["failure_reason"] == "no_tool_called":
                right_reason += 1
    n_ = sum(conf.values())
    po = (conf["pass_clean"] + conf["fail_fail"]) / n_
    sp, sf = (conf["pass_clean"] + conf["pass_fail"]) / n_, (conf["fail_fail"] + conf["fail_clean"]) / n_
    ac, af = (conf["pass_clean"] + conf["fail_clean"]) / n_, (conf["pass_fail"] + conf["fail_fail"]) / n_
    pe = sp * ac + sf * af
    out["scorer_vs_audit_trap"] = {**conf, "n": n_, "agreement": round(100 * po, 1), "kappa": round((po - pe) / (1 - pe), 3),
        "sensitivity": round(100 * conf["fail_fail"] / (conf["fail_fail"] + conf["pass_fail"]), 1),
        "specificity": round(100 * conf["pass_clean"] / (conf["pass_clean"] + conf["fail_clean"]), 1),
        "right_reason_catches": right_reason,
        "right_reason_sensitivity": round(100 * right_reason / (conf["fail_fail"] + conf["pass_fail"]), 1)}

    inv_any = {c: set(TRAP_INV[c]) | {s_ for s_, (k_, _) in NO_LOOKUP.get((settings.AUDITED_SET, c), {}).items() if k_ == "invented"} for c in settings.LABELS}

    def two_sided(s_, c):
        r_ = by[(s_, c)]
        if s_ in NON_ANSWERS.get((settings.AUDITED_SET, c), []) or s_ in inv_any[c]:
            return False
        if r_["grounded"]:
            return True
        if r_["failure_reason"] == "no_tool_called":
            return False
        return NUMBER_FLAGS[(settings.AUDITED_SET, c)][s_][0] in ("time_format", "caller_echo")
    v = {c: {s_: two_sided(s_, c) for s_ in sc} for c in settings.LABELS}
    ts = {c: {"k": sum(v[c].values()), "rate": round(100 * sum(v[c].values()) / len(sc), 1), "wilson": wilson_percent(sum(v[c].values()), len(sc))} for c in v}
    for a_, b_ in settings.AUDIT_COMPARISONS:
        o1 = sum(1 for s_ in sc if v[a_][s_] and not v[b_][s_])
        o2 = sum(1 for s_ in sc if not v[a_][s_] and v[b_][s_])
        ts[f"{a_}_vs_{b_}"] = {f"only_{a_}": o1, f"only_{b_}": o2, "p": mcnemar_exact(o1, o2)}
    out["hard_two_sided"] = ts

    with open(OUTDIR / "audit_transcripts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["set", "scenario", "condition", "audit_part", "scorer_result", "audit_code", "note"])
        w.writerows(csv_rows)
    json.dump(out, open(OUTDIR / "audit_stats.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "p3_invented_claim_tags"}, indent=1))
    print("csv rows:", len(csv_rows))


if __name__ == "__main__":
    main()
