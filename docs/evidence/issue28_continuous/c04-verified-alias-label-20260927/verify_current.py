"""Read-only V13/V14 and current factory/controller receipt identity check."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.canonical import content_hash, sha256_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

FROZEN = 'scripts/vnext/governance_signals.py'
HEAD = '084ed60139d847b182631ff549820b078f930b15'
assert (ROOT / FROZEN).read_bytes() == subprocess.check_output(
    ['git', 'show', HEAD + ':' + FROZEN], cwd=ROOT)
parent = load_requirement_snapshot(
    snapshot_dir=ROOT / 'requirements/issue_28_v13')
child = load_requirement_snapshot(
    snapshot_dir=ROOT / 'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=parent)
validate_execution_authority(repo_root=ROOT, requirement=child)
assert child['parent_snapshot']['requirement_closure_hash'] == parent[
    'requirement_closure_hash']
receipt = validate_wiring_receipt(requirement=child)
authority = content_hash(value=child['execution_authority'])
other = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)
counts = [len(receipt['evidence'])]
for relative in other:
    value = json.loads((ROOT / relative).read_text())
    assert value['execution_authority_hash'] == authority
    for name, digest in value['evidence'].items():
        assert sha256_file(path=ROOT / name) == digest, name
    counts.append(len(value['evidence']))
print(json.dumps({'status': 'PASS_CURRENT_C04_ALIAS_LABEL_WIRING',
    'code_root': str(ROOT),
    'v13_closure': parent['requirement_closure_hash'],
    'v14_closure': child['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'provider_sec_refresh_evidence_counts': counts,
    'frozen_governance_signals_bytes_unchanged': True,
    'new_calls': [0, 0, 0]}, sort_keys=True))
