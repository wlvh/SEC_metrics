"""Append receipts for the V6 scoped-review repair without rewriting V6 originals."""
import json
from pathlib import Path

from vnext.canonical import content_hash, sha256_file, strict_json_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent


def evidence_from(receipt):
    for relative, digest in receipt['evidence'].items():
        assert sha256_file(path=ROOT/relative) == digest, relative
    return dict(receipt['evidence'])


def add(evidence, *names):
    for name in names:
        path = HERE/name
        assert path.is_file()
        evidence[str(path.relative_to(ROOT))] = sha256_file(path=path)
    return evidence


def main():
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements/issue_28_v14')
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    closure = requirement['requirement_closure_hash']
    execution_hash = content_hash(value=requirement['execution_authority'])
    provider_log = (HERE/'provider-wiring-test-assertion-repair.log').read_text()
    directed = (HERE/'assertion-scope-repair-directed.log').read_text()
    native = (HERE/'assertion-scope-repair-native.log').read_text()
    assert ('OFFLINE_WIRING_PASS' in provider_log and closure in provider_log
            and 'Ran 1 test' in provider_log and '\nOK\n' in provider_log)
    assert 'Ran 32 tests' in directed and '\nOK\n' in directed
    assert 'Ran 1 test' in native and '\nOK\n' in native
    provider_path = ROOT/requirement['policy']['offline_wiring_receipt_path']
    sec_path = ROOT/requirement['policy']['sec_wiring_receipt_path']
    assert provider_path == HERE/'provider-wiring-assertion-repair.json'
    assert sec_path == HERE/'sec-wiring-assertion-repair.json'
    old_provider = strict_json_file(path=HERE/'provider-wiring-assertion-v6.json')
    old_sec = strict_json_file(path=HERE/'sec-wiring-assertion-v6.json')
    provider = {**old_provider,
        'requirement_closure_hash': closure,
        'execution_authority_hash': execution_hash,
        'evidence': add(evidence_from(old_provider),
            'assertion-scope-repair-directed.log',
            'assertion-scope-repair-native.log',
            'provider-wiring-test-assertion-repair.log'),
        'scope': ('Current V15 identity after scoped assertion review repair. '
            'Exact two-stage recorded native acceptance and portable stage '
            'read rerun; current mocked provider factory/controller rerun '
            'without network. Earlier unchanged evidence revalidated by bytes.'),
        'independent_review': 'ASSERTION_SCOPE_REPAIR_DELTA_REVIEW_PENDING'}
    provider_path.write_text(json.dumps(provider, ensure_ascii=False, indent=2)+'\n')
    assert validate_wiring_receipt(requirement=requirement) == provider
    sec = {**old_sec,
        'execution_authority_hash': execution_hash,
        'evidence': evidence_from(old_sec),
        'validation_scope': ('Current V15 execution file identity rebound. '
            'SEC code and acquisition policy bytes were unchanged by the '
            'B13-only scope repair; prior recorded SEC HTTP, checkpoint '
            'and failure-isolation test and original source/cold-read '
            'evidence revalidated by exact hashes. No new SEC request.')}
    sec_path.write_text(json.dumps(sec, ensure_ascii=False, indent=2)+'\n')
    assert sec['record_type'] == 'SEC_ACQUISITION_OFFLINE_WIRING'
    assert sec['execution_authority_hash'] == execution_hash
    assert sec['calls'] == [0, 0, 0]
    assert sec['actual_http_path_verified'] is True
    assert sec['checkpoint_import_and_failure_isolation_verified'] is True
    evidence_from(sec)
    print(json.dumps({'status': 'PASS_CURRENT_PROVIDER_AND_SEC_OFFLINE_WIRING',
        'requirement_closure_hash': closure,
        'execution_authority_hash': execution_hash,
        'new_calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
