"""Registered B13/D04 share ordinary update history without enabling calls.

The short tests exercise contract routing and real absence validators. The
optional material test consumes an already registered source copy; it neither
creates model responses nor changes the fixed live ledger/source-inputs.
"""
from copy import deepcopy
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch
from vnext import ordinary_update_cycle as cycle, normal_run_v3 as normal
from vnext.canonical import content_hash


class RegisteredNativeUpdateTest(unittest.TestCase):
    def test_scope_adds_only_registered_b13_d04_without_changing_old_policy(self):
        original=normal._policy(normal.ROOT)
        self.assertEqual(set(normal.update_metric_ids()),set(original['metric_ids'])|{'B13','D04'})
        self.assertNotIn('D03',normal.update_metric_ids())
        self.assertNotIn('B13',original['metric_ids'])
        self.assertNotIn('D04',original['metric_ids'])

    def test_old_configuration_bytes_stay_old_and_native_uses_its_requirement(self):
        digest='sha256:'+'1'*64
        with tempfile.TemporaryDirectory() as temporary, patch.object(cycle,'load_requirement_snapshot',return_value={'requirement_closure_hash':digest}) as loader:
            root=Path(temporary).resolve();source=root/'source'
            old=cycle._config(root/'old',source,'enphase_energy',['B01'])
            body={'record_type':'ORDINARY_UPDATE_CONFIGURATION','schema_version':1,'company_id':'enphase_energy',
                'metric_ids':['B01'],'source_root':str(source),'requirement_closure_hash':digest,
                'provider_enabled':False,'sec_fetch_enabled':False,'production_authorized':False}
            self.assertEqual(old,{**body,'record_id':content_hash(value=body)})
            self.assertEqual(loader.call_args.kwargs['snapshot_dir'].name,normal.REQUIREMENT_ID)
            new=cycle._config(root/'new',source,'enphase_energy',['D04'],'RECORDED_TEST_ONLY')
            self.assertEqual(loader.call_args.kwargs['snapshot_dir'].name,'issue_28_v14')
            self.assertEqual(new['registered_update_options'],normal.registered_update_options('D04',assessment_mode='RECORDED_TEST_ONLY'))
            with self.assertRaisesRegex(ValueError,'CONFIGURATION_OR_RUNTIME_CHANGED'):
                cycle._config(root/'new',source,'enphase_energy',['D04'],'LIVE')
            with self.assertRaisesRegex(ValueError,'PER_METRIC_HISTORY'):
                cycle._config(root/'mixed',source,'enphase_energy',['B01','B13'])

    def test_registered_assessment_identity_changes_descriptor_without_source_changes(self):
        cfg={'company_id':'enphase_energy','metric_ids':['D04'],'requirement_closure_hash':'runtime'}
        case={'target_period':{'period_end':'2025-12-31'},'compiled_specs':{'D04':{'spec_closure_hash':'spec'}},
            'source_proofs':[{'source_url':'source','accession':'a','document_name':'source.htm','content_sha256':'source-bytes'}],
            'input_binding':{'source_id':'source-id','assessment_set_id':'assessment-a'},
            'registered_input':{'input_record_id':'input-a','mode':'LIVE','response_contract_version':'contract-a'}}
        first=cycle._descriptor({'D04':case},cfg)
        for field,value in [('input_record_id','input-b'),('mode','RECORDED_TEST_ONLY'),('response_contract_version','contract-b')]:
            changed=deepcopy(case);changed['registered_input'][field]=value
            current=cycle._descriptor({'D04':changed},cfg)
            self.assertEqual(first['source_contents'],current['source_contents'])
            self.assertNotEqual(first['content_id'],current['content_id'])
        plain=deepcopy(case);plain.pop('registered_input')
        self.assertNotIn('registered_assessment_inputs',cycle._descriptor({'D04':plain},cfg))

    def test_native_current_contract_is_passed_to_existing_trusted_preparer(self):
        from vnext import capacity_run,capacity_update_input
        options=normal.registered_update_options('D04')
        with patch.object(capacity_update_input,'prepare_registered_update',side_effect=ValueError('UPDATE_NATIVE_COMPLETE_ORIGINAL_SET_MISSING_OR_AMBIGUOUS')) as prepare:
            with self.assertRaisesRegex(ValueError,'MISSING_OR_AMBIGUOUS'):
                normal.prepare_case(data_root=normal.ROOT,company_id='enphase_energy',metric_id='D04',registered_update_options=options)
            self.assertEqual(prepare.call_args.kwargs['options'],options)
            self.assertEqual(prepare.call_count,1)
        selected={'source':{'source_id':'routing-double'},'registered_input':{'input_record_id':'creator-selected'}}
        with patch.object(capacity_update_input,'prepare_registered_update',return_value=selected),patch.object(capacity_run,'install_inputs',return_value='installed') as install:
            self.assertEqual(normal.install_normal_inputs(data_root=Path('/tmp/example-native-update-data'),company_id='enphase_energy',metric_id='D04',registered_update_options=options),'installed')
            self.assertEqual(install.call_args.kwargs['request_context_format'],options['request_context_format'])
            self.assertTrue(install.call_args.kwargs['current_runtime'])
            self.assertEqual(install.call_args.kwargs['assessment_input_id'],'creator-selected')
        bad={**options,'request_context_format':'unrecognized'}
        with patch.object(capacity_update_input,'prepare_registered_update') as prepare:
            with self.assertRaisesRegex(ValueError,'CONTRACT_CHANGED'):
                normal.prepare_case(data_root=normal.ROOT,company_id='enphase_energy',metric_id='D04',registered_update_options=bad)
            prepare.assert_not_called()
        with patch.object(capacity_run,'prepare_case',return_value='structural') as prepare:
            normal.prepare_case(data_root=normal.ROOT,company_id='pfizer',metric_id='B13',registered_update_options=normal.registered_update_options('B13'))
            self.assertNotIn('assessment_mode',prepare.call_args.kwargs)

    def test_complete_equivalence_is_only_provenance_not_changed_semantic_input(self):
        from vnext.capacity_update_input import source_equivalence
        from tests.vnext.test_capacity_utilization_source import quantity_source
        original,_=quantity_source('<p>For fiscal year 2025, we produced 80 widgets worldwide.</p>')
        original['source_proofs']=[{'source_url':'https://data.sec.gov/submissions/source.json','accession':'','document_name':'source.json','content_sha256':'a'*64,'request_attempt_id':'old'}]
        original['module_sha256']='old-module'
        original['semantic_source_id']=content_hash(value={k:v for k,v in original.items() if k!='semantic_source_id'})
        current=deepcopy(original);current['source_proofs'][0]['request_attempt_id']='new';current['module_sha256']='current-module'
        current['semantic_source_id']=content_hash(value={k:v for k,v in current.items() if k!='semantic_source_id'})
        receipt=source_equivalence(current=current,original=original)
        self.assertFalse(receipt['original_provider_bytes_rewritten'])
        for attack in ['body','unit','period','scope']:
            bad=deepcopy(current)
            if attack=='body':bad['source_proofs'][0]['content_sha256']='b'*64
            elif attack=='unit':bad['units'][0]['payload']['blocks'][0]['text']='changed'
            elif attack=='period':bad['prepared_annual_input']['table_input']['target_period']['period_end']='2026-12-31'
            else:bad['quantity_scope_context']['format']='unknown'
            bad['semantic_source_id']=content_hash(value={k:v for k,v in bad.items() if k!='semantic_source_id'})
            with self.subTest(attack=attack),self.assertRaises(ValueError):source_equivalence(current=bad,original=original)

    def test_caller_json_cannot_supply_ledger_or_execute_replay_only(self):
        from vnext.capacity_update_input import _ledger
        from vnext.continuous_semantic_calls import _execute_semantic
        from types import SimpleNamespace
        requirement={'policy':{'budget_root':'/fixed-live-budget'}}
        with self.assertRaisesRegex(ValueError,'LEDGER_FACTORY_OR_MODE_CHANGED'):
            _ledger(requirement,'LIVE',{'status':'SUCCEEDED','root':'/fixed-live-budget'})
        with self.assertRaisesRegex(ValueError,'RECORDED_NATIVE_LEDGER_REQUIRED'):
            _ledger(requirement,'RECORDED_TEST_ONLY',None)
        with self.assertRaisesRegex(ValueError,'REPLAY_OBJECT_CANNOT_EXECUTE'):
            _execute_semantic(prepared=SimpleNamespace(request_bytes=b'{}',replay_only=True),
                ledger=None,recorded_wire=None,native_assessment=True)

    @staticmethod
    def absence(metric):
        from tests.vnext.test_d04_native_assessment import text_arguments,D04NativeTextRecordsTest
        args=text_arguments('Revenue is recognized when services are delivered.',None,'CURRENT_REPORT')
        if metric=='B13':
            from vnext.capacity_semantic_review import requests_from_source
            from vnext.specs import compile_spec_file
            source=args['source'];source.update(record_type='B13_COMPLETE_SEMANTIC_SOURCE',metric_id='B13')
            source['semantic_source_id']=content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'})
            requests=requests_from_source(source)
            assessment=args['assessment'];assessment.update(record_type='B13_NATIVE_SOURCE_ASSESSMENT_SET',source_id=source['semantic_source_id'],
                required_request_ids=[r['request_id'] for r in requests],completed=[{'request_id':r['request_id'],'candidate':{'selected':{'source_assessment':{'findings':[]}}}} for r in requests])
            assessment['assessment_set_id']=content_hash(value={k:v for k,v in assessment.items() if k!='assessment_set_id'})
            args['compiled_spec']=compile_spec_file(path=normal.ROOT/'catalog/r5/B13_capacity_disclosures_v1.md',dependency_specs={})
            args['target']['scope']=args['compiled_spec']['compiled']['required_claims']
            args['target']['scope_key']=content_hash(value=args['target']['scope'])
        result=D04NativeTextRecordsTest().reviewed_result(args)
        case={'kind':'TEXT','registered_input':{'assessment':args['assessment']},'selection':{'status':'TEXT_QUAL' if metric=='D04' else 'NOT_AVAILABLE_SEC'},'text_arguments':args}
        from vnext.capacity_run import project_defined_absence
        row,evidence=project_defined_absence(case=case,result=result,row={},company={'display_name':'Sample','primary_cik':'12345'})
        return case,result,{'row':row,'evidence':evidence}

    def test_only_specialized_complete_absence_can_join_successful_history(self):
        registry=[{'company_id':'sample_entity','display_name':'Sample','primary_cik':'12345'}]
        for metric in ['B13','D04']:
            case,result,rendered=self.absence(metric)
            self.assertEqual(result['publication'],'WITHHELD')
            with patch.object(cycle,'_registry_rows',return_value=registry):
                self.assertTrue(cycle._completed_result(metric=metric,result=result,case=case,rendered=rendered,data_root=normal.ROOT))
                bad=deepcopy(case);bad['registered_input']['assessment']['missing_request_ids']=['missing']
                with self.assertRaisesRegex(ValueError,'ABSENCE_PROJECTION_NOT_ESTABLISHED'):
                    cycle._completed_result(metric=metric,result=result,case=bad,rendered=rendered,data_root=normal.ROOT)
                changed=deepcopy(rendered);changed['evidence']=[]
                with self.assertRaisesRegex(ValueError,'ABSENCE_PROJECTION_CHANGED'):
                    cycle._completed_result(metric=metric,result=result,case=case,rendered=changed,data_root=normal.ROOT)
                self.assertFalse(cycle._completed_result(metric=metric,result={**result,'reason_code':'IMPLEMENTATION_UNSUPPORTED'},case=case,rendered=rendered,data_root=normal.ROOT))
                self.assertFalse(cycle._completed_result(metric='B06',result=result,case=case,rendered=rendered,data_root=normal.ROOT))
                self.assertFalse(cycle._completed_result(metric=metric,result={**result,'value_kind':'NUMBER'},case=case,rendered=rendered,data_root=normal.ROOT))

    def test_reason_string_does_not_override_current_source_relation(self):
        from tests.vnext.test_d04_native_assessment import text_arguments
        case,result,rendered=self.absence('D04')
        bad=text_arguments('These conditions raise substantial doubt about our ability to continue as a going concern.','VALUATION_OR_OTHER_MEANING','CURRENT_REPORT')
        bad['assessment']['proposed_branch']='DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
        bad['assessment']['assessment_set_id']=content_hash(value={k:v for k,v in bad['assessment'].items() if k!='assessment_set_id'})
        case.update(registered_input={'assessment':bad['assessment']},text_arguments=bad)
        with patch.object(cycle,'_registry_rows',return_value=[{'company_id':'sample_entity','display_name':'Sample','primary_cik':'12345'}]):
            with self.assertRaisesRegex(ValueError,'D04_SOURCE_.*CONFLICT'):
                cycle._completed_result(metric='D04',result=result,case=case,rendered=rendered,data_root=normal.ROOT)


