"""Append no-network receipts after fail-closing B13 V6 native acceptance."""
import json
from pathlib import Path

from vnext.canonical import content_hash, sha256_file, strict_json_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent


def checked(receipt):
    for relative, digest in receipt['evidence'].items():
        assert sha256_file(path=ROOT/relative) == digest, relative
    return dict(receipt['evidence'])


def append(evidence, *names):
    for name in names:
        path = HERE/name
        evidence[str(path.relative_to(ROOT))] = sha256_file(path=path)
    return evidence


def main():
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements/issue_28_v14')
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    closure = requirement['requirement_closure_hash']
    execution_hash = content_hash(value=requirement['execution_authority'])
    directed = (HERE/'assertion-v6-suspension-directed.log').read_text()
    material = (HERE/'assertion-v6-suspension-material.log').read_text()
    provider_log = (HERE/'provider-wiring-test-v6-suspended.log').read_text()
    assert 'Ran 32 tests' in directed and '\nOK\n' in directed
    assert 'Ran 1 test' in material and '\nOK\n' in material
    assert ('OFFLINE_WIRING_PASS' in provider_log and closure in provider_log
            and 'Ran 1 test' in provider_log and '\nOK\n' in provider_log)
    provider_path = ROOT/requirement['policy']['offline_wiring_receipt_path']
    sec_path = ROOT/requirement['policy']['sec_wiring_receipt_path']
    assert provider_path == HERE/'provider-wiring-v6-suspended.json'
    assert sec_path == HERE/'sec-wiring-v6-suspended.json'
    old_provider = strict_json_file(path=HERE/'provider-wiring-assertion-repair.json')
    old_sec = strict_json_file(path=HERE/'sec-wiring-assertion-repair.json')
    provider = {**old_provider,
        'requirement_closure_hash': closure,
        'execution_authority_hash': execution_hash,
        'evidence': append(checked(old_provider),
            'assertion-v6-suspension-directed.log',
            'assertion-v6-suspension-material.log',
            'provider-wiring-test-v6-suspended.log'),
        'scope': ('Current V15 B13 V6 fail-closed binding. Mocked provider '
            'factory/controller rerun without network; recorded scan still '
            'saves only a scan receipt, while V6 judgment stops before a '
            'second claim and every native/registered acceptance entry '
            'rejects. Earlier evidence revalidated by exact bytes.'),
        'independent_review': 'V6_SUSPENSION_INCREMENT_REVIEW_PENDING'}
    provider_path.write_text(json.dumps(provider, ensure_ascii=False, indent=2)+'\n')
    assert validate_wiring_receipt(requirement=requirement) == provider
    sec = {**old_sec,
        'execution_authority_hash': execution_hash,
        'evidence': checked(old_sec),
        'validation_scope': ('Current execution file identity rebound. SEC '
            'source/acquisition code and policy unchanged by B13 V6 native '
            'suspension; prior no-network SEC HTTP, checkpoint and failure '
            'isolation evidence revalidated by exact byte hashes. No new '
            'SEC request or production credit.')}
    sec_path.write_text(json.dumps(sec, ensure_ascii=False, indent=2)+'\n')
    assert sec['record_type'] == 'SEC_ACQUISITION_OFFLINE_WIRING'
    assert sec['execution_authority_hash'] == execution_hash
    assert sec['calls'] == [0, 0, 0]
    checked(sec)
    print(json.dumps({'status': 'PASS_CURRENT_PROVIDER_AND_SEC_OFFLINE_WIRING',
        'requirement_closure_hash': closure,
        'execution_authority_hash': execution_hash,
        'new_calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
