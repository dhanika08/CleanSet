"""
judge.py - Gemini makes the JUDGEMENT calls.

Plain code cannot decide whether "cotton garments" conflicts with "100% cotton polo shirts".
Gemini can, if we give it the relevant banking principles (paraphrased from UCP 600) and ask
it to answer in a fixed format, naming only the facts it was given.
"""
from . import gemini

INSTRUCTION = (
    "You are an experienced letter-of-credit document checker at a bank. Apply these principles:\n"
    "- Data in documents need not be identical to the credit, but must not conflict (UCP 600 Art. 14(d)).\n"
    "- The commercial invoice goods description must correspond to the credit (Art. 18(c)).\n"
    "- Other documents may describe goods in general terms that do not conflict with the credit (Art. 14(e)).\n"
    "- 'About' allows a 10 percent tolerance more or less on the quantity (Art. 30(a)).\n"
    "- Address details need not be identical but must be in the same country (Art. 14(j)).\n"
    "Decide only from the two texts given. Do not invent facts. "
    "Use ONLY the fact ids given to you in cited_fields."
)


def judge(item):
    prompt = (
        "Question: %s\n\nFact A (id %s):\n%s\n\nFact B (id %s):\n%s\n\n"
        "Answer ONLY with JSON: "
        '{"verdict": "CONFLICT" or "ACCEPTABLE", "reason": "one plain sentence a business owner can understand", '
        '"article": "UCP 600 article that applies", "cited_fields": ["%s", "%s"]}'
    ) % (item["question"], item["a_id"], item["a_text"], item["b_id"], item["b_text"], item["a_id"], item["b_id"])
    try:
        reply = gemini.generate([gemini.text_part(prompt)], instruction=INSTRUCTION)
        obj = gemini.parse_json(reply["text"])
        verdict = str(obj.get("verdict", "")).upper()
        if verdict not in ("CONFLICT", "ACCEPTABLE"):
            return {"verdict": "ERROR", "reason": "unexpected answer"}
        return {"verdict": verdict, "reason": str(obj.get("reason", "")), "article": str(obj.get("article", "")),
                "cited_fields": obj.get("cited_fields") or [item["a_id"], item["b_id"]],
                "model_used": reply["model_used"], "tokens": reply["tokens"]}
    except Exception as e:
        return {"verdict": "ERROR", "reason": str(e)}
