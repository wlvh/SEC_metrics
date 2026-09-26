"""Bind final unfrozen V15 identity to actually rerun, no-network wiring."""
import json
from pathlib import Path

from vnext.canonical import content_hash, sha256_file, strict_json_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.normal_source_authority import ROOT
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.requirements import load_requirement_snapshot


HERE = Path(__file__).resolve().parent
PROVIDER_OLD = ('docs/evidence/issue28_continuous/'
                'b13-170-source-audit/offline-wiring.json')
SEC_OLD = ('docs/evidence/issue28_continuous/'
           'ordinary-refresh-cycle/sec-wiring.json')


def checked_evidence(receipt):
    for relative, digest in receipt['evidence'].items():
        assert sha256_file(path=ROOT / relative) == digest, relative
    return dict(receipt['evidence'])


def main():
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT / 'requirements/issue_28_v14')
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    assert requirement['policy']['offline_wiring_receipt_path'] == str(
        (HERE / 'provider-wiring.json').relative_to(ROOT))
    assert requirement['policy']['sec_wiring_receipt_path'] == str(
        (HERE / 'sec-wiring.json').relative_to(ROOT))
    provider_log = (HERE / 'provider-wiring-test.log').read_text()
    sec_log = (HERE / 'sec-wiring-test.log').read_text()
    assert ('OFFLINE_WIRING_PASS' in provider_log
            and requirement['requirement_closure_hash'] in provider_log
            and 'Ran 1 test' in provider_log and '\nOK\n' in provider_log)
    assert 'Ran 1 test' in sec_log and '\nOK\n' in sec_log
    execution_hash = content_hash(value=requirement['execution_authority'])

    old = strict_json_file(path=ROOT / PROVIDER_OLD)
    provider = {**old,
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'execution_authority_hash': execution_hash,
        'evidence': {**checked_evidence(old),
            str((HERE / 'provider-wiring-test.log').relative_to(ROOT)):
                sha256_file(path=HERE / 'provider-wiring-test.log')},
        'scope': ('Current V15 execution identity after explicit C04 four-form '
                  'development binding; actual source factory, mocked provider '
                  'opener and controller rerun under network-disabled test. '
                  'Earlier unchanged evidence is verified, not re-executed.'),
        'independent_review': 'CURRENT_C04_DELTA_REVIEW_PENDING'}
    (HERE / 'provider-wiring.json').write_text(
        json.dumps(provider, ensure_ascii=False, indent=2) + '\n')
    assert validate_wiring_receipt(requirement=requirement) == provider

    old = strict_json_file(path=ROOT / SEC_OLD)
    sec = {**old,
        'execution_authority_hash': execution_hash,
        'evidence': {**checked_evidence(old),
            str((HERE / 'sec-wiring-test.log').relative_to(ROOT)):
                sha256_file(path=HERE / 'sec-wiring-test.log'),
            str((HERE / 'native-repair.log').relative_to(ROOT)):
                sha256_file(path=HERE / 'native-repair.log'),
            str((HERE / 'cold.log').relative_to(ROOT)):
                sha256_file(path=HERE / 'cold.log')},
        'validation_scope': ('Current V15 execution identity, recorded SEC HTTP '
            'and checkpoint/failure-isolation suite rerun without network; '
            'Paramount C04 used already-acquired sources and installed cold '
            'read. No new SEC acquisition or production credit.')}
    (HERE / 'sec-wiring.json').write_text(
        json.dumps(sec, ensure_ascii=False, indent=2) + '\n')
    assert sec['record_type'] == 'SEC_ACQUISITION_OFFLINE_WIRING'
    assert sec['execution_authority_hash'] == execution_hash
    assert sec['calls'] == [0, 0, 0]
    assert sec['actual_http_path_verified'] is True
    assert sec['checkpoint_import_and_failure_isolation_verified'] is True
    checked_evidence(sec)
    print(json.dumps({'status': 'PASS_CURRENT_PROVIDER_AND_SEC_OFFLINE_WIRING',
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'execution_authority_hash': execution_hash,
        'new_calls': [0, 0, 0]}))


if __name__ == '__main__':
    main()
