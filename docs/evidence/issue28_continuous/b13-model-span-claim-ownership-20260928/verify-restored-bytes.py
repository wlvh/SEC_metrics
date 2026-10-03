"""Check that the stopped V8 experiment left current code at its prior bytes."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

BASE = 'ba56a51fb069ff53c4b9a831b901c4323c06d534'
PATHS = (
    'scripts/vnext/capacity_two_stage.py',
    'tests/vnext/test_capacity_two_stage.py',
    'requirements/issue_28_v14/baseline_manifest.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)
for relative in PATHS:
    expected = subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)
    assert (ROOT / relative).read_bytes() == expected, relative
requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_wiring_receipt(requirement=requirement)
print('PASS: six current files byte-identical to ' + BASE)
print('PASS: V14 execution authority and provider, SEC, refresh wiring')
print('requirement_closure_hash', requirement['requirement_closure_hash'])
