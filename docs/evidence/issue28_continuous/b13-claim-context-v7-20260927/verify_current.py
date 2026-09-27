"""Read-only current identity check after the V7 diagnostic rebind."""
import json
from pathlib import Path

from vnext.canonical import content_hash, sha256_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
validate_execution_authority(repo_root=ROOT, requirement=requirement)
provider = validate_wiring_receipt(requirement=requirement)
authority = content_hash(value=requirement['execution_authority'])
paths = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)
evidence_counts = [len(provider['evidence'])]
for relative in paths:
    value = json.loads((ROOT/relative).read_text())
    assert value['execution_authority_hash'] == authority
    for name, digest in value['evidence'].items():
        assert sha256_file(path=ROOT/name) == digest, name
    evidence_counts.append(len(value['evidence']))
print(json.dumps({'code_root': str(ROOT),
    'v14_closure': requirement['requirement_closure_hash'],
    'execution_authority_hash': authority,
    'provider_sec_refresh_evidence_counts': evidence_counts,
    'all_current_receipts_match': True}, sort_keys=True))
