"""
web_test.py - tests the web server (page, health, upload, demo, limits) using a PRETEND Gemini.
Run from the project root:   python3 tests/web_test.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["GEMINI_API_KEY"] = "test-key-not-real"
os.environ["DEMO_DIR"] = "data/demo/planted"
os.environ["RATE_LIMIT_PER_HOUR"] = "5"
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))
import fake_gemini
from app import main

state = {"truth": json.load(open("data/truth/demo.json"))}
fake_gemini.install(lambda: state["truth"])
client = TestClient(main.app)
failures = []


def expect(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        failures.append(name)


r = client.get("/")
expect("home page loads and has the demo button", r.status_code == 200 and "Try the demo deal" in r.text)
expect("health check", client.get("/health").json() == {"status": "ok"})

r = client.post("/api/demo")
j = r.json()
expect("demo deal returns 4 problems", r.status_code == 200 and j["result"]["problem_count"] == 4 and j["result"]["verdict"] == "discrepant")
expect("demo shows the two accepted variations", sorted(a["rule_id"] for a in j["result"]["accepted"]) == ["CHK-18", "CHK-20"])
expect("every finding carries evidence and a fix", all(f["evidence"] and f["fix"] for f in j["result"]["findings"]))
expect("first demo call is not cached", j["cached"] is False)
r2 = client.post("/api/demo")
expect("second demo call is served from cache", r2.json()["cached"] is True)

# upload a compliant deal
state["truth"] = json.load(open("data/gold/C01/truth.json"))
folder = "data/gold/C01/docs"
files = [("files", (n, open(os.path.join(folder, n), "rb").read())) for n in sorted(os.listdir(folder)) if n.endswith((".html", ".txt"))]
r = client.post("/api/analyze", files=files)
expect("upload of a clean deal says ready to submit", r.status_code == 200 and r.json()["result"]["verdict"] == "compliant")

# upload with an error
state["truth"] = json.load(open("data/gold/E06/truth.json"))
folder = "data/gold/E06/docs"
files = [("files", (n, open(os.path.join(folder, n), "rb").read())) for n in sorted(os.listdir(folder)) if n.endswith((".html", ".txt"))]
r = client.post("/api/analyze", files=files)
j = r.json()
expect("upload with low insurance finds CHK-11", [f["rule_id"] for f in j["result"]["findings"]] == ["CHK-11"])

# limits
r = client.post("/api/analyze", files=[("files", ("x%d.txt" % i, b"hello")) for i in range(11)])
expect("more than 10 files is refused", r.status_code in (400, 429))
codes = [client.post("/api/analyze", files=[("files", ("a.txt", b"hello"))]).status_code for _ in range(8)]
expect("rate limit eventually returns 429", 429 in codes)

print("\n%d problem(s)." % len(failures))
sys.exit(1 if failures else 0)
