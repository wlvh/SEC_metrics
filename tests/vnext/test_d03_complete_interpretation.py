"""D03 complete-response checking remains a proposal without Result credit."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import d03_complete_interpretation as interpretation
from vnext.d03_native_preparation import prepare_native_input
from vnext.normal_source_authority import ROOT


class D03CompleteInterpretationTest(unittest.TestCase):
    def test_current_saved_marriott_requires_every_response_and_preserves_uncertainty(self):
        self.enterContext(original_sources_only())
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',
                   side_effect=AssertionError('HTTP_FORBIDDEN')):
            prepared = prepare_native_input(company_id='marriott_international')
            self.assertTrue(prepared['groups'])
            self.assertFalse(any(row['source_anchor_successor']
                                 for row in prepared['groups']))
            responses = {}
            for group in prepared['groups']:
                request = group['effective_request']
                units = []
                for unit in request['units']:
                    required = sorted({row['source_index'] for row in
                        request['required_candidate_assessments']
                        if row['unit_id'] == unit['unit_id']})
                    units.append({'unit_id': unit['unit_id'], 'reviewed': True,
                        'findings': [], 'context_only_source_indices': required,
                        'unresolved': ['Recorded response, meaning not verified.']})
                responses[request['request_id']] = (json.dumps({
                    'request_id': request['request_id'], 'units': units},
                    ensure_ascii=False, indent=2) + '\n').encode()
            result = interpretation.validate_complete_interpretation(
                prepared_input=prepared, response_bytes_by_request=responses)
            self.assertEqual('UNRESOLVED_REQUIRES_REVIEW',
                             result['proposed_branch'])
            self.assertEqual(len(prepared['groups']),
                             len(result['group_rows']))
            self.assertEqual(list(range(len(prepared['groups']))),
                             result['unresolved_group_indices'])
            self.assertFalse(result['provider_execution_identity_verified'])
            self.assertFalse(result['native_candidate_or_evidence_created'])
            self.assertFalse(result['native_result_or_run_created'])
            self.assertFalse(result['production_authorized'])
            missing = dict(responses)
            missing.pop(prepared['groups'][-1]['effective_request_id'])
            with self.assertRaisesRegex(ValueError,
                    'D03_COMPLETE_INTERPRETATION_RESPONSE_SET_CHANGED'):
                interpretation.validate_complete_interpretation(
                    prepared_input=prepared, response_bytes_by_request=missing)
            altered = deepcopy(prepared)
            altered['groups'][0]['effective_request']['system_prompt'] += ' Changed.'
            with self.assertRaisesRegex(ValueError,
                    'D03_COMPLETE_INTERPRETATION_PREPARATION_CHANGED'):
                interpretation.validate_complete_interpretation(
                    prepared_input=altered, response_bytes_by_request=responses)

    def test_complete_empty_proposal_never_becomes_negative_result(self):
        source = {'semantic_source_id': 'sha256:' + 'a'*64}
        request = {'request_id': 'request-0', 'source_statement_facts': []}
        prepared = {'company_id': 'marriott_international',
                    'source_id': source['semantic_source_id'], 'input_id': 'input-0',
                    'source': source, 'groups': [{'group_index': 0,
                        'original_request_id': request['request_id'],
                        'effective_request_id': request['request_id'],
                        'unit_ids': ['unit-0'], 'source_anchor_successor': False,
                        'effective_request': request}]}
        with patch.object(interpretation, 'prepare_native_input',
                          return_value=prepared), patch.object(
                          interpretation, 'requests_from_source',
                          return_value=[request]), patch.object(
                          interpretation, 'validate_response',
                          return_value={'findings': [], 'unresolved': []}) as checked:
            result = interpretation.validate_complete_interpretation(
                prepared_input=prepared,
                response_bytes_by_request={'request-0': b'{}'})
            current = {'kind': 'CURRENT_REGULATORY_ACTION',
                'subject': 'TARGET_REGISTRANT',
                'reported_status': 'ONGOING_AS_REPORTED',
                'timing': 'CURRENT_REPORT'}
            checked.return_value = {'findings': [current], 'unresolved': []}
            positive = interpretation.validate_complete_interpretation(
                prepared_input=prepared,
                response_bytes_by_request={'request-0': b'{}'})
            context = {'kind': 'OTHER_MEANING', 'subject': 'UNRESOLVED',
                'timing': 'UNRESOLVED',
                'reported_status': 'NOT_AN_ACTION_STATEMENT',
                'unit_id': 'unit-0',
                'evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': 7}]}
            checked.return_value = {'findings': [context], 'unresolved': [],
                'provider_response': {'units': [{'unit_id': 'unit-0',
                    'context_only_source_indices': [7]}]}}
            context_only = interpretation.validate_complete_interpretation(
                prepared_input=prepared,
                response_bytes_by_request={'request-0': b'{}'})
            checked.return_value = {'findings': [context], 'unresolved': [],
                'provider_response': {'units': [{'unit_id': 'unit-0',
                    'context_only_source_indices': []}]}}
            explicit_other = interpretation.validate_complete_interpretation(
                prepared_input=prepared,
                response_bytes_by_request={'request-0': b'{}'})
            checked.return_value = {'findings': [{**current,
                'subject': 'UNRESOLVED'}], 'unresolved': []}
            unknown_subject = interpretation.validate_complete_interpretation(
                prepared_input=prepared,
                response_bytes_by_request={'request-0': b'{}'})
        self.assertEqual('ABSENCE_RULE_NOT_APPROVED', result['proposed_branch'])
        self.assertEqual([], result['proposed_current_findings'])
        self.assertFalse(result['native_result_or_run_created'])
        self.assertEqual('CURRENT_DISCLOSURE_REQUIRES_NATIVE_REVIEW',
                         positive['proposed_branch'])
        self.assertEqual([current], positive['proposed_current_findings'])
        self.assertFalse(positive['native_result_or_run_created'])
        self.assertEqual('ABSENCE_RULE_NOT_APPROVED', context_only['proposed_branch'])
        self.assertEqual([], context_only['unresolved_group_indices'])
        self.assertFalse(context_only['native_result_or_run_created'])
        self.assertEqual('UNRESOLVED_REQUIRES_REVIEW',
                         explicit_other['proposed_branch'])
        self.assertEqual('UNRESOLVED_REQUIRES_REVIEW',
                         unknown_subject['proposed_branch'])
        self.assertEqual([0], unknown_subject['unresolved_group_indices'])
        with self.assertRaisesRegex(ValueError,
                'D03_COMPLETE_INTERPRETATION_INPUT_INVALID'):
            interpretation.validate_complete_interpretation(
                prepared_input=prepared, response_bytes_by_request={},
                repo_root=ROOT.parent)

    def test_recorded_bridge_maps_original_to_effective_ids_without_credit(self):
        packet_id = 'sha256:' + 'a'*64
        prepared = {'company_id': 'marriott_international',
            'source_id': 'sha256:' + 'b'*64, 'input_id': 'sha256:' + 'c'*64,
            'groups': [
                {'group_index': 0, 'source_anchor_successor': False,
                 'original_request_id': 'old-0',
                 'effective_request_id': 'old-0'},
                {'group_index': 1, 'source_anchor_successor': True,
                 'original_request_id': 'old-1',
                 'effective_request_id': 'successor-1'}]}
        packet = {'packet_id': packet_id, 'request_count': 2,
            'raw_response_bytes': {'old-0': b'first', 'old-1': b'second'},
            'calls': [0, 0, 0], 'native_result_created': False}
        proposal = {'proposal_id': 'sha256:' + 'd'*64,
            'source_id': prepared['source_id'],
            'input_id': prepared['input_id'],
            'unresolved_group_indices': [1],
            'proposed_branch': 'UNRESOLVED_REQUIRES_REVIEW',
            'provider_execution_identity_verified': False,
            'native_candidate_or_evidence_created': False,
            'native_result_or_run_created': False}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root/'packet.json').write_text(json.dumps({
                'packet_id': packet_id,
                'company_id': 'marriott_international',
                'source_id': prepared['source_id']}))
            with patch('vnext.d03_recorded_response_set.replay_offline_set',
                       return_value=packet) as replay, patch.object(
                       interpretation, 'prepare_native_input',
                       return_value=prepared), patch.object(
                       interpretation, 'validate_complete_interpretation',
                       return_value=proposal) as validate:
                result = interpretation.replay_recorded_complete_interpretation(
                    packet_root=root, expected_packet_id=packet_id,
                    company_id='marriott_international')
                self.assertEqual({'old-0': b'first', 'successor-1': b'second'},
                    validate.call_args.kwargs['response_bytes_by_request'])
                self.assertEqual(packet_id, replay.call_args.kwargs[
                    'expected_packet_id'])
                self.assertEqual(2, result['group_count'])
                self.assertEqual([('old-0', 'old-0'),
                                  ('old-1', 'successor-1')], [
                    (row['original_request_id'], row['effective_request_id'])
                    for row in result['request_mapping']])
                self.assertEqual([1], result['unresolved_group_indices'])
                self.assertFalse(result['provider_execution_identity_verified'])
                self.assertFalse(result['native_result_or_run_created'])
                self.assertEqual([0, 0, 0], result['calls'])
                with self.assertRaisesRegex(ValueError,
                        'D03_RECORDED_INTERPRETATION_PACKET_OR_REQUEST_CHANGED'):
                    replay.return_value = {**packet,
                        'raw_response_bytes': {'old-0': b'first'}}
                    interpretation.replay_recorded_complete_interpretation(
                        packet_root=root, expected_packet_id=packet_id,
                        company_id='marriott_international')
                replay.return_value = packet
                with self.assertRaisesRegex(ValueError,
                        'D03_RECORDED_INTERPRETATION_CREDIT_CHANGED'):
                    validate.return_value = {**proposal,
                        'native_result_or_run_created': True}
                    interpretation.replay_recorded_complete_interpretation(
                        packet_root=root, expected_packet_id=packet_id,
                        company_id='marriott_international')

    def test_saved_marriott_context_only_stays_unapproved_without_fake_unresolved(self):
        self.enterContext(original_sources_only())
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',
                   side_effect=AssertionError('HTTP_FORBIDDEN')):
            prepared = prepare_native_input(company_id='marriott_international')
            self.assertTrue(prepared['groups'])
            self.assertFalse(any(row['source_anchor_successor']
                                 for row in prepared['groups']))
            responses = {}
            for group in prepared['groups']:
                request = group['effective_request']
                units = []
                for unit in request['units']:
                    required = sorted({row['source_index'] for row in
                        request['required_candidate_assessments']
                        if row['unit_id'] == unit['unit_id']})
                    units.append({'unit_id': unit['unit_id'], 'reviewed': True,
                        'findings': [], 'context_only_source_indices': required,
                        'unresolved': []})
                responses[request['request_id']] = json.dumps({
                    'request_id': request['request_id'], 'units': units},
                    ensure_ascii=False).encode()
            result = interpretation.validate_complete_interpretation(
                prepared_input=prepared, response_bytes_by_request=responses)
            self.assertEqual([], result['unresolved_group_indices'])
            self.assertEqual('ABSENCE_RULE_NOT_APPROVED', result['proposed_branch'])
            self.assertFalse(result['provider_execution_identity_verified'])
            self.assertFalse(result['native_result_or_run_created'])
            self.assertFalse(result['production_authorized'])
            first = prepared['groups'][0]['effective_request_id']
            altered = json.loads(responses[first])
            altered['units'][0]['unresolved'] = ['Actor and status require review.']
            with_uncertainty = {**responses, first: json.dumps(altered).encode()}
            unresolved = interpretation.validate_complete_interpretation(
                prepared_input=prepared,
                response_bytes_by_request=with_uncertainty)
            self.assertEqual('UNRESOLVED_REQUIRES_REVIEW',
                             unresolved['proposed_branch'])
            self.assertIn(0, unresolved['unresolved_group_indices'])


if __name__ == '__main__':
    unittest.main()
