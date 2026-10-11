"""
main.py - the web server.

    GET  /              the page
    GET  /health        for Cloud Run checks
    POST /api/analyze   upload documents, get the verdict
    POST /api/demo      run the bundled demo deal

Safety limits: at most 10 files, 10 MB each, and a simple per-visitor request limit,
so a public link cannot burn through the free quota.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from . import extract, judge
from .files import collect_files
from .pipeline import analyze
from .web import PAGE

app = FastAPI(title="CleanSet")

MAX_FILES = 10
MAX_BYTES = 10 * 1024 * 1024
LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "12"))
DEMO_DIR = os.environ.get("DEMO_DIR", "data/demo/planted")
DEMO_CACHE_SECONDS = 600

_hits = defaultdict(deque)
_demo_cache = {"time": 0, "payload": None}


def _check_rate(request: Request):
    who = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    now = time.time()
    q = _hits[who]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= LIMIT_PER_HOUR:
        raise HTTPException(429, "Too many checks from this connection in the last hour. Please try again later.")
    q.append(now)


def _run(files):
    start = time.time()
    facts, log = extract.extract_all(files)
    if not facts:
        raise HTTPException(502, "Gemini could not read any facts from these files. Please try again in a moment.")
    result = analyze(facts, judge.judge)
    return {"result": result, "read_log": log, "seconds": round(time.time() - start, 1), "cached": False}


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def api_analyze(request: Request, files: list[UploadFile] = File(...)):
    _check_rate(request)
    if not 1 <= len(files) <= MAX_FILES:
        raise HTTPException(400, "Please upload between 1 and %d files." % MAX_FILES)
    loaded = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(400, "%s is larger than 10 MB." % f.filename)
        loaded.append((f.filename or "file", data))
    return _run(loaded)


@app.post("/api/demo")
def api_demo(request: Request):
    now = time.time()
    if _demo_cache["payload"] and now - _demo_cache["time"] < DEMO_CACHE_SECONDS:
        return dict(_demo_cache["payload"], cached=True)
    _check_rate(request)
    if not os.path.isdir(DEMO_DIR):
        raise HTTPException(500, "Demo documents are missing from this deployment.")
    payload = _run(collect_files(DEMO_DIR))
    _demo_cache.update(time=now, payload=payload)
    return payload
