"""Read current V14 closure without granting the new opt-in module credit."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_semantic_calls import validate_semantic_rule_bindings
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
validate_semantic_rule_bindings(requirement)
validate_wiring_receipt(requirement=requirement)
assert 'scripts/vnext/e01_item_source.py' not in (
    requirement['execution_authority']['files'])
print(json.dumps({'status': 'PASS_EXISTING_V14_AUTHORITY',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'new_module_runtime_authorized': False}, sort_keys=True))
