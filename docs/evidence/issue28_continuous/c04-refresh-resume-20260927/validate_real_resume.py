"""Authenticate the prior live C04 source capture without issuing a GET."""
import json
from pathlib import Path

from vnext.continuous_sec_acquisition import live_sec_session
from vnext.normal_run_v3 import prepare_case
from vnext.c04_registration_successor import EVENT_FORMS
from vnext.normal_source_requirements import discover_saved_source_requirements
from vnext.ordinary_refresh_cycle import (
    _check_session, _failed_urls, _pending, _resume_one_c04_source)


STATE = Path('/private/tmp/issue28-c04-live-zero-refresh-20260926-03/state')
PRIOR = Path('/private/tmp/issue28-c04-live-zero-refresh-20260926-03/real-refresh-1.json')
COMPANY = 'marriott_international'


def main():
    session = live_sec_session()
    _check_session(session, c04_successor=True)
    with session.ledger.locked():
        snapshot = session.ledger.snapshot()
    resumed = _resume_one_c04_source(session=session, state_root=STATE,
        company_id=COMPANY, snapshot=snapshot, report_path=PRIOR)
    discovery = discover_saved_source_requirements(
        repo_root=session.data_root, company_id=COMPANY)
    pending = _pending(discovery, {resumed['prior_source_url']},
                       _failed_urls(session.data_root))
    case = prepare_case(data_root=session.data_root, company_id=COMPANY,
        metric_id='C04', c04_event_forms=EVENT_FORMS)
    next_url = pending[0]['source_url']
    assert snapshot['counts'] == [143, 143, 50]
    assert resumed['prior_ordinal'] == 193
    assert next_url in resumed['allowed_next_urls']
    assert next_url in {p['source_url'] for p in case['source_proofs']}
    assert next_url.endswith('/CIK0001048286.json')
    assert pending[0]['roles'] == ['companyfacts']
    print(json.dumps({'status': 'PASS_PRIOR_LIVE_SEC_CAPTURE_AUTHENTICATED',
        'prior_ordinal': resumed['prior_ordinal'],
        'prior_source_url': resumed['prior_source_url'],
        'next_source_url': next_url, 'next_roles': pending[0]['roles'],
        'prior_report_sha256': resumed['prior_report_sha256'],
        'source_ledger_sha256': resumed['source_ledger_sha256'],
        'ledger_counts': snapshot['counts'], 'new_real_calls': [0, 0, 0],
        'production_authorized': False}, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
