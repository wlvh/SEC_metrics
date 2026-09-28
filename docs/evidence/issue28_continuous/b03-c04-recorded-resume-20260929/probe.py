"""Recorded-only Salesforce B03 historical pointer + two C04 source captures."""
import csv
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from sec_urls import submissions_url, companyfacts_url
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.normal_governance_input import prepare_saved_governance_input
from vnext import ordinary_update_cycle as old_update
from vnext import ordinary_refresh_cycle as refresh
from vnext.canonical import strict_json_file

COMPANY = 'salesforce'
CIK = 1108524
SAVED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
EVIDENCE = Path(__file__).resolve().parent


def say(stage, **details):
    print(json.dumps({'stage': stage, **details}, ensure_ascii=False,
                     sort_keys=True, default=str), flush=True)


def saved(url):
    with (SAVED/'evidence/requests_log.csv').open(newline='') as handle:
        rows = [row for row in csv.DictReader(handle)
                if row['source_url'] == url and row['status_code'] == '200']
    assert rows, 'SOURCE_NOT_IN_ORIGINAL_ISSUE28_LEDGER:' + url
    row = rows[-1]
    raw = (SAVED/row['repo_relative_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['content_sha256']
    return raw, row


def summaries(report):
    company, = report['companies']
    return {'status': report['status'],
            'source_status': company['source_refresh']['status'],
            'processing_status': report.get('current_processing_source_status'),
            'captures': [x['source_url'] for x in report['captures']],
            'metrics': {x['metric_id']: {'status': x['status'],
                         'successful_attempt': x.get('successful_attempt'),
                         'current_candidate': x.get('last_verified_candidate') is not None,
                         'error': x.get('reason') or x.get('terminal', {}).get('error')}
                        for x in company['updates']['metrics']},
            'calls': report['calls']}


def main():
    prior = prepare_saved_governance_input(repo_root=ROOT,
                                          company_id=COMPANY)['input_binding']
    current = prepare_saved_governance_input(repo_root=SAVED,
                                            company_id=COMPANY)['input_binding']
    assert prior['metric_input_status']['C04'] == 'BLOCKED'
    assert current['metric_input_status']['C04'] == 'PREPARED'
    old_urls = {p['source_url'] for p in prior['source_proofs']}
    extra = [p for p in current['source_proofs']
             if p['source_url'] not in old_urls]
    assert len(extra) == 8 and len({p['source_url'] for p in extra}) == 8
    for proof in extra:
        raw, _ = saved(proof['source_url'])
        assert hashlib.sha256(raw).hexdigest() == proof['content_sha256']
    say('source_setup', missing_saved_urls=[p['source_url'] for p in extra],
        raw_bodies_authenticated=True, actual_http_requests=0)

    with tempfile.TemporaryDirectory(prefix='issue28-b03-c04-mixed-') as temp:
        root = Path(temp).resolve()
        session = recorded_sec_session(root=root/'ledger', response=b'RECORDED')
        state = root/'state'
        setup_claims = 0
        with (patch.object(socket.socket, 'connect',
                           side_effect=AssertionError('NETWORK_FORBIDDEN')),
              patch.object(socket, 'getaddrinfo',
                           side_effect=AssertionError('DNS_FORBIDDEN')),
              patch('sec_http.urlopen',
                    side_effect=AssertionError('HTTP_FORBIDDEN'))):
            for proof in extra:
                raw, _ = saved(proof['source_url'])
                session.response = raw
                result = session.capture(company_id=COMPANY,
                    url=proof['source_url'], source_only_c04=True)
                assert result['status'] in {
                    'SUCCEEDED', 'EXISTING_VERIFIED_SOURCE_REUSED'}
                assert result['calls'] == [0,0,0]
                if result['status'] == 'SUCCEEDED':
                    setup_claims += 1
                say('recorded_setup_capture', url=proof['source_url'],
                    status=result['status'],
                    ledger_row_index=(result['receipt']['ledger_row_index']
                        if result['status'] == 'SUCCEEDED' else None),
                    response_sha256=hashlib.sha256(raw).hexdigest())
            restored = prepare_saved_governance_input(
                repo_root=session.data_root,
                company_id=COMPANY)['input_binding']
            say('restored_c04_input',
                status=restored['metric_input_status']['C04'],
                source_proofs=len(restored['source_proofs']))
            assert restored['metric_input_status']['C04'] == 'PREPARED'
            historical = old_update.run_company(
                state_root=state/COMPANY, source_root=session.data_root,
                company_id=COMPANY, metric_ids=['B03'],
                native_assessment_mode='RECORDED_TEST_ONLY',
                native_assessment_ledger=session.ledger)
            old_row, = historical['metrics']
            say('old_b03_execution', status=old_row['status'],
                historical_pointer=old_row.get('successful_attempt'),
                current_business_credit_after_new_guard=False)
            assert old_row['status'] == 'CANDIDATE_READY'
            old_pointer = old_row['successful_attempt']
            assert old_pointer
            source = session.data_root
            (source/'config/issue28_normal_results_v2.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            (source/'config/ordinary_public_projection_v1.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            (source/'catalog/r5/C04_auditor_changes_v3.md').unlink()
            metadata = [submissions_url(cik=CIK), companyfacts_url(cik=CIK)]
            responses = {url: saved(url)[0] for url in metadata}
            actual_capture = session.capture
            captured = []
            def recorded_capture(**kwargs):
                url = kwargs['url']
                assert url in responses
                captured.append(url)
                session.response = responses[url]
                return actual_capture(**kwargs)
            with patch.object(session, 'capture', side_effect=recorded_capture):
                first = refresh.refresh_and_process(session=session,
                    state_root=state, company_ids=[COMPANY],
                    metric_ids=['B03','C04'], max_sec_requests=1,
                    c04_successor=True)
                say('first_mixed_pass', **summaries(first))
                report = root/'prior-report.json'
                report.write_text(json.dumps(first, ensure_ascii=False)+'\n')
                tampered = deepcopy(first)
                bad_b03, = [row for row in tampered['companies'][0][
                    'updates']['metrics'] if row['metric_id'] == 'B03']
                bad_b03['last_verified_candidate'] = {
                    'attempt_id': old_pointer}
                bad = root/'false-current-credit-report.json'
                bad.write_text(json.dumps(tampered, ensure_ascii=False)+'\n')
                before_rejected = list(captured)
                try:
                    refresh.refresh_and_process(session=session,
                        state_root=state, company_ids=[COMPANY],
                        metric_ids=['B03','C04'], max_sec_requests=1,
                        c04_successor=True, resume_from=bad)
                except ValueError as error:
                    assert 'ORDINARY_REFRESH_RESUME_OTHER_METRIC_CHANGED' in str(error)
                    say('false_current_credit_rejected', reason=str(error))
                else:
                    raise AssertionError('FALSE_B03_CURRENT_CREDIT_ACCEPTED')
                assert captured == before_rejected
                second = refresh.refresh_and_process(session=session,
                    state_root=state, company_ids=[COMPANY],
                    metric_ids=['B03','C04'], max_sec_requests=1,
                    c04_successor=True, resume_from=report)
                say('second_mixed_pass', **summaries(second))
            assert captured == metadata
            first_rows = {x['metric_id']:x for x in
                          first['companies'][0]['updates']['metrics']}
            second_rows = {x['metric_id']:x for x in
                           second['companies'][0]['updates']['metrics']}
            assert first_rows['B03']['status'] == 'PREVIOUS_INPUT_WITHHELD'
            assert second_rows['B03']['status'] == 'PREVIOUS_INPUT_WITHHELD'
            assert first_rows['B03']['last_verified_candidate'] is None
            assert second_rows['B03']['last_verified_candidate'] is None
            assert first_rows['B03']['successful_attempt'] == old_pointer
            assert second_rows['B03']['successful_attempt'] == old_pointer
            assert second_rows['C04']['last_verified_candidate'] is not None
            assert first['companies'][0]['source_refresh']['status'] == 'REFRESH_INCOMPLETE'
            assert second['companies'][0]['source_refresh']['status'] == 'REFRESH_CHECK_COMPLETED'
            with session.ledger.locked():
                counts = session.ledger.snapshot()['counts']
            assert counts == [0,0,setup_claims+2], counts
            check_paths = [session.data_root/'evidence/requests_log.csv',
                state/COMPANY/'metrics/B03/current.json',
                state/COMPANY/'metrics/C04-registration-v3/current.json']
            before_cold = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in check_paths}
            cold = subprocess.run([sys.executable, str(EVIDENCE/'cold.py'),
                str(session.ledger.root), str(state)], cwd=ROOT,
                capture_output=True, text=True,
                env={**os.environ,
                     'PYTHONPATH':str(ROOT/'scripts'),
                     'PYTHONDONTWRITEBYTECODE':'1'})
            (EVIDENCE/'cold.log').write_text(cold.stdout+cold.stderr)
            assert cold.returncode == 0, 'INDEPENDENT_COLD_READ_FAILED'
            cold_result = json.loads(cold.stdout)
            assert cold_result['status'] == 'PASS_INDEPENDENT_INSTALLED_READ'
            assert cold_result['old_b03_current_credit'] is False
            after_cold = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in check_paths}
            assert before_cold == after_cold
            summary = {'record_type':'ISSUE28_B03_C04_RECORDED_TWO_SOURCE_RESUME',
                'base_saved_source_root':str(SAVED),
                'old_b03_pointer_unchanged': True,
                'b03_current_candidate_credit': False,
                'c04_current_candidate_created': True,
                'recorded_sec_claims':setup_claims+2,
                'real_provider_paid_sec_calls':[0,0,0],
                'actual_online_new_filing_proven':False,
                'all_390_coordinates_proven':False,
                'first': summaries(first), 'second':summaries(second),
                'false_current_credit_report_rejected':True,
                'cold_read': cold_result,
                'cold_read_selected_state_bytes_unchanged': True}
            (EVIDENCE/'result.json').write_text(
                json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
            say('complete', recorded_claims=counts,
                real_calls=[0,0,0], old_pointer_unchanged=True)


if __name__ == '__main__':
    main()
