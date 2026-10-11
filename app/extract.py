"""
extract.py - Gemini READS the documents.

For each uploaded file (PDF, photo, or text) we ask Gemini two things at once:
  1. what kind of document is this?
  2. what are the values of these facts, and which exact words did you read them from?

"Which exact words" is the source snippet. It is what lets us show evidence to the user and
lets the verifier trust a fact.
"""
import html as htmllib
import mimetypes
import re
import time

from . import fieldmap, gemini

INSTRUCTION = (
    "You are a careful trade-finance document reader. You read export documents (letters of credit, "
    "invoices, packing lists, bills of lading, insurance certificates, certificates of origin). "
    "Copy values exactly as written. Never guess: if a value is not on the document, use null."
)


def _field_menu():
    lines = []
    for doc, label in fieldmap.DOC_TYPES.items():
        lines.append('\n"%s" = %s. Facts to read:' % (doc, label))
        for fid, _, kind, desc, _ in fieldmap.fields_for(doc):
            lines.append('  - %s (%s): %s' % (fid, kind, desc))
    return "\n".join(lines)


def build_prompt():
    return (
        "Step 1: decide which ONE document type this file is. Choose from: "
        + ", ".join('"%s"' % d for d in fieldmap.DOC_TYPES) + ".\n"
        "Step 2: read ONLY the facts listed for that document type.\n"
        + _field_menu() + "\n\n"
        "Rules for values:\n"
        "- dates as YYYY-MM-DD\n"
        "- numbers as plain numbers without commas or currency symbols\n"
        "- text exactly as written on the document\n"
        "- true/false for bool facts\n"
        "- null if the fact is not on the document\n\n"
        "For every fact also return \"source\": the short exact words from the document you read it from (under 15 words).\n\n"
        "Return ONLY JSON in this shape:\n"
        '{"document_type": "<type>", "facts": {"<fact id>": {"value": <value or null>, "source": "<exact words>"}}}'
    )


def html_to_text(raw):
    """Turn an HTML page into plain readable text (used for generated test pages)."""
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)</(td|th)>", " | ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</tr>|</p>|</h\d>|</div>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = htmllib.unescape(raw)
    return "\n".join(" ".join(line.split()) for line in raw.splitlines() if line.strip())


def build_parts(filename, data):
    """Turn an uploaded file into the pieces Gemini needs."""
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if mime in ("application/pdf",) or mime.startswith("image/"):
        return [gemini.file_part(data, mime)]
    text = data.decode("utf-8", errors="replace")
    if mime == "text/html":
        text = html_to_text(text)
    return [gemini.text_part("DOCUMENT TEXT:\n" + text)]


def extract_document(filename, data):
    """Read one file. Returns {"filename","document_type","facts":{id:{value,source}},"model_used","tokens"}."""
    parts = build_parts(filename, data) + [gemini.text_part(build_prompt())]
    reply = gemini.generate(parts, instruction=INSTRUCTION)
    obj = gemini.parse_json(reply["text"])
    doc_type = obj.get("document_type")
    facts = {}
    if doc_type in fieldmap.DOC_TYPES:
        allowed = {f[0] for f in fieldmap.fields_for(doc_type)}
        for fid, entry in (obj.get("facts") or {}).items():
            if fid in allowed and isinstance(entry, dict):
                kind = fieldmap.FIELD_INDEX[fid][2]
                value = fieldmap.coerce(kind, entry.get("value"))
                if value is not None:
                    facts[fid] = {"value": value, "source": str(entry.get("source", ""))[:200]}
    return {"filename": filename, "document_type": doc_type, "facts": facts,
            "model_used": reply["model_used"], "tokens": reply["tokens"]}


def extract_all(files, pause=0):
    """files: list of (filename, bytes). Returns (merged facts, per-file log).
    pause = seconds to wait between files (helps stay inside free-tier rate limits)."""
    merged, log = {}, []
    for i, (name, data) in enumerate(files):
        if pause and i:
            time.sleep(pause)
        try:
            r = extract_document(name, data)
        except Exception as e:                      # one bad file must not stop the rest
            log.append({"filename": name, "document_type": None, "error": str(e), "facts_read": 0})
            continue
        for fid, entry in r["facts"].items():
            merged.setdefault(fid, entry)
        log.append({"filename": name, "document_type": r["document_type"], "facts_read": len(r["facts"]),
                    "model_used": r["model_used"], "tokens": r["tokens"]})
    return merged, log
