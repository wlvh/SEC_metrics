"""Current #28 update selects guarded B03 without changing V13 defaults."""
from copy import deepcopy
from contextlib import ExitStack, nullcontext
from pathlib import Path
import socket
import tempfile
from unittest import TestCase
from unittest.mock import patch

from vnext.canonical import content_hash, strict_json_file
from vnext.ordinary_b03_scope_update import run_company
from vnext import ordinary_b03_scope_update as successor
from vnext import ordinary_refresh_cycle as refresh
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
            root = Path(tmp).resolve()
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



class B03LegacyRecoveryMaterialTest(TestCase):
    def test_old_success_has_no_current_credit_but_new_input_can_attempt(self):
        self.enterContext(patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')))
        self.enterContext(patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')))
        self.enterContext(patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')))
        with tempfile.TemporaryDirectory(prefix='b03-old-success-') as tmp:
            root = Path(tmp).resolve()
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
            b03_root = root/'salesforce/metrics/B03'
            b03_configuration = successor.inherited._config(
                b03_root, ROOT, 'salesforce', ['B03'], 'LIVE')
            b03_state = successor.inherited._state(b03_root,
                                                    b03_configuration)
            self.assertFalse(refresh._ordinary_current_candidate_present(
                metric='B03', metric_root=b03_root, state=b03_state,
                configuration=b03_configuration))
            old_terminal = successor.inherited._terminal(b03_root,
                b03_state['successful_attempt'])
            name = next(iter(old_terminal['metrics']['B03']['files']))
            row_path = b03_root/'attempts'/b03_state['successful_attempt']/\
                'rows/B03'/name
            saved_row = row_path.read_bytes()
            try:
                row_path.write_bytes(b'CHANGED_ROW')
                with self.assertRaisesRegex(ValueError,
                                            'UPDATE_SUCCESS_ROW_CHANGED'):
                    refresh._ordinary_current_candidate_present(
                        metric='B03', metric_root=b03_root, state=b03_state,
                        configuration=b03_configuration)
            finally:
                row_path.write_bytes(saved_row)
            # A corrected input must be allowed to start a *new* attempt.
            # This fabricated descriptor only tests control flow: installation
            # is deliberately stopped before it can claim a business result.
            changed = deepcopy(after['metrics'][0]['terminal']['input'])
            changed['source_contents'][0]['sha256'] = 'synthetic-new-source'
            changed['content_id'] = content_hash(value={k:v for k,v in
                changed.items() if k != 'content_id'})
            historical = earlier['metrics'][0]['last_verified_candidate'][
                'results']
            with patch.object(successor.inherited, '_inspect',
                              return_value=({'B03': {'primary_metric_id': 'B03'}},
                                            changed, 'synthetic-ledger')), \
                 patch.object(successor, '_verify_candidate',
                              side_effect=successor.B03CurrentScopeConflict(
                                  'B03_CURRENT_SUCCESS_SCOPE_UNRESOLVED',
                                  historical)), \
                 patch.object(successor, 'assess_current_b03_scope',
                              return_value={'blocked': False,
                                            'status': 'NO_DIRECT_DEPRECIATION_SELECTION'}), \
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


class B03SouthwestUpdateMaterialTest(TestCase):
    def test_positive_b03_still_repeats_without_a_new_result(self):
        self.enterContext(patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')))
        self.enterContext(patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')))
        self.enterContext(patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')))
        with tempfile.TemporaryDirectory(prefix='b03-positive-update-') as tmp:
            root = Path(tmp).resolve()
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
            southwest_root = root/'southwest/metrics/B03'
            southwest_configuration = successor.inherited._config(
                southwest_root, ROOT, 'southwest_airlines', ['B03'], 'LIVE')
            southwest_state = successor.inherited._state(southwest_root,
                southwest_configuration)
            self.assertTrue(refresh._ordinary_current_candidate_present(
                metric='B03', metric_root=southwest_root,
                state=southwest_state,
                configuration=southwest_configuration))


class B03FordUpdateMaterialTest(TestCase):
    def test_exact_original_split_creates_new_current_b03_without_rewriting_old(self):
        self.enterContext(patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')))
        self.enterContext(patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')))
        self.enterContext(patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')))
        with tempfile.TemporaryDirectory(prefix='b03-ford-impairment-') as tmp:
            root = Path(tmp).resolve()
            outcome = run_company(state_root=root/'ford', source_root=ROOT,
                company_id='ford_motor_company', metric_ids=['B03'])
            row, = outcome['metrics']
            self.assertEqual('UPDATES_READY', outcome['status'])
            self.assertEqual('CANDIDATE_READY', row['status'])
            current = row['last_verified_candidate']['results']['B03']
            self.assertEqual('-0.007128858795196163766173431518',
                             current['value'])
            self.assertNotEqual(
                'sha256:1829d73dac66a195a590ab84ea1f1d1800a77fae60d828b6f37d5cbeec2abd30',
                current['result_id'])
            state = strict_json_file(
                path=root/'ford/metrics/B03/current.json')
            self.assertEqual(row['attempt_id'], state['successful_attempt'])
            work = root/'ford/metrics/B03/attempts'/row['attempt_id']
            from vnext.ordinary_projection import render_ordinary_run
            replay = render_ordinary_run(data_root=work/'data',
                run_dir=work/'runs/B03', _return_replay_context=True)
            self.assertEqual(
                'catalog/r6/B03_impairment_excluded_v1.md',
                replay['replay_context']['case']['spec_paths']['B03'])
            self.assertEqual(current['result_id'], next(item['result_id']
                for item in replay['replay_context']['records']
                if item['record_type'] == 'METRIC_RESULT'
                and item['metric_id'] == 'B03'))
            self.assertEqual({'provider':0,'paid':0,'sec':0}, outcome['calls'])


class B03HistoricalRecoveryVerifierTest(TestCase):
    def test_only_source_scope_conflict_can_retain_a_historical_terminal(self):
        old_rows = {'B03': {'result_id': 'historical-only'}}
        with (patch.object(successor, '_verify_candidate',
                           side_effect=successor.B03CurrentScopeConflict(
                               'B03_CURRENT_SUCCESS_SCOPE_UNRESOLVED',
                               old_rows)),
              patch.object(successor.inherited, '_verify_candidate',
                           return_value=old_rows) as mechanical):
            self.assertEqual(old_rows, successor._verify_historical_candidate(
                'root', 'terminal', 'configuration'))
            mechanical.assert_not_called()
        with (patch.object(successor, '_verify_candidate',
                           side_effect=ValueError('UPDATE_SUCCESS_ROW_CHANGED')),
              patch.object(successor.inherited, '_verify_candidate') as mechanical):
            with self.assertRaisesRegex(ValueError,
                                        'UPDATE_SUCCESS_ROW_CHANGED'):
                successor._verify_historical_candidate(
                    'root', 'terminal', 'configuration')
            mechanical.assert_not_called()

    def test_late_processing_failure_cannot_recredit_old_success(self):
        old = 'a'*32
        previous_input = {'targets': {'B03': {'period_end': '2025-01-31'}}}
        changed_input = {'targets': {'B03': {'period_end': '2026-01-31'}}}
        configuration = {'record_id': 'configuration',
                         'company_id': 'salesforce', 'metric_ids': ['B03']}
        state = {'latest_attempt': old, 'successful_attempt': old,
                 'configuration_id': 'configuration'}
        prior = {'attempt_id': old, 'status': 'CANDIDATE_READY',
                 'input': previous_input}
        created = {'result': {'result_id': 'new-result',
                              'publication': 'PUBLISHED'},
                   'input_binding': {'source_admission': {
                       'source_credit': 'RECORDED_TEST_ONLY'}},
                   'manifest': {'run_id': 'synthetic-new-run'}}
        with tempfile.TemporaryDirectory(prefix='b03-postcheck-') as tmp:
            root = Path(tmp)
            with ExitStack() as stack:
                stack.enter_context(patch.object(successor.inherited,
                    '_locked', return_value=nullcontext()))
                stack.enter_context(patch.object(successor.inherited,
                    '_config', return_value=configuration))
                stack.enter_context(patch.object(successor.inherited,
                    '_state', return_value=state))
                stack.enter_context(patch.object(successor.inherited,
                    '_recover', return_value=state))
                stack.enter_context(patch.object(successor.inherited,
                    '_terminal', return_value=prior))
                stack.enter_context(patch.object(successor.inherited,
                    '_record', side_effect=lambda path, body: {
                        **body, 'record_id': content_hash(value=body)}))
                stack.enter_context(patch.object(successor.inherited,
                    '_inspect', return_value=({'B03': {'primary_metric_id': 'B03'}}, changed_input,
                                              'unchanged-ledger')))
                installed = stack.enter_context(patch.object(successor.normal,
                    'install_normal_inputs'))
                made = stack.enter_context(patch.object(successor.normal,
                    'create_normal_run', return_value=created))
                rendered = stack.enter_context(patch.object(successor,
                    'render_ordinary_run', return_value={'files': {},
                        'replay_context': {'case': {
                            'primary_metric_id': 'B03'}}}))
                scoped = stack.enter_context(patch.object(successor,
                    'assess_current_b03_scope',
                    return_value={'blocked': False,
                                  'status': 'NO_EXPLICIT_NARROW_SCOPE_FOUND'}))
                stack.enter_context(patch.object(successor,
                    'sha256_file', return_value='unchanged-ledger'))
                stack.enter_context(patch.object(successor,
                    'load_requirement_snapshot', return_value={}))
                stack.enter_context(patch.object(successor,
                    'atomic_write_json'))
                postcheck = stack.enter_context(patch(
                    'vnext.ordinary_processing_source.verify_processing_source',
                    side_effect=[{}, ValueError('POSTCHECK_SOURCE_CHANGED')]))
                verifier = stack.enter_context(patch.object(successor,
                    '_verify_candidate', side_effect=[
                        successor.B03CurrentScopeConflict(
                            'B03_CURRENT_SUCCESS_SCOPE_UNRESOLVED',
                            {'B03': {'result_id': 'historical-only'}}),
                        {'B03': {'result_id': 'new-result'}}]))
                outcome = successor._run_once_b03(
                    state_root=root/'state', source_root=root/'processing',
                    source_identity_root=root/'identity',
                    company_id='salesforce')
            self.assertEqual(2, postcheck.call_count)
            self.assertEqual(2, verifier.call_count)
            self.assertEqual((1, 1, 1, 2),
                             (installed.call_count, made.call_count,
                              rendered.call_count, scoped.call_count))
            self.assertEqual('EXECUTION_FAILED', outcome['status'])
            self.assertEqual('POSTCHECK_SOURCE_CHANGED',
                             outcome['terminal']['error']['reason'])
            self.assertEqual(old, outcome['successful_attempt'])
            self.assertIsNone(outcome['last_verified_candidate'])
