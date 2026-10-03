"""Which files a D04 historical case executes that issue_47_v1 does not yet bind.

A fresh process registers the synthetic outputs the unit tests use (recorded
mode), builds the D04 case, its Candidate, Evidence and review unit, and then
lists every module it loaded and every rule file it opened - opens are logged
from before the first import, so import-time reads count. Files it lists that
are not in the snapshot's authority are what the mint's AUTHORITY_ADDITIONS
must name. Zero calls; the registration is discarded at the end.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/semantic-route-wiring/measure_executed_files.py
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT))
import builtins, io
opened = set()
_open = builtins.open
def logging_open(path, *a, **k):
    try:
        rp = Path(path).resolve()
        if str(rp).startswith(str(ROOT)) and "/.git/" not in str(rp):
            opened.add(str(rp.relative_to(ROOT)))
    except Exception:
        pass
    return _open(path, *a, **k)
import pathlib
_read_bytes, _read_text = pathlib.Path.read_bytes, pathlib.Path.read_text
def rb(self): logging_open(self, "rb").close(); return _read_bytes(self)
def rt(self, *a, **k): logging_open(self, "rb").close(); return _read_text(self, *a, **k)
pathlib.Path.read_bytes, pathlib.Path.read_text = rb, rt
builtins.open = logging_open
before = set(sys.modules)
from tests.vnext.test_historical_semantic_routes import synthetic_output
from tests.vnext.test_normal_zero_ai_results import original_sources_only
test_modules = set(sys.modules) - before
from vnext import historical_model_session as S, historical_semantic_results as R, capacity_text_results as T
from vnext.normal_period_selection import resolve_period_selection
from vnext.review import create_system_review_decision
from vnext.text_review import build_text_review_unit

with original_sources_only():
    sel = resolve_period_selection(repo_root=ROOT, company_id="marriott_international", report_end="2023-12-31")
    s = S.recorded_historical_model_session()
    plan = s.plan(repo_root=ROOT, company_id="marriott_international", metric_id="D04", period_selection=sel)
    s.register(repo_root=ROOT, company_id="marriott_international", metric_id="D04", period_selection=sel,
               outputs={r["request_id"]: synthetic_output(r) for r in plan["requests"]})
    try:
        case = R.prepare_historical_semantic_case(repo_root=ROOT, company_id="marriott_international", metric_id="D04",
                                                  period_selection=sel, assessment_mode="RECORDED_TEST_ONLY")
        args = {"compiled_spec": case["compiled_spec"], **case["text_arguments"]}
        cand = T.create_deterministic_text_candidate(**args)
        ev = T.build_text_evidence(candidate=cand, **args)
        unit, assets = build_text_review_unit(compiled_spec=case["compiled_spec"], candidate=cand, evidence_check=ev, source_bindings=args["source_references"])
    finally:
        s.discard()
mods = sorted(m for m in sys.modules if m.startswith("vnext.") or m in ("sec_http", "sec_urls", "git_workspace"))
files = []
for m in mods:
    f = getattr(sys.modules[m], "__file__", None)
    if f and f.startswith(str(ROOT)):
        files.append(str(Path(f).relative_to(ROOT)))
m = json.load(open(ROOT / "requirements/issue_47_v1/baseline_manifest.json"))
bound = set(m["execution_authority"]["files"]) | set(m["new_rule_files"])
missing = [f for f in files if f not in bound]
print(len(files), "loaded;", len(missing), "not bound:")
for f in missing: print("   ", f)

data = sorted(f for f in opened if not f.endswith(".py") and not f.startswith("evidence/"))
print("data files read (non-evidence):", len(data))
for f in data: print("   ", "BOUND" if f in bound else "NOT  ", f)
