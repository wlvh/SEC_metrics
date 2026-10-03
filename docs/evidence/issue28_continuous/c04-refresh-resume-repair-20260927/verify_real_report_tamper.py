"""Reject a modified deferred URL list against the actual ordinal 193."""
import json
from pathlib import Path
import tempfile

from vnext.continuous_sec_acquisition import live_sec_session
from vnext.ordinary_refresh_cycle import _check_session, _resume_one_c04_source


STATE = Path('/private/tmp/issue28-c04-live-zero-refresh-20260926-03/state')
PRIOR = Path('/private/tmp/issue28-c04-live-zero-refresh-20260926-03/real-refresh-1.json')


def main():
    session = live_sec_session()
    _check_session(session, c04_successor=True)
    with session.ledger.locked():
        before = session.ledger.snapshot()
    report = json.loads(PRIOR.read_text())
    report['companies'][0]['source_refresh']['deferred_source_urls'].append(
        report['captures'][0]['source_url'])
    with tempfile.TemporaryDirectory() as temporary:
        altered = Path(temporary).resolve()/'altered.json'
        altered.write_text(json.dumps(report, ensure_ascii=False)+'\n')
        try:
            _resume_one_c04_source(session=session, state_root=STATE,
                company_id='marriott_international', snapshot=before,
                report_path=altered)
        except ValueError as error:
            assert str(error) == 'ORDINARY_REFRESH_RESUME_DEFERRED_SET_CHANGED'
        else:
            raise AssertionError('ALTERED_DEFERRED_SET_ACCEPTED')
    with session.ledger.locked():
        after = session.ledger.snapshot()
    assert before['counts'] == after['counts'] == [143, 143, 50]
    assert len(before['rows']) == len(after['rows']) == 193
    print(json.dumps({'status': 'PASS_REAL_REPORT_DEFERRED_TAMPER_REJECTED',
        'reason': 'ORDINARY_REFRESH_RESUME_DEFERRED_SET_CHANGED',
        'ledger_counts': after['counts'], 'ledger_slots': len(after['rows']),
        'new_real_calls': [0, 0, 0]}, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
