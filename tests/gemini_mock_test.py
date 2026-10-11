"""
gemini_mock_test.py - tests our Gemini code against a PRETEND Google server.

It checks: normal answers work, a busy model (503) is retried, a missing model (404) falls back,
a bad request (400) fails at once, JSON wrapped in ``` is read, and the reader keeps only valid facts.
No internet and no API key needed.
Run from the project root:   python3 tests/gemini_mock_test.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["GEMINI_API_KEY"] = "test-key-not-real"
from app import gemini, extract, judge

gemini._sleep = lambda s: None                      # do not actually wait in tests
calls = []


def ok(text, model="gemini-3.8-flash"):
    return 200, {"candidates": [{"content": {"parts": [{"text": text, "thoughtSignature": "x"}]}, "finishReason": "STOP"}],
                 "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "thoughtsTokenCount": 3, "totalTokenCount": 18},
                 "modelVersion": model}


def run(script, fn):
    """script = list of (status, payload) the pretend server returns, in order."""
    calls.clear()
    it = iter(script)

    def fake_post(url, key, body, timeout=120):
        calls.append(url.split("/models/")[1].split(":")[0])
        return next(it)
    gemini._post = fake_post
    return fn()


failures = []


def expect(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        failures.append(name)


# 1. normal answer
r = run([ok('{"a": 1}')], lambda: gemini.generate([gemini.text_part("hi")]))
expect("normal answer returns text and token counts", r["text"] == '{"a": 1}' and r["tokens"]["total"] == 18)

# 2. busy model is retried on the same model
r = run([(503, {"error": {"message": "busy"}}), ok("{}")], lambda: gemini.generate([gemini.text_part("hi")]))
expect("503 is retried on the main model", calls == ["gemini-3.7-flash", "gemini-3.7-flash"] and r["tries"] == 2)

# 3. 404 goes straight to the fallback model
r = run([(404, {"error": {"message": "gone"}}), ok("{}")], lambda: gemini.generate([gemini.text_part("hi")]))
expect("404 switches to the fallback model", calls == ["gemini-3.7-flash", "gemini-3.5-flash"])

# 4. three busy answers then fallback
r = run([(503, {})] * 3 + [ok("{}")], lambda: gemini.generate([gemini.text_part("hi")]))
expect("3 busy answers then fallback model", calls == ["gemini-3.7-flash"] * 3 + ["gemini-3.5-flash"])

# 5. everything fails
try:
    run([(503, {})] * 6, lambda: gemini.generate([gemini.text_part("hi")]))
    expect("total failure raises an error", False)
except gemini.GeminiError:
    expect("total failure raises an error", True)

# 6. bad request is not retried
try:
    run([(400, {"error": {"message": "bad"}})], lambda: gemini.generate([gemini.text_part("hi")]))
    expect("400 fails immediately without retry", False)
except gemini.GeminiError:
    expect("400 fails immediately without retry", len(calls) == 1)

# 7. JSON inside code fences
expect("JSON in ``` fences is read", gemini.parse_json('```json\n{"x": 2}\n```') == {"x": 2})
expect("JSON with chatter around it is read", gemini.parse_json('Here you go: {"x": 3} Thanks') == {"x": 3})

# 8. the reader keeps valid facts only
reply = {"document_type": "bill_of_lading", "facts": {
    "bill_of_lading.port_of_loading": {"value": "Tuticorin, India", "source": "Port of loading TUTICORIN"},
    "bill_of_lading.gross_weight_kg": {"value": "1,180.0 KGS", "source": "1,180.0 KGS"},
    "bill_of_lading.shipped_on_board_date": {"value": "10 Nov 2026", "source": "Shipped on board 10 Nov 2026"},
    "invoice.total_amount": {"value": 5, "source": "wrong document type, must be ignored"},
    "bill_of_lading.made_up_field": {"value": "x", "source": "x"}}}
r = run([ok(json.dumps(reply))], lambda: extract.extract_document("bl.pdf", b"%PDF fake"))
f = r["facts"]
expect("reader keeps valid facts and cleans them",
       f["bill_of_lading.gross_weight_kg"]["value"] == 1180.0 and f["bill_of_lading.shipped_on_board_date"]["value"] == "2026-11-10")
expect("reader drops facts from other document types and unknown facts",
       "invoice.total_amount" not in f and "bill_of_lading.made_up_field" not in f and len(f) == 3)

# 9. judge
j = run([ok('{"verdict": "ACCEPTABLE", "reason": "General wording, no conflict.", "article": "Art. 14(e)", "cited_fields": ["a","b"]}')],
        lambda: judge.judge({"question": "q", "a_id": "a", "b_id": "b", "a_text": "x", "b_text": "y"}))
expect("judge returns a verdict", j["verdict"] == "ACCEPTABLE" and j["model_used"] == "gemini-3.8-flash")
j = run([ok('{"verdict": "MAYBE"}')], lambda: judge.judge({"question": "q", "a_id": "a", "b_id": "b", "a_text": "x", "b_text": "y"}))
expect("judge treats an unexpected verdict as ERROR", j["verdict"] == "ERROR")

# 10. html to text
txt = extract.html_to_text("<html><style>a{}</style><td>Port</td><td><b>TUTICORIN, INDIA</b></td></html>")
expect("html is turned into readable text", "TUTICORIN, INDIA" in txt and "a{}" not in txt)

print("\n%d problem(s)." % len(failures))
sys.exit(1 if failures else 0)
