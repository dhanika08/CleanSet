"""
run_eval.py - measures how well CleanSet does on the 30 test deals, using the REAL Gemini.

For every test deal it:
  1. reads the documents with Gemini,
  2. runs the rules and judgement calls,
  3. compares with the answer key,
and then writes eval/report.md (the numbers for your slides) and eval/results.json.

Each deal's raw result is saved in eval/raw/, so if you stop (or hit the free-tier limit)
you can run the same command again and it carries on where it stopped.

Usage (from the project root, with GEMINI_API_KEY set):
    python3 scripts/run_eval.py --cases C01,E03,N01      # a few deals first
    python3 scripts/run_eval.py --pause 5                # all 30, waiting 5 s between calls
    python3 scripts/run_eval.py --fresh                  # ignore saved results and redo
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import extract, fieldmap, judge
from app.files import collect_files
from app.pipeline import analyze, clean_values

JUDGEMENT_RULES = {"CHK-05", "CHK-18", "CHK-20"}


def run_case(case_id, pause, fresh, out_dir):
    raw_path = os.path.join(out_dir, "raw", case_id + ".json")
    if os.path.exists(raw_path) and not fresh:
        return json.load(open(raw_path, encoding="utf-8")), True
    folder = os.path.join("data", "gold", case_id)
    files = collect_files(os.path.join(folder, "docs"))
    tokens = {"input": 0, "output": 0, "thinking": 0, "total": 0}
    models = set()
    judge_calls = []

    def counted_judge(item):
        if pause:
            time.sleep(pause)
        v = judge.judge(item)
        judge_calls.append({"rule_id": item["rule_id"], "verdict": v.get("verdict")})
        for k, n in (v.get("tokens") or {}).items():
            tokens[k] = tokens.get(k, 0) + n
        if v.get("model_used"):
            models.add(v["model_used"])
        return v

    start = time.time()
    F, log = extract.extract_all(files, pause=pause)
    for entry in log:
        for k, n in (entry.get("tokens") or {}).items():
            tokens[k] = tokens.get(k, 0) + n
        if entry.get("model_used"):
            models.add(entry["model_used"])
    result = analyze(F, counted_judge)
    rec = {"case_id": case_id, "seconds": round(time.time() - start, 1), "tokens": tokens, "models": sorted(models),
           "read_log": log, "facts": F, "result": result, "judge_calls": judge_calls}
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    json.dump(rec, open(raw_path, "w", encoding="utf-8"), indent=2)
    return rec, False


def score_case(rec, case_id):
    folder = os.path.join("data", "gold", case_id)
    key = json.load(open(os.path.join(folder, "answer_key.json"), encoding="utf-8"))
    truth = json.load(open(os.path.join(folder, "truth.json"), encoding="utf-8"))
    expected = {f["rule_id"] for f in key["expected_findings"]}
    got = {f["rule_id"] for f in rec["result"]["findings"]}
    truth_F = fieldmap.truth_to_fields(truth)
    V = clean_values(rec["facts"])
    right = 0
    for fid, t in truth_F.items():
        v = V.get(fid)
        if v is not None and (v == t["value"] or (isinstance(v, str) and str(t["value"]).upper() == v.upper())):
            right += 1
    return {"case_id": case_id, "group": key["group"], "expected": sorted(expected), "got": sorted(got),
            "tp": len(expected & got), "fn": len(expected - got), "fp": len(got - expected),
            "verdict_ok": rec["result"]["verdict"] == key["expected_verdict"],
            "facts_right": right, "facts_total": len(truth_F),
            "unchecked": rec["result"]["unchecked"], "dropped": len(rec["result"]["dropped"]),
            "seconds": rec["seconds"], "tokens": rec["tokens"]["total"], "models": rec["models"]}


def pct(a, b):
    return "n/a" if b == 0 else "%.0f%%" % (100.0 * a / b)


def write_report(rows, out_dir):
    tp = sum(r["tp"] for r in rows); fn = sum(r["fn"] for r in rows); fp = sum(r["fp"] for r in rows)
    ok = sum(r["verdict_ok"] for r in rows)
    fr = sum(r["facts_right"] for r in rows); ft = sum(r["facts_total"] for r in rows)
    quiet = [r for r in rows if r["group"] in ("clean", "near_miss")]
    false_alarm_cases = [r for r in quiet if r["got"]]
    models = sorted({m for r in rows for m in r["models"]})
    lines = ["# CleanSet evaluation report", "",
             "Measured on %d test deals (fictional documents with answer keys)." % len(rows), "",
             "Models that answered: %s" % (", ".join(models) or "none"), "",
             "## Summary", "",
             "| Measure | Result |", "|---|---|",
             "| Deals with the correct verdict | %d of %d (%s) |" % (ok, len(rows), pct(ok, len(rows))),
             "| Planted problems found (recall) | %d of %d (%s) |" % (tp, tp + fn, pct(tp, tp + fn)),
             "| Findings that were correct (precision) | %d of %d (%s) |" % (tp, tp + fp, pct(tp, tp + fp)),
             "| False alarms on clean and look-wrong-but-fine deals | %d of %d deals |" % (len(false_alarm_cases), len(quiet)),
             "| Facts read correctly from documents | %d of %d (%s) |" % (fr, ft, pct(fr, ft)),
             "| Average time per deal | %.0f s |" % (sum(r["seconds"] for r in rows) / len(rows)),
             "| Average tokens per deal | %.0f |" % (sum(r["tokens"] for r in rows) / len(rows)), "",
             "## By group", "", "| Group | Deals | Correct verdict | Problems found | False findings |", "|---|---|---|---|---|"]
    for g in ["clean", "single_error", "multi_error", "near_miss"]:
        gr = [r for r in rows if r["group"] == g]
        if gr:
            lines.append("| %s | %d | %d | %d of %d | %d |" % (g, len(gr), sum(r["verdict_ok"] for r in gr),
                         sum(r["tp"] for r in gr), sum(r["tp"] + r["fn"] for r in gr), sum(r["fp"] for r in gr)))
    lines += ["", "## Every deal", "", "| Deal | Expected | Found | Verdict ok | Facts read | Not checked |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %d/%d | %s |" % (r["case_id"], ", ".join(r["expected"]) or "none",
                     ", ".join(r["got"]) or "none", "yes" if r["verdict_ok"] else "NO", r["facts_right"], r["facts_total"],
                     ", ".join(r["unchecked"]) or "-"))
    miss = [r for r in rows if r["fn"] or r["fp"] or not r["verdict_ok"]]
    lines += ["", "## Deals to look at", ""]
    lines += ["- %s: expected %s, found %s" % (r["case_id"], r["expected"] or "none", r["got"] or "none") for r in miss] or ["- none"]
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    json.dump(rows, open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8"), indent=2)
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", help="comma-separated case ids, e.g. C01,E03 (default: all)")
    ap.add_argument("--pause", type=float, default=0, help="seconds to wait between Gemini calls")
    ap.add_argument("--fresh", action="store_true", help="ignore saved results")
    ap.add_argument("--out", default="eval")
    args = ap.parse_args(argv)

    index = json.load(open("data/gold/index.json", encoding="utf-8"))
    ids = [i["case_id"] for i in index]
    if args.cases:
        wanted = [c.strip() for c in args.cases.split(",")]
        ids = [i for i in ids if i in wanted]

    rows = []
    for cid in ids:
        rec, from_cache = run_case(cid, args.pause, args.fresh, args.out)
        row = score_case(rec, cid)
        rows.append(row)
        print("%-4s %s  found=%-26s expected=%-26s facts %d/%d  %s" % (
            cid, "OK  " if row["verdict_ok"] and not row["fn"] and not row["fp"] else "CHECK", row["got"], row["expected"],
            row["facts_right"], row["facts_total"], "(saved earlier)" if from_cache else "(%.0fs)" % rec["seconds"]))
    print()
    print(write_report(rows, args.out))


if __name__ == "__main__":
    main()
