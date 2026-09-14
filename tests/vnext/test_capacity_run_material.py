"""Complete recorded B13 source execution, ordinary native Run and disk attacks."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import os
import socket
import tempfile
import unittest

from vnext.canonical import canonical_json_bytes, content_hash, strict_json_loads
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import prepare_requests, execute_capacity_assessment
from vnext.capacity_semantic_review import _restore_units
from vnext.r6_semantic_review import _source_items
from vnext.capacity_assessment_input import register_assessment_input, load_registered_input, EXPORT_PATH
from vnext.normal_source_authority import ROOT


def recorded_response(request):
    rows = []
    for unit in _restore_units(request['units'], request['shared_source_dictionaries']):
        kind, items = _source_items(unit)
        required = [r['source_index'] for r in request['required_candidate_assessments'] if r['unit_id'] == unit['unit_id']]
        findings = []
        for index in required:
            text = items[index].get('text', items[index].get('raw_xml', ''))
            chosen = ('AVAILABLE_CAPACITY' if kind == 'VISIBLE_BLOCK'
                      and 'approximately five-million microinverters per quarter' in text else 'OTHER_CONTEXT')
            # These classifications are explicitly test data, not a claim that
            # the model has interpreted the other source language correctly.
            findings.append({'kind': chosen, 'subject': 'TARGET_REGISTRANT', 'timing': 'CURRENT_REPORT',
                'evidence': [{'kind': kind, 'source_index': index}],
                'reason': 'Recorded source-role input for native Run tests, not provider or semantic qualification.'})
        rows.append({'unit_id': unit['unit_id'], 'reviewed': True, 'findings': findings, 'unresolved': []})
    return {'request_id': request['request_id'], 'units': rows}


class CapacityRunMaterialTest(unittest.TestCase):
    def test_native_run_recorded_mode_exact_source_and_resigned_input_rejection(self):
        requested = os.environ.get('B13_NATIVE_RUN_MATERIAL_ROOT')
        if requested:
            directory = Path(requested).resolve(); self.assertFalse(directory.exists()); directory.mkdir(parents=True)
        else:
            tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); directory = Path(tmp.name)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen', side_effect=AssertionError('SEC_FORBIDDEN')):
            prepared = prepare_requests(company_id='enphase_energy', metric_id='B13')
            ledger = recorded_ledger(root=directory / 'ledger')
            for request_object in prepared:
                request = strict_json_loads(text=request_object.request_bytes.decode())
                response = recorded_response(request)
                wire = canonical_json_bytes(value={'id': 'b13-native-run-recorded', 'model': 'deepseek-flash',
                    'choices': [{'message': {'role': 'assistant', 'content': json.dumps(response)}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                              'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}})
                path, outcome = execute_capacity_assessment(prepared=request_object, ledger=ledger, recorded_wire=wire)
                self.assertEqual(outcome['terminal']['status'], 'SUCCEEDED', str(path) + ': ' + str(outcome))
            registered = register_assessment_input(prepared_requests=prepared, ledger=ledger)
            self.assertEqual(registered['mode'], 'RECORDED_TEST_ONLY')
            source = strict_json_loads(text=prepared[0].source_bytes.decode())
            from vnext.capacity_run import install_inputs
            from vnext.normal_run_v3 import create_normal_run
            from vnext.ordinary_projection import render_ordinary_run
            data, run = directory / 'data', directory / 'run'
            install_inputs(data_root=data, company_id='enphase_energy', assessment_mode='RECORDED_TEST_ONLY',
                           assessment_input_id=registered['input_record_id'])
            with self.assertRaises(ValueError):
                load_registered_input(data_root=data, source=source, requirement=prepared[0].requirement, mode='LIVE')
            created = create_normal_run(data_root=data, run_dir=run, company_id='enphase_energy', metric_id='B13')
            self.assertEqual(created['manifest']['requirement_id'], 'issue_28_v14')
            self.assertEqual(created['manifest']['status'], 'OPEN')
            self.assertEqual(created['result']['value_kind'], 'TEXT_V1')
            self.assertIn('approximately five-million microinverters per quarter', created['result']['value'])
            rendered = render_ordinary_run(data_root=data, run_dir=run)
            self.assertEqual(rendered['receipt']['semantic_assessment_mode'], 'RECORDED_TEST_ONLY')
            self.assertFalse(rendered['receipt']['production_authorized'])
            for name, raw in rendered['files'].items():
                target = directory / 'rows' / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
            from vnext.run_store import _mechanically_replay_open_run, RunStoreError
            checkpoint = data / EXPORT_PATH; original = checkpoint.read_bytes()
            for mutation in ('omit_request', 'upgrade_mode'):
                bad = json.loads(original)
                if mutation == 'omit_request': bad['native_requests'].pop()
                else: bad['mode'] = 'LIVE'; bad['assessment']['mode'] = 'LIVE'
                bad['input_record_id'] = content_hash(value={k: v for k, v in bad.items() if k != 'input_record_id'})
                checkpoint.write_bytes(canonical_json_bytes(value=bad))
                try:
                    with self.assertRaisesRegex(RunStoreError, 'Native text input replay failed'):
                        _mechanically_replay_open_run(run_dir=run, repo_root=data, require_complete_results=True)
                finally:
                    checkpoint.write_bytes(original)
            summary = {'status': 'B13_RECORDED_NATIVE_OPEN_AND_ROWS_PASS', 'run_id': created['manifest']['run_id'],
                'result_id': created['result']['result_id'], 'source_requests': len(prepared),
                'real_calls': [0, 0, 0], 'semantic_assessment_mode': 'RECORDED_TEST_ONLY',
                'complete_b13_real_acceptance': False, 'production_authorized': False,
                'negative_cases': ['missing native request', 'recorded input relabelled live']}
            (directory / 'summary.json').write_bytes(canonical_json_bytes(value=summary))
            print(summary)
