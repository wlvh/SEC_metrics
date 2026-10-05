"""Current interface against immutable v3 source inputs, with no live credit.

The source/proof inputs come from a complete historical Git archive. Current
Python performs normal scoped acceptance, persistence, Review/Calculator and
fresh-process replay. This is an offline interface regression, NOT a claim
that changed Python satisfies v3's frozen formal execution hashes. That formal
entry must continue rejecting this checkout until a new execution grant exists.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from vnext import ai_adapter
import sec_http
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_file
from vnext.live_scoped_reader import prepare_live_scoped_reader_session, prepare_live_scoped_reader_request
from vnext.scoped_reader import (MODEL_RESPONSIBILITIES_V1, ScopedReaderError,
    prepare_scoped_reader_request_in_session, validate_scoped_reader_response_in_session,
    replay_scoped_offline_artifact_set, model_scope_responsibilities)
from vnext.requirements import load_requirement_snapshot
from vnext.requirement_profile import validate_execution_authority, RequirementProfileError

SOURCE_COMMIT = 'f6117862093c78865be0f112cdf8a264f202ca27'
SAMPLE = REPO_ROOT / 'tests/fixtures/r4_citi_interface'
FIXTURES = ('r4_a03_production', 'r4_a03_alternate', 'r4_a04_production',
    'r4_a04_alternate', 'r4_a09_production', 'r4_a11_production',
    'r4_a11_alternate', 'r4_a12_production', 'r4_a12_alternate')


def no_network(stack):
    return [stack.enter_context(mock.patch.object(owner, name,
        side_effect=AssertionError('OFFLINE_REGRESSION forbids network')))
        for owner, name in ((ai_adapter, '_open_provider_request'),
            (sec_http.SecHttpClient, 'fetch'), (sec_http, 'urlopen'),
            (socket.socket, 'connect'), (socket.socket, 'connect_ex'))]


def native_result(*, session, fixture_id, attempt):
    """Use existing Review/Observation/Calculator; persist no publication credit."""
    from vnext.evidence import _plain_owned
    from vnext.render import build_review_context, render_review_markdown
    from vnext.review import build_review_unit, create_system_review_decision
    from vnext.observations import reviewed_observation
    from vnext.calculator import calculate_observation_metric
    from vnext.specs import compile_spec_file
    fixture, _, _, scope, authority = session._fixture(fixture_id)
    task = authority['task_contract']
    declaration = next(t for t in strict_json_file(path=session._root / 'config/r4_task_contracts_v2.json')['tasks']
        if t['task_contract_id'] == task['task_contract_id'])
    spec = compile_spec_file(path=session._root / declaration['metric_spec_path'], dependency_specs={})
    candidate, evidence = attempt['candidate'], attempt['evidence']
    source, derived = _plain_owned(authority['source_reference']), _plain_owned(authority['full_derived_asset'])
    review = build_review_context(candidate=candidate, evidence_check=evidence, derived_asset=derived,
        source_bindings=[source], spec_semantic_hash=task['task_spec_semantic_hash'],
        required_claims=spec['compiled']['required_claims'])
    rendered = render_review_markdown(review_context=review['review_context'])
    unit = build_review_unit(candidate=candidate, evidence_check=evidence,
        source_bindings=[source], compiled_spec=spec, review_context_hash=review['review_context_hash'],
        rendered_review_hash=rendered['rendered_review_hash'], renderer_semantic_version=rendered['review_renderer_semantic_version'])
    decision = create_system_review_decision(review_unit=unit, required_claims=spec['compiled']['required_claims'],
        decided_at_utc='2026-09-07T04:00:00Z', requirement=authority['requirement'])
    company = session._company(fixture['source_id'])
    period = scope['source_bound_proof']['disclosed_period']
    role = next(iter(candidate['selected']))
    observation = reviewed_observation(metric_id=fixture['metric_id'], role=role,
        company_id=company['company_id'], period_start=period['period_start'], period_end=period['period_end'],
        canonical_unit=spec['compiled']['canonical_unit'], candidate=candidate, evidence_check=evidence,
        review_unit=unit, decision=decision, source_reference=source, derived_asset_id=derived['derived_asset_id'], quality='EXACT')
    approved_scope = dict(decision['approved_claims'])
    result, trace = calculate_observation_metric(compiled_spec=spec,
        target={'company_id': company['company_id'], 'period_start': period['period_start'],
            'period_end': period['period_end'], 'scope': approved_scope, 'scope_key': content_hash(value=approved_scope)},
        company_traits=company['company_traits'], observation=observation)
    return {'classification': 'SYNTHETIC_NEW_REQUEST_FIXTURE', 'qualification_credit': 'NONE',
        'publication_credit': 'NONE', 'review': decision, 'observation': observation, 'result': result, 'trace': trace}


def cold_replay(root, fixture_id, bundle_path):
    """New process reads saved request revision and response; no parent memory."""
    with ExitStack() as stack:
        from vnext.evidence import _plain_owned
        guards = no_network(stack)
        bundle = strict_json_file(path=bundle_path)
        session = prepare_live_scoped_reader_session(repo_root=root, requirement_id='issue_28_v3')
        _, _, _, _, authority = session._fixture(fixture_id)
        replay = replay_scoped_offline_artifact_set(directory=root / bundle['directory'], repo_root=root,
            file_bindings=bundle['files'], expected_manifest_id=bundle['manifest_id'],
            expected_plan_id=bundle['plan_id'], expected_request_id=bundle['request_id'],
            expected_attempt_id=bundle['attempt_id'],
            **{k: _plain_owned(v) for k, v in authority.items() if k != 'repo_root'})
        result = native_result(session=session, fixture_id=fixture_id, attempt=replay['attempt'])
        assert canonical_json_bytes(value=result) == (root / bundle['result_path']).read_bytes()
        assert content_hash(value=result) == bundle['result_hash']
        for guard in guards:
            guard.assert_not_called()
        print(json.dumps({'independent_replay': 'PASS', 'value': result['result']['value'],
            'unit': result['result']['unit'], 'qualification_credit': 'NONE', 'provider_paid_sec': [0, 0, 0]}))


class R4ReaderResponsibilitiesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.temp = Path(cls.stack.enter_context(tempfile.TemporaryDirectory(prefix='r4-interface-')))
        cls.root = cls.temp / 'immutable-v3-inputs'
        cls.root.mkdir()
        # Explicit historical source-input archive, not a modified current
        # checkout and not a new execution authority masquerading as v3.
        archive = cls.temp / 'inputs.tar'
        with archive.open('wb') as output:
            subprocess.run(['git', 'archive', SOURCE_COMMIT], cwd=REPO_ROOT, stdout=output, check=True)
        subprocess.run(['tar', '-xf', str(archive), '-C', str(cls.root)], check=True)
        (cls.root / 'outputs/active_publication.json.lock').touch()
        cls.guards = no_network(cls.stack)
        cls.session = prepare_live_scoped_reader_session(repo_root=cls.root, requirement_id='issue_28_v3')
        cls.provenance = strict_json_file(path=SAMPLE / 'provenance.json')
        for name, binding in cls.provenance['files'].items():
            raw = (SAMPLE / name).read_bytes()
            assert sha256_bytes(content=raw) == binding['sha256'] and len(raw) == binding['size']
        cls.original = json.loads((SAMPLE / 'provider_response.json').read_bytes())['choices'][0]['message']['content']
        cls.inputs = {}
        cls.rows = []
        cls.export = os.environ.get('R4_INTERFACE_EVIDENCE_DIR')
        if cls.export:
            cls.export = Path(cls.export).resolve()
            cls.export.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    def inputs_for(self, fixture_id='r4_a03_alternate', revision=MODEL_RESPONSIBILITIES_V1):
        key = fixture_id, revision
        if key not in self.inputs:
            _, _, source, scope, authority = self.session._fixture(fixture_id)
            request = prepare_scoped_reader_request_in_session(context=source['scoped'],
                source_scope_manifest_id=scope['source_scope_manifest_id'], interface_revision=revision)
            self.inputs[key] = (source, scope, authority, request)
        return self.inputs[key]

    def accept(self, text, fixture_id='r4_a03_alternate', revision=MODEL_RESPONSIBILITIES_V1):
        source, scope, _, request = self.inputs_for(fixture_id, revision)
        return validate_scoped_reader_response_in_session(context=source['scoped'],
            source_scope_manifest_id=scope['source_scope_manifest_id'], prepared_request=request,
            response_text=text, attempt_id='attempt:synthetic-new-interface', )

    def compliant(self, fixture_id='r4_a03_alternate'):
        # This is declared test data for a NEW request. The paid wire is never
        # changed or presented as a response to the new envelope.
        response = json.loads(strict_json_file(path=self.root / 'docs/r4_v3/qualified_cases'
            / fixture_id / 'scoped_attempt.json')['response_text'])
        if fixture_id == 'r4_a03_alternate':
            competitor = copy.deepcopy(json.loads(self.original)['candidates'][0]['competing_candidates'][0])
            competitor.update(claimed_period='2025Q3', claimed_scope=[],
                rejection_reason_claim='The supplied Sep. 30, 2025 column is 2025Q3, not target 2025Q4.')
            response['candidates'][0]['competing_candidates'] = [competitor]
        return response

    def test_a_original_wire_still_rejected_and_old_request_bytes_unchanged(self):
        request = prepare_live_scoped_reader_request(repo_root=self.root, fixture_id='r4_a03_alternate',
            requirement_id='issue_28_v3', session=self.session)
        self.assertEqual(request.provider_request_body_bytes, (SAMPLE / 'provider_request.json').read_bytes())
        for revision in (None, MODEL_RESPONSIBILITIES_V1):
            attempt = self.accept(self.original, revision=revision)
            self.assertEqual(attempt['evidence']['reason_codes'], ['SCOPE_LABEL_TEXT_MISMATCH'])
            self.assertEqual(attempt['response_text'], self.original)
            self.assertEqual(attempt['candidate']['status'], 'REVIEW_REQUIRED')
            self.assertEqual(attempt['qualification_credit'], 'NONE')
        print('ORIGINAL_PAID_WIRE: rejected unchanged in both request revisions; no new credit', flush=True)

    def test_b_all_nine_requests_responsibilities_and_native_acceptance(self):
        expected = (['aggregation', 'entity_scope'], [], ['basis'], ['basis'], ['loan_population'],
            ['asset_scope'], ['asset_scope'], [], ['confidence_level'])
        policy = ai_adapter.approved_scoped_transport_policy(requirement=self.session._requirement)
        for fixture_id, dimensions in zip(FIXTURES, expected):
            with self.subTest(fixture_id=fixture_id):
                _, scope, authority, request = self.inputs_for(fixture_id)
                _, _, _, historical = self.inputs_for(fixture_id, None)
                self.assertEqual(historical.request_bytes, (self.root / 'docs/r4_v3/qualified_cases'
                    / fixture_id / 'scoped_request.json').read_bytes())
                body = json.loads(request.request_bytes)
                contract = body['scoped_transport_contract']
                self.assertEqual(contract['model_scope_dimensions'], dimensions)
                self.assertNotIn('target_locator', body)
                self.assertNotIn('reference', body)
                body.pop('scoped_plan_id'); body['record_type'] = 'LIVE_SCOPED_READER_INPUT'
                outbound, schema_bytes = ai_adapter.build_scoped_provider_request_body(policy=policy,
                    reader_request_bytes=canonical_json_bytes(value=body))
                prompt = json.loads(outbound)['messages'][0]['content']
                self.assertNotIn('Copy claimed_period exactly from', prompt)
                self.assertIn('For the selected candidate ONLY', prompt)
                self.assertIn('Do not unconditionally clear unresolved claims', prompt)
                schema = json.loads(schema_bytes)['properties']['candidates']['items']['properties']
                self.assertEqual(schema['claimed_period']['const'], scope['task_period'])
                self.assertNotIn('const', schema['competing_candidates']['items']['properties']['claimed_period'])
                if not dimensions:
                    self.assertEqual(schema['claimed_scope']['maxItems'], 0)
                    self.assertEqual(schema['scope_evidence_locators']['maxItems'], 0)
                response = canonical_json_bytes(value=self.compliant(fixture_id)).decode()
                attempt = self.accept(response, fixture_id)
                self.assertEqual(attempt['evidence']['status'], 'PASS', attempt['evidence'])
                self.assertTrue(attempt['evidence']['system_approval_eligible'])
                self.assertEqual(attempt['response_text'], response)
                self.assertEqual(attempt['qualification_credit'], 'NONE')
                row = {'fixture_id': fixture_id, 'task_period': scope['task_period'],
                    'source_scope_manifest_id': scope['source_scope_manifest_id'],
                    'source_sha256': scope['source_sha256'], 'request_sha256': sha256_bytes(content=outbound),
                    'request_bytes': len(outbound), 'output_schema_sha256': sha256_bytes(content=schema_bytes),
                    **model_scope_responsibilities(scope=scope, task_contract=authority['task_contract'])}
                self.rows.append(row)
                if self.export:
                    (self.export / (fixture_id + '.request.json')).write_bytes(outbound)
        if self.export:
            (self.export / 'nine_request_review.json').write_bytes(canonical_json_bytes(value={
                'status': 'PROPOSED_NOT_AUTHORIZED', 'interface_revision': MODEL_RESPONSIBILITIES_V1,
                'source_input_commit': SOURCE_COMMIT, 'request_count': 9, 'executed_provider_paid_sec': [0, 0, 0],
                'qualification_credit': 'NONE', 'publication_credit': 'NONE', 'entries': self.rows}))
        print('NINE_NEW_REQUESTS: native acceptance PASS; partition 2/0/1/1/1/1/1/0/1; all synthetic', flush=True)

    def test_c_normal_accept_save_result_and_fresh_process_replay(self):
        _, scope, _, request = self.inputs_for()
        attempt = self.accept(canonical_json_bytes(value=self.compliant()).decode())
        result = native_result(session=self.session, fixture_id='r4_a03_alternate', attempt=attempt)
        self.assertEqual(result['result']['value'], '1.15')
        self.assertEqual(result['review']['decision'], 'APPROVE')
        self.assertEqual(attempt['evidence']['normalized_scope'], {'aggregation': 'average', 'entity_scope': 'firm'})
        selected = next(iter(attempt['candidate']['selected'].values()))
        self.assertEqual(selected['claimed_scope'], [])
        self.assertEqual(selected['scope_evidence_locators'], [])
        directory = self.root / 'offline-interface-case'
        directory.mkdir()
        payloads = {'source_scope.json': canonical_json_bytes(value=scope),
            'scoped_plan.json': request.plan_bytes, 'scoped_request.json': request.request_bytes,
            'scoped_attempt.json': canonical_json_bytes(value=attempt)}
        for name, raw in payloads.items():
            (directory / name).write_bytes(raw)
        (self.root / 'offline-result.json').write_bytes(canonical_json_bytes(value=result))
        bundle = {'directory': directory.name, 'files': {n: {'sha256': sha256_bytes(content=b), 'size': len(b)}
            for n, b in payloads.items()}, 'manifest_id': scope['source_scope_manifest_id'], 'plan_id': request.plan_id,
            'request_id': request.request_id, 'attempt_id': attempt['scoped_attempt_id'],
            'result_path': 'offline-result.json', 'result_hash': content_hash(value=result)}
        bundle_path = self.root / 'offline-replay-input.json'
        bundle_path.write_bytes(canonical_json_bytes(value=bundle))
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ('KEY', 'TOKEN', 'SECRET'))}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        # Explicit current executable checkout; historical input Python is data.
        env['PYTHONPATH'] = str(REPO_ROOT / 'scripts') + os.pathsep + str(REPO_ROOT)
        completed = subprocess.run([sys.executable, '-m', 'tests.vnext.test_r4_reader_responsibilities',
            '--cold-replay', str(self.root), 'r4_a03_alternate', str(bundle_path)], cwd=REPO_ROOT,
            env=env, capture_output=True, text=True, timeout=240)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('"independent_replay": "PASS"', completed.stdout)
        print(completed.stdout.strip(), flush=True)
        if self.export:
            (self.export / 'independent_replay.json').write_text(completed.stdout)

    def test_d_wrong_value_period_same_value_column_caption_and_unresolved(self):
        response = self.compliant()
        mutations = {
            'wrong-value': lambda r: r['candidates'][0].update(claimed_raw_value='116'),
            'wrong-selected-period': lambda r: r['candidates'][0].update(claimed_period='2025Q3'),
            'same-115-wrong-column': lambda r: r['candidates'][0].update(locator=r['candidates'][0]['competing_candidates'][0]['locator']),
            'fabricated-caption': lambda r: r['candidates'][0].update(
                claimed_scope=json.loads(self.original)['candidates'][0]['claimed_scope'],
                scope_evidence_locators=json.loads(self.original)['candidates'][0]['scope_evidence_locators']),
            'real-unresolved-conflict': lambda r: r.update(unresolved_competing_claims=[
                {'description': 'Two same-entity, same-quarter, same-scope values remain unresolved.'}]),
            'unresolved-array-is-not-cleaned': lambda r: r.update(
                unresolved_competing_claims=json.loads(self.original)['unresolved_competing_claims']),
            'cross-table': lambda r: r['candidates'][0]['locator'].update(table_id='table_000074'),
        }
        reasons = {}
        for name, mutate in mutations.items():
            changed = copy.deepcopy(response); mutate(changed)
            with self.subTest(case=name):
                try:
                    attempt = self.accept(canonical_json_bytes(value=changed).decode())
                except ValueError as error:
                    reasons[name] = str(error)
                    continue
                self.assertFalse(attempt['evidence']['status'] == 'PASS' and attempt['evidence']['system_approval_eligible'])
                reasons[name] = attempt['evidence']['reason_codes']
        for fixture_id in ('r4_a03_production', 'r4_a12_alternate'):
            response = self.compliant(fixture_id)
            response['candidates'][0].update(claimed_scope=[], scope_evidence_locators=[])
            with self.subTest(required_table_evidence=fixture_id):
                try:
                    attempt = self.accept(canonical_json_bytes(value=response).decode(), fixture_id)
                except ValueError as error:
                    reasons[fixture_id + ':missing-labels'] = str(error)
                    continue
                self.assertFalse(attempt['evidence']['system_approval_eligible'])
                reasons[fixture_id + ':missing-labels'] = attempt['evidence']['reason_codes']
        if self.export:
            (self.export / 'negative_results.json').write_bytes(canonical_json_bytes(value=reasons))
        print('NEGATIVES: wrong value/period, same-value other column, fabricated caption, cross-table, real conflict, missing required/disambiguating labels rejected', flush=True)

    def test_e_history_and_live_execution_remain_blocked(self):
        requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / 'requirements/issue_28_v3')
        self.assertEqual(requirement['requirement_closure_hash'],
            'sha256:58e821a4987cb65042570008021ea41819d5bd9071af66aa4f394eccac5940b7')
        with self.assertRaises(RequirementProfileError):
            validate_execution_authority(repo_root=REPO_ROOT, requirement=requirement)
        # A development request is still an offline object, never the private
        # repository capability required by the unchanged provider boundary.
        _, _, _, request = self.inputs_for()
        with self.assertRaises(ValueError):
            from vnext.live_scoped_reader import rebuild_live_scoped_reader_request
            rebuild_live_scoped_reader_request(request=request)

    def test_f_local_proof_does_not_remove_a_disambiguation_obligation(self):
        scope = {'source_bound_proof': {'composite_scope': {
            'normalized_scope': {'aggregation': 'average', 'entity_scope': 'firm'},
            'table_disambiguation_dimensions': ['entity_scope']}}}
        contract = {'scope_contract': {'required_dimensions': ['entity_scope', 'aggregation']}}
        responsibilities = model_scope_responsibilities(scope=scope, task_contract=contract)
        self.assertEqual(responsibilities['model_scope_dimensions'], ['entity_scope'])
        self.assertEqual(responsibilities['local_only_scope_dimensions'], ['aggregation'])


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--cold-replay':
        cold_replay(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
    else:
        unittest.main()
