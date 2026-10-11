"""
pipeline.py - joins the steps together.

    facts read from documents  ->  plain-code rule checks
                               ->  judgement questions (Gemini)
                               ->  verifier
                               ->  verdict

The function analyze() takes the facts and a "judge" function. In the real app the judge
calls Gemini. In offline tests it is a simple stand-in, so we can test everything else.
"""
from . import fieldmap
from .rules import run_rules, judgement_items, judgement_finding
from .verify import verify_findings


def clean_values(F):
    """From {id: {"value","source"}} make {id: clean value}, dropping anything unreadable."""
    V = {}
    for fid, entry in F.items():
        spec = fieldmap.FIELD_INDEX.get(fid)
        if not spec or not isinstance(entry, dict):
            continue
        v = fieldmap.coerce(spec[2], entry.get("value"))
        if v is not None:
            V[fid] = v
    return V


def analyze(F, judge):
    V = clean_values(F)
    findings, unchecked = run_rules(V)

    accepted = []
    for item in judgement_items(V):
        verdict = judge(item)
        v = (verdict or {}).get("verdict", "ERROR")
        if v == "CONFLICT":
            findings.append(judgement_finding(item, verdict))
        elif v == "ACCEPTABLE":
            accepted.append({"rule_id": item["rule_id"], "reason": verdict.get("reason", ""),
                             "article": verdict.get("article", ""),
                             "compared": [item["a_id"], item["b_id"]]})
        else:
            unchecked.append(item["rule_id"])

    kept, dropped = verify_findings(findings, V, F)
    kept.sort(key=lambda f: f["rule_id"])
    return {
        "verdict": "discrepant" if kept else "compliant",
        "problem_count": len(kept),
        "findings": kept,
        "accepted": accepted,
        "dropped": dropped,
        "unchecked": sorted(set(unchecked)),
    }
