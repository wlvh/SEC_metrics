"""Two saved B13 stages replay independently with networking disabled."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import socket
import tempfile
import unittest
from unittest.mock import patch

from vnext.canonical import canonical_json_bytes, strict_json_loads
from vnext.capacity_reference_contract import upgrade_request
from vnext.capacity_two_stage import interpretation_request, scan_request, validate_scan


class CapacityTwoStageMaterialTest(unittest.TestCase):
    def test_scoped_interpretation_records_both_stages_without_live_permission(self):
        from vnext.continuous_call_ledger import recorded_ledger
        from vnext.continuous_call_policy import configured_transport_policy
        from vnext.continuous_semantic_calls import (
            _json, _source_json, execute_capacity_interpretation,
            execute_capacity_scan, prepare_requests, request_body)
        from vnext.capacity_two_stage import _assertion_segments, saved_scan_stage
        from vnext.native_assessment_replay import replay_native_response
        from vnext.normal_source_authority import ROOT

        def wire(value):
            return canonical_json_bytes(value={
                'id': 'b13-scoped-recorded', 'model': 'deepseek-flash',
                'choices': [{'message': {'role': 'assistant',
                             'content': json.dumps(value)}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20,
                          'total_tokens': 120}})

        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')):
            prepared = prepare_requests(company_id='enphase_energy', metric_id='B13',
                reference_context=True, program_quantity_roles=True)[1]
            prior = upgrade_request(json.loads(prepared.request_bytes),
                compact=True, role_labels=True, relevance_scope=True)
            policy = configured_transport_policy(requirement=prepared.requirement,
                                                 repo_root=ROOT)
            scan = scan_request(prior)
            scan_prepared = replace(prepared, request_bytes=_source_json(scan),
                provider_request_body_bytes=request_body(scan, policy),
                output_schema_bytes=_json(scan['response_protocol']))
            ledger = recorded_ledger(root=Path(temporary)/'ledger')
            scan_value = {'units_reviewed': list(range(len(prior['units']))),
                          'candidate_refs': ['B2382'], 'unresolved_refs': []}
            scan_path, scan_outcome = execute_capacity_scan(prepared=scan_prepared,
                ledger=ledger, recorded_wire=wire(scan_value))
            self.assertEqual(scan_outcome['terminal']['status'], 'SUCCEEDED')
            draft = interpretation_request(request=prior,
                scan_result=validate_scan(request=prior, scan_request_value=scan,
                    raw_response=canonical_json_bytes(value=scan_value)),
                scan_raw_response=canonical_json_bytes(value=scan_value),
                assertion_scopes=True)
            stage = saved_scan_stage(prepared=replace(prepared,
                request_bytes=_source_json(draft)), scan_path=scan_path)
            request = interpretation_request(request=prior,
                scan_result=stage['scan_result'],
                scan_raw_response=stage['scan_raw_response'],
                scan_execution_proof=stage['stage_proof'], assertion_scopes=True)
            assessed = replace(prepared, request_bytes=_source_json(request),
                provider_request_body_bytes=request_body(request, policy),
                output_schema_bytes=_json(request['response_protocol']))
            source = strict_json_loads(text=prepared.source_bytes.decode('utf-8'))
            block = next(block for unit in source['units']
                if unit['kind'] == 'VISIBLE_TEXT'
                for block in unit['payload']['blocks']
                if block['block_index'] == 2382)
            span = next((start, end) for start, end in _assertion_segments(block['text'])
                if 'destination of shipments' in block['text'][start:end])
            books = request['response_protocol']['classification_codebooks']
            response = {'units': [{'unit_index': index, 'reviewed': True,
                'unresolved': [], 'calculation_limits': []}
                for index in range(len(prior['units']))],
                'findings': [['sales_or_shipments',
                    books['subject'].index('TARGET_REGISTRANT'),
                    books['timing'].index('CURRENT_REPORT'), ['B2382'],
                    'Shipment destination is sales context, not factory output.',
                    [['B2382', *span]]]]}
            second_path, second = execute_capacity_interpretation(
                prepared=assessed, ledger=ledger, recorded_wire=wire(response))
            self.assertEqual(second['terminal']['status'], 'SUCCEEDED')
            replay = replay_native_response(prepared=assessed, path=second_path)
            self.assertEqual(replay['success']['acceptance_receipt']['candidate_record']
                ['selected']['source_assessment']['request_id'], request['request_id'])
            self.assertEqual((second_path/'semantic-request.json').read_bytes(),
                             assessed.request_bytes)
            from vnext.capacity_two_stage import build_registered_interpretation_acceptance
            from vnext.canonical import strict_json_file
            scan_replay = stage['replay']
            scan_record = {'request_id': scan['request_id'],
                'ordinal': int(scan_path.name),
                'stage_proof': stage['stage_proof'],
                'semantic_request': scan,
                'assistant_output': stage['scan_raw_response'].decode('utf-8'),
                'plan': scan_replay['plan'],
                'acceptance_receipt': scan_replay['success']['acceptance_receipt'],
                'intent': strict_json_file(path=scan_path/'intent.json'),
                'terminal': strict_json_file(path=scan_path/'terminal.json'),
                'wire': strict_json_file(path=scan_path/'wire/journal.json'),
                'source_revalidation': scan_replay['revalidation']}
            portable = build_registered_interpretation_acceptance(
                prepared=assessed, plan=replay['plan'],
                response_body=replay['success']['response_body'],
                stage_record=scan_record)
            self.assertEqual(portable['candidate_record'],
                             replay['success']['acceptance_receipt']['candidate_record'])
            with ledger.locked():
                self.assertEqual(ledger.snapshot()['counts'], [2, 2, 0])

    def test_recorded_scan_and_interpretation_keep_both_execution_identities(self):
        from vnext.continuous_call_ledger import recorded_ledger
        from vnext.continuous_call_policy import configured_transport_policy
        from vnext.continuous_semantic_calls import (
            _json, _source_json, execute_capacity_interpretation,
            execute_capacity_scan, prepare_requests, request_body)
        from vnext.capacity_two_stage import saved_scan_stage
        from vnext.native_assessment_replay import replay_native_response
        from vnext.normal_source_authority import ROOT

        def wire(value):
            return canonical_json_bytes(value={
                'id': 'b13-two-stage-recorded', 'model': 'deepseek-flash',
                'choices': [{'message': {'role': 'assistant',
                             'content': json.dumps(value)}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20,
                          'total_tokens': 120}})

        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')):
            prepared = prepare_requests(company_id='enphase_energy', metric_id='B13',
                reference_context=True, program_quantity_roles=True)[1]
            original = json.loads(prepared.request_bytes)
            prior = upgrade_request(original, compact=True, role_labels=True,
                                    relevance_scope=True)
            sales = prior['units'][1]['payload']['blocks']['2382'][-1]
            self.assertIn('destination of shipments', sales)
            policy = configured_transport_policy(requirement=prepared.requirement,
                                                 repo_root=ROOT)
            scan = scan_request(prior)
            scan_prepared = replace(prepared, request_bytes=_source_json(scan),
                provider_request_body_bytes=request_body(scan, policy),
                output_schema_bytes=_json(scan['response_protocol']))
            ledger = recorded_ledger(root=Path(temporary)/'ledger')
            scan_value = {'units_reviewed': list(range(len(prior['units']))),
                          'candidate_refs': ['B2382'], 'unresolved_refs': []}
            scan_path, scan_outcome = execute_capacity_scan(prepared=scan_prepared,
                ledger=ledger, recorded_wire=wire(scan_value))
            self.assertEqual(scan_outcome['terminal']['status'], 'SUCCEEDED')
            self.assertFalse(scan_outcome['native_result_created'])
            self.assertEqual(scan_outcome['acceptance_scope'],
                             'SCAN_SHAPE_ONLY_NO_B13_METRIC_CREDIT')
            scan_result = validate_scan(request=prior, scan_request_value=scan,
                raw_response=canonical_json_bytes(value=scan_value))
            # Stage two may only use the saved and independently replayed first stage.
            draft = interpretation_request(request=prior, scan_result=scan_result,
                scan_raw_response=canonical_json_bytes(value=scan_value))
            with self.assertRaisesRegex(ValueError, 'SCAN_EXECUTION_PROOF_REQUIRED'):
                from vnext.capacity_native_assessment import build_acceptance
                build_acceptance(prepared=replace(prepared,
                    request_bytes=_source_json(draft)), plan={}, response_body=b'{}')
            saved_scan = saved_scan_stage(prepared=replace(prepared,
                request_bytes=_source_json(draft)), scan_path=scan_path)
            self.assertEqual(saved_scan['scan_result']['response'], scan_result['response'])
            staged = interpretation_request(request=prior,
                scan_result=saved_scan['scan_result'],
                scan_raw_response=saved_scan['scan_raw_response'],
                scan_execution_proof=saved_scan['stage_proof'])
            assessed = replace(prepared, request_bytes=_source_json(staged),
                provider_request_body_bytes=request_body(staged, policy),
                output_schema_bytes=_json(staged['response_protocol']))
            codes = staged['response_protocol']['classification_codebooks']
            response = {'units': [
                {'unit_index': index, 'reviewed': True, 'unresolved': [],
                 'calculation_limits': []} for index in range(len(prior['units']))],
                'findings': [['sales_or_shipments',
                              codes['subject'].index('TARGET_REGISTRANT'),
                              codes['timing'].index('CURRENT_REPORT'), ['B2382'],
                              'Shipment destination is sales context, not factory output.']]}
            second_path, second_outcome = execute_capacity_interpretation(
                prepared=assessed, ledger=ledger, recorded_wire=wire(response))
            self.assertEqual(second_outcome['terminal']['status'], 'SUCCEEDED')
            replay = replay_native_response(prepared=assessed, path=second_path)
            selected = replay['success']['acceptance_receipt']['candidate_record']['selected']
            self.assertEqual(selected['source_assessment']['request_id'], staged['request_id'])
            self.assertEqual(selected['source_assessment']['scan_stage_proof']['scan_ordinal'],
                             int(scan_path.name))
            self.assertEqual((scan_path/'semantic-request.json').read_bytes(),
                             scan_prepared.request_bytes)
            self.assertEqual((second_path/'semantic-request.json').read_bytes(),
                             assessed.request_bytes)
            from vnext.capacity_two_stage import build_registered_interpretation_acceptance
            from vnext.canonical import strict_json_file
            scan_replay = saved_scan['replay']
            scan_record = {'request_id': scan['request_id'],
                'ordinal': int(scan_path.name),
                'stage_proof': saved_scan['stage_proof'],
                'semantic_request': scan,
                'assistant_output': saved_scan['scan_raw_response'].decode('utf-8'),
                'plan': scan_replay['plan'],
                'acceptance_receipt': scan_replay['success']['acceptance_receipt'],
                'intent': strict_json_file(path=scan_path/'intent.json'),
                'terminal': strict_json_file(path=scan_path/'terminal.json'),
                'wire': strict_json_file(path=scan_path/'wire/journal.json'),
                'source_revalidation': scan_replay['revalidation']}
            portable = build_registered_interpretation_acceptance(
                prepared=assessed, plan=replay['plan'],
                response_body=replay['success']['response_body'],
                stage_record=scan_record)
            self.assertEqual(portable['candidate_record'],
                             replay['success']['acceptance_receipt']['candidate_record'])
            changed = deepcopy(scan_record)
            changed['assistant_output'] = changed['assistant_output'].replace('B2382', 'B999999')
            with self.assertRaises(ValueError):
                build_registered_interpretation_acceptance(prepared=assessed,
                    plan=replay['plan'], response_body=replay['success']['response_body'],
                    stage_record=changed)
            with ledger.locked():
                self.assertEqual(ledger.snapshot()['counts'], [2, 2, 0])


if __name__ == '__main__':
    unittest.main()
