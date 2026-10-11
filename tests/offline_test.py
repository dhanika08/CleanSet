"""
offline_test.py - tests the whole engine WITHOUT calling Gemini.

For each of the 30 test deals (and the demo deal) it:
  1. takes the true facts from truth.json (as if Gemini had read the documents perfectly),
  2. runs the plain-code rules, the judgement step and the verifier,
  3. compares the result with the answer key.

The judgement step here uses a SIMPLE STAND-IN (stub_judge), not Gemini. So this test
proves the rules, the verifier and the plumbing work. It does NOT prove Gemini judges well.
That is measured later, on the real run.

Run from the project root:   python3 tests/offline_test.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import fieldmap
from app.pipeline import analyze


def stub_judge(item):
    """A crude stand-in for Gemini, used ONLY in this test."""
    a, b, rule = item["a_text"], item["b_text"], item["rule_id"]
    if rule == "CHK-18":                                   # general wording is fine unless it names other goods
        ok = "COTTON" in b.upper()
        return {"verdict": "ACCEPTABLE" if ok else "CONFLICT", "reason": "stub", "article": "UCP 600 Art. 14(e)",
                "cited_fields": [item["a_id"], item["b_id"]]}
    if rule == "CHK-20":                                   # same street root and same city = fine
        ok = a.split(",")[1].strip().upper() == b.split(",")[1].strip().upper()
        return {"verdict": "ACCEPTABLE" if ok else "CONFLICT", "reason": "stub", "article": "UCP 600 Art. 14(j)",
                "cited_fields": [item["a_id"], item["b_id"]]}
    if rule == "CHK-05":                                   # equal apart from an allowed quantity change under 'ABOUT'
        qa = int(re.search(r"([\d,]+) PCS", a).group(1).replace(",", ""))
        qb = int(re.search(r"([\d,]+) PCS", b).group(1).replace(",", ""))
        strip = lambda s: re.sub(r"(ABOUT )?[\d,]+ PCS", "", s)
        ok = a.upper().startswith("ABOUT ") and abs(qa - qb) <= 0.1 * qa and strip(a) == strip(b)
        return {"verdict": "ACCEPTABLE" if ok else "CONFLICT", "reason": "stub", "article": "UCP 600 Art. 18(c), 30(a)",
                "cited_fields": [item["a_id"], item["b_id"]]}
    return {"verdict": "ERROR"}


def check_case(label, truth_path, key_path):
    truth = json.load(open(truth_path, encoding="utf-8"))
    key = json.load(open(key_path, encoding="utf-8"))
    F = fieldmap.truth_to_fields(truth)
    result = analyze(F, stub_judge)
    got = sorted({f["rule_id"] for f in result["findings"]})
    want = sorted({f["rule_id"] for f in key["expected_findings"]})
    got_acc = sorted({a["rule_id"] for a in result["accepted"]})
    want_acc = sorted({a["rule_id"] for a in key["expected_accepted"] if a["rule_id"] in ("CHK-05", "CHK-18", "CHK-20")})
    ok = got == want and result["verdict"] == key["expected_verdict"] and not result["dropped"] and not result["unchecked"]
    print("%s %-5s found=%-30s expected=%-30s accepted-by-judgement=%s" % ("OK  " if ok else "FAIL", label, got, want, got_acc))
    if not ok:
        print("       verdict:", result["verdict"], "dropped:", len(result["dropped"]), "unchecked:", result["unchecked"])
    return ok, got_acc, want_acc


def main():
    index = json.load(open("data/gold/index.json", encoding="utf-8"))
    results = []
    for item in index:
        cid = item["case_id"]
        folder = os.path.join("data", "gold", cid)
        results.append(check_case(cid, os.path.join(folder, "truth.json"), os.path.join(folder, "answer_key.json"))[0])
    results.append(check_case("DEMO", "data/truth/demo.json", "data/demo/demo_answer_key.json")[0])
    passed = sum(results)
    print("\n%d of %d cases passed." % (passed, len(results)))
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
