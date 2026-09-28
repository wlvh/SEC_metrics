"""D03's real saved source reaches recorded WB-3 without company credit."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from vnext.canonical import (canonical_json_bytes, content_hash,
                             strict_json_file, strict_json_loads)
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.continuous_semantic_calls import (
    execute_d03_recorded_assessment, execute_feasibility,
    prepare_d03_replay_only_requests, request_digest,
)
from vnext.native_assessment_replay import replay_native_response
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot
from vnext.d03_native_assessment import collect_recorded_assessments


def _response(request, *, unresolved=False):
    units = []
    for unit in request['units']:
        indices = sorted({row['source_index'] for row in
            request['required_candidate_assessments']
            if row['unit_id'] == unit['unit_id']})
        units.append({'unit_id': unit['unit_id'], 'reviewed': True,
            'findings': [], 'context_only_source_indices': indices,
            'unresolved': (['Needs source relationship review.']
                           if unresolved else [])})
    return {'request_id': request['request_id'], 'units': units}


def _wire(response):
    return canonical_json_bytes(value={
        'id': 'recorded-d03-native-unit', 'model': 'deepseek-flash',
        'choices': [{'message': {'role': 'assistant',
            'content': json.dumps(response, ensure_ascii=False)},
            'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 100,
                  'total_tokens': 200, 'prompt_cache_hit_tokens': 0,
                  'prompt_cache_miss_tokens': 100}})


class D03NativeAssessmentTest(unittest.TestCase):
    def test_saved_source_recorded_candidate_replays_but_is_not_company_result(self):
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')):
            prepared = prepare_d03_replay_only_requests(
                company_id='marriott_international')
            selected = next(row for row in prepared if
                strict_json_loads(text=row.request_bytes.decode())[
                    'required_candidate_assessments'])
            request = strict_json_loads(text=selected.request_bytes.decode())
            with tempfile.TemporaryDirectory(prefix='d03-native-recorded-') as temporary:
                ledger = recorded_ledger(root=Path(temporary) / 'ledger')
                path, outcome = execute_d03_recorded_assessment(
                    prepared=selected, ledger=ledger,
                    recorded_wire=_wire(_response(request)))
                self.assertEqual('SUCCEEDED', outcome['terminal']['status'])
                self.assertTrue(outcome['native_candidate_evidence_created'])
                self.assertFalse(outcome['native_result_created'])
                self.assertEqual('ONE_REQUEST_SOURCE_ASSESSMENT_NOT_COMPLETE_METRIC',
                                 outcome['acceptance_scope'])
                saved = strict_json_file(path=path/'d03-assessment.json')
                self.assertEqual(outcome, saved)
                replay = replay_native_response(prepared=selected, path=path)
                self.assertEqual(content_hash(value={
                    'purpose': 'D03_SOURCE_ASSESSMENT',
                    'source': request['source_id']}),
                    replay['plan']['release_input_plan_id'])
                accepted = replay['success']['acceptance_receipt']
                self.assertEqual('D03_REQUEST_SOURCE_ASSESSMENT_V1',
                                 accepted['validator_semantic_version'])
                self.assertEqual('OBSERVATION_CANDIDATE',
                                 accepted['candidate_record']['record_type'])
                self.assertEqual('EVIDENCE_CHECK',
                                 accepted['evidence_record']['record_type'])
                self.assertEqual('PASS', accepted['evidence_record']['status'])
                self.assertIn('D03_ORIGINAL_SOURCE_REFERENCES_AND_FORMAT',
                    [row['check'] for row in accepted['evidence_record']['checks']])
                self.assertEqual(12, len(accepted['candidate_record']['selected'][
                    'source_assessment']['findings']))
                self.assertFalse(replay['revalidation']['new_provider_execution'])
                with ledger.locked():
                    self.assertEqual([1, 1, 0], ledger.snapshot()['counts'])
                collection = collect_recorded_assessments(
                    company_id='marriott_international', ledger=ledger)
                self.assertEqual(1, len(collection['completed']))
                self.assertEqual(len(prepared)-1,
                                 len(collection['missing_request_ids']))
                self.assertEqual('INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE',
                                 collection['proposed_branch'])
                self.assertFalse(collection['native_result_or_run_created'])
                (path/'semantic-request.json').write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError,
                        'NATIVE_SAVED_REQUEST_OR_SOURCE_CHANGED'):
                    replay_native_response(prepared=selected, path=path)

    def test_unresolved_recorded_group_is_retained_without_company_credit(self):
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')):
            selected = next(row for row in prepare_d03_replay_only_requests(
                company_id='marriott_international') if
                strict_json_loads(text=row.request_bytes.decode())[
                    'required_candidate_assessments'])
            request = strict_json_loads(text=selected.request_bytes.decode())
            with tempfile.TemporaryDirectory(prefix='d03-native-rejected-') as temporary:
                ledger = recorded_ledger(root=Path(temporary) / 'ledger')
                with self.assertRaisesRegex(ValueError,
                        'D03_NATIVE_RECORDED_LEDGER_REQUIRED'):
                    execute_d03_recorded_assessment(
                        prepared=selected, ledger=object(),
                        recorded_wire=_wire(_response(request)))
                with patch.object(ledger, 'root', Path(selected.requirement[
                        'policy']['budget_root'])):
                    with self.assertRaisesRegex(ValueError,
                            'D03_NATIVE_RECORDED_LEDGER_REQUIRED'):
                        execute_d03_recorded_assessment(
                            prepared=selected, ledger=ledger,
                            recorded_wire=_wire(_response(request)))
                    with self.assertRaisesRegex(ValueError,
                            'D03_NATIVE_RECORDED_LEDGER_REQUIRED'):
                        collect_recorded_assessments(
                            company_id='marriott_international',
                            ledger=ledger)
                with self.assertRaisesRegex(ValueError,
                        'CONTINUOUS_REPLAY_OBJECT_CANNOT_EXECUTE'):
                    execute_feasibility(prepared=selected, ledger=ledger,
                        recorded_wire=_wire(_response(request)))
                with ledger.locked():
                    self.assertEqual([0, 0, 0], ledger.snapshot()['counts'])
                path, outcome = execute_d03_recorded_assessment(
                    prepared=selected, ledger=ledger,
                    recorded_wire=_wire(_response(request, unresolved=True)))
                self.assertEqual('SUCCEEDED', outcome['terminal']['status'])
                self.assertTrue(outcome['native_candidate_evidence_created'])
                self.assertFalse(outcome['native_result_created'])
                replay = replay_native_response(prepared=selected, path=path)
                accepted = replay['success']['acceptance_receipt']
                self.assertTrue(accepted['candidate_record'][
                    'unresolved_competing_claims'])
                self.assertIn('D03_UNRESOLVED_RETAINED_FOR_COMPANY_REVIEW',
                    [row['check'] for row in accepted['evidence_record']['checks']])
                with ledger.locked():
                    self.assertEqual([1, 1, 0], ledger.snapshot()['counts'])
                collection = collect_recorded_assessments(
                    company_id='marriott_international', ledger=ledger)
                self.assertEqual(1, len(collection['completed']))
                self.assertEqual([], collection['failed_requests'])
                self.assertEqual([request['request_id']],
                                 collection['unresolved_request_ids'])
                self.assertEqual('INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE',
                                 collection['proposed_branch'])
                self.assertFalse(collection['native_result_or_run_created'])
            with tempfile.TemporaryDirectory(prefix='d03-native-malformed-') as temporary:
                invalid = recorded_ledger(root=Path(temporary) / 'ledger')
                answer = _response(request)
                answer['request_id'] = 'changed-request'
                path, outcome = execute_d03_recorded_assessment(
                    prepared=selected, ledger=invalid,
                    recorded_wire=_wire(answer))
                self.assertEqual('FAILED_TERMINAL', outcome['terminal']['status'])
                self.assertFalse(outcome['native_candidate_evidence_created'])
                with self.assertRaisesRegex(ValueError,
                        'NATIVE_SUCCESSFUL_ORIGINAL_TERMINAL_REQUIRED'):
                    replay_native_response(prepared=selected, path=path)

    def test_anchor_candidate_changes_business_digest(self):
        request = {
            'record_type': 'D03_INTERPRETATION_REQUEST', 'metric_id': 'D03',
            'system_prompt': 'Review source candidates.',
            'target_cik': '0000000001', 'target_period': {'fiscal_year': 2025},
            'fiscal_label_context': {'selected_fiscal_year': 2025},
            'document_context': {'filing': {'accessionNumber': 'accession'}},
            'units': [], 'response_protocol': {}, 'category_definitions': {},
            'required_candidate_assessments': [],
            'source_fact_candidates': [{'candidate_id': 'candidate-a'}],
            'source_fact_review_contract': {'version': 'D03_SOURCE_ANCHOR_REVIEW_V1',
                                            'original_request_id': 'original-a'},
        }
        changed = deepcopy(request)
        changed['source_fact_candidates'][0]['candidate_id'] = 'candidate-b'
        policy = SimpleNamespace(model='deepseek-flash')
        self.assertNotEqual(request_digest(request, policy),
                            request_digest(changed, policy))


class D03NativeAnchorMaterialTest(unittest.TestCase):
    def test_saved_jpm_anchor_reaches_recorded_native_without_old_fact_credit(self):
        started = time.perf_counter()
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')):
            with tempfile.TemporaryDirectory(prefix='d03-anchor-recorded-') as temporary:
                ledger = recorded_ledger(root=Path(temporary) / 'ledger')
                requirement = load_requirement_snapshot(
                    snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
                # One complete company update may share only the current
                # construction scope. The following replay starts a new one.
                with request_construction_session(requirement):
                    selected = next(row for row in prepare_d03_replay_only_requests(
                        company_id='jpmorgan_chase') if
                        'source_fact_review_contract' in strict_json_loads(
                            text=row.request_bytes.decode()))
                    prepared_at = time.perf_counter()
                    request = strict_json_loads(text=selected.request_bytes.decode())
                    anchors = request['source_fact_candidates']
                    self.assertEqual(1, len(anchors))
                    anchor = anchors[0]
                    response = {'request_id': request['request_id'], 'units': [],
                        'candidate_reviews': [{'candidate_id': anchor['candidate_id'],
                            'unit_id': anchor['unit_id'], 'finding_indices': [0]}]}
                    for unit in request['units']:
                        required = sorted({row['source_index'] for row in
                            request['required_candidate_assessments']
                            if row['unit_id'] == unit['unit_id']})
                        finding = ({'kind': 'CURRENT_REGULATORY_ACTION',
                            'subject': 'TARGET_REGISTRANT', 'event_dates': [],
                            'reported_status': 'ONGOING_AS_REPORTED',
                            'evidence': [{'kind': 'VISIBLE_BLOCK',
                                          'source_index': anchor['block_index']}],
                            'reason': 'Recorded protocol path only; native Review still required.'}
                            if unit['unit_id'] == anchor['unit_id'] else None)
                        response['units'].append({'unit_id': unit['unit_id'],
                            'reviewed': True, 'findings': [finding] if finding else [],
                            'context_only_source_indices': [index for index in required
                                if finding is None or index != anchor['block_index']],
                            'unresolved': []})
                    path, outcome = execute_d03_recorded_assessment(
                        prepared=selected, ledger=ledger,
                        recorded_wire=_wire(response))
                    executed_at = time.perf_counter()
                self.assertEqual('SUCCEEDED', outcome['terminal']['status'])
                self.assertTrue(outcome['native_candidate_evidence_created'])
                self.assertFalse(outcome['native_result_created'])
                self.assertFalse(outcome['response_check'][
                    'source_fact_current_status_proven_by_program'])
                replay = replay_native_response(prepared=selected, path=path)
                replayed_at = time.perf_counter()
                self.assertEqual('D03_REQUEST_SOURCE_ASSESSMENT_V1',
                    replay['success']['acceptance_receipt'][
                        'validator_semantic_version'])
                self.assertEqual(33, len(request['required_candidate_assessments']))
                with ledger.locked():
                    self.assertEqual([1, 1, 0], ledger.snapshot()['counts'])
            print(json.dumps({'factory_seconds': round(prepared_at-started, 3),
                'recorded_execute_seconds': round(executed_at-prepared_at, 3),
                'independent_replay_seconds': round(replayed_at-executed_at, 3)}),
                flush=True)


class D03NativeCollectionMaterialTest(unittest.TestCase):
    def test_complete_recorded_marriott_retains_uncertainty_and_requires_review(self):
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')):
            with tempfile.TemporaryDirectory(prefix='d03-complete-native-') as temporary:
                ledger = recorded_ledger(root=Path(temporary)/'ledger')
                requirement = load_requirement_snapshot(
                    snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
                with request_construction_session(requirement):
                    prepared = prepare_d03_replay_only_requests(
                        company_id='marriott_international')
                    self.assertEqual(5, len(prepared))
                    for group_index, selected in enumerate(prepared):
                        request = strict_json_loads(
                            text=selected.request_bytes.decode())
                        response = _response(request)
                        if group_index == 2:
                            response['units'][0]['unresolved'] = [
                                'Synthetic recorded ambiguity; no current conclusion.']
                        if group_index == 1:
                            reference = request['required_candidate_assessments'][0]
                            unit = next(row for row in response['units']
                                if row['unit_id'] == reference['unit_id'])
                            unit['context_only_source_indices'].remove(
                                reference['source_index'])
                            unit['findings'] = [{
                                'kind': 'UNRESOLVED',
                                'subject': 'UNRESOLVED',
                                'event_dates': [],
                                'reported_status': 'UNRESOLVED',
                                'evidence': [{'kind': reference['kind'],
                                    'source_index': reference['source_index']}],
                                'reason': 'Synthetic target identity is undecided.'}]
                        if group_index == 0:
                            # Deliberately model-shaped, not a certified
                            # reading of this source. A current proposal must
                            # still stop before company Result creation.
                            reference = request['required_candidate_assessments'][0]
                            unit = next(row for row in response['units']
                                if row['unit_id'] == reference['unit_id'])
                            unit['context_only_source_indices'].remove(
                                reference['source_index'])
                            unit['findings'] = [{
                                'kind': 'CURRENT_REGULATORY_ACTION',
                                'subject': 'TARGET_REGISTRANT',
                                'event_dates': [],
                                'reported_status': 'ONGOING_AS_REPORTED',
                                'evidence': [{'kind': reference['kind'],
                                    'source_index': reference['source_index']}],
                                'reason': 'Synthetic recorded proposal; native Review required.'}]
                        _, outcome = execute_d03_recorded_assessment(
                            prepared=selected, ledger=ledger,
                            recorded_wire=_wire(response))
                        self.assertEqual('SUCCEEDED',
                                         outcome['terminal']['status'],
                                         msg={'group_index': group_index,
                                              'terminal': outcome['terminal']})
                collection = collect_recorded_assessments(
                    company_id='marriott_international', ledger=ledger)
                self.assertEqual(5, len(collection['completed']))
                self.assertEqual([], collection['missing_request_ids'])
                self.assertEqual([], collection['failed_requests'])
                self.assertEqual([strict_json_loads(text=row.request_bytes.decode())[
                    'request_id'] for row in prepared[1:3]],
                    collection['unresolved_request_ids'])
                self.assertEqual(1,
                                 len(collection['proposed_current_findings']))
                self.assertEqual('UNRESOLVED_REQUIRES_NATIVE_REVIEW',
                                 collection['proposed_branch'])
                self.assertFalse(collection['semantic_correctness_verified'])
                self.assertFalse(collection['native_review_complete'])
                self.assertFalse(collection['native_result_or_run_created'])
                with ledger.locked():
                    self.assertEqual([5, 5, 0], ledger.snapshot()['counts'])


if __name__ == '__main__':
    unittest.main()
