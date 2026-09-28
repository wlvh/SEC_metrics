"""Current #28 update selects guarded B03 without changing V13 defaults."""
from pathlib import Path
import socket
import tempfile
from unittest import TestCase
from unittest.mock import patch

from vnext.canonical import strict_json_file
from vnext.ordinary_b03_scope_update import run_company
from vnext.ordinary_update_cycle import run_company as inherited_run_company
from vnext.normal_source_authority import ROOT


class B03CurrentUpdateMaterialTest(TestCase):
    def test_conflicted_b03_stops_while_independent_b01_completes(self):
        self.enterContext(patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')))
        self.enterContext(patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')))
        self.enterContext(patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')))
        with tempfile.TemporaryDirectory(prefix='b03-guarded-update-') as tmp:
            root = Path(tmp)
            salesforce = run_company(state_root=root/'salesforce',
                source_root=ROOT, company_id='salesforce',
                metric_ids=['B01', 'B03'])
            self.assertEqual('UPDATES_PARTIAL', salesforce['status'])
            by_metric = {row['metric_id']: row
                         for row in salesforce['metrics']}
            self.assertEqual('CANDIDATE_READY', by_metric['B01']['status'])
            self.assertEqual('EXECUTION_FAILED', by_metric['B03']['status'])
            self.assertIn('B03_CURRENT_SOURCE_SCOPE_UNRESOLVED',
                          by_metric['B03']['terminal']['error']['reason'])
            self.assertIsNone(strict_json_file(
                path=root/'salesforce/metrics/B03/current.json')[
                    'successful_attempt'])
            self.assertEqual({'provider':0,'paid':0,'sec':0},
                             salesforce['calls'])

            # Preserve an old candidate's disk history but refuse to grant it
            # current credit through the new entry when the source conflicts.
            earlier = inherited_run_company(state_root=root/'salesforce',
                source_root=ROOT, company_id='salesforce',
                metric_ids=['B03'])
            self.assertEqual('CANDIDATE_READY',
                             earlier['metrics'][0]['status'])
            after = run_company(state_root=root/'salesforce',
                source_root=ROOT, company_id='salesforce',
                metric_ids=['B03'])
            self.assertEqual('UPDATE_BLOCKED', after['metrics'][0]['status'])
            self.assertIsNone(after['metrics'][0]['last_verified_candidate'])
            self.assertEqual(earlier['metrics'][0]['successful_attempt'],
                strict_json_file(path=root/'salesforce/metrics/B03/current.json')[
                    'successful_attempt'])

            southwest = run_company(state_root=root/'southwest',
                source_root=ROOT, company_id='southwest_airlines',
                metric_ids=['B03'])
            self.assertEqual('UPDATES_READY', southwest['status'])
            self.assertEqual('CANDIDATE_READY',
                             southwest['metrics'][0]['status'])
            again = run_company(state_root=root/'southwest',
                source_root=ROOT, company_id='southwest_airlines',
                metric_ids=['B03'])
            self.assertEqual('NO_SOURCE_CONTENT_CHANGE',
                             again['metrics'][0]['status'])
            self.assertEqual(southwest['metrics'][0]['successful_attempt'],
                             again['metrics'][0]['successful_attempt'])
