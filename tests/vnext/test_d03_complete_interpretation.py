"""D03 complete-response checking remains a proposal without Result credit."""
from copy import deepcopy
import json
import socket
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
        self.assertEqual('ABSENCE_RULE_NOT_APPROVED', result['proposed_branch'])
        self.assertEqual([], result['proposed_current_findings'])
        self.assertFalse(result['native_result_or_run_created'])
        self.assertEqual('CURRENT_DISCLOSURE_REQUIRES_NATIVE_REVIEW',
                         positive['proposed_branch'])
        self.assertEqual([current], positive['proposed_current_findings'])
        self.assertFalse(positive['native_result_or_run_created'])
        with self.assertRaisesRegex(ValueError,
                'D03_COMPLETE_INTERPRETATION_INPUT_INVALID'):
            interpretation.validate_complete_interpretation(
                prepared_input=prepared, response_bytes_by_request={},
                repo_root=ROOT.parent)


if __name__ == '__main__':
    unittest.main()