@unittest.skipUnless(os.environ.get('ORDINARY_NATIVE_UPDATE_SOURCE_ROOT'),'Requires an already registered copied native source fixture')
class RegisteredNativeUpdateMaterialTest(unittest.TestCase):
    def test_registered_native_history_repeat_failure_and_recovery(self):
        source_fixture=Path(os.environ['ORDINARY_NATIVE_UPDATE_SOURCE_ROOT']).resolve()
        metric=os.environ.get('ORDINARY_NATIVE_UPDATE_METRIC','B13')
        company=os.environ.get('ORDINARY_NATIVE_UPDATE_COMPANY','enphase_energy')
        mode=os.environ.get('ORDINARY_NATIVE_UPDATE_MODE','RECORDED_TEST_ONLY')
        self.assertIn(metric,{'B13','D04'})
        retained=os.environ.get('ORDINARY_NATIVE_UPDATE_MATERIAL_ROOT')
        if retained:
            self.assertTrue(Path(retained).is_absolute())
            destination=Path(retained).resolve()
            self.assertFalse(destination.exists())
            self.assertNotEqual(destination,normal.ROOT)
            self.assertNotIn(normal.ROOT,destination.parents)
        workspace=nullcontext(retained) if retained else tempfile.TemporaryDirectory()
        with workspace as temporary, patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
            root=Path(temporary).resolve();source=root/'source';shutil.copytree(source_fixture,source)
            from vnext.continuous_call_ledger import recorded_ledger
            ledger=recorded_ledger(root=Path(os.environ.get('ORDINARY_NATIVE_UPDATE_LEDGER_ROOT',str(source_fixture.parent/'ledger')))) if mode=='RECORDED_TEST_ONLY' else None
            def check():return cycle.run_company(state_root=root/'history',source_root=source,company_id=company,metric_ids=[metric],native_assessment_mode=mode,native_assessment_ledger=ledger)['metrics'][0]
            first=check();self.assertEqual(first['status'],'CANDIDATE_READY',first)
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Identical registered input must reuse its native Run')):
                again=check();self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
                self.assertEqual(first['successful_attempt'],again['successful_attempt'])
                original=(source/'evidence/requests_log.csv').read_bytes()
                (source/'evidence/requests_log.csv').write_bytes(original+b'corrupt')
                failed=check();self.assertEqual(failed['status'],'INPUT_FAILED',failed)
                self.assertEqual(failed['successful_attempt'],first['successful_attempt'])
                (source/'evidence/requests_log.csv').write_bytes(original)
                recovered=check();self.assertEqual(recovered['status'],'NO_SOURCE_CONTENT_CHANGE',recovered)
                self.assertEqual(recovered['successful_attempt'],first['successful_attempt'])
