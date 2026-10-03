"""Which files' bytes enter the D04 request identity: perturb (append a comment/space), rebuild, compare.

Runs in a disposable sparse worktree; every run restores the tree first and uses a fresh
bytecode prefix, so no stale bytecode can answer for a perturbed file.
"""
import json, subprocess, sys, tempfile, time
from pathlib import Path
S = Path(sys.argv[1]); wt = Path(sys.argv[2]); position = sys.argv[3]
base = json.loads((S / "probe-base.json").read_text())
code_candidates = ["scripts/vnext/normal_history_catalog.py", "scripts/vnext/r6_semantic_source.py",
                   "scripts/vnext/capacity_semantic_source.py", "scripts/vnext/fiscal_year_labels.py",
                   "scripts/vnext/normal_annual_input_v2.py", "scripts/vnext/historical_fiscal_labels.py",
                   "scripts/vnext/historical_semantic_source.py", "scripts/vnext/historical_annual_input.py",
                   "scripts/vnext/normal_period_selection.py", "scripts/vnext/normal_annual_input.py",
                   "scripts/vnext/continuous_semantic_calls.py", "scripts/vnext/historical_semantic_results.py"]
code_candidates = [c for c in code_candidates if c in base["modules"]]
others = [m for m in base["modules"] if m not in code_candidates]
data_files = ["config/normal_candidate_sources_v1.json", "config/normal_fiscal_year_labels_v1.json",
              "config/normal_period_selection_v1.json", "catalog/r6/semantic_source_v1.json",
              "catalog/r6/semantic_review_v5.json", "config/company_registry.csv"]
def run(label, files):
    subprocess.run(["git", "-C", str(wt), "checkout", "--", "scripts", "config", "catalog"], check=True)
    for f in files:
        p = wt / f
        p.write_bytes(p.read_bytes() + (b"\n# identity probe\n" if f.endswith(".py") else
                                         b"\n" if f.endswith(".csv") else b" "))
    prefix = tempfile.mkdtemp(dir=S)
    started = time.time()
    proc = subprocess.run([sys.executable, str(S / "d04_identity_probe.py"), str(wt), position],
                          cwd=wt, capture_output=True, text=True, timeout=1500,
                          env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                               "PYTHONPYCACHEPREFIX": prefix, "HOME": "/root"})
    subprocess.run(["rm", "-rf", prefix])
    row = {"label": label, "perturbed": files, "seconds": round(time.time() - started)}
    if proc.returncode != 0:
        row.update(outcome="BUILD_FAILED", error=proc.stderr.strip().splitlines()[-1][:300])
    else:
        got = json.loads(proc.stdout)
        row.update(outcome=("ID_MOVED" if got["semantic_source_id"] != base["semantic_source_id"] else "ID_SAME"),
                   digests_moved=got["digests"] != base["digests"])
    print(json.dumps(row), flush=True)
    return row
rows = [run("all_other_loaded_modules", others)]
rows += [run(c, [c]) for c in code_candidates]
rows += [run(d, [d]) for d in data_files]
subprocess.run(["git", "-C", str(wt), "checkout", "--", "scripts", "config", "catalog"], check=True)
(S / "d04-identity-perturbation.json").write_text(json.dumps({"position": position, "base": {k: base[k] for k in ("semantic_source_id", "digests")}, "loaded_module_count": len(base["modules"]), "rows": rows}, indent=1))
print("DONE")
