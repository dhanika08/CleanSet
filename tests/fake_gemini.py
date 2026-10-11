"""
fake_gemini.py - a PRETEND Gemini for tests. It "reads" documents perfectly by looking up the true
facts, and makes simple judgement calls. Used so we can test the web app and evaluation script
without internet or an API key. It proves our plumbing works, not that real Gemini is accurate.
"""
import json
from collections import defaultdict

from app import fieldmap, gemini

GUESS = [("COVERING SCHEDULE", "presentation"), ("MT 700", "lc"), ("COMMERCIAL INVOICE", "invoice"), ("PACKING LIST", "packing_list"),
         ("BILL OF LADING", "bill_of_lading"), ("INSURANCE CERTIFICATE", "insurance"),
         ("CERTIFICATE OF ORIGIN", "certificate_of_origin")]


def install(truth_getter):
    """Replace the real network call. truth_getter() returns the truth dict of the deal being tested."""
    def fake_post(url, key, body, timeout=120):
        prompt = body["contents"][0]["parts"][-1]["text"]
        if "decide which ONE document type" in prompt:
            text = body["contents"][0]["parts"][0].get("text", "")
            doc = next((d for marker, d in GUESS if marker in text.upper()), "presentation")
            tf = fieldmap.truth_to_fields(truth_getter())
            facts = {f[0]: {"value": tf[f[0]]["value"], "source": "stub"} for f in fieldmap.fields_for(doc) if f[0] in tf}
            out = {"document_type": doc, "facts": facts}
        else:
            ok = ("GARMENTS" in prompt) or ("Speicherstr." in prompt) or ("ABOUT" in prompt and "4,800" in prompt)
            out = {"verdict": "ACCEPTABLE" if ok else "CONFLICT", "reason": "stub reason", "article": "UCP 600", "cited_fields": []}
        return 200, {"candidates": [{"content": {"parts": [{"text": json.dumps(out)}]}}], "modelVersion": "stub-model",
                     "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50, "thoughtsTokenCount": 0, "totalTokenCount": 150}}
    gemini._post = fake_post
    gemini._sleep = lambda s: None
