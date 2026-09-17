"""Complete recorded D04 source execution, ordinary native Run and disk attacks."""
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
from vnext.continuous_semantic_calls import prepare_requests, execute_d04_assessment, select_native_request_variants
from vnext.capacity_semantic_review import _restore_units
from vnext.r6_semantic_review import _source_items
from vnext.capacity_assessment_input import register_assessment_input, load_registered_input, EXPORT_PATHS
from vnext.normal_source_authority import ROOT

EXPORT_PATH = EXPORT_PATHS['D04']


def recorded_response(request):
    if 'indexed_unit_contract' in request:
        from vnext.native_unit_index import restore_base_request
        base = recorded_response(restore_base_request(request))
        return {'units':[{**{k:v for k,v in row.items() if k != 'unit_id'}, 'unit_index':index}
                         for index,row in reversed(list(enumerate(base['units'])))]}
    rows = []
    for unit in _restore_units(request['units'], request['shared_source_dictionaries']):
        kind, items = _source_items(unit)
        required = [r['source_index'] for r in request['required_candidate_assessments'] if r['unit_id'] == unit['unit_id']]
        findings = []
        for index in required:
            text = items[index].get('text', items[index].get('raw_xml', ''))
            chosen = 'VALUATION_OR_OTHER_MEANING'
            # These classifications are explicitly test data, not a claim that
            # the model has interpreted the other source language correctly.
            findings.append({'kind': chosen, 'subject': 'TARGET_REGISTRANT', 'timing': 'CURRENT_REPORT',
                'evidence': [{'kind': kind, 'source_index': index}],
                'reason': 'Recorded source-role input for native Run tests, not provider or semantic qualification.'})
        rows.append({'unit_id': unit['unit_id'], 'reviewed': True, 'findings': findings, 'unresolved': []})
    return {'request_id': request['request_id'], 'units': rows}


