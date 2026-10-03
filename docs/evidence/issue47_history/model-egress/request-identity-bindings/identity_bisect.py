"""Find every file whose bytes move a request set's identities, by perturbation and bisection.

A disposable sparse worktree; each run restores it, perturbs a set (a comment line for Python,
one trailing space or newline otherwise) and rebuilds in a fresh process with a fresh bytecode
prefix. A set that leaves every identity unchanged holds no relevant file; a set that moves one
(or makes the build refuse) is split until single files remain.
"""
import json, subprocess, sys, tempfile, time
from pathlib import Path
S = Path(sys.argv[1]); wt = Path(sys.argv[2]); metric = sys.argv[3]; position = sys.argv[4]; out = Path(sys.argv[5])
runs = []
def build():
    prefix = tempfile.mkdtemp(dir=S)
    proc = subprocess.run([sys.executable, str(S / "identity_probe.py"), str(wt), metric, position], cwd=wt,
                          capture_output=True, text=True, timeout=3000,
                          env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                               "PYTHONPYCACHEPREFIX": prefix, "HOME": "/root"})
    subprocess.run(["rm", "-rf", prefix])
    return proc
def restore():
    subprocess.run(["git", "-C", str(wt), "checkout", "--", "scripts", "config", "catalog", "requirements"], check=True)
restore()
base_proc = build()
assert base_proc.returncode == 0, base_proc.stderr[-2000:]
base = json.loads(base_proc.stdout)
candidates = base["modules"] + base["data_reads"]
def moved(files):
    restore()
    for f in files:
        p = wt / f
        suffix = (b"\n# identity probe\n" if f.endswith(".py")
                  else b"\n" if f.endswith((".csv", ".md")) else b" ")
        p.write_bytes(p.read_bytes() + suffix)
    started = time.time()
    proc = build()
    row = {"files": len(files), "seconds": round(time.time() - started)}
    if proc.returncode != 0:
        row.update(outcome="BUILD_REFUSED", error=(proc.stderr.strip().splitlines() or [""])[-1][:240])
    else:
        got = json.loads(proc.stdout)["ids"]
        row.update(outcome="MOVED" if got != base["ids"] else "SAME",
                   moved_fields=sorted(k for k in got if got[k] != base["ids"].get(k)))
    if len(files) <= 3:
        row["perturbed"] = files
    runs.append(row); print(json.dumps(row), flush=True)
    return row
found = []
def bisect(files):
    if not files:
        return
    row = moved(files)
    if row["outcome"] == "SAME":
        return
    if len(files) == 1:
        found.append({"file": files[0], **{k: row[k] for k in ("outcome", "moved_fields", "error") if k in row}})
        return
    half = len(files) // 2
    bisect(files[:half]); bisect(files[half:])
bisect([c for c in candidates if not c.endswith(".gz")])
restore()
out.write_text(json.dumps({"metric": metric, "position": position, "base_ids": base["ids"],
                           "candidates": len(candidates), "found": found, "runs": runs,
                           "not_perturbed": [c for c in candidates if c.endswith(".gz")]}, indent=1))
print("DONE", json.dumps(found))
