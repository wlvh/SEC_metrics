"""Run selected verify.py injections in the review copy, judged as verify.py judges them,
and keep each failing case's last raised line. Restores every file byte for byte."""
import hashlib, json, os, subprocess, sys, tempfile, shutil
from pathlib import Path

C = Path(sys.argv[1]); names = sys.argv[2].split(","); out = Path(sys.argv[3])
extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []
guard = sys.argv[5] if len(sys.argv) > 5 else ""
src = (C / "docs/evidence/issue47_history/model-egress/verify.py").read_text()
ns = {}
ns["Path"] = Path
exec(src[src.index("HERE = "):src.index("SLOW_FIRST = ")], ns)
table = {name: (path, edits) for name, path, edits in ns["INJECTIONS"]}
table.update({row["id"]: (row["file"], [tuple(e) for e in row["edits"]]) for row in extra})
expected = dict(ns["EXPECTED"]); expected.update({row["id"]: row["expected"] for row in extra})
SUITE = ns["SUITE"]

def failures(lines):
    rows = []
    for i, line in enumerate(lines):
        if line.startswith(("FAIL: ", "ERROR: ")):
            case = line.split(": ", 1)[1].split(" (")[0]
            raised = ""
            for later in lines[i + 2:]:
                if later.startswith(("=" * 20, "-" * 20)):
                    break
                if later.strip():
                    raised = later.strip()
            rows.append({"case": case, "raised": raised[:240]})
    return rows

results = []
for name in names:
    path, edits = table[name]
    target = C / path
    original = target.read_bytes()
    text = original.decode()
    assert all(text.count(old) == 1 for old, _ in edits), name
    for old, new in edits:
        text = text.replace(old, new)
    compile(text, path, "exec")
    klass = expected[name]
    dotted = klass if klass.startswith("tests.") else SUITE + "." + klass
    private = Path(tempfile.mkdtemp(prefix="inj-", dir=os.environ["TMPDIR"]))
    (private / "pyc").mkdir(); (private / "tmp").mkdir()
    try:
        target.write_text(text, encoding="utf-8")
        env = {**os.environ, "PYTHONPYCACHEPREFIX": str(private / "pyc"), "TMPDIR": str(private / "tmp"),
               "PYTHONPATH": guard}
        run = subprocess.run([sys.executable, "-m", "unittest", "-f", dotted], cwd=C,
                             capture_output=True, text=True, timeout=3000, env=env)
    finally:
        target.write_bytes(original)
        shutil.rmtree(private, ignore_errors=True)
    assert hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(original).digest()
    lines = run.stderr.strip().splitlines()
    rows = failures(lines)
    results.append({"id": name, "expected_class": klass, "returncode": run.returncode,
                    "caught": run.returncode != 0 and any(r["case"] not in ("setUpClass", "setUpModule") for r in rows),
                    "failures": rows, "summary": lines[-1] if lines else ""})
    print(name, "CAUGHT" if results[-1]["caught"] else "NOT_CAUGHT", [r["case"] for r in rows], flush=True)
    out.write_text(json.dumps(results, indent=1))
