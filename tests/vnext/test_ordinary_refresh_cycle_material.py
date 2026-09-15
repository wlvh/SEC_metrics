"""Bounded recorded SEC refresh into real JPM/Pfizer ordinary update history."""
import json
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from vnext import normal_run_v3 as normal
from vnext import ordinary_refresh_cycle as refresh
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.normal_governance_input import _Sources
from vnext.normal_source_requirements import discover_saved_source_requirements


@unittest.skipUnless(os.environ.get('ORDINARY_REFRESH_MATERIAL_ROOT'), 'Requires a fresh external material root')
class OrdinaryRefreshCycleMaterialTest(unittest.TestCase):
    def test_discovery_capture_update_reentry_failure_and_recovery(self):
        root = Path(os.environ['ORDINARY_REFRESH_MATERIAL_ROOT']).resolve()
        resuming = os.environ.get('ORDINARY_REFRESH_REUSE_ACQUIRED_SOURCES') == '1'
        if resuming:
            self.assertTrue((root / 'ledger/source-inputs').is_dir())
        else:
            self.assertFalse(root.exists()); root.mkdir(parents=True)
        report_prefix = os.environ.get('ORDINARY_REFRESH_REPORT_PREFIX', '')
        state_root = Path(os.environ.get('ORDINARY_REFRESH_STATE_ROOT', str(root / 'state'))).resolve()
        originals = Path(os.environ.get('ORDINARY_REFRESH_ORIGINALS_ROOT',
            '/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')).resolve()
        self.assertTrue(originals.is_dir())
        session = recorded_sec_session(root=root / 'ledger', response=b'RECORDED_RESPONSE_IS_SET_FROM_ORIGINAL_BEFORE_CAPTURE')
        native_capture = session.capture
        companies = ['jpmorgan_chase', 'pfizer']; ciks = {'jpmorgan_chase': '19617', 'pfizer': '78003'}
        requests, phases, phase = [], {}, 'initial'
        pointer = normal.ROOT / 'outputs/active_publication.json'; protected = pointer.read_bytes()

        def capture(**kwargs):
            company, url = kwargs['company_id'], kwargs['url']
            discovered = discover_saved_source_requirements(repo_root=session.data_root, company_id=company)
            entry = next(item for item in discovered['requirements'] if item['source_url'] == url)
            status, body = 200, None
            if phase == 'remote-failure' and company == 'pfizer':
                status, body = 503, b'RECORDED_SERVICE_UNAVAILABLE'
            else:
                for source_root in (originals, normal.ROOT):
                    try:
                        source = _Sources(source_root, company, ciks[company]).read(url,
                            accession=entry['accession'], role=entry['roles'][0], media_type=entry['media_type'])
                        body = source['raw_bytes']; break
                    except ValueError:
                        continue
                if body is None:
                    status, body = 503, b'RECORDED_SOURCE_NOT_IN_SAVED_TEST_CORPUS'
            session.response, session.response_status = body, status
            requests.append({'phase': phase, 'company_id': company, 'source_url': url, 'status_code': status,
                             'roles': entry['roles'], 'saved_status_before': entry['saved_status']})
            return native_capture(**kwargs)

        def run(name, maximum):
            result = refresh.refresh_and_process(session=session, state_root=state_root, company_ids=companies,
                metric_ids=['B01'], max_sec_requests=maximum)
            phases[name] = result
            report_path = root / (report_prefix + name + '.json')
            self.assertFalse(report_path.exists())
            report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
            self.assertLessEqual(len(result['captures']), maximum)
            urls = [item['source_url'] for item in result['captures']]
            self.assertEqual(len(urls), len(set(urls)))
            self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0}, result['calls'])
            return {c['company_id']: c['updates']['metrics'][0] for c in result['companies']}

        with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN')), \
             patch.object(session, 'capture', side_effect=capture):
            first = run('initial', 0 if resuming else 6)
            for company in companies:
                self.assertEqual('CANDIDATE_READY', first[company]['status'])
                self.assertEqual(2025, first[company]['last_verified_candidate']['targets']['B01']['fiscal_year'])
            phase = 'repeat'
            repeated = run('repeat', 2)
            for company in companies:
                self.assertEqual('NO_SOURCE_CONTENT_CHANGE', repeated[company]['status'])
                self.assertEqual(first[company]['successful_attempt'], repeated[company]['successful_attempt'])
            phase = 'remote-failure'
            failed = run('remote-failure', 2)
            self.assertEqual('NO_SOURCE_CONTENT_CHANGE', failed['jpmorgan_chase']['status'])
            self.assertEqual('INPUT_FAILED', failed['pfizer']['status'])
            self.assertEqual(first['pfizer']['successful_attempt'], failed['pfizer']['successful_attempt'])
            self.assertFalse(failed['pfizer']['last_verified_candidate']['current_input_matches'])
            failed_urls = {r['source_url'] for r in requests if r['status_code'] != 200}
            phase = 'after-remote-failure'
            run('after-remote-failure', 2)
            self.assertFalse(failed_urls.intersection(r['source_url'] for r in requests if r['phase'] == phase))
            # A local input-read fault is different from a remote retry. Restore
            # the exact immutable original without issuing another SEC request.
            case = normal.prepare_case(data_root=session.data_root, company_id='jpmorgan_chase', metric_id='B01')
            proof = next(p for p in case['source_proofs'] if p['document_name'].endswith('.htm'))
            source_path = session.data_root / proof['request_repo_relative_path']; original = source_path.read_bytes()
            source_path.write_bytes(original + b' ')
            phase = 'local-input-failure'
            local_failed = run('local-input-failure', 0)
            self.assertEqual('INPUT_FAILED', local_failed['jpmorgan_chase']['status'])
            self.assertEqual(first['jpmorgan_chase']['successful_attempt'], local_failed['jpmorgan_chase']['successful_attempt'])
            source_path.write_bytes(original)
            phase = 'local-input-restored'
            restored = run('local-input-restored', 0)
            self.assertEqual('NO_SOURCE_CONTENT_CHANGE', restored['jpmorgan_chase']['status'])
            self.assertEqual(first['jpmorgan_chase']['successful_attempt'], restored['jpmorgan_chase']['successful_attempt'])
        self.assertEqual(protected, pointer.read_bytes())
        (root / (report_prefix + 'requests.json')).write_text(json.dumps(requests, indent=2) + '\n')
        (root / (report_prefix + 'summary.json')).write_text(json.dumps({'status': 'PASS', 'phases': list(phases),
            'reused_acquired_recorded_source_inputs': resuming,
            'native_initial_results': {c: first[c]['last_verified_candidate']['results']['B01'] for c in companies},
            'recorded_sec_slots': len(requests), 'calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'failed_urls_never_automatically_retried': sorted(failed_urls),
            'actual_new_fiscal_year': False, 'full390_acceptance': False, 'production_authorized': False}, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
