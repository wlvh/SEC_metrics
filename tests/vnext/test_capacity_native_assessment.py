"""Actual source/factory/opener and native acceptance, with networking denied."""
from pathlib import Path
from unittest.mock import patch
import io
import json
import os
import socket
import tempfile
import unittest

from vnext import ai_adapter as adapter
from vnext import invocation_control as control
from vnext.canonical import canonical_json_bytes, strict_json_loads
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import prepare_requests, build_plan, execute_capacity_assessment, execute_feasibility, select_native_request_variants


class CapacityNativeAssessmentMaterialTest(unittest.TestCase):
    def test_actual_factory_native_acceptance_and_omitted_unit_failure(self):
        requested = os.environ.get('B13_ASSESSMENT_MATERIAL_ROOT')
        if requested:
            directory = Path(requested).resolve()
            self.assertFalse(directory.exists())
            directory.mkdir(parents=True)
        else:
            temp = tempfile.TemporaryDirectory()
            self.addCleanup(temp.cleanup)
            directory = Path(temp.name)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen', side_effect=AssertionError('SEC_FORBIDDEN')), \
             patch.object(control, 'effective_invocation_policy', side_effect=AssertionError('LEGACY_DEFAULT_FORBIDDEN')):
            requests = prepare_requests(company_id='enphase_energy', metric_id='B13',
                reference_context=os.environ.get('B13_REFERENCE_CONTEXT') == '1')
            if os.environ.get('B13_INDEXED_UNITS') == '1':
                requests, _ = select_native_request_variants(prepared_requests=requests,
                    ledger=recorded_ledger(root=directory/'selection'))
            # No interpretation success is claimed by this simulated empty
            # response. This exact request only exercises transport/acceptance.
            eligible = [r for r in requests if not strict_json_loads(
                text=r.request_bytes.decode())['required_candidate_assessments']]
            self.assertTrue(eligible)
            prepared = min(eligible, key=lambda r: len(r.provider_request_body_bytes))
            policy, plan = build_plan(prepared)
            request = strict_json_loads(text=prepared.request_bytes.decode())
            response = {'request_id': request['request_id'], 'units': [
                {'unit_id': u['unit_id'], 'reviewed': True, 'findings': [], 'unresolved': [], 'calculation_limits': []}
                for u in request['units']]}
            if 'indexed_unit_contract' in request:
                response = {'units':[{**{k:v for k,v in row.items() if k != 'unit_id'}, 'unit_index':i}
                                     for i,row in enumerate(response['units'])]}

            def wire(value):
                return canonical_json_bytes(value={'id': 'b13-offline-native', 'model': 'deepseek-flash',
                    'choices': [{'message': {'role': 'assistant', 'content': json.dumps(value)}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                              'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}})

            raw = wire(response)
            class FakeResponse(io.BytesIO):
                headers = {'x-request-id': 'b13-offline-native'}

            observed = []
            def fake_open(*, fullurl, timeout):
                self.assertEqual(fullurl.full_url, 'https://api.deepseek.com/chat/completions')
                self.assertEqual(fullurl.data, prepared.provider_request_body_bytes)
                self.assertEqual(timeout, 120)
                observed.append(fullurl.data)
                return FakeResponse(raw)

            with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'offline-test-not-a-secret'}), \
                 patch.object(adapter._DEEPSEEK_OPENER, 'open', side_effect=fake_open):
                transport = adapter._build_repository_transport(policy=policy)
                with self.assertRaisesRegex(adapter.AIAdapterError, 'RESERVATION_OWNER_EGRESS_REQUIRED'):
                    transport.complete(prepared_request=prepared)
                result = transport.complete(prepared_request=prepared,
                    egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
                self.assertEqual(result.raw_response_bytes, raw)
            self.assertEqual(len(observed), 1)
            ledger = recorded_ledger(root=directory / 'accepted')
            with self.assertRaisesRegex(ValueError, 'B13_REQUIRES_NATIVE_ASSESSMENT_ENTRY'):
                execute_feasibility(prepared=prepared, ledger=ledger, recorded_wire=raw)
            path, outcome = execute_capacity_assessment(prepared=prepared, ledger=ledger, recorded_wire=raw)
            self.assertEqual(outcome['terminal']['status'], 'SUCCEEDED')
            self.assertTrue(outcome['native_candidate_evidence_created'])
            self.assertFalse(outcome['native_result_created'])
            self.assertFalse(outcome['semantic_correctness_verified'])
            from vnext.capacity_native_assessment import collect_native_assessments
            partial = collect_native_assessments(prepared_requests=requests, ledger=ledger)
            self.assertFalse(partial['all_source_requests_accepted'])
            self.assertEqual(partial['proposed_branch'], 'INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE')
            self.assertEqual(len(partial['completed']), 1)
            with ledger.locked():
                self.assertEqual(ledger.snapshot()['counts'], [1, 1, 0])
                self.assertEqual(ledger.snapshot()['stopped_channels'], [])
            failed = recorded_ledger(root=directory / 'omitted-unit')
            _, bad = execute_capacity_assessment(prepared=prepared, ledger=failed,
                recorded_wire=wire({**response, 'units': []}))
            self.assertEqual(bad['terminal']['status'], 'FAILED_TERMINAL')
            self.assertFalse(bad['native_candidate_evidence_created'])
            summary = {'status': 'OFFLINE_NATIVE_REQUEST_ACCEPTANCE_PASS', 'network_disabled': True,
                'actual_factory_and_opener_verified': True, 'required_native_evidence_verified': True,
                'missing_unit_rejected': True, 'request_count': len(requests),
                'selected_request_bytes': len(prepared.provider_request_body_bytes),
                'estimated_context_tokens': plan['observability']['estimated_context_tokens'],
                'closure': prepared.requirement['requirement_closure_hash'],
                'real_calls': [0, 0, 0], 'complete_b13_result': False}
            (directory / 'summary.json').write_bytes(canonical_json_bytes(value=summary))
            print(summary)
