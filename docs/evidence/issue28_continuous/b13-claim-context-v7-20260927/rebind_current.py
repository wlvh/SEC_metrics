"""Rebind only the unfrozen #28 V14 execution files after local V7 checks."""
import hashlib
import json
from pathlib import Path
import subprocess

from vnext.canonical import content_hash, sha256_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot

HERE = Path(__file__).resolve().parent
BASE = '1613dab6b4d41e378c5f6d3ef922789f14ff0331'
FILES = (
    'scripts/vnext/capacity_reference_contract.py',
    'scripts/vnext/capacity_two_stage.py',
    'scripts/vnext/continuous_semantic_calls.py',
    'scripts/vnext/capacity_native_assessment.py',
    'scripts/vnext/native_assessment_replay.py',
    'scripts/vnext/native_unit_index.py',
)
RECEIPTS = (
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/provider-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/b13-two-stage-offline-20260925/sec-wiring-v6-suspended.json',
    'docs/evidence/issue28_continuous/ordinary-refresh-cycle/wiring.json',
)


def binding(content):
    return {'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    path = ROOT/'requirements/issue_28_v14/baseline_manifest.json'
    baseline = json.loads(path.read_text())
    before = {}
    for relative in FILES:
        old = subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)
        expected = binding(old)
        assert baseline['execution_authority']['files'][relative] == expected
        if relative in baseline['new_rule_files']:
            assert baseline['new_rule_files'][relative] == expected
        before[relative] = expected
    write(HERE/'binding-before.json', {'pushed_parent': BASE, 'files': before,
        'prior_v14_closure': json.loads((ROOT/RECEIPTS[0]).read_text())[
            'requirement_closure_hash']})
    for relative in FILES:
        current = binding((ROOT/relative).read_bytes())
        baseline['execution_authority']['files'][relative] = current
        if relative in baseline['new_rule_files']:
            baseline['new_rule_files'][relative] = current
    write(path, baseline)
    requirement = load_requirement_snapshot(snapshot_dir=path.parent)
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    authority = content_hash(value=requirement['execution_authority'])
    for relative in RECEIPTS:
        receipt_path = ROOT/relative
        receipt = json.loads(receipt_path.read_text())
        receipt['execution_authority_hash'] = authority
        if 'requirement_closure_hash' in receipt:
            receipt['requirement_closure_hash'] = requirement['requirement_closure_hash']
        if relative == RECEIPTS[0]:
            receipt['scope'] += (' V7 separates nonoverlapping claim spans from shared '
                'sentence context in offline diagnostics; its provider and native '
                'entrypoints are still default-closed. The short current-factory '
                'guards and V5/V6 byte-compatibility checks are recorded separately.')
            receipt['claim_context_v7_review'] = 'PENDING_EXACT_PATCH_REVIEW'
            for evidence in ('legacy-identity.log', 'targeted-tests.log'):
                name = (HERE/evidence).relative_to(ROOT).as_posix()
                receipt['evidence'][name] = sha256_file(path=HERE/evidence)
        write(receipt_path, receipt)
    validate_wiring_receipt(requirement=requirement)
    write(HERE/'binding-after.json', {
        'code_root': str(ROOT), 'pushed_parent': BASE,
        'changed_execution_files': list(FILES),
        'v14_closure': requirement['requirement_closure_hash'],
        'execution_authority_hash': authority,
        'v13_frozen_binding_modified': False,
        'provider_paid_sec_calls': [0, 0, 0],
        'current_provider_receipt_validated': True})
    print(json.dumps({'v14_closure': requirement['requirement_closure_hash'],
        'execution_authority_hash': authority, 'changed_files': len(FILES)},
        sort_keys=True))


if __name__ == '__main__':
    main()
