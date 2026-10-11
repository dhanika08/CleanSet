"""
gemini.py - the one place that talks to Google's Gemini API.

Everything else in CleanSet calls generate() from here. It handles three annoying realities:
  1. A model can be busy (HTTP 503) or rate-limited (429): we wait and retry up to 3 times.
  2. A model name can disappear (HTTP 404): we switch to a fallback model.
  3. We want to record which model really answered, and how many tokens it used.

Settings come from environment variables, so nothing secret or model-specific is in the code:
    GEMINI_API_KEY          your key (never written in code or printed)
    GEMINI_MODEL            main model          (default gemini-3.7-flash)
    GEMINI_FALLBACK_MODEL   backup model        (default gemini-3.5-flash)
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_TRIES_PER_MODEL = 3


class GeminiError(Exception):
    pass


def _sleep(seconds):                      # a separate function so tests can skip the waiting
    time.sleep(seconds)


def _post(url, api_key, body, timeout=120):
    """Send one request. Returns (http_status, parsed_json). The key goes in a header, not in the URL."""
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {}
        return e.code, payload
    except Exception as e:                # network problem
        return 0, {"error": {"message": str(e)}}


def text_part(text):
    return {"text": text}


def file_part(data, mime):
    """Attach a PDF or image to the request."""
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}


def parse_json(text):
    """Gemini sometimes wraps JSON in ``` fences or adds a sentence. Pull out the JSON object."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise GeminiError("Gemini did not return valid JSON")


def generate(parts, instruction=None, json_mode=True):
    """
    Ask Gemini something.
    parts: list of text_part(...) / file_part(...)
    Returns {"text", "model_used", "tokens", "tries"}.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiError("GEMINI_API_KEY is not set")
    models = [os.environ.get("GEMINI_MODEL", "gemini-3.7-flash"),
              os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")]

    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0}}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    if instruction:
        body["systemInstruction"] = {"parts": [{"text": instruction}]}

    tries, last_error = 0, ""
    for model in models:
        for attempt in range(MAX_TRIES_PER_MODEL):
            tries += 1
            status, payload = _post(API_URL.format(model=model), api_key, body)
            if status == 200:
                cand = (payload.get("candidates") or [{}])[0]
                texts = [p["text"] for p in (cand.get("content", {}).get("parts") or [])
                         if "text" in p and not p.get("thought")]
                if not texts:
                    last_error = "empty answer (finish reason: %s)" % cand.get("finishReason")
                    continue
                usage = payload.get("usageMetadata", {})
                return {"text": "".join(texts),
                        "model_used": payload.get("modelVersion", model),
                        "tokens": {"input": usage.get("promptTokenCount", 0),
                                   "output": usage.get("candidatesTokenCount", 0),
                                   "thinking": usage.get("thoughtsTokenCount", 0),
                                   "total": usage.get("totalTokenCount", 0)},
                        "tries": tries}
            msg = (payload.get("error") or {}).get("message", "")
            last_error = "%s on %s: %s" % (status, model, msg[:200])
            if status in RETRY_STATUSES or status == 0:
                _sleep(2 * (attempt + 1))         # wait 2s, then 4s, then 6s
                continue
            if status == 404:                     # this model name is not available: go to the fallback
                break
            raise GeminiError(last_error)         # 400/401/403 etc: retrying will not help
    raise GeminiError("All attempts failed. Last error: " + last_error)
