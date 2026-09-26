"""Old acquisition roots remain immutable while the explicit C04 route reads them."""
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from sec_urls import submissions_url

from vnext import normal_run_v3 as normal
from vnext import ordinary_refresh_cycle as refresh
from vnext.c04_registration_successor import EVENT_FORMS
from vnext.continuous_sec_acquisition import (
    initialize_source_inputs, recorded_sec_session)
from vnext.canonical import strict_json_file
from vnext.normal_governance_input import _Sources
from vnext.normal_source_authority import ROOT


class C04SourceOnlyInstallTest(unittest.TestCase):
    def test_old_processing_files_remain_old_and_unrelated_drift_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            source = session.data_root
            with session.ledger.locked():
                initialize_source_inputs(root=source, requirement=session.requirement)
            stale = ('config/issue28_normal_results_v2.json',
                     'config/ordinary_public_projection_v1.json')
            for name in stale:
                (source/name).write_bytes(b'{"historical_processing_copy":true}\n')
            (source/'catalog/r5/C04_auditor_changes_v3.md').unlink()
            initialize_source_inputs(root=source, requirement=session.requirement,
                                     c04_source_only=True)
            self.assertTrue(all((source/name).read_bytes() ==
                b'{"historical_processing_copy":true}\n' for name in stale))
            self.assertFalse((source/'catalog/r5/C04_auditor_changes_v3.md').exists())
            case = normal.prepare_case(data_root=source,
                company_id='marriott_international', metric_id='C04',
                c04_event_forms=EVENT_FORMS)
            self.assertEqual('PUBLISHED', case['results']['C04']['publication'])
            url = submissions_url(cik=1048286)
            session.response = _Sources(ROOT, 'marriott_international', '1048286').read(
                url, role='sec_submissions_inventory',
                media_type='application/json')['raw_bytes']
            with patch.object(socket.socket, 'connect',
                              side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                 patch.object(socket, 'getaddrinfo',
                              side_effect=AssertionError('DNS_FORBIDDEN')), \
                 patch('sec_http.urlopen',
                       side_effect=AssertionError('HTTP_FORBIDDEN')):
                captured = session.capture(company_id='marriott_international',
                    url=url, refresh_metadata=True, source_only_c04=True)
            self.assertEqual('SUCCEEDED', captured['status'])
            self.assertEqual([0, 0, 0], captured['calls'])
            plan = strict_json_file(path=root/'ledger/calls/0001/sec-plan.json')
            self.assertEqual('C04_REGISTRATION_FOUR_FORM_UPDATE_V1',
                             plan['source_only_processing_route'])
            with self.assertRaisesRegex(ValueError, 'Immutable receipt bytes differ'):
                initialize_source_inputs(root=source, requirement=session.requirement)
            (source/'catalog/zero_ai_public_projection.json').write_bytes(b'{}\n')
            with self.assertRaisesRegex(ValueError, 'Immutable receipt bytes differ'):
                initialize_source_inputs(root=source, requirement=session.requirement,
                                         c04_source_only=True)


class C04MixedSourceRouteMaterialTest(unittest.TestCase):
    def test_mixed_old_root_refreshes_only_c04_and_blocks_other_metrics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            source = session.data_root
            with session.ledger.locked():
                initialize_source_inputs(root=source, requirement=session.requirement)
            (source/'config/issue28_normal_results_v2.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            (source/'config/ordinary_public_projection_v1.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            (source/'catalog/r5/C04_auditor_changes_v3.md').unlink()
            session.response = _Sources(ROOT, 'marriott_international', '1048286').read(
                submissions_url(cik=1048286), role='sec_submissions_inventory',
                media_type='application/json')['raw_bytes']
            with patch.object(socket.socket, 'connect',
                              side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                 patch.object(socket, 'getaddrinfo',
                              side_effect=AssertionError('DNS_FORBIDDEN')), \
                 patch('sec_http.urlopen',
                       side_effect=AssertionError('HTTP_FORBIDDEN')):
                result = refresh.refresh_and_process(session=session,
                    state_root=root/'state', company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True)
            self.assertEqual(1, len(result['captures']))
            self.assertEqual('SUCCEEDED', result['captures'][0]['result']['status'])
            self.assertEqual(submissions_url(cik=1048286),
                             result['captures'][0]['source_url'])
            self.assertTrue(result['c04_mixed_source_only'])
            self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0}, result['calls'])
            company, = result['companies']
            self.assertEqual('UPDATES_PARTIAL', company['updates']['status'])
            self.assertEqual(['UPDATE_BLOCKED', 'CANDIDATE_READY'],
                [row['status'] for row in company['updates']['metrics']])
            self.assertEqual('SOURCE_SCOPE', company['acquisition_errors'][0]['stage'])
            plan = strict_json_file(path=root/'ledger/calls/0001/sec-plan.json')
            self.assertEqual('C04_REGISTRATION_FOUR_FORM_UPDATE_V1',
                             plan['source_only_processing_route'])
            with session.ledger.locked():
                self.assertEqual([0, 0, 1], session.ledger.snapshot()['counts'])

    def test_mixed_old_root_does_not_capture_unproved_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            session = recorded_sec_session(root=root/'ledger', response=b'RECORDED_ONLY')
            source = session.data_root
            with session.ledger.locked():
                initialize_source_inputs(root=source, requirement=session.requirement)
            (source/'config/issue28_normal_results_v2.json').write_bytes(
                b'{"historical_processing_copy":true}\n')
            unproved = {'source_url': 'https://www.sec.gov/Archives/unproved.json',
                'refresh_for_new_discovery': True, 'saved_status': 'MISSING_SAVED_SOURCE'}
            with patch.object(refresh, '_pending', return_value=[unproved]), \
                 patch.object(session, 'capture',
                              side_effect=AssertionError('UNPROVED_SOURCE_CLAIMED')):
                result = refresh.refresh_and_process(session=session,
                    state_root=root/'state', company_ids=['marriott_international'],
                    metric_ids=['B01', 'C04'], max_sec_requests=1,
                    c04_successor=True)
            self.assertEqual([], result['captures'])
            with session.ledger.locked():
                self.assertEqual([0, 0, 0], session.ledger.snapshot()['counts'])


if __name__ == '__main__':
    unittest.main()
