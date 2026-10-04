from copy import deepcopy
import unittest
from unittest.mock import patch

import task_contract as contract
from tests.vnext.test_d03_context_requests import D03ContextRequestsTest
from vnext.canonical import content_hash, sha256_bytes
from vnext.native_unit_index import evidence_json_bytes


class BoundedTaskPrototypeTest(unittest.TestCase):
    def setUp(self):
        f = D03ContextRequestsTest(); f.setUp(); self.f = f
        supplement = deepcopy(f.supp['payload'])
        for root in supplement['objects']:
            for element in [root, *root['nested_objects']]:
                element['namespace_environment_id'] = 'env'
        raw_other = '<other id="unrequested">other context</other>'
        supplement['objects'].append({'attributes': {'id': 'unrequested'}, 'raw_xml': raw_other,
            'raw_xml_sha256': sha256_bytes(content=raw_other.encode()), 'nested_objects': [],
            'namespaces': {'ix': 'inline-uri'}, 'namespace_environment_id': 'env'})
        f.supp = f.unit('NATIVE_SUPPLEMENTS', supplement)
        f.source = f.seal([f.visible, f.fact, f.supp])
        self.source = {**f.source, 'prepared_annual_input': {'table_input': {'target_period': '2025'}}}
        self.source['documents'] = [{'document_id': 'doc:one', 'filing': {'form': '10-K', 'reportDate': '2025-12-31'}}]
        self.source['semantic_source_id'] = content_hash(value={k:v for k,v in self.source.items() if k!='semantic_source_id'})
        self.digest = sha256_bytes(content=evidence_json_bytes(self.source))
        self.task = contract.prepare_scan(self.source, self.digest, [f.fact['unit_id']])
        self.response = {'reviewed_unit_ids': [f.fact['unit_id']], 'findings': [{
            'kind': 'REPORTED_REGULATORY_PROCESS', 'subject': 'synthetic registrant', 'event_dates': [],
            'reported_context_times': [], 'status': 'not stated', 'description': 'Synthetic proposal, not source truth.',
            'evidence': [{'unit_id': f.fact['unit_id'], 'kind': 'NATIVE_FACT', 'source_index': 9}]}],
            'scope_current_involvement': 'UNRESOLVED', 'unresolved': ['Continuation is needed'],
            'scan_complete': False, 'context_requests': [f.xml()]}

    def raw(self, response=None):
        raw = evidence_json_bytes(self.response if response is None else response)
        return raw, sha256_bytes(content=raw)

    def test_nonempty_scan_exact_context_and_once_followup_are_structural_only(self):
        raw, digest = self.raw(); parsed = contract.parse_scan(self.source, self.digest, self.task, raw, digest)
        self.assertEqual(parsed['original_response'], self.response)
        self.assertFalse(parsed['semantic_acceptance'])
        follow = contract.prepare_followup(self.source, self.digest, self.task, raw, digest)
        self.assertEqual(follow['status'], 'OFFLINE_FOLLOWUP_FITS')
        self.assertEqual(follow['payload']['original_scan_response_utf8'].encode(), raw)
        done = {**self.response, 'context_requests': [], 'scan_complete': True, 'unresolved': []}
        done = deepcopy(done)
        done['findings'][0]['evidence'].append({'unit_id': self.f.supp['unit_id'],
            'kind': 'NATIVE_SUPPLEMENT', 'source_index': 0})
        answer, answer_digest = self.raw(done)
        result = contract.parse_followup(self.source, self.digest, self.task, raw, digest, answer, answer_digest,
            actual_request_body=follow['request_body'], expected_request_sha256=follow['proposed_request_sha256'])
        self.assertEqual(result['status'], 'FOLLOWUP_STRUCTURE_READ')
        self.assertFalse(result['company_result_created'])
        self.assertFalse(result['next_execution_prepared'])

    def test_complete_plan_keeps_every_original_owner_once_and_fixed_design_ceiling(self):
        plan = contract.scan_plan(self.source, self.digest, max_owner_units=1)
        self.assertEqual([u for t in plan['tasks'] for u in t['payload']['responsibility_unit_ids']],
                         self.source['required_unit_ids'])
        self.assertEqual(plan['total_request_ceiling'], 6)
        self.assertFalse(plan['runtime_opportunity_guard_connected'])
        self.assertFalse(plan['completion_guaranteed'])

    def test_missing_context_and_output_work_never_become_empty_success(self):
        response = deepcopy(self.response); response['context_requests'][0]['target']['element_id'] = 'missing'
        raw, digest = self.raw(response)
        follow = contract.prepare_followup(self.source, self.digest, self.task, raw, digest)
        self.assertEqual(follow['status'], 'STOP_UNRESOLVED_CONTEXT')
        self.assertIsNone(follow['request_body'])
        response['context_requests'] = []; response['unresolved'] = []
        raw, digest = self.raw(response)
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE_REASON_MISSING'):
            contract.parse_scan(self.source, self.digest, self.task, raw, digest)

    def test_foreign_anchor_wrong_evidence_and_mutable_task_fields_refused(self):
        changed = deepcopy(self.task); changed['payload']['company_id'] = 'other'
        raw, digest = self.raw()
        with self.assertRaisesRegex(ValueError, 'INPUT_CHANGED'):
            contract.parse_scan(self.source, self.digest, changed, raw, digest)
        response = deepcopy(self.response); response['findings'][0]['evidence'][0]['source_index'] = True
        raw, digest = self.raw(response)
        with self.assertRaisesRegex(ValueError, 'REFERENCE_KIND_OR_INDEX'):
            contract.parse_scan(self.source, self.digest, self.task, raw, digest)
        response = deepcopy(self.response); response['context_requests'][0]['anchor']['unit_id'] = self.f.visible['unit_id']
        raw, digest = self.raw(response)
        with self.assertRaisesRegex(ValueError, 'ANCHOR_NOT_OWNED'):
            contract.parse_scan(self.source, self.digest, self.task, raw, digest)

    def test_new_response_digest_and_whole_4096_budget_checked_before_projection(self):
        raw, digest = self.raw()
        with self.assertRaisesRegex(ValueError, 'RESPONSE_CHANGED'):
            contract.parse_scan(self.source, self.digest, self.task, raw, '0'*64)
        long = {**self.response, 'unresolved': ['word ' * 5000]}; raw, digest = self.raw(long)
        with self.assertRaisesRegex(ValueError, 'OUTPUT_LIMIT'):
            contract.parse_scan(self.source, self.digest, self.task, raw, digest)

    def test_second_context_need_is_retained_without_another_request(self):
        raw, digest = self.raw()
        follow = contract.prepare_followup(self.source, self.digest, self.task, raw, digest)
        result = contract.parse_followup(self.source, self.digest, self.task, raw, digest, raw, digest,
            actual_request_body=follow['request_body'], expected_request_sha256=follow['proposed_request_sha256'])
        self.assertEqual(result['status'], 'STOP_FOLLOWUP_CEILING')
        self.assertEqual(result['original_response'], self.response)
        self.assertFalse(result['next_execution_prepared'])

    def test_unsupplied_item_in_added_context_unit_is_not_accepted(self):
        raw, digest = self.raw(); follow = {**deepcopy(self.response), 'scan_complete': True,
                                           'context_requests': [], 'unresolved': []}
        # The located continuation supplies supplement index0 only, not arbitrary indices.
        follow['findings'][0]['evidence'].append({'unit_id': self.f.supp['unit_id'],
                                               'kind': 'NATIVE_SUPPLEMENT', 'source_index': 1})
        answer, answer_digest = self.raw(follow)
        request = contract.prepare_followup(self.source, self.digest, self.task, raw, digest)
        with self.assertRaisesRegex(ValueError, 'UNSUPPLIED_CONTEXT_REFERENCE'):
            contract.parse_followup(self.source, self.digest, self.task, raw, digest, answer, answer_digest,
                actual_request_body=request['request_body'], expected_request_sha256=request['proposed_request_sha256'])

    def test_followup_actual_request_cannot_be_replaced_by_a_computed_identity(self):
        raw, digest = self.raw(); follow = contract.prepare_followup(self.source, self.digest, self.task, raw, digest)
        with self.assertRaisesRegex(ValueError, 'ACTUAL_FOLLOWUP_REQUEST_CHANGED'):
            contract.parse_followup(self.source, self.digest, self.task, raw, digest, raw, digest,
                actual_request_body=self.task['request_body'], expected_request_sha256=self.task['request_sha256'])

    def test_over_limit_followup_retains_original_need_instead_of_trimming(self):
        raw, digest = self.raw(); original_measure = contract.measure_request
        def measured(body, **kwargs):
            result = original_measure(body, **kwargs)
            payload = __import__('json').loads(__import__('json').loads(body)['messages'][1]['content'])
            if payload['stage'] == 'FOLLOWUP':
                result['fits'] = False
            return result
        with patch.object(contract, 'measure_request', side_effect=measured):
            result = contract.prepare_followup(self.source, self.digest, self.task, raw, digest)
        self.assertEqual(result['status'], 'STOP_UNRESOLVED_RESOURCE')
        self.assertIsNone(result['request_body'])
        self.assertEqual(result['parsed']['original_response'], self.response)

    def test_literal_forward_continuation_is_restored_without_model_guessing_next_id(self):
        payload = deepcopy(self.f.supp['payload'])
        root = payload['objects'][0]
        root['raw_xml'] = root['raw_xml'].replace('id="continued"', 'id="continued" continuedat="unrequested"')
        root['raw_xml_sha256'] = sha256_bytes(content=root['raw_xml'].encode())
        nested = root['nested_objects'][0]
        nested['attributes']['continuedat'] = 'unrequested'
        nested['relative_end_character'] += len(' continuedat="unrequested"')
        raw = root['raw_xml'][nested['relative_start_character']:nested['relative_end_character']]
        nested['raw_xml_sha256'] = sha256_bytes(content=raw.encode())
        unit = self.f.unit('NATIVE_SUPPLEMENTS', payload)
        source = {**self.source, 'units': [self.f.visible, self.f.fact, unit],
                  'required_unit_ids': [self.f.visible['unit_id'], self.f.fact['unit_id'], unit['unit_id']]}
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'})
        digest = sha256_bytes(content=evidence_json_bytes(source))
        first = contract.prepare_scan(source, digest, [self.f.fact['unit_id']])
        raw, response_digest = self.raw()
        parsed = contract.parse_scan(source, digest, first, raw, response_digest)
        self.assertEqual(len(parsed['located_context']['rows']), 2)
        self.assertEqual(parsed['original_response']['context_requests'], [self.f.xml()])
        self.assertEqual(parsed['literal_continuation_trace'][0]['to_request']['target']['element_id'], 'unrequested')
        self.assertEqual(parsed['unresolved_continuations'], [])

    def test_cycles_and_eight_location_ceiling_remain_unresolved(self):
        def packet(next_id):
            return {'rows': [{'status': 'LOCATED', 'request': self.f.xml(), 'context': [{
                'original_element': {'attributes': {'continuedat': next_id}}}]}]}
        with patch.object(contract, 'resolve_context_requests', return_value=packet('continued')):
            _, _, pending = contract._context(self.source, self.digest, [self.f.fact['unit_id']], [self.f.xml()])
        self.assertEqual(pending[0]['reason'], 'D03_TASK_CONTINUATION_CYCLE')
        requests = [self.f.xml()]+[self.f.xml('id'+str(i)) for i in range(7)]
        with patch.object(contract, 'resolve_context_requests', return_value=packet('ninth')):
            _, _, pending = contract._context(self.source, self.digest, [self.f.fact['unit_id']], requests)
        self.assertEqual(pending[0]['reason'], 'D03_TASK_CONTINUATION_LOCATION_CEILING')

    def test_prompt_named_dictionary_layout_restores_original_index_order_and_fact_columns(self):
        prompt = (contract.HERE/'scan-prompt.txt').read_text()
        self.assertIn('payload.row_layout.source_order', prompt)
        self.assertIn('DICTIONARY', prompt)
        self.assertNotIn('row_layouts', prompt)
        packed = self.task['payload']['source_units']
        for unit in packed:
            payload = unit['payload']; layout = payload['row_layout']
            name = 'blocks' if unit['kind'] == 'VISIBLE_TEXT' else 'facts'
            self.assertIsInstance(payload[name], dict)
            decoded = [dict(zip(layout['columns'], payload[name][str(i)])) for i in layout['source_order']]
            if 'fact_columns' in layout:
                for row in decoded:
                    row['fact'] = dict(zip(layout['fact_columns'], row['fact']))
            self.assertEqual(decoded, self.task['provided_units'][unit['unit_id']]['payload'][name])
        payload = {'blocks': {'10': ['ten', 10], '2': ['two', 2]},
                   'row_layout': {'source_order': [2, 10], 'columns': ['text', 'block_index']}}
        decoded = [dict(zip(payload['row_layout']['columns'], payload['blocks'][str(i)]))
                   for i in payload['row_layout']['source_order']]
        self.assertEqual([b['block_index'] for b in decoded], [2, 10])


if __name__ == '__main__':
    unittest.main()
