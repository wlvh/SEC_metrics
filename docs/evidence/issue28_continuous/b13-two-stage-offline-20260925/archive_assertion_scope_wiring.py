"""Append current V15 no-network receipts; preserve preceding C04 receipts."""
import json
from pathlib import Path

from vnext.canonical import content_hash, sha256_file, strict_json_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
C04 = ROOT / 'docs/evidence/issue28_continuous/paramount-c04-native-four-forms-20260926'


def checked_evidence(receipt):
    for relative, digest in receipt['evidence'].items():
        assert sha256_file(path=ROOT / relative) == digest, relative
    return dict(receipt['evidence'])


def append_logs(evidence, *names):
    for name in names:
        path = HERE / name
        assert path.is_file()
        evidence[str(path.relative_to(ROOT))] = sha256_file(path=path)
    return evidence


def main():
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT / 'requirements/issue_28_v14')
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    closure = requirement['requirement_closure_hash']
    execution_hash = content_hash(value=requirement['execution_authority'])
    provider_log = (HERE / 'provider-wiring-test-assertion-v6.log').read_text()
    sec_log = (HERE / 'sec-wiring-test-assertion-v6.log').read_text()
    directed = (HERE / 'assertion-scoped-directed.log').read_text()
    native = (HERE / 'assertion-scoped-native.log').read_text()
    assert ('OFFLINE_WIRING_PASS' in provider_log and closure in provider_log
            and 'Ran 1 test' in provider_log and '\nOK\n' in provider_log)
    assert ('OFFLINE_SEC_CAPTURE_PASS' in sec_log and 'Ran 1 test' in sec_log
            and '\nOK\n' in sec_log and 'Ran 32 tests' in directed
            and '\nOK\n' in directed and 'Ran 1 test' in native
            and '\nOK\n' in native)

    provider_path = ROOT / requirement['policy']['offline_wiring_receipt_path']
    sec_path = ROOT / requirement['policy']['sec_wiring_receipt_path']
    assert provider_path == HERE / 'provider-wiring-assertion-v6.json'
    assert sec_path == HERE / 'sec-wiring-assertion-v6.json'
    old_provider = strict_json_file(path=C04 / 'provider-wiring-shard-repair.json')
    old_sec = strict_json_file(path=C04 / 'sec-wiring-shard-repair.json')
    provider = {**old_provider,
        'requirement_closure_hash': closure,
        'execution_authority_hash': execution_hash,
        'evidence': append_logs(checked_evidence(old_provider),
            'assertion-scoped-directed.log', 'assertion-scoped-native.log',
            'provider-wiring-test-assertion-v6.log'),
        'scope': ('Current V15 assertion-scoped B13 offline successor. Exact '
                  'two-stage recorded execution, current source factory and '
                  'mocked provider controller pass without network. Earlier '
                  'unchanged evidence revalidated by bytes.'),
        'independent_review': 'ASSERTION_SCOPE_DELTA_REVIEW_PENDING'}
    provider_path.write_text(json.dumps(provider, ensure_ascii=False, indent=2) + '\n')
    assert validate_wiring_receipt(requirement=requirement) == provider

    sec = {**old_sec,
        'execution_authority_hash': execution_hash,
        'evidence': append_logs(checked_evidence(old_sec),
            'sec-wiring-test-assertion-v6.log'),
        'validation_scope': ('Current V15 execution file identity rebound. '
            'Recorded SEC HTTP, checkpoint and failure isolation were run '
            'without network before the final B13-only candidate/output cap '
            'edit; SEC implementation bytes did not change thereafter. '
            'Original C04 source and cold-read evidence retained by exact '
            'hash; no new acquisition or production credit.')}
    sec_path.write_text(json.dumps(sec, ensure_ascii=False, indent=2) + '\n')
    assert sec['record_type'] == 'SEC_ACQUISITION_OFFLINE_WIRING'
    assert sec['execution_authority_hash'] == execution_hash
    assert sec['calls'] == [0, 0, 0]
    assert sec['actual_http_path_verified'] is True
    assert sec['checkpoint_import_and_failure_isolation_verified'] is True
    checked_evidence(sec)
    print(json.dumps({'status': 'PASS_CURRENT_PROVIDER_AND_SEC_OFFLINE_WIRING',
        'requirement_closure_hash': closure,
        'execution_authority_hash': execution_hash,
        'new_calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
