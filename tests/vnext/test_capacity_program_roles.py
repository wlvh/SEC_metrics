"""Explicit V6 program-owned roles reuse native checks without model quantity labels."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from tests.vnext.test_capacity_utilization_source import quantity_source
from vnext.capacity_program_roles import program_source
from vnext.capacity_semantic_review import requests_from_source,validate_response
from vnext.capacity_native_assessment import build_acceptance
from vnext.canonical import content_hash,canonical_json_bytes


def answer(request):
    return {'request_id':request['request_id'],'units':[{'unit_id':u['unit_id'],'reviewed':True,
        'findings':[],'unresolved':[],'calculation_limits':[]} for u in request['units']]}


def acceptance(source,request,response):
    plan={k:content_hash(value=k) for k in ('selected_representation_hash','ai_invocation_plan_id','source_identity_hash','task_contract_hash')}
    return build_acceptance(prepared=SimpleNamespace(source_bytes=canonical_json_bytes(value=source),
        request_bytes=canonical_json_bytes(value=request)),plan=plan,response_body=canonical_json_bytes(value=response))


class CapacityProgramRolesTest(unittest.TestCase):
    def test_explicit_contract_preserves_old_default_and_fills_quantity_coverage(self):
        source,_=quantity_source('<p>For fiscal year 2025, we produced 80 widgets worldwide.</p>'
            '<p>For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.</p>')
        first=requests_from_source(source);old=deepcopy(source)
        new=program_source(source);request=requests_from_source(new)[0]
        self.assertEqual(source,old);self.assertEqual(requests_from_source(source),first)
        self.assertNotEqual(request['source_id'],first[0]['source_id']);self.assertNotEqual(request['request_id'],first[0]['request_id'])
        self.assertNotIn('ACTUAL_PRODUCTION',request['response_protocol']['finding_kinds'])
        response=answer(request);checked=validate_response(request=request,raw_response=canonical_json_bytes(value=response),source=new)
        self.assertEqual({f['kind'] for f in checked['findings']},{'ACTUAL_PRODUCTION','AVAILABLE_CAPACITY'})
        self.assertEqual(checked['unresolved'],[])
        result=acceptance(new,request,response)
        self.assertIn('program_quantity_contract',result['candidate_record']['selected']['source_assessment'])
        self.assertEqual(result['evidence_status'],'PASS')
        missing=deepcopy(response);missing['units']=[]
        with self.assertRaises(ValueError):acceptance(new,request,missing)

    def test_model_cannot_reintroduce_quantity_or_forge_program_roles(self):
        source,_=quantity_source('<p>For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.</p>')
        source=program_source(source);request=requests_from_source(source)[0];response=answer(request)
        unit=source['units'][0];block=unit['payload']['blocks'][0]
        response['units'][0]['findings']=[{'kind':'AVAILABLE_CAPACITY','subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT',
            'reason':'Forbidden model-owned quantity role.','evidence':[{'kind':'VISIBLE_BLOCK','source_index':block['block_index']}]}]
        with self.assertRaises(ValueError):acceptance(source,request,response)
        bad=deepcopy(request);bad['program_quantity_contract']['verified_quantity_roles']=[]
        bad['program_quantity_contract']['contract_id']=content_hash(value={k:v for k,v in bad['program_quantity_contract'].items() if k!='contract_id'})
        bad['request_id']=content_hash(value={k:v for k,v in bad.items() if k!='request_id'})
        with self.assertRaisesRegex(ValueError,'PROGRAM_SOURCE_PROOFS_CHANGED'):acceptance(source,bad,answer(bad))

    def test_unsupported_source_quantity_is_not_model_discretion(self):
        source,_=quantity_source('<p>Our production volume totaled 80 widgets in the first quarter.</p>')
        source=program_source(source);request=requests_from_source(source)[0]
        response=answer(request)
        self.assertTrue(request['program_quantity_contract']['implementation_unresolved'])
        with self.assertRaisesRegex(ValueError,'SOURCE_ASSESSMENT_UNRESOLVED'):acceptance(source,request,response)

    def test_unproved_operating_time_prefix_is_not_program_current_quantity(self):
        source,_=quantity_source('<p>Historically, we continued to operate our domestic manufacturing footprint. '
            'These arrangements maintained a combined manufacturing capacity of approximately five-million microinverters per quarter.</p>')
        source=program_source(source);request=requests_from_source(source)[0]
        self.assertEqual(request['program_quantity_contract']['verified_quantity_roles'],[])
        self.assertTrue(request['program_quantity_contract']['implementation_unresolved'])
        with self.assertRaisesRegex(ValueError,'SOURCE_ASSESSMENT_UNRESOLVED'):acceptance(source,request,answer(request))

    def test_empty_calculation_limits_do_not_establish_comparability(self):
        from vnext.capacity_utilization_source import calculate_source_comparable_pair
        source,raw=quantity_source('<p>For fiscal year 2025, we produced 80 widgets worldwide.</p>'
            '<p>For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.</p>')
        source=program_source(source);request=requests_from_source(source)[0]
        self.assertEqual(acceptance(source,request,answer(request))['evidence_status'],'PASS')
        self.assertEqual(calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)['result']['value'],'0.8')
        source,raw=quantity_source('<p>For fiscal year 2025, we produced 80 widgets worldwide.</p>'
            '<p>Our plant can manufacture 100 widgets per quarter.</p>')
        source=program_source(source);request=requests_from_source(source)[0]
        self.assertEqual(acceptance(source,request,answer(request))['evidence_status'],'PASS')
        with self.assertRaisesRegex(ValueError,'RELATION_NOT_UNIQUE_OR_UNSUPPORTED'):
            calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)

    def test_native_shapes_remain_source_obligations_without_model_quantity_kinds(self):
        from vnext.capacity_program_roles import quantity_contract
        from vnext.canonical import sha256_bytes
        native={'unit_id':'native-test','kind':'NATIVE_FACTS','payload':{
            'facts':[{'expanded_concept':['http://fasb.org/us-gaap/2025','LineOfCreditFacilityMaximumBorrowingCapacity'],
                'fact':{'ordinal':1,'qualified_name':'us-gaap:LineOfCreditFacilityMaximumBorrowingCapacity','unit_ref':'u','text':'100'}}],
            'units':{'u':{'namespace_environment_id':'env','raw_xml':'<xbrli:unit id="u"><xbrli:measure>iso:USD</xbrli:measure></xbrli:unit>'}},
            'namespace_environments':{'env':{'xbrli':'http://www.xbrl.org/2003/instance','iso':'http://www.xbrl.org/2003/iso4217'}}}}
        good=quantity_contract(units=[native],period={'fiscal_year':2025},scope=None)
        self.assertEqual(len(good['verified_nonphysical_native_roles']),1)
        self.assertEqual(good['implementation_unresolved'],[])
        native['payload']['units']['u']['raw_xml']='<xbrli:unit id="u"><xbrli:measure>units</xbrli:measure></xbrli:unit>'
        for local in ['ProductionQuantity','UnitsProduced','ManufacturingOutput']:
            changed=deepcopy(native)
            changed['payload']['facts'][0]['fact']['qualified_name']='issuer:'+local
            changed['payload']['facts'][0]['expanded_concept']=['https://issuer.example/2025',local]
            self.assertTrue(quantity_contract(units=[changed],period={'fiscal_year':2025},scope=None)['implementation_unresolved'])
        bad=quantity_contract(units=[native],period={'fiscal_year':2025},scope=None)
        self.assertTrue(bad['implementation_unresolved'])
        raw='<ix:continuation id="test">For fiscal year 2025, we produced 80 widgets worldwide.</ix:continuation>'
        supplement={'unit_id':'supplement-test','kind':'NATIVE_SUPPLEMENTS','payload':{'objects':[{
            'raw_xml':raw,'raw_xml_sha256':sha256_bytes(content=raw.encode()),'namespaces':{'ix':'http://www.xbrl.org/2013/inlineXBRL'},'nested_objects':[]}]}}
        checked=quantity_contract(units=[supplement],period={'fiscal_year':2025},scope=None)
        self.assertTrue(checked['implementation_unresolved'])
        self.assertEqual(checked['required_unit_ids'],['supplement-test'])

    def test_current_normal_entry_selects_v6_while_factory_default_stays_v5(self):
        import tempfile
        from vnext import ordinary_update_cycle as cycle,normal_run_v3 as normal
        from unittest.mock import patch
        self.assertNotIn('program_quantity_roles',normal.registered_update_options('B13'))
        with tempfile.TemporaryDirectory() as temporary,patch.object(cycle,'load_requirement_snapshot',return_value={'requirement_closure_hash':'synthetic-runtime'}):
            base=Path(temporary).resolve()
            configuration=cycle._config(base/'history',base/'source','enphase_energy',['B13'],'RECORDED_TEST_ONLY')
            self.assertTrue(configuration['registered_update_options']['program_quantity_roles'])

    def test_finite_refresh_preparation_and_run_share_current_native_contract(self):
        import tempfile
        from contextlib import nullcontext
        from unittest.mock import Mock, patch
        from vnext import ordinary_refresh_cycle as refresh, ordinary_update_cycle as cycle
        from vnext import capacity_update_input as native, normal_run_v3 as normal
        from vnext.continuous_sec_acquisition import SecAcquisitionSession
        for metric in ['B13','D04']:
            with self.subTest(metric=metric), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary).resolve();observed={}
                session=object.__new__(SecAcquisitionSession)
                session.ledger=SimpleNamespace(live=False,root=root/'ledger',locked=nullcontext,
                    snapshot=lambda:{'counts':[0,0,0]})
                session.data_root=session.ledger.root/'source-inputs';session.requirement={}
                session.capture=Mock(side_effect=AssertionError('No source request expected'))
                def prepare(**kwargs):
                    observed['prepared_options']=kwargs['options']
                    self.assertTrue(kwargs['allow_incomplete'])
                    return {'registered_input':{'input_record_id':'synthetic-registered-boundary'}}
                def consume(**kwargs):
                    configuration=cycle._config(kwargs['state_root'],kwargs['source_root'],
                        kwargs['company_id'],kwargs['metric_ids'],kwargs['native_assessment_mode'])
                    observed['run_options']=configuration['registered_update_options']
                    return {'status':'UPDATES_READY','metrics':[]}
                discovery={'status':'SAVED_SOURCE_DEPENDENCIES_AVAILABLE','requirements_id':'synthetic-discovery',
                    'limitations':[],'requirements':[]}
                # The actual coordinator, native preparer dispatch and Run
                # configuration execute. Source/session reads and registered
                # input are doubles: this is routing evidence, not Run credit.
                with patch.object(refresh,'_check_session'), patch.object(refresh,'initialize_source_inputs'), \
                     patch.object(refresh,'_failed_urls',return_value=set()), \
                     patch.object(refresh,'discover_saved_source_requirements',return_value=discovery), \
                     patch.object(native,'prepare_registered_update',side_effect=prepare), \
                     patch.object(refresh,'run_company',side_effect=consume), \
                     patch.object(cycle,'load_requirement_snapshot',return_value={'requirement_closure_hash':'synthetic-runtime'}):
                    result=refresh.refresh_and_process(session=session,state_root=root/'history',
                        company_ids=['enphase_energy'],metric_ids=[metric],max_sec_requests=0,max_provider_requests=1)
                self.assertEqual(result['native_preparations'][0]['status'],'REGISTERED_INPUT_REUSED')
                self.assertEqual(result['status'],'UPDATES_READY')
                self.assertEqual(observed['prepared_options'],observed['run_options'])
                self.assertEqual(observed['prepared_options'],normal.current_registered_update_options(metric,
                    assessment_mode='RECORDED_TEST_ONLY'))
                self.assertEqual(observed['prepared_options'].get('program_quantity_roles',False),metric=='B13')
                self.assertEqual(result['calls'],{'provider':0,'paid':0,'sec':0})
                session.capture.assert_not_called()
        self.assertNotIn('program_quantity_roles',normal.registered_update_options('B13'))
        self.assertEqual(native._LIVE_UPDATE_METRICS,frozenset({'D04'}))

    def test_program_proof_zero_does_not_fill_model_candidate_coverage(self):
        source,_=quantity_source('<p>We operate our plants at less than full capacity.</p>')
        unit=source['units'][0];block=unit['payload']['blocks'][0]
        source['capacity_navigation']=[{'unit_id':unit['unit_id'],'kind':'VISIBLE_BLOCK','source_index':block['block_index']}]
        source['semantic_source_id']=content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'})
        source=program_source(source);request=requests_from_source(source)[0]
        self.assertEqual(request['program_quantity_contract']['verified_quantity_roles'],[])
        with self.assertRaisesRegex(ValueError,'KNOWN_SOURCE_CANDIDATE_NOT_ASSESSED'):acceptance(source,request,answer(request))
