"""Entry boundaries before a coordinator may reach the actual SEC session."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext
import tempfile
import unittest
from unittest.mock import Mock, patch

from vnext.continuous_sec_acquisition import SecAcquisitionSession
from vnext.ordinary_refresh_cycle import _call_accounting, _check_session, refresh_and_process
from vnext import ordinary_refresh_cycle as refresh
from vnext.canonical import sha256_file
from vnext.canonical import strict_json_file
from vnext.requirements import load_requirement_snapshot
from vnext import c04_update_cycle
from tools import vnext_ordinary_refresh as refresh_cli
from contextlib import redirect_stdout
import io


class OrdinaryRefreshBoundaryTest(unittest.TestCase):
    def test_c04_precapture_state_binds_prior_pointer_and_attempt_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            args = {'state_root': root, 'company_id': 'marriott_international',
                    'metric_ids': ['B01', 'C04']}
            first = refresh._ordinary_pre_capture_state(**args)
            metric = root/'marriott_international/metrics/B01'
            metric.mkdir(parents=True)
            (metric/'configuration.json').write_bytes(b'{}\n')
            configured = refresh._ordinary_pre_capture_state(**args)
            self.assertNotEqual(first['prestate_id'], configured['prestate_id'])
            (metric/'current.json').write_bytes(b'{"latest_attempt":null}\n')
            historical = refresh._ordinary_pre_capture_state(**args)
            self.assertNotEqual(configured['prestate_id'], historical['prestate_id'])
            work = metric/'attempts'/('a'*32)
            work.mkdir(parents=True)
            (work/'intent.json').write_bytes(b'{}\n')
            attempted = refresh._ordinary_pre_capture_state(**args)
            self.assertNotEqual(historical['prestate_id'], attempted['prestate_id'])
            (work/'terminal.json').write_bytes(b'{}\n')
            self.assertNotEqual(attempted['prestate_id'],
                                refresh._ordinary_pre_capture_state(**args)['prestate_id'])
            (metric/'other.json').symlink_to(metric/'current.json')
            (metric/'current.json').unlink()
            (metric/'current.json').symlink_to(metric/'other.json')
            with self.assertRaisesRegex(ValueError,
                    'ORDINARY_REFRESH_PRESTATE_PATH_ALIAS'):
                refresh._ordinary_pre_capture_state(**args)

    def test_c04_precapture_scope_does_not_extend_other_acquisition_modes(self):
        session = object.__new__(SecAcquisitionSession)
        with self.assertRaisesRegex(ValueError,
                'SEC_ACQUISITION_ORDINARY_PRESTATE_SCOPE_INVALID'):
            session.capture(company_id='marriott_international',
                url='https://data.sec.gov/submissions/CIK0001048286.json',
                ordinary_prestate_root=Path('/unexecuted-state'),
                ordinary_prestate_metric_ids=['B01', 'C04'])
        with self.assertRaisesRegex(ValueError,
                'SEC_ACQUISITION_RESUME_PREDECESSOR_SCOPE_INVALID'):
            session.capture(company_id='marriott_international',
                url='https://data.sec.gov/submissions/CIK0001048286.json',
                source_only_c04=True,
                resume_predecessor={'previous_intent_id': 'unbound',
                    'counts': [0, 0, 1], 'ordinal': 1,
                    'source_ledger_sha256': '0'*64})

    def test_config_written_before_failed_state_read_is_not_an_attempt(self):
        from vnext import ordinary_update_cycle as update
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()/'marriott'
            with patch.object(update, '_state',
                              side_effect=ValueError('INJECTED_STATE_READ_FAILURE')):
                outcome = update.run_company(state_root=root,
                    source_root=refresh.ROOT, company_id='marriott_international',
                    metric_ids=['B01'], native_assessment_mode='RECORDED_TEST_ONLY')
            row, = outcome['metrics']
            self.assertEqual('UPDATE_BLOCKED', row['status'])
            self.assertNotIn('attempt_id', row)
            self.assertTrue((root/'metrics/B01/configuration.json').is_file())
            self.assertFalse((root/'metrics/B01/current.json').exists())
            self.assertFalse((root/'metrics/B01/attempts').exists())

    def test_unbound_live_coordinator_never_enters_the_sec_session(self):
        session = object.__new__(SecAcquisitionSession)
        session.ledger = SimpleNamespace(live=True, root=Path('/unexecuted-test-ledger'))
        session.data_root = session.ledger.root / 'source-inputs'
        session.requirement = {'execution_authority': {'files': {}}}
        session._check = Mock(side_effect=AssertionError('Must not reach SEC authorization'))
        with self.assertRaisesRegex(ValueError, 'ORDINARY_REFRESH_IMPLEMENTATION_NOT_BOUND'):
            _check_session(session)
        session._check.assert_not_called()

    def test_unbound_c04_successor_never_enters_the_sec_session(self):
        session = object.__new__(SecAcquisitionSession)
        session.ledger = SimpleNamespace(live=True, root=Path('/unexecuted-test-ledger'))
        session.data_root = session.ledger.root / 'source-inputs'
        path = Path(refresh.__file__)
        session.requirement = {'execution_authority': {'files': {
            path.relative_to(refresh.ROOT).as_posix(): {
                'sha256': sha256_file(path=path), 'size': path.stat().st_size}}}}
        session._check = Mock(side_effect=AssertionError('Must not reach SEC authorization'))
        with self.assertRaisesRegex(ValueError, 'ORDINARY_REFRESH_C04_SUCCESSOR_NOT_BOUND'):
            _check_session(session, c04_successor=True)
        session._check.assert_not_called()

    def test_c04_receipt_cannot_claim_only_the_older_update_route(self):
        session = object.__new__(SecAcquisitionSession)
        session.ledger = SimpleNamespace(live=True, root=Path('/unexecuted-test-ledger'))
        session.data_root = session.ledger.root/'source-inputs'
        session.requirement = load_requirement_snapshot(
            snapshot_dir=refresh.ROOT/'requirements/issue_28_v14')
        session._check = Mock()
        receipt = strict_json_file(path=refresh.ROOT/refresh.WIRING_PATH)
        with patch.object(refresh, 'strict_json_file', return_value={
                **receipt, 'c04_successor_recorded_route_verified': False}):
            with self.assertRaisesRegex(ValueError, 'ORDINARY_REFRESH_OFFLINE_WIRING_CHANGED'):
                _check_session(session, c04_successor=True)
            _check_session(session, c04_successor=False)

    def test_a_session_cannot_redirect_acquisition_to_another_source_root(self):
        session = object.__new__(SecAcquisitionSession)
        session.ledger = SimpleNamespace(live=False, root=Path('/unexecuted-test-ledger'))
        session.data_root = Path('/different-source-root')
        session._check = Mock(side_effect=AssertionError('Must not enter redirected session'))
        with self.assertRaisesRegex(ValueError, 'ORDINARY_REFRESH_SESSION_SOURCE_ROOT_CHANGED'):
            _check_session(session)
        session._check.assert_not_called()

    def test_finite_limit_and_native_session_are_required(self):
        for value in [True, -1, 81, None]:
            with self.subTest(limit=value), self.assertRaisesRegex(ValueError, 'FINITE_REQUEST_LIMIT_REQUIRED'):
                refresh_and_process(session=object(), state_root=Path('/unexecuted-state'), max_sec_requests=value)
        with self.assertRaisesRegex(ValueError, 'NATIVE_SESSION_REQUIRED'):
            refresh_and_process(session=object(), state_root=Path('/unexecuted-state'), max_sec_requests=1)

    def test_receipts_do_not_take_credit_for_other_cumulative_calls(self):
        captures = [{'result': {'calls': [0, 0, 1]}}]
        result = _call_accounting(captures, [20, 20, 10], [21, 21, 13], True, False)
        self.assertEqual([1, 1, 3], result['cumulative_ledger_delta'])
        self.assertEqual({'provider': 0, 'paid': 0, 'sec': 1}, result['calls'])
        self.assertEqual('KNOWN', result['status'])
        uncertain = _call_accounting(captures, [20, 20, 10], [21, 21, 13], True, True)
        self.assertIsNone(uncertain['calls']['sec'])
        self.assertEqual('UNKNOWN', uncertain['status'])
        recorded = _call_accounting([{'result': {'calls': [0, 0, 0]}}], [0, 0, 2], [0, 0, 3], False, True)
        self.assertEqual(0, recorded['calls']['sec'])
        with self.assertRaisesRegex(ValueError, 'LEDGER_COUNT_REGRESSED'):
            _call_accounting([], [0, 0, 3], [0, 0, 2], True, False)

    def test_saved_readiness_cannot_hide_a_capture_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            session = object.__new__(SecAcquisitionSession)
            session.ledger = SimpleNamespace(live=False, root=root / 'ledger', locked=nullcontext,
                snapshot=lambda: {'counts': [0, 0, 0]})
            session.data_root = session.ledger.root / 'source-inputs'; session.requirement = {}
            session.capture = Mock(side_effect=ValueError('captured source could not be verified'))
            discovery = {'status': 'SAVED_SOURCE_DEPENDENCIES_AVAILABLE', 'requirements_id': 'test-discovery',
                'limitations': [], 'requirements': [{'source_url': 'https://data.sec.gov/submissions/CIK0000078003.json',
                    'refresh_for_new_discovery': True, 'saved_status': 'VERIFIED_SAVED_SOURCE'}]}
            # Deliberate read/transport doubles isolate the coordinator's
            # status composition; native positive credit is tested separately.
            with patch.object(refresh, '_check_session'), patch.object(refresh, 'initialize_source_inputs'), \
                 patch.object(refresh, '_failed_urls', return_value=set()), \
                 patch.object(refresh, 'discover_saved_source_requirements', return_value=discovery), \
                 patch.object(refresh, 'run_company', return_value={'status': 'UPDATES_READY', 'metrics': []}):
                result = refresh_and_process(session=session, state_root=root / 'state',
                    company_ids=['pfizer'], metric_ids=['B01'], max_sec_requests=1)
            session.capture.assert_called_once()
            self.assertEqual('UPDATES_INCOMPLETE', result['status'])
            self.assertEqual('REFRESH_INCOMPLETE', result['companies'][0]['source_refresh']['status'])
            self.assertEqual('CAPTURE', result['companies'][0]['acquisition_errors'][0]['stage'])

    def test_c04_success_cannot_hide_a_neighbor_update_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            session = object.__new__(SecAcquisitionSession)
            session.ledger = SimpleNamespace(live=False, root=root/'ledger',
                locked=nullcontext, snapshot=lambda: {'counts': [0, 0, 0]})
            session.data_root = session.ledger.root/'source-inputs'
            session.requirement = {}
            discovery = {'status': 'SAVED_SOURCE_DEPENDENCIES_AVAILABLE',
                'requirements_id': 'recorded-complete', 'limitations': [], 'requirements': []}
            with patch.object(refresh, '_check_session'), \
                 patch.object(refresh, 'initialize_source_inputs'), \
                 patch.object(refresh, '_failed_urls', return_value=set()), \
                 patch.object(refresh, 'discover_saved_source_requirements', return_value=discovery), \
                 patch.object(refresh, 'run_company', side_effect=ValueError('B01_RUN_FAILED')), \
                 patch.object(c04_update_cycle, 'run_company', return_value={
                     'metrics': [{'metric_id': 'C04', 'status': 'CANDIDATE_READY'}]}):
                result = refresh_and_process(session=session, state_root=root/'state',
                    company_ids=['marriott_international'], metric_ids=['B01', 'C04'],
                    max_sec_requests=0, c04_successor=True)
            company, = result['companies']
            self.assertEqual('UPDATES_INCOMPLETE', result['status'])
            self.assertEqual('UPDATES_PARTIAL', company['updates']['status'])
            self.assertEqual(['UPDATE_BLOCKED', 'CANDIDATE_READY'],
                [row['status'] for row in company['updates']['metrics']])

    def test_public_cli_keeps_non_c04_metric_on_old_route(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.object(refresh_cli, 'live_sec_session', return_value=object()), \
                 patch.object(refresh_cli, 'refresh_and_process', return_value={
                     'status': 'UPDATES_READY', 'calls': {'provider': 0, 'paid': 0, 'sec': 0}}) as run, \
                 patch.object(refresh_cli, 'write_immutable_bytes'), \
                 redirect_stdout(io.StringIO()):
                code = refresh_cli.main(['--company', 'marriott_international',
                    '--metric', 'B01', '--state-root', str(root/'state'),
                    '--max-sec-requests', '0', '--output', str(root/'report.json')])
            self.assertEqual(0, code)
            self.assertFalse(run.call_args.kwargs['c04_successor'])

    def test_missing_new_c04_spec_alone_does_not_block_mixed_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement = load_requirement_snapshot(
                snapshot_dir=refresh.ROOT/'requirements/issue_28_v14')
            self.assertFalse(refresh._historical_c04_processing_copies(
                Path(directory).resolve(), requirement))

    def test_resume_requires_only_c04_and_one_finite_sec_request(self):
        session = object.__new__(SecAcquisitionSession)
        session.ledger = SimpleNamespace(live=False)
        session.data_root = Path('/unexecuted-source')
        session.requirement = {}
        for metrics, maximum, successor in [(['B01'], 1, False),
                                            (['B01', 'C04'], 1, True),
                                            (['C04'], 2, True)]:
            with self.subTest(metrics=metrics, maximum=maximum), \
                 patch.object(refresh, '_historical_c04_processing_copies',
                              return_value=False), \
                 self.assertRaisesRegex(ValueError,
                     'ORDINARY_REFRESH_RESUME_C04_ONE_REQUEST_REQUIRED'):
                refresh_and_process(session=session, state_root=Path('/unexecuted-state'),
                    company_ids=['marriott_international'], metric_ids=metrics,
                    max_sec_requests=maximum, c04_successor=successor,
                    resume_from=Path('/unexecuted-report'))


if __name__ == '__main__':
    unittest.main()
