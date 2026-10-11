"""
verify.py - the verifier. Its job: do not let the AI invent things.

A finding is only kept if EVERY fact it points to was actually read from a document.
If a finding mentions a fact that does not exist (or has no value), it is thrown away
and recorded in "dropped", so we can show how often the AI tried to make something up.
"""


def verify_findings(findings, V, F):
    """
    findings : list of finding dicts
    V        : field_id -> clean value
    F        : field_id -> {"value", "source"}   (what was read, with the text it came from)
    Returns (kept, dropped). Each kept finding gets an "evidence" list.
    """
    kept, dropped = [], []
    for f in findings:
        cited = f.get("fields") or []
        bad = [c for c in cited if V.get(c) is None]
        if not cited or bad:
            dropped.append({"rule_id": f.get("rule_id"), "reason": "cites facts that were not read from the documents: %s" % (bad or "none cited"),
                            "finding": f})
            continue
        f = dict(f)
        f["evidence"] = [{"field": c, "value": V[c], "source": F[c].get("source", "")} for c in cited]
        kept.append(f)
    return kept, dropped
