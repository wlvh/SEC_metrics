"""Append a receipt for the final unfrozen V15 no-network wiring."""
import argparse
import json
from pathlib import Path
import re

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


def main(evidence_suffix):
    assert re.fullmatch(r'[a-z0-9-]+', evidence_suffix)
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT / 'requirements/issue_28_v14')
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    provider_path = HERE / ('provider-wiring-' + evidence_suffix + '.json')
    sec_path = HERE / ('sec-wiring-' + evidence_suffix + '.json')
    provider_log_path = HERE / ('provider-wiring-test-' + evidence_suffix + '.log')
    sec_log_path = HERE / ('sec-wiring-test-' + evidence_suffix + '.log')
    native_log_path = HERE / ('native-' + evidence_suffix + '.log')
    cold_log_path = HERE / ('cold-' + evidence_suffix + '.log')
    assert requirement['policy']['offline_wiring_receipt_path'] == str(
        provider_path.relative_to(ROOT))
    assert requirement['policy']['sec_wiring_receipt_path'] == str(
        sec_path.relative_to(ROOT))
    provider_log = provider_log_path.read_text()
    sec_log = sec_log_path.read_text()
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
            str(provider_log_path.relative_to(ROOT)):
                sha256_file(path=provider_log_path)},
        'scope': ('Current V15 execution identity after explicit C04 four-form '
                  'development binding; actual source factory, mocked provider '
                  'opener and controller rerun under network-disabled test. '
                  'Earlier unchanged evidence is verified, not re-executed.'),
        'independent_review': 'CURRENT_C04_DELTA_REVIEW_PENDING'}
    provider_path.write_text(
        json.dumps(provider, ensure_ascii=False, indent=2) + '\n')
    assert validate_wiring_receipt(requirement=requirement) == provider

    old = strict_json_file(path=ROOT / SEC_OLD)
    sec = {**old,
        'execution_authority_hash': execution_hash,
        'evidence': {**checked_evidence(old),
            str(sec_log_path.relative_to(ROOT)):
                sha256_file(path=sec_log_path),
            str(native_log_path.relative_to(ROOT)):
                sha256_file(path=native_log_path),
            str(cold_log_path.relative_to(ROOT)):
                sha256_file(path=cold_log_path)},
        'validation_scope': ('Current V15 execution identity, recorded SEC HTTP '
            'and checkpoint/failure-isolation suite rerun without network; '
            'Paramount C04 used already-acquired sources and installed cold '
            'read. No new SEC acquisition or production credit.')}
    sec_path.write_text(
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-suffix', required=True)
    args = parser.parse_args()
    main(args.evidence_suffix)
