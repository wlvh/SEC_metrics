"""Which files an E01 historical case executes that issue_47_v1 does not yet bind.

A fresh process registers a synthetic confirmation (recorded mode) for one
window with candidates, prepares the E01 Run input from it - which reads the
registration back and checks it again under the current code - and then lists
every module it loaded and every rule file it opened. Opens are logged from
before the first import, so import-time reads count. Files it lists that are
not in the snapshot's authority are what the mint's AUTHORITY_ADDITIONS must
name. Zero calls; the registration is removed at the end.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/e01-content-confirmed/measure_executed_files.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import builtins
import pathlib

opened = set()
_open = builtins.open


def logging_open(path, *args, **kwargs):
    try:
        resolved = Path(path).resolve()
        if str(resolved).startswith(str(ROOT)) and "/.git/" not in str(resolved):
            opened.add(str(resolved.relative_to(ROOT)))
    except (TypeError, ValueError, OSError):
        pass
    return _open(path, *args, **kwargs)


_read_bytes, _read_text = pathlib.Path.read_bytes, pathlib.Path.read_text


def read_bytes(self):
    logging_open(self, "rb").close()
    return _read_bytes(self)


def read_text(self, *args, **kwargs):
    logging_open(self, "rb").close()
    return _read_text(self, *args, **kwargs)


pathlib.Path.read_bytes, pathlib.Path.read_text = read_bytes, read_text
builtins.open = logging_open

from vnext import historical_ma_confirmation as confirmation  # noqa: E402
from vnext.historical_results import prepare_historical_run_input  # noqa: E402
from vnext.historical_zero_ai_results import e01_confirmation_request  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

COMPANY, REPORT_END = "ford_motor_company", "2025-12-31"
selection = resolve_period_selection(repo_root=ROOT, company_id=COMPANY, report_end=REPORT_END)
request, _ = e01_confirmation_request(repo_root=ROOT, company_id=COMPANY, period_selection=selection)
output = json.dumps({"item_decisions": [
    {"item_id": item["item_id"], "decision": "DOES_NOT_REPORT_A_TRANSACTION",
     "quote": item["text"][:120].strip()} for item in request["items"]]}).encode("utf-8")
record, path = confirmation.register_confirmation(
    request=request, period_selection_id=selection["selection_id"], output=output,
    mode="RECORDED_TEST_ONLY")
try:
    prepared = prepare_historical_run_input(repo_root=ROOT, company_id=COMPANY, metric_id="E01",
                                            period_selection=selection,
                                            assessment_mode="RECORDED_TEST_ONLY")
    assert prepared["primary_result"]["publication"] == "PUBLISHED", prepared["primary_result"]
finally:
    path.unlink()
    for parent in path.parents:
        if parent.name == "RECORDED_TEST_ONLY" or any(parent.iterdir()):
            break
        parent.rmdir()
# What the case read, taken before this script reads the manifest itself.
case_opened = set(opened)

modules = sorted(name for name in sys.modules
                 if name.startswith("vnext.") or name in ("sec_http", "sec_urls", "git_workspace"))
files = []
for name in modules:
    location = getattr(sys.modules[name], "__file__", None)
    if location and location.startswith(str(ROOT)):
        files.append(str(Path(location).relative_to(ROOT)))
manifest = json.loads((ROOT / "requirements/issue_47_v1/baseline_manifest.json").read_text(encoding="utf-8"))
bound = set(manifest["execution_authority"]["files"]) | set(manifest["new_rule_files"])
missing = [name for name in files if name not in bound]
data = sorted(name for name in case_opened if not name.endswith(".py") and not name.startswith("evidence/"))
report = {"case": {"company_id": COMPANY, "report_end": REPORT_END, "metric_id": "E01",
                   "registration_mode": "RECORDED_TEST_ONLY", "items": len(request["items"])},
          "modules_loaded": len(files), "modules_not_bound": missing,
          "data_files_read": [{"path": name, "bound": name in bound} for name in data],
          "calls": [0, 0, 0]}
print(json.dumps(report, indent=1, ensure_ascii=False))
