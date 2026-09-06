"""Offline candidate against frozen source inputs; never a live authorization.

Candidate Python is imported from this checkout. The disposable *input* root
retains the exact historical source/Requirement bytes so its existing source
certificates remain independently verifiable. This is an explicit test harness,
not a claim that the changed Python satisfies the old execution authority.
"""

from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_r4_live_qualification import copy_r4_release_workspace, recorded_r4_transports
import sec_http
from vnext import ai_adapter, r4_run_store
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_file
from vnext.evidence import RAW_LABEL_POLICY, SOURCE_LABEL_POLICY_CANDIDATE, _verify_local_labels, _plain_owned
from vnext.live_scoped_reader import _acceptance_inputs, build_scoped_invocation_acceptance_context
from vnext.r4_live_authority import prepare_r4_execution_context, build_r4_recorded_test_plan
from vnext.r4_live_qualification import execute_r4_qualification, R4QualificationError, RUNTIME_ROOT
from vnext.scoped_reader import check_scoped_reader_response, prepare_scoped_reader_request_in_session
from vnext.requirements import load_requirement_snapshot
from vnext.requirement_profile import validate_execution_authority, RequirementProfileError


FIXTURE = REPO_ROOT / 'tests/fixtures/r4_label_representation'
FROZEN_INPUT_COMMIT = '75002a861555c91aeadd72260d98707225d96f49'


