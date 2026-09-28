"""Current #28 update selects guarded B03 without changing V13 defaults."""
from copy import deepcopy
from pathlib import Path
import socket
import tempfile
from unittest import TestCase
from unittest.mock import patch

from vnext.canonical import content_hash, strict_json_file
from vnext.ordinary_b03_scope_update import run_company
from vnext import ordinary_b03_scope_update as successor
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
            self.assertEqual('PREVIOUS_INPUT_WITHHELD',
                             after['metrics'][0]['status'])
            self.assertIsNone(after['metrics'][0]['last_verified_candidate'])
            self.assertEqual(earlier['metrics'][0]['successful_attempt'],
                strict_json_file(path=root/'salesforce/metrics/B03/current.json')[
                    'successful_attempt'])
            # A corrected input must be allowed to start a *new* attempt.
            # This fabricated descriptor only tests control flow: installation
            # is deliberately stopped before it can claim a business result.
            changed = deepcopy(after['metrics'][0]['terminal']['input'])
            changed['source_contents'][0]['sha256'] = 'synthetic-new-source'
            changed['content_id'] = content_hash(value={k:v for k,v in
                changed.items() if k != 'content_id'})
            with patch.object(successor.inherited, '_inspect',
                              return_value=({}, changed, 'synthetic-ledger')), \
                 patch.object(successor.normal, 'install_normal_inputs',
                              side_effect=RuntimeError('SYNTHETIC_INSTALL_STOP')):
                new_attempt = run_company(state_root=root/'salesforce',
                    source_root=ROOT, company_id='salesforce',
                    metric_ids=['B03'])
            self.assertEqual('EXECUTION_FAILED',
                             new_attempt['metrics'][0]['status'])
            self.assertEqual('SYNTHETIC_INSTALL_STOP',
                             new_attempt['metrics'][0]['terminal']['error']['reason'])
            self.assertEqual(earlier['metrics'][0]['successful_attempt'],
                             new_attempt['metrics'][0]['successful_attempt'])
            self.assertIsNone(new_attempt['metrics'][0]['last_verified_candidate'])

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


class B03HistoricalRecoveryVerifierTest(TestCase):
    def test_only_source_scope_conflict_can_retain_a_historical_terminal(self):
        old_rows = {'B03': {'result_id': 'historical-only'}}
        with (patch.object(successor, '_verify_candidate',
                           side_effect=successor.B03CurrentScopeConflict(
                               'B03_CURRENT_SUCCESS_SCOPE_UNRESOLVED')),
              patch.object(successor.inherited, '_verify_candidate',
                           return_value=old_rows) as mechanical):
            self.assertEqual(old_rows, successor._verify_historical_candidate(
                'root', 'terminal', 'configuration'))
            mechanical.assert_called_once_with('root', 'terminal',
                                               'configuration')
        with (patch.object(successor, '_verify_candidate',
                           side_effect=ValueError('UPDATE_SUCCESS_ROW_CHANGED')),
              patch.object(successor.inherited, '_verify_candidate') as mechanical):
            with self.assertRaisesRegex(ValueError,
                                        'UPDATE_SUCCESS_ROW_CHANGED'):
                successor._verify_historical_candidate(
                    'root', 'terminal', 'configuration')
            mechanical.assert_not_called()
