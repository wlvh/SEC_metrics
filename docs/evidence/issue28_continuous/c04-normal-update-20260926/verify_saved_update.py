"""No-network C04 update history using two authentic saved SEC inventories."""
import contextlib
import csv
import io
import json
from pathlib import Path
import socket
from unittest.mock import patch

from sec_http import request_log_attempt_id
from sec_urls import submissions_url
from vnext import c04_update_cycle as c04, normal_run_v3 as normal
from vnext.c04_registration_successor import EVENT_FORMS
from vnext.canonical import strict_json_file
from vnext.continuous_call_ledger import live_ledger
from vnext.normal_source_authority import ROOT
from vnext.ordinary_source_authority import register_recorded_session
from vnext.ordinary_source_session import recorded_source_session
from vnext.requirements import load_requirement_snapshot
from tools.vnext_normal_update import main as update_cli


HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-c04-normal-update-20260926-01')
PARAMOUNT_SOURCE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
MARRIOTT = 'marriott_international'
PARAMOUNT = 'paramount_skydance_paramount_global'


def ledger_counts():
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements/issue_28_v14')
    ledger = live_ledger(requirement=requirement)
    with ledger.locked():
        value = ledger.snapshot()
    return {'rows': len(value['rows']), 'counts': value['counts']}


def update(*, source, state, company):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = update_cli(['--process', '--data-root', str(source),
            '--state-root', str(state), '--company', company, '--metric', 'C04'])
    report = json.loads(output.getvalue())
    row, = report['companies'][0]['metrics']
    assert row['metric_id'] == 'C04'
    return code, report['companies'][0]['status'], row


def terminal_input(state, company, attempt):
    path = state/company/'metrics/C04-registration-v3'/'attempts'/attempt/'terminal.json'
    return strict_json_file(path=path)['input']


def historical_attempts(url):
    rows = list(csv.DictReader((ROOT/'evidence/requests_log.csv').open()))
    matches = [(index, row) for index, row in enumerate(rows)
               if row['source_url'] == url and row['status_code'] == '200']
    assert len(matches) >= 3
    old, latest = matches[-2], matches[-1]
    assert old[1]['content_sha256'] != latest[1]['content_sha256']
    return [(request_log_attempt_id(row_index=index, row=row),
             row['content_sha256']) for index, row in (old, latest)]