class R4LabelRepresentationIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.temp = cls.stack.enter_context(tempfile.TemporaryDirectory(prefix='r4-label-regression-'))
        cls.root = Path(cls.temp) / 'frozen-inputs'
        copy_r4_release_workspace(cls.root)
        baseline = strict_json_file(path=cls.root / 'requirements/issue_28_v2/baseline_manifest.json')
        # Restore only input files whose bytes changed in this candidate. No
        # loader, hash validator, Reader, Evidence or finalizer is mocked.
        for relative, binding in baseline['execution_authority']['files'].items():
            path = cls.root / relative
            if sha256_bytes(content=path.read_bytes()) != binding['sha256']:
                raw = subprocess.check_output(['git', 'show', FROZEN_INPUT_COMMIT + ':' + relative], cwd=REPO_ROOT)
                if sha256_bytes(content=raw) != binding['sha256'] or len(raw) != binding['size']:
                    raise AssertionError('Frozen test input is not the historical bound file: ' + relative)
                path.write_bytes(raw)
        cls.guards = [cls.stack.enter_context(mock.patch.object(owner, name,
            side_effect=AssertionError('OFFLINE_REGRESSION forbids network')))
            for owner, name in [(ai_adapter, '_open_provider_request'),
                (sec_http.SecHttpClient, 'fetch'), (sec_http, 'urlopen'),
                (socket.socket, 'connect'), (socket.socket, 'connect_ex')]]
        cls.context = prepare_r4_execution_context(repo_root=cls.root)
        cls.plan = build_r4_recorded_test_plan(context=cls.context)
        cls.provenance = strict_json_file(path=FIXTURE / 'provenance.json')
        for name, binding in cls.provenance['files'].items():
            raw = (FIXTURE / name).read_bytes()
            if {'sha256': sha256_bytes(content=raw), 'size': len(raw)} != binding:
                raise AssertionError('Regression sample bytes differ')
        cls.wire = (FIXTURE / 'provider_response.json').read_bytes()
        cls.response = json.loads(cls.wire)['choices'][0]['message']['content']
        cls.request = cls.context._requests['r4_a03_production']
        if cls.request.provider_request_body_bytes != (FIXTURE / 'provider_request.json').read_bytes():
            raise AssertionError('Real response does not belong to this exact source request')
        cls.inputs_cache = {}
        print('OFFLINE_REGRESSION: frozen inputs and original request/response verified', flush=True)

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    @classmethod
    def inputs(cls, fixture_id):
        if fixture_id not in cls.inputs_cache:
            request = cls.context._requests[fixture_id]
            accept = build_scoped_invocation_acceptance_context(request=request, execution_context=cls.context)
            request, (_, _, source, scope, authority) = _acceptance_inputs(context=accept)
            prepared = prepare_scoped_reader_request_in_session(context=source['scoped'],
                source_scope_manifest_id=scope['source_scope_manifest_id'])
            cls.inputs_cache[fixture_id] = (source, scope, authority, prepared)
        return cls.inputs_cache[fixture_id]

    inputs_cache = {}

    def checked(self, response=None, *, fixture_id='r4_a03_production', policy=SOURCE_LABEL_POLICY_CANDIDATE):
        source, scope, authority, prepared = self.inputs(fixture_id)
        return check_scoped_reader_response(prepared_request=prepared,
            response_text=self.response if response is None else response,
            attempt_id='attempt:offline-regression', source_scope_manifest=scope,
            expected_manifest_id=scope['source_scope_manifest_id'],
            _verified_scope_context=source['scoped'], _label_policy=policy, **authority)

    def test_real_response_old_failure_and_candidate_full_native_result(self):
        old = self.checked(policy=RAW_LABEL_POLICY)
        self.assertEqual(old['evidence']['reason_codes'], ['SCOPE_LABEL_TEXT_MISMATCH'])
        new = self.checked()
        self.assertEqual(new['candidate'], old['candidate'])
        self.assertEqual(new['evidence']['status'], 'PASS', new['evidence'])
        self.assertTrue(new['evidence']['system_approval_eligible'])
        self.assertEqual(list(new['evidence']['normalized_values'].values()), ['1.11'])
        self.assertNotEqual(new['evidence']['evidence_check_id'], old['evidence']['evidence_check_id'])
        self._native_result(new)

    def _native_result(self, checked):
        from vnext.render import build_review_context, render_review_markdown
        from vnext.review import build_review_unit, create_system_review_decision
        from vnext.observations import reviewed_observation
        from vnext.calculator import calculate_observation_metric
        from vnext.specs import compile_spec_file
        _, _, authority, _ = self.inputs('r4_a03_production')
        task = authority['task_contract']
        declaration = next(t for t in strict_json_file(path=self.root / 'config/r4_task_contracts_v2.json')['tasks']
                           if t['metric_id'] == 'A03')
        spec = compile_spec_file(path=self.root / declaration['metric_spec_path'], dependency_specs={})
        candidate, evidence = checked['candidate'], checked['evidence']
        source = _plain_owned(authority['source_reference'])
        derived = _plain_owned(authority['full_derived_asset'])
        review = build_review_context(candidate=candidate, evidence_check=evidence,
            derived_asset=derived, source_bindings=[source], spec_semantic_hash=task['task_spec_semantic_hash'],
            required_claims=spec['compiled']['required_claims'])
        rendered = render_review_markdown(review_context=review['review_context'])
        unit = build_review_unit(candidate=candidate, evidence_check=evidence,
            source_bindings=[source], compiled_spec=spec, review_context_hash=review['review_context_hash'],
            rendered_review_hash=rendered['rendered_review_hash'], renderer_semantic_version=rendered['review_renderer_semantic_version'])
        decision = create_system_review_decision(review_unit=unit,
            required_claims=spec['compiled']['required_claims'], decided_at_utc='2026-09-06T16:00:00Z',
            requirement=authority['requirement'])
        self.assertEqual(decision['decision'], 'APPROVE')
        company = strict_json_file(path=self.root / 'config/r4_fixture_company_authority_v1.json')['entries']
        fixture = next(row for row in self.context._session._authority['fixtures'] if row['fixture_id'] == 'r4_a03_production')
        company = next(row for row in company if row['source_id'] == fixture['source_id'])
        role = next(iter(candidate['selected']))
        observation = reviewed_observation(metric_id='A03', role=role, company_id=company['company_id'],
            period_start='2025-01-01', period_end='2025-12-31', canonical_unit=spec['compiled']['canonical_unit'],
            candidate=candidate, evidence_check=evidence, review_unit=unit, decision=decision,
            source_reference=source, derived_asset_id=derived['derived_asset_id'], quality='EXACT')
        scope = dict(decision['approved_claims'])
        result, trace = calculate_observation_metric(compiled_spec=spec,
            target={'company_id':company['company_id'], 'period_start':'2025-01-01', 'period_end':'2025-12-31',
                    'scope':scope, 'scope_key':content_hash(value=scope)},
            company_traits=company['company_traits'], observation=observation)
        self.assertEqual(result['value'], '1.11')
        self.assertEqual(result['publication'], 'PUBLISHED')
        self.assertEqual(trace['record_type'], 'EXECUTION_TRACE')
        print('OFFLINE_REGRESSION: original response -> Reader/Evidence/SYSTEM Review/Calculator = 1.11 ratio; no live credit', flush=True)

    def test_exact_representations_recover_source_raw_and_do_not_mutate_response(self):
        source, _, authority, _ = self.inputs('r4_a03_production')
        candidate = self.checked()['candidate']
        claim = next(iter(candidate['selected'].values()))
        recovered = _verify_local_labels(claim=claim, derived_asset=authority['full_derived_asset'],
            offline_context=source['evidence'], label_policy=SOURCE_LABEL_POLICY_CANDIDATE)
        raw = recovered['cell_28_0']
        self.assertTrue(raw.startswith('\n'))
        self.assertIn('&#8220;', raw)
        original = json.loads(self.response)
        original['candidates'][0]['scope_evidence_locators'][0]['raw_text'] = raw
        self.assertEqual(self.checked(json.dumps(original))['evidence']['status'], 'PASS')
        self.assertEqual(self.checked(json.dumps(original), policy=RAW_LABEL_POLICY)['evidence']['status'], 'PASS')
        self.assertEqual((FIXTURE / 'provider_response.json').read_bytes(), self.wire)

    def test_wrong_subject_value_period_scope_unit_and_locator_still_reject(self):
        mutations = {
            'subject': lambda c: c['scope_evidence_locators'][0].update(raw_text='JPMorgan Chase Bank, N.A.'),
            'value': lambda c: c.update(claimed_raw_value='115'),
            'period': lambda c: c.update(claimed_period='FY2024'),
            'unit': lambda c: c.update(claimed_reported_unit='USD'),
            'scope': lambda c: c['claimed_scope'][1].update(raw_value='year-end'),
            'entity_scope': lambda c: c['claimed_scope'][0].update(raw_value='JPMorgan Chase Bank, N.A.'),
            'source_identity': lambda c: c['locator'].update(derived_asset_id='sha256:' + '0' * 64),
            'cross_table': lambda c: c['scope_evidence_locators'][0]['locator'].update(table_id='table_000066'),
            'geometry': lambda c: c['scope_evidence_locators'][0]['locator'].update(colspan=2),
            'wrong_cell': lambda c: c['locator'].update(row_index=29, origin_row_index=29),
            'deleted_word': lambda c: c['scope_evidence_locators'][0].update(raw_text='Firm Liquidity coverage ratio'),
            'casefold': lambda c: c['scope_evidence_locators'][0].update(raw_text=c['scope_evidence_locators'][0]['raw_text'].lower()),
            'strip_only': lambda c: c['scope_evidence_locators'][0].update(raw_text='Firm Liquidity coverage ratio (&#8220;LCR&#8221;) (average)(b)'),
        }
        for name, mutate in mutations.items():
            data = json.loads(self.response); mutate(data['candidates'][0])
            with self.subTest(mutation=name):
                try:
                    result = self.checked(json.dumps(data))
                except ValueError:
                    continue
                self.assertEqual(result['evidence']['status'], 'REJECTED', (name, result))

    def test_legacy_composite_scope_checks_with_frozen_input_authority(self):
        # Existing tests execute candidate Python against the same immutable
        # input authority. The default policy is unchanged, with no loader or
        # semantic validator bypass. The current-root drift rejection remains
        # separately asserted by test_candidate_is_not_activated_by_changed_python.
        from tests.vnext import test_composite_scope
        with mock.patch.object(test_composite_scope, 'REPO_ROOT', self.root):
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_composite_scope.CompositeScopeTest)
            result = unittest.TestResult()
            suite.run(result)
        self.assertGreaterEqual(result.testsRun, 10)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])

    def test_unrecognized_policy_or_model_policy_field_cannot_enable_candidate(self):
        with self.assertRaisesRegex(ValueError, 'Unknown source label'):
            self.checked(policy='case_insensitive')
        data = json.loads(self.response)
        data['label_policy'] = SOURCE_LABEL_POLICY_CANDIDATE
        with self.assertRaises(ValueError):
            self.checked(json.dumps(data), policy=RAW_LABEL_POLICY)

    def test_all_nine_requests_old_and_candidate_keep_exact_certified_results(self):
        for fixture_id in self.context._requests:
            response = strict_json_file(path=self.root / 'docs/r4_offline/qualified_cases' / fixture_id / 'scoped_attempt.json')['response_text']
            with self.subTest(fixture=fixture_id):
                old = self.checked(response, fixture_id=fixture_id, policy=RAW_LABEL_POLICY)
                new = self.checked(response, fixture_id=fixture_id)
                self.assertEqual(old['evidence']['status'], 'PASS')
                self.assertEqual(new['evidence']['status'], 'PASS')
                for field in ['normalized_values','normalized_scope','system_approval_eligible']:
                    self.assertEqual(old['evidence'][field], new['evidence'][field])
                # Exercise both supplied representations across the whole
                # affected request set, not just the historical A03 failure.
                source, _, authority, _ = self.inputs(fixture_id)
                display = json.loads(response)
                for claim in display['candidates']:
                    for label in claim['scope_evidence_locators']:
                        if label['location_type'] != 'caption':
                            cell = source['evidence'].resolve_cell(
                                derived_asset=authority['full_derived_asset'], locator=label['locator'])
                            label['raw_text'] = cell['text']
                display_checked = self.checked(json.dumps(display), fixture_id=fixture_id)
                self.assertEqual(display_checked['evidence']['status'], 'PASS')
                for field in ['normalized_values','normalized_scope','system_approval_eligible']:
                    self.assertEqual(old['evidence'][field], display_checked['evidence'][field])

    def test_failure_finalizer_seals_failed_run_and_stops_before_second_transport(self):
        transports = recorded_r4_transports(context=self.context, plan=self.plan)
        first = self.plan['entries'][0]
        transports[first['entry_id']] = ai_adapter.build_recorded_scoped_transport(
            raw_response_bytes=self.wire,
            expected_provider_request_body_sha256=self.request.identity['provider_request_body_sha256'])
        native = ai_adapter._ScopedInvocationControllerTransport.send
        sends = []
        def counted(sender, **kwargs):
            sends.append(1)
            return native(sender, **kwargs)
        with mock.patch.object(ai_adapter._ScopedInvocationControllerTransport, 'send', new=counted), \
                mock.patch.object(r4_run_store, 'finalize_r4_scoped_run', wraps=r4_run_store.finalize_r4_scoped_run) as finalizer:
            with self.assertRaisesRegex(R4QualificationError, 'stopped on terminal FAILED_TERMINAL'):
                execute_r4_qualification(repo_root=self.root, plan=self.plan, context=self.context,
                    recorded_transports=transports, clock=lambda:datetime(2026,9,6,16,tzinfo=timezone.utc))
        self.assertEqual(finalizer.call_count, 1)
        self.assertEqual(len(sends), 1)
        parent = self.root / RUNTIME_ROOT / self.plan['pending_plan_id'][7:]
        entry_root = parent / 'entries' / first['entry_id'][7:]
        terminal = strict_json_file(path=entry_root / 'qualification_terminal.json')
        self.assertEqual(terminal['status'], 'FAILED')
        self.assertEqual(terminal['run_status'], 'FAILED')
        self.assertEqual(terminal['execution_status'], 'FAILED_TERMINAL')
        self.assertEqual(terminal['counters']['real_model_provider_egress_count'], 0)
        receipt = strict_json_file(path=entry_root / 'run/validation.json')
        self.assertEqual(receipt['status'], 'FAILED')
        self.assertEqual(receipt['checks'], [{'check':'R4_SCOPED_TERMINAL_EXECUTION','status':'FAIL'}])
        self.assertEqual(len(list((parent/'entries').iterdir())), 1)
        self.assertFalse((parent/'execution_summary.json').exists())
        print('OFFLINE_REGRESSION: real failure finalizer sealed FAILED; later sends=0', flush=True)

    def test_candidate_is_not_activated_by_changed_python(self):
        requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / 'requirements/issue_28_v2')
        with self.assertRaisesRegex(RequirementProfileError, 'execution authority bytes differ'):
            validate_execution_authority(repo_root=REPO_ROOT, requirement=requirement)


if __name__ == '__main__':
    unittest.main()
