"""Recorded C04 FY2024→FY2025 rehearsal with labelled derived prior metadata."""

import csv
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

from sec_urls import submissions_url
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext import ordinary_refresh_cycle as refresh
from vnext.normal_source_authority import ROOT


COMPANIES = {'marriott_international': 1048286, 'salesforce': 1108524}


def saved_response(url):
    with (ROOT / 'evidence/requests_log.csv').open(newline='') as handle:
        rows = [row for row in csv.DictReader(handle)
                if row['source_url'] == url and row['status_code'] == '200']
    assert rows
    row = rows[-1]
    raw = (ROOT / row['repo_relative_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['content_sha256']
    return raw, row


def derived_prior_response(current):
    value = json.loads(current)
    recent = value['filings']['recent']
    annual = [(index, recent['filingDate'][index], recent['accessionNumber'][index])
              for index, form in enumerate(recent['form']) if form == '10-K']
    assert len(annual) >= 2
    cutoff = annual[0][1]
    original_count = len(recent['form'])
    keep = [index for index, filed in enumerate(recent['filingDate'])
            if filed < cutoff]
    assert annual[0][0] not in keep and annual[1][0] in keep
    for key, field in recent.items():
        if isinstance(field, list):
            assert len(field) == original_count
            recent[key] = [field[index] for index in keep]
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            .encode('utf-8'), annual[:2])


def main():
    company_id = ('salesforce' if '--salesforce' in sys.argv[1:]
                  else 'marriott_international')
    url = submissions_url(cik=COMPANIES[company_id])
    current, original_row = saved_response(url)
    prior, annual = derived_prior_response(current)
    with tempfile.TemporaryDirectory(prefix='issue28-c04-adjacent-') as temporary:
        root = Path(temporary).resolve()
        session = recorded_sec_session(root=root/'ledger', response=prior)
        state = root/'state'
        def advance(maximum):
            result = refresh.refresh_and_process(session=session,
                state_root=state, company_ids=[company_id], metric_ids=['C04'],
                max_sec_requests=maximum, c04_successor=True)
            company, = result['companies']
            metric, = company['updates']['metrics']
            print(json.dumps({'step_max_sec_requests': maximum,
                'report_status': result['status'],
                'source_status': company['source_refresh']['status'],
                'metric_status': metric['status'],
                'metric_error': metric.get('error'),
                'metric_reason': metric.get('reason'),
                'terminal_error': metric.get('terminal', {}).get('error'),
                'acquisition_errors': company['acquisition_errors'],
                'deferred_source_urls': company['source_refresh'].get(
                    'deferred_source_urls'),
                'candidate': metric.get('last_verified_candidate'),
                'captures': [(item['source_url'],item['result']['status'])
                             for item in result['captures']]},
                default=str, ensure_ascii=False), flush=True)
            return result, metric
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',
                   side_effect=AssertionError('HTTP_FORBIDDEN')):
            old_capture = session.capture(company_id=company_id, url=url,
                refresh_metadata=True, source_only_c04=True)
            assert old_capture['status'] == 'SUCCEEDED'
            first, first_metric = advance(0)
            if '--prior-only' in sys.argv[1:]:
                return
            session.response = current
            second, second_metric = advance(1)
            third, third_metric = advance(0)
        state_root = state/company_id/'metrics/C04-registration-v3'
        pointer = json.loads((state_root/'current.json').read_text())
        with session.ledger.locked():
            counts = session.ledger.snapshot()['counts']
        summary = {
            'kind': 'RECORDED_DERIVED_PRIOR_METADATA_REHEARSAL',
            'company_id': company_id,
            'current_original_source_path': original_row['repo_relative_path'],
            'current_original_source_sha256': hashlib.sha256(current).hexdigest(),
            'derived_prior_submissions_sha256': hashlib.sha256(prior).hexdigest(),
            'removed_from_prior_metadata': annual[0],
            'retained_in_prior_metadata': annual[1],
            'steps': [first_metric['status'], second_metric['status'],
                      third_metric['status']],
            'first_candidate': first_metric.get('last_verified_candidate'),
            'second_candidate': second_metric.get('last_verified_candidate'),
            'current_pointer': pointer,
            'recorded_ledger_counts': counts,
            'network_enabled': False,
            'real_provider_paid_sec_calls': [0, 0, 0],
            'actual_historical_submissions_response_used': False,
            'authentic_online_cross_year_update_proven': False,
        }
        Path(__file__).with_name('salesforce-result.json' if company_id ==
            'salesforce' else 'result.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str)+'\n')
        print(json.dumps({'final': summary}, ensure_ascii=False,
                         default=str), flush=True)


if __name__ == '__main__':
    main()
