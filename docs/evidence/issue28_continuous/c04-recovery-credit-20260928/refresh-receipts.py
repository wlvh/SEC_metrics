"""Bind existing zero-egress receipts to the tested current authority."""
from copy import deepcopy
import json
from pathlib import Path

from vnext.canonical import content_hash
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
RECEIPTS = (
    Path('docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json'),
    Path('docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json'),
    Path('docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json'),
)


def main():
    before = json.loads((HERE/'binding-before.json').read_text())
    after = json.loads((HERE/'binding-after.json').read_text())
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements/issue_28_v14')
    assert requirement['requirement_closure_hash'] == after['continuous_requirement_closure']
    old_execution = deepcopy(requirement['execution_authority'])
    for relative, entry in before['bindings']['requirements/issue_28_v14'].items():
        old_execution['files'][relative] = entry['execution_authority']
    old_authority = content_hash(value=old_execution)
    new_authority = content_hash(value=requirement['execution_authority'])
    old_controller = before['bindings']['requirements/issue_28_v14'][
        'scripts/vnext/c04_update_cycle.py']['execution_authority']['sha256']
    new_controller = after['bindings']['scripts/vnext/c04_update_cycle.py']['sha256']
    for relative in RECEIPTS:
        path = ROOT/relative
        receipt = json.loads(path.read_text())
        assert receipt['execution_authority_hash'] == old_authority
        if 'c04_controller_sha256' in receipt:
            assert receipt['c04_controller_sha256'] == old_controller
            receipt['c04_controller_sha256'] = new_controller
        receipt['execution_authority_hash'] = new_authority
        if 'requirement_closure_hash' in receipt:
            receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    validate_wiring_receipt(requirement=requirement)
    print(json.dumps({'old_execution_authority_hash': old_authority,
        'new_execution_authority_hash': new_authority,
        'receipt_paths': [str(path) for path in RECEIPTS]}, sort_keys=True))


if __name__ == '__main__':
    main()
