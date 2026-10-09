"""Read current no-network provider, SEC and C04 refresh binding receipts."""
import json
from pathlib import Path
from types import SimpleNamespace

from vnext.canonical import content_hash, sha256_file, strict_json_file
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.continuous_sec_acquisition import SecAcquisitionSession
from vnext.normal_source_authority import ROOT
from vnext.requirement_profile import validate_execution_authority
from vnext.requirements import load_requirement_snapshot
from vnext.sources import resolve_repository_file
from vnext import ordinary_refresh_cycle as refresh


def main():
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements/issue_28_v14')
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    validate_wiring_receipt(requirement=requirement)
    sec = strict_json_file(path=resolve_repository_file(repo_root=ROOT,
        repo_relative_path=requirement['policy']['sec_wiring_receipt_path']))
    assert sec['record_type'] == 'SEC_ACQUISITION_OFFLINE_WIRING'
    assert sec['execution_authority_hash'] == content_hash(
        value=requirement['execution_authority'])
    assert sec['calls'] == [0, 0, 0]
    assert sec['actual_http_path_verified'] is True
    for path, digest in sec['evidence'].items():
        assert sha256_file(path=resolve_repository_file(repo_root=ROOT,
            repo_relative_path=path)) == digest
    # The real SEC session is tested separately in recorded mode. This is the
    # local refresh receipt gate only; do not contact GitHub or the SEC here.
    session = object.__new__(SecAcquisitionSession)
    session.ledger = SimpleNamespace(live=True,
        root=Path('/unexecuted-issue28-c04-wiring-ledger'))
    session.data_root = session.ledger.root/'source-inputs'
    session.requirement = requirement
    session._check = lambda: None
    refresh._check_session(session, c04_successor=True)
    result = {'status': 'PASS_CURRENT_C04_REFRESH_OFFLINE_WIRING',
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'execution_authority_hash': content_hash(
            value=requirement['execution_authority']),
        'c04_controller_sha256': sha256_file(
            path=ROOT/'scripts/vnext/c04_update_cycle.py'),
        'provider_receipt_valid': True, 'sec_receipt_valid': True,
        'refresh_receipt_valid_with_stubbed_sec_authorizer': True,
        'actual_live_sec_capture_executed': False,
        'new_real_calls': [0, 0, 0], 'production_authorized': False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