def main():
    assert not WORK.exists()
    before = ledger_counts()
    source = WORK/'source'
    state = WORK/'state'
    url = submissions_url(cik=1048286)
    old, latest = historical_attempts(url)
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')):
        normal.install_normal_inputs(data_root=source, company_id=MARRIOTT,
            metric_id='C04', c04_event_forms=EVENT_FORMS)
        session = recorded_source_session(data_root=source,
            journal_root=WORK/'source-journal', company_id=MARRIOTT,
            max_responses=2)
        session.record_saved_response(url=url,
            historical_test_attempt_id=old[0])
        register_recorded_session(session=session)
        first_code, first_status, first = update(source=source,
            state=state, company=MARRIOTT)
        assert first_code == 0 and first_status == 'UPDATES_READY'
        assert first['status'] == 'CANDIDATE_READY'
        first_input = terminal_input(state, MARRIOTT, first['attempt_id'])
        session.record_saved_response(url=url,
            historical_test_attempt_id=latest[0])
        register_recorded_session(session=session)
        second_code, second_status, second = update(source=source,
            state=state, company=MARRIOTT)
        assert second_code == 0 and second_status == 'UPDATES_READY'
        assert second['status'] == 'CANDIDATE_READY'
        assert second['successful_attempt'] != first['successful_attempt']
        assert second['previous_successful_attempt'] == first['successful_attempt']
        second_input = terminal_input(state, MARRIOTT, second['attempt_id'])
        assert first_input['content_id'] != second_input['content_id']
        with patch.object(normal, 'create_normal_run',
                          side_effect=AssertionError('UNCHANGED_MUST_REUSE')):
            _, _, repeat = update(source=source, state=state,
                                  company=MARRIOTT)
        assert repeat['status'] == 'NO_SOURCE_CONTENT_CHANGE'
        assert repeat['successful_attempt'] == second['successful_attempt']
        with patch.object(c04, '_inspect',
                          side_effect=ValueError('RECORDED_INSPECTION_FAILURE')):
            _, failed_status, failed = update(source=source,
                state=state, company=MARRIOTT)
        assert failed_status == 'UPDATES_INCOMPLETE'
        assert failed['status'] == 'INPUT_FAILED'
        assert failed['successful_attempt'] == second['successful_attempt']
        with patch.object(normal, 'create_normal_run',
                          side_effect=AssertionError('RESTORE_MUST_REUSE')):
            _, _, restored = update(source=source, state=state,
                                    company=MARRIOTT)
        assert restored['status'] == 'NO_SOURCE_CONTENT_CHANGE'
        assert restored['successful_attempt'] == second['successful_attempt']

        # A completed terminal survives a lost mutable pointer write.
        interrupted_state = WORK/'interrupted-state'
        original_write = c04.atomic_write_json
        def fail_pointer(*, path, value):
            if path.name == 'current.json':
                raise OSError('RECORDED_POINTER_INTERRUPTION')
            return original_write(path=path, value=value)
        with patch.object(c04, 'atomic_write_json', side_effect=fail_pointer):
            blocked_code, _, blocked = update(source=source,
                state=interrupted_state, company=MARRIOTT)
        assert blocked_code == 2 and blocked['status'] == 'UPDATE_BLOCKED'
        with patch.object(normal, 'create_normal_run',
                          side_effect=AssertionError('RECOVER_MUST_REUSE')):
            _, _, recovered = update(source=source,
                state=interrupted_state, company=MARRIOTT)
        assert recovered['status'] == 'NO_SOURCE_CONTENT_CHANGE'
        assert recovered['successful_attempt'] is not None

        paramount_state = WORK/'paramount-state'
        withheld_code, withheld_status, withheld = update(
            source=PARAMOUNT_SOURCE, state=paramount_state,
            company=PARAMOUNT)
        assert withheld_code == 2 and withheld_status == 'UPDATES_INCOMPLETE'
        assert withheld['status'] == 'CANDIDATE_WITHHELD'
        assert withheld['successful_attempt'] is None
        with patch.object(normal, 'create_normal_run',
                          side_effect=AssertionError('WITHHELD_MUST_NOT_RERUN')):
            _, _, held_repeat = update(source=PARAMOUNT_SOURCE,
                state=paramount_state, company=PARAMOUNT)
        assert held_repeat['status'] == 'PREVIOUS_INPUT_WITHHELD'
        assert held_repeat['successful_attempt'] is None

    after = ledger_counts()
    assert before == after == {'rows': 192, 'counts': [143, 143, 49]}
    summary = {'status': 'PASS_RECORDED_C04_NORMAL_UPDATE_V1',
        'code_root': str(ROOT), 'source_root': str(source),
        'marriott_first_success': first['successful_attempt'],
        'marriott_changed_source_success': second['successful_attempt'],
        'marriott_source_content_ids': [first_input['content_id'],
                                        second_input['content_id']],
        'marriott_source_inventory_hashes': [old[1], latest[1]],
        'marriott_repeat': repeat['status'],
        'marriott_failure': failed['status'],
        'marriott_restored': restored['status'],
        'interrupted_recovery': recovered['status'],
        'paramount': withheld['status'],
        'paramount_repeat': held_repeat['status'],
        'ledger_before_after': [before, after],
        'new_real_calls': [0, 0, 0],
        'real_new_filing_verified': False,
        'production_authorized': False,
        'boundary': 'Two authentic saved SEC submission versions were replayed locally; no new SEC acquisition or routine live update was tested.'}
    (HERE/'recorded-update-summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
