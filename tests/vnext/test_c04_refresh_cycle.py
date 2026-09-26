"""A bounded recorded source refresh reaches the C04 four-form update route."""
import csv
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from sec_urls import companyfacts_url, submissions_url
from vnext import ordinary_refresh_cycle as refresh
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.normal_source_authority import ROOT


class C04RefreshCycleMaterialTest(unittest.TestCase):
    def test_two_saved_metadata_versions_create_two_native_c04_results(self):
        url = submissions_url(cik=1048286)
        companyfacts = companyfacts_url(cik=1048286)
        with (ROOT/'evidence/requests_log.csv').open(newline='') as handle:
            rows = [row for row in csv.DictReader(handle) if row['status_code'] == '200']
        matches = [row for row in rows if row['source_url'] == url]
        self.assertGreaterEqual(len(matches), 3)
        old, latest = matches[-2:]
        self.assertNotEqual(old['content_sha256'], latest['content_sha256'])
        responses = [(ROOT/row['repo_relative_path']).read_bytes()
                     for row in (old, latest)]
        facts = [row for row in rows if row['source_url'] == companyfacts]
        self.assertTrue(facts)
        facts_response = (ROOT/facts[-1]['repo_relative_path']).read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=responses[0])
            capture = session.capture
            state = root/'state'
            def advance(maximum):
                result = refresh.refresh_and_process(session=session, state_root=state,
                    company_ids=['marriott_international'], metric_ids=['C04'],
                    max_sec_requests=maximum, c04_successor=True)
                company, = result['companies']
                row, = company['updates']['metrics']
                self.assertEqual('C04', row['metric_id'])
                self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0}, result['calls'])
                self.assertEqual('SAVED_SOURCE_DEPENDENCIES_AVAILABLE',
                                 company['source_refresh']['source_discovery_status'])
                return result, row
            current_submissions = responses[0]
            def recorded_capture(**kwargs):
                session.response = (current_submissions if kwargs['url'] == url
                                    else facts_response if kwargs['url'] == companyfacts
                                    else None)
                self.assertIsNotNone(session.response)
                return capture(**kwargs)
            with patch.object(socket.socket, 'connect',
                              side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                 patch.object(socket, 'getaddrinfo',
                              side_effect=AssertionError('DNS_FORBIDDEN')), \
                 patch('sec_http.urlopen',
                       side_effect=AssertionError('HTTP_FORBIDDEN')), \
                 patch.object(session, 'capture', side_effect=recorded_capture):
                first_report, first = advance(2)
                self.assertEqual('UPDATES_READY', first_report['status'])
                self.assertEqual('CANDIDATE_READY', first['status'])
                self.assertEqual('0', first['last_verified_candidate']['results']['C04']['value'])
                current_submissions = responses[1]
                second_report, second = advance(2)
                self.assertEqual('UPDATES_READY', second_report['status'])
                self.assertEqual('CANDIDATE_READY', second['status'])
                self.assertNotEqual(first['successful_attempt'], second['successful_attempt'])
                self.assertEqual(first['successful_attempt'],
                                 second['previous_successful_attempt'])
                self.assertEqual('0', second['last_verified_candidate']['results']['C04']['value'])
                self.assertNotEqual(first['last_verified_candidate']['results']['C04']['result_id'],
                                    second['last_verified_candidate']['results']['C04']['result_id'])
            self.assertEqual(url, first_report['captures'][0]['source_url'])
            self.assertEqual(url, second_report['captures'][0]['source_url'])
            self.assertEqual(companyfacts, first_report['captures'][1]['source_url'])
            self.assertEqual(companyfacts, second_report['captures'][1]['source_url'])
            self.assertEqual(4, len(list((root/'ledger/calls').iterdir())))
            self.assertTrue((state/'marriott_international/metrics/C04-registration-v3').is_dir())
            self.assertFalse((state/'marriott_international/metrics/C04').exists())


if __name__ == '__main__':
    unittest.main()
