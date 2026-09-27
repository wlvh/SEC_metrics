"""Two recorded C04 dependencies in one bounded ordinary update invocation."""

import csv
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))


def cold(root):
    from vnext import c04_update_cycle as c04
    from vnext import ordinary_update_cycle as ordinary
    from vnext.canonical import strict_json_file

    checks = {}
    company = root/'state/marriott_international/metrics'
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')):
        for metric, directory, verifier in (
                ('B01', company/'B01', ordinary._verify_candidate),
                ('C04', company/'C04-registration-v3', c04._verify_candidate)):
            configuration = ordinary._read(directory/'configuration.json')
            state = ordinary._state(directory, configuration)
            terminal = ordinary._terminal(directory, state['successful_attempt'])
            result = verifier(directory, terminal, configuration)[metric]
            row = directory/'attempts'/state['successful_attempt']/\
                'rows'/metric/'metrics_matrix.csv'
            checks[metric] = {'result_id': result['result_id'],
                'publication': result['publication'],
                'value': result['value'],
                'row_sha256': hashlib.sha256(row.read_bytes()).hexdigest(),
                'successful_attempt': state['successful_attempt']}
    (root/'cold.json').write_text(json.dumps(checks, sort_keys=True)+'\n')
    print(json.dumps({'cold_read': checks}, sort_keys=True), flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--cold':
        cold(Path(sys.argv[2])); return
    assert sys.argv[1:] == []
    from sec_urls import submissions_url, companyfacts_url
    from vnext.continuous_sec_acquisition import (
        initialize_source_inputs, recorded_sec_session)
    from vnext import ordinary_refresh_cycle as refresh
    urls = [submissions_url(cik=1048286), companyfacts_url(cik=1048286)]
    with (ROOT/'evidence/requests_log.csv').open(newline='') as handle:
        rows = [row for row in csv.DictReader(handle)
                if row['status_code'] == '200' and row['source_url'] in urls]
    bodies = {url: (ROOT/next(row['repo_relative_path'] for row in
               reversed(rows) if row['source_url'] == url)).read_bytes()
              for url in urls}
    with tempfile.TemporaryDirectory(prefix='issue28-c04-one-pass-') as temp:
        root = Path(temp).resolve()
        session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
        source = session.data_root
        with session.ledger.locked():
            initialize_source_inputs(root=source, requirement=session.requirement)
        (source/'config/issue28_normal_results_v2.json').write_bytes(
            b'{"historical_processing_copy":true}\n')
        (source/'config/ordinary_public_projection_v1.json').write_bytes(
            b'{"historical_processing_copy":true}\n')
        (source/'catalog/r5/C04_auditor_changes_v3.md').unlink()
        captured = []
        actual_capture = session.capture

        def record(**kwargs):
            captured.append(kwargs['url'])
            session.response = bodies[kwargs['url']]
            return actual_capture(**kwargs)

        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',
                   side_effect=AssertionError('HTTP_FORBIDDEN')), \
             patch.object(session, 'capture', side_effect=record):
            report = refresh.refresh_and_process(session=session,
                state_root=root/'state',
                company_ids=['marriott_international'],
                metric_ids=['B01', 'C04'], max_sec_requests=2,
                c04_successor=True)
        company, = report['companies']
        outcomes = {row['metric_id']: row for row in company['updates']['metrics']}
        print(json.dumps({'captures': captured, 'report_status': report['status'],
            'source_status': company['source_refresh']['status'],
            'metrics': {key: row['status'] for key,row in outcomes.items()}},
            sort_keys=True), flush=True)
        assert captured == urls and len(report['captures']) == 2
        assert report['status'] == company['updates']['status'] == 'UPDATES_READY'
        assert company['source_refresh']['deferred_source_urls'] == []
        assert {key: row['status'] for key,row in outcomes.items()} == {
            'B01': 'CANDIDATE_READY', 'C04': 'CANDIDATE_READY'}
        assert report['calls'] == {'provider': 0, 'paid': 0, 'sec': 0}
        subprocess.run([sys.executable, str(Path(__file__).resolve()),
                        '--cold', str(root)], cwd=ROOT, check=True)
        cold_result = json.loads((root/'cold.json').read_text())
        assert all(cold_result[metric]['result_id'] == outcomes[metric]
                   ['last_verified_candidate']['results'][metric]['result_id']
                   for metric in ('B01', 'C04'))
        with session.ledger.locked():
            counts = session.ledger.snapshot()['counts']
        assert counts == [0, 0, 2]
        result = {'status': 'MIXED_B01_C04_ONE_PASS_RECORDED_SOURCE_UPDATE',
            'company_id': 'marriott_international', 'source_urls': urls,
            'recorded_capture_count': 2,
            'manual_resume_report_used': False,
            'report_status': report['status'],
            'source_status': company['source_refresh']['status'],
            'metrics': cold_result, 'independent_process_cold_read': True,
            'real_provider_paid_sec_calls': [0, 0, 0],
            'historical_to_new_fiscal_year_proven': False,
            'production_authorized': False}
        Path(__file__).with_name('result.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({'final': result}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