class D04RunMaterialTest(unittest.TestCase):
    def test_scoped_assertions_complete_run_and_final_public_row(self):
        """Synthetic source/admission doubles; real result, Run and projection.

        This extends each review counterexample through disk replay. Neither
        these doubles nor a recorded response supplies real company credit.
        """
        from tests.vnext.test_capacity_utilization_source import quantity_source
        from tests.vnext.test_d04_native_assessment import REVIEW_SCOPE_CASES
        from vnext.d04_native_assessment import native_source, requests_from_source, validate_response
        from vnext.capacity_run import create_run
        from vnext.normal_run_v3 import _install_case_inputs
        from vnext.requirements import load_requirement_snapshot
        from vnext.ordinary_projection import render_ordinary_run
        from vnext.run_store import _mechanically_replay_open_run, RunStoreError
        admission = {'source_credit':'RECORDED_TEST_ONLY', 'checkpoint_id':content_hash(value='synthetic D04 source admission')}
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('vnext.capacity_run.verify_ordinary_source_proofs', return_value=admission), \
             patch('vnext.normal_run_v3.verify_ordinary_source_proofs', return_value=admission):
            data = Path(temporary)/'data'
            requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
            _install_case_inputs(data_root=data, source_root=ROOT, company_id='enphase_energy',
                case={'source_proofs':[], 'primary_metric_id':'D04'}, requirement=requirement)
            for number, (statement, wrong_kind, wrong_timing) in enumerate(REVIEW_SCOPE_CASES[:3]):
                original, raw = quantity_source('<p>'+statement+'</p>')
                unit = original['units'][0]
                index = next(b['block_index'] for b in unit['payload']['blocks'] if b['text'] == statement)
                original.update(record_type='D04_COMPLETE_SEMANTIC_SOURCE', metric_id='D04', source_proofs=[])
                original['documents'][0].update(language_candidate_block_indices=[index], native_candidate_ordinals=[])
                original['semantic_source_id'] = content_hash(value={k:v for k,v in original.items() if k != 'semantic_source_id'})
                source = native_source(original); request = requests_from_source(source)[0]
                response = {'request_id':request['request_id'],'units':[{'unit_id':unit['unit_id'], 'reviewed':True,
                    'unresolved':[], 'findings':[{'kind':'DOUBT_DISCLOSED', 'subject':'TARGET_REGISTRANT',
                    'timing':'CURRENT_REPORT', 'reason':'Synthetic assertion scope integration case.',
                    'evidence':[{'kind':'VISIBLE_BLOCK','source_index':index}]}]}]}
                checked = validate_response(request=request, raw_response=canonical_json_bytes(value=response))
                self.assertEqual(checked['unresolved'], [])
                body = {'record_type':'D04_NATIVE_SOURCE_ASSESSMENT_SET', 'source_id':source['semantic_source_id'],
                    'company_id':source['company_id'], 'required_request_ids':[request['request_id']],
                    'completed':[{'request_id':request['request_id'],'candidate':{'selected':{'source_assessment':{'findings':checked['findings']}}}}],
                    'all_source_requests_accepted':True,'missing_request_ids':[],'failed_requests':[],
                    'source_findings':checked['findings'],'mode':'RECORDED_TEST_ONLY',
                    'proposed_branch':'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW'}
                assessment = {**body,'assessment_set_id':content_hash(value=body)}
                registered = {'assessment':assessment,'mode':'RECORDED_TEST_ONLY',
                    'input_record_id':content_hash(value=['synthetic D04 registration',number])}
                raw_path = data/source['documents'][0]['raw_blob']['storage_uri']
                raw_path.parent.mkdir(parents=True,exist_ok=True);raw_path.write_bytes(next(iter(raw.values())))
                with patch('vnext.r6_semantic_source.prepare_d04_semantic_source',return_value=original), \
                     patch('vnext.capacity_run.load_registered_input',return_value=registered), \
                     patch('vnext.ordinary_projection.prepare_saved_annual_input',return_value=source['prepared_annual_input']):
                    run = Path(temporary)/('run-'+str(number))
                    created = create_run(data_root=data,run_dir=run,company_id=source['company_id'],metric_id='D04')
                    self.assertEqual(created['result']['value'],statement)
                    rendered = render_ordinary_run(data_root=data,run_dir=run)
                    self.assertEqual(rendered['row']['value'],statement)
                    self.assertNotIn('未披露持续经营疑虑', rendered['row']['notes'])
                    self.assertEqual(rendered['receipt']['semantic_assessment_mode'],'RECORDED_TEST_ONLY')
                    bad = deepcopy(assessment)
                    bad['source_findings'][0].update(kind=wrong_kind,timing=wrong_timing)
                    bad['completed'][0]['candidate']['selected']['source_assessment']['findings'] = bad['source_findings']
                    bad['proposed_branch'] = 'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
                    bad['assessment_set_id'] = content_hash(value={k:v for k,v in bad.items() if k != 'assessment_set_id'})
                    with patch('vnext.capacity_run.load_registered_input',return_value={**registered,'assessment':bad}):
                        with self.assertRaisesRegex(ValueError,'D04_SOURCE_.*CONFLICT'):
                            create_run(data_root=data,run_dir=Path(temporary)/('wrong-'+str(number)),
                                company_id=source['company_id'],metric_id='D04')
                        with self.assertRaises(RunStoreError):
                            _mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
                        with self.assertRaises((ValueError, RunStoreError)):
                            render_ordinary_run(data_root=data,run_dir=run)

    def test_native_run_recorded_mode_exact_source_and_resigned_input_rejection(self):
        requested = os.environ.get('D04_NATIVE_RUN_MATERIAL_ROOT')
        if requested:
            directory = Path(requested).resolve(); self.assertFalse(directory.exists()); directory.mkdir(parents=True)
        else:
            tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); directory = Path(tmp.name)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen', side_effect=AssertionError('SEC_FORBIDDEN')):
            prepared = prepare_requests(company_id='enphase_energy', metric_id='D04', native=True,
                reference_context=os.environ.get('D04_REFERENCE_CONTEXT') == '1',
                complete_response_contract=os.environ.get('D04_COMPLETE_RESPONSE_CONTRACT') == '1')
            ledger = recorded_ledger(root=directory / 'ledger')
            def execute_recorded(request_object):
                request = strict_json_loads(text=request_object.request_bytes.decode())
                response = recorded_response(request)
                wire = canonical_json_bytes(value={'id': 'd04-native-run-recorded', 'model': 'deepseek-flash',
                    'choices': [{'message': {'role': 'assistant', 'content': json.dumps(response)}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                              'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}})
                path, outcome = execute_d04_assessment(prepared=request_object, ledger=ledger, recorded_wire=wire)
                self.assertEqual(outcome['terminal']['status'], 'SUCCEEDED', str(path) + ': ' + str(outcome))
            if os.environ.get('D04_INDEXED_UNITS') == '1':
                original_first = prepared[0]
                execute_recorded(original_first)
                prepared, retained = select_native_request_variants(prepared_requests=prepared, ledger=ledger)
                self.assertEqual(prepared[0].request_bytes, original_first.request_bytes)
                self.assertEqual(retained[0]['original_ordinal'], 1)
                self.assertTrue(all(r['variant'] == 'INDEXED_UNITS_V1' for r in retained[1:]))
                for request_object in prepared[1:]:execute_recorded(request_object)
            else:
                for request_object in prepared:execute_recorded(request_object)
            registered = register_assessment_input(prepared_requests=prepared, ledger=ledger)
            self.assertEqual(registered['mode'], 'RECORDED_TEST_ONLY')
            source = strict_json_loads(text=prepared[0].source_bytes.decode())
            from vnext.capacity_run import install_inputs
            from vnext.normal_run_v3 import create_normal_run
            from vnext.ordinary_projection import render_ordinary_run
            data, run = directory / 'data', directory / 'run'
            install_inputs(data_root=data, company_id='enphase_energy', assessment_mode='RECORDED_TEST_ONLY',
                           assessment_input_id=registered['input_record_id'], metric_id='D04',
                           request_context_format=source.get('request_context_format'),
                           complete_response_contract=bool(source.get('response_contract_version')))
            with self.assertRaises(ValueError):
                load_registered_input(data_root=data, source=source, requirement=prepared[0].requirement, mode='LIVE')
            created = create_normal_run(data_root=data, run_dir=run, company_id='enphase_energy', metric_id='D04')
            self.assertEqual(created['manifest']['requirement_id'], 'issue_28_v14')
            self.assertEqual(created['manifest']['status'], 'OPEN')
            self.assertEqual(created['result']['value_kind'], 'TEXT_V1')
            self.assertIsNone(created['result']['value'])
            self.assertEqual(created['result']['reason_code'], 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE')
            rendered = render_ordinary_run(data_root=data, run_dir=run)
            self.assertEqual(rendered['receipt']['semantic_assessment_mode'], 'RECORDED_TEST_ONLY')
            self.assertEqual(rendered['row']['status'], 'TEXT_QUAL')
            self.assertIn('未披露持续经营疑虑', rendered['row']['notes'])
            self.assertTrue(rendered['evidence'])
            self.assertFalse(rendered['receipt']['production_authorized'])
            for name, raw in rendered['files'].items():
                target = directory / 'rows' / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
            from vnext.run_store import _mechanically_replay_open_run, RunStoreError
            checkpoint = data / EXPORT_PATH; original = checkpoint.read_bytes()
            for mutation in ('omit_request', 'upgrade_mode', 'context_format', 'response_contract'):
                bad = json.loads(original)
                if mutation == 'omit_request': bad['native_requests'].pop()
                elif mutation == 'upgrade_mode': bad['mode'] = 'LIVE'; bad['assessment']['mode'] = 'LIVE'
                elif mutation == 'context_format': bad['request_context_format'] = 'unapproved-format'
                else: bad['response_contract_version'] = 'unapproved-contract'
                bad['input_record_id'] = content_hash(value={k: v for k, v in bad.items() if k != 'input_record_id'})
                checkpoint.write_bytes(canonical_json_bytes(value=bad))
                try:
                    with self.assertRaisesRegex(RunStoreError, 'Native text input replay failed'):
                        _mechanically_replay_open_run(run_dir=run, repo_root=data, require_complete_results=True)
                finally:
                    checkpoint.write_bytes(original)
            summary = {'status': 'D04_RECORDED_NATIVE_OPEN_AND_ROWS_PASS', 'run_id': created['manifest']['run_id'],
                'result_id': created['result']['result_id'], 'source_requests': len(prepared),
                'real_calls': [0, 0, 0], 'semantic_assessment_mode': 'RECORDED_TEST_ONLY',
                'complete_d04_real_acceptance': False, 'production_authorized': False,
                'negative_cases': ['missing native request', 'recorded input relabelled live', 'changed request context format', 'changed response coverage contract']}
            (directory / 'summary.json').write_bytes(canonical_json_bytes(value=summary))
            print(summary)
