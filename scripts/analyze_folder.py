"""
analyze_folder.py - run CleanSet on one folder of documents, using the REAL Gemini.

Usage (from the project root):
    export GEMINI_API_KEY=...            (see the instructions, do not type the key into any file)
    python3 scripts/analyze_folder.py data/demo/planted
    python3 scripts/analyze_folder.py data/gold/E06/docs --truth data/gold/E06/truth.json

What it prints:
  1. what Gemini read from each file,
  2. (with --truth) which facts it read WRONG compared with the true data,
  3. the verdict, the problems found, and the things it correctly accepted.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import extract, fieldmap, judge
from app.files import collect_files
from app.pipeline import analyze, clean_values

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--truth", help="truth.json of this case, to check the reading")
    ap.add_argument("--save", help="save the full result as JSON to this path")
    args = ap.parse_args()

    files = collect_files(args.folder)
    print("Reading %d files with Gemini ..." % len(files))
    F, log = extract.extract_all(files)
    for entry in log:
        if entry.get("error"):
            print("  %-28s FAILED: %s" % (entry["filename"], entry["error"]))
        else:
            print("  %-28s read as %-22s %2d facts  (model %s)" % (entry["filename"], entry["document_type"], entry["facts_read"], entry["model_used"]))

    if args.truth:
        truth_F = fieldmap.truth_to_fields(json.load(open(args.truth, encoding="utf-8")))
        V = clean_values(F)
        wrong, missing = [], []
        for fid, t in truth_F.items():
            if fid not in V:
                missing.append(fid)
            elif V[fid] != t["value"] and not (isinstance(V[fid], str) and isinstance(t["value"], str) and V[fid].upper() == t["value"].upper()):
                wrong.append((fid, V[fid], t["value"]))
        print("\nReading check: %d of %d facts correct, %d wrong, %d missing" %
              (len(truth_F) - len(wrong) - len(missing), len(truth_F), len(wrong), len(missing)))
        for fid, got, want in wrong:
            print("  WRONG  %-42s read=%r  true=%r" % (fid, got, want))
        for fid in missing:
            print("  MISSING", fid)

    print("\nChecking rules and asking Gemini for judgement calls ...")
    result = analyze(F, judge.judge)

    print("\n=========== VERDICT: %s ===========" % ("Bank would REFUSE: %d problem(s)" % result["problem_count"] if result["verdict"] == "discrepant" else "Ready to submit"))
    for f in result["findings"]:
        print("\n[%s] %s  (%s)" % (f["rule_id"], f["title"], f["type"]))
        print("   ", f["explanation"])
        print("    Fix:", f["fix"])
    if result["accepted"]:
        print("\nLooked wrong but ACCEPTED:")
        for a in result["accepted"]:
            print("  [%s] %s %s" % (a["rule_id"], a["reason"], ("(" + a["article"] + ")") if a["article"] else ""))
    if result["dropped"]:
        print("\nDropped by the verifier:", len(result["dropped"]))
    if result["unchecked"]:
        print("Could not check:", ", ".join(result["unchecked"]))

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump({"result": result, "read_log": log, "facts": F}, f, indent=2)
        print("\nSaved to", args.save)


if __name__ == "__main__":
    main()
