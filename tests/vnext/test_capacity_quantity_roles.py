"""Physical roles cannot come from labels; quarterly capacity is not annualized."""
import unittest
from tests.vnext.test_capacity_utilization_source import quantity_source
from vnext.capacity_semantic_review import requests_from_source,validate_response
from vnext.capacity_utilization_source import calculate_source_comparable_pair
from vnext.r6_semantic_source import _bytes

QUARTER='We continued to operate our domestic manufacturing footprint, including our in-house manufacturing facility and our partnership with an external manufacturer. These arrangements maintained a combined manufacturing capacity of approximately five-million microinverters per quarter.'


def assessment(text,kind,subject='TARGET_REGISTRANT'):
    source,raw=quantity_source('<p>'+text+'</p>')
    request=requests_from_source(source)[0]
    units=[]
    for unit in source['units']:
        blocks=unit.get('payload',{}).get('blocks',[])
        units.append({'unit_id':unit['unit_id'],'reviewed':True,'unresolved':[],'calculation_limits':[],
            'findings':[{'kind':kind,'subject':subject,'timing':'CURRENT_REPORT','reason':'Synthetic source role test.',
                'evidence':[{'kind':'VISIBLE_BLOCK','source_index':b['block_index']}]} for b in blocks]})
    response={'request_id':request['request_id'],'units':units}
    return source,raw,request,response


def text_arguments(text,kind):
    from vnext.canonical import content_hash
    from vnext.normal_source_authority import ROOT
    from vnext.specs import compile_spec_file
    source,raw,request,response=assessment(text,kind or 'OTHER_CONTEXT')
    source['source_check_scope']='SYNTHETIC_COMPLETE_PRIMARY_TEST_ONLY'
    source['semantic_source_id']=content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'})
    request=requests_from_source(source)[0]
    findings=[]
    if kind:
        for unit in source['units']:
            for b in unit['payload'].get('blocks',[]):
                findings.append({'unit_id':unit['unit_id'],'kind':kind,'subject':'TARGET_REGISTRANT',
                    'timing':'CURRENT_REPORT','reason':'Synthetic native role test.',
                    'resolved_evidence':[{'kind':'VISIBLE_BLOCK','source_index':b['block_index'],'text':b['text']}]})
    body={'record_type':'B13_NATIVE_SOURCE_ASSESSMENT_SET','source_id':source['semantic_source_id'],
        'company_id':source['company_id'],'required_request_ids':[request['request_id']],
        'completed':[{'request_id':request['request_id'],'candidate':{'selected':{'source_assessment':{'findings':findings}}}}],
        'all_source_requests_accepted':True,'missing_request_ids':[],'failed_requests':[],
        'proposed_branch':('TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW' if findings else 'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'),
        'source_findings':findings,'mode':'RECORDED_TEST_ONLY'}
    body['assessment_set_id']=content_hash(value=body)
    spec=compile_spec_file(path=ROOT/'catalog/r5/B13_capacity_disclosures_v1.md',dependency_specs={})
    annual=source['prepared_annual_input'];period=annual['table_input']['target_period'];scope=spec['compiled']['required_claims']
    target={'company_id':source['company_id'],'entity':annual['entity'],'accession':annual['filing']['accessionNumber'],
        'period_start':period['period_start'],'period_end':period['period_end'],'scope':scope,'scope_key':content_hash(value=scope)}
    return {'compiled_spec':spec,'target':target,'source':source,'assessment':body,
        'source_references':[d['source_reference'] for d in source['documents']],'raw_bytes_by_id':raw}


class CapacityQuantityRolesTest(unittest.TestCase):
    def test_qualitative_production_is_not_a_quantity(self):
        for text in ['For example, in 2025, our production was disrupted by fires at a supplier.',
                     'Structural costs typically do not have a directly proportionate relationship to production volume.']:
            _,_,request,response=assessment(text,'ACTUAL_PRODUCTION')
            with self.assertRaisesRegex(ValueError,'PHYSICAL_QUANTITY_ROLE_NOT_ESTABLISHED'):
                validate_response(request=request,raw_response=_bytes(response))
            response['units'][0]['findings'][0]['kind']='OTHER_CONTEXT'
            self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])

    def test_quarterly_arrangements_role_is_preserved_without_annualization(self):
        source,raw,request,response=assessment(QUARTER,'AVAILABLE_CAPACITY')
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])
        wrong={**response,'units':[{**response['units'][0],'findings':[{**response['units'][0]['findings'][0],'kind':'OTHER_CONTEXT'}]}]}
        with self.assertRaisesRegex(ValueError,'SOURCE_PHYSICAL_QUANTITY_CLASSIFICATION_CONFLICT'):
            validate_response(request=request,raw_response=_bytes(wrong))
        with self.assertRaisesRegex(ValueError,'RELATION_NOT_UNIQUE_OR_UNSUPPORTED'):
            calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)

    def test_operating_antecedent_dates_its_quantity_without_dating_cause_or_later_shipping(self):
        historical=QUARTER.replace('We continued','In 2024, we continued')
        _,_,request,response=assessment(historical,'AVAILABLE_CAPACITY')
        with self.assertRaisesRegex(ValueError,'CLASSIFICATION_CONFLICT'):
            validate_response(request=request,raw_response=_bytes(response))
        response['units'][0]['findings'][0]['timing']='HISTORICAL'
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])
        for text in ['To mitigate 2024 tariffs, '+QUARTER[0].lower()+QUARTER[1:],
                     QUARTER+' In 2024, we began shipping other products.']:
            _,_,request,response=assessment(text,'AVAILABLE_CAPACITY')
            self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])
        _,_,request,response=assessment('Following developments in 2024, '+QUARTER[0].lower()+QUARTER[1:],'AVAILABLE_CAPACITY')
        self.assertTrue(validate_response(request=request,raw_response=_bytes(response))['unresolved'])

    def test_unsupported_quantity_is_implementation_unresolved(self):
        _,_,request,response=assessment('We produced a total of 80 widgets in the first quarter.','ACTUAL_PRODUCTION')
        checked=validate_response(request=request,raw_response=_bytes(response))
        self.assertTrue(any(u['reason']=='B13_PHYSICAL_QUANTITY_ROLE_SYNTAX_OR_SCOPE_UNSUPPORTED' for u in checked['unresolved']))

    def test_unsupported_source_quantity_cannot_be_erased_by_other_or_missing_finding(self):
        from vnext import capacity_text_results as api
        from vnext.capacity_run import project_defined_absence
        from tests.vnext.test_capacity_text_results import CapacityTextResultTest,reseal
        def result(args):return api.replay_text_result(**CapacityTextResultTest.reviewed(self,args))[0]
        absence=result(text_arguments('Revenue is recognized when services are delivered.',None))
        for text in ['We produced a total of 80 widgets in the first quarter.',
                     'Our manufacturing capacity was approximately 150 widgets per month.',
                     'Our production volume totaled 80 widgets in the first quarter.',
                     'Our available production capacity amounted to 150 widgets per month.',
                     'We produced 80 of these widgets in 2025.']:
            role='ACTUAL_PRODUCTION' if 'production volume' in text or text.startswith('We produced') else 'AVAILABLE_CAPACITY'
            for label in [role,'OTHER_CONTEXT',None]:
                _,_,request,response=assessment(text,label or 'OTHER_CONTEXT')
                if label is None:response['units'][0]['findings']=[]
                checked=validate_response(request=request,raw_response=_bytes(response))
                self.assertTrue(checked['unresolved'])
                args=text_arguments(text,label)
                with self.assertRaisesRegex(ValueError,'QUANTITY_SCOPE_UNRESOLVED'):result(args)
                args['assessment']['proposed_branch']='DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
                reseal(args['assessment'],'assessment_set_id')
                with self.assertRaisesRegex(ValueError,'QUANTITY_SCOPE_UNRESOLVED'):
                    project_defined_absence(case={'registered_input':{'assessment':args['assessment']},
                        'selection':{'status':'NOT_AVAILABLE_SEC'},'text_arguments':args},result=absence,row={},
                        company={'display_name':'Synthetic fixture','primary_cik':'1463101'})

    def test_nonquantity_dates_model_names_and_cancelled_plans_do_not_create_amounts(self):
        text='In December 2025, we announced plans to rationalize manufacturing capacity, including cancelling three previously planned product programs and ending production of the current generation F-150 model.'
        _,_,request,response=assessment(text,'CAPACITY_QUALITATIVE')
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])

    def test_industry_assertion_does_not_become_company_capacity(self):
        for text in ['The global automotive industry is intensely competitive, with installed manufacturing capacity generally exceeding current demand.',
                     'These developments could extend underutilization of EV production capacity across the industry.']:
            _,_,request,response=assessment(text,'CAPACITY_QUALITATIVE')
            with self.assertRaisesRegex(ValueError,'INDUSTRY_CAPACITY_IS_NOT_TARGET_CAPACITY'):
                validate_response(request=request,raw_response=_bytes(response))
            response['units'][0]['findings'][0]['subject']='OTHER_ENTITY'
            self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])

    def test_historical_company_assertion_does_not_unlock_current_industry(self):
        text='The global automotive industry has installed manufacturing capacity that exceeds demand. Our manufacturing capacity was discontinued in 2024.'
        _,_,request,response=assessment(text,'CAPACITY_QUALITATIVE')
        with self.assertRaisesRegex(ValueError,'INDUSTRY_CAPACITY_IS_NOT_TARGET_CAPACITY'):
            validate_response(request=request,raw_response=_bytes(response))
        response['units'][0]['findings'][0]['timing']='HISTORICAL'
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])

    def test_native_records_and_public_absence_repeat_source_role_checks(self):
        from vnext import capacity_text_results as api
        from vnext.capacity_run import project_defined_absence
        from tests.vnext.test_capacity_text_results import CapacityTextResultTest,reseal
        def result(args):return api.replay_text_result(**CapacityTextResultTest.reviewed(self,args))[0]
        absence=result(text_arguments('Revenue is recognized when services are delivered.',None))
        self.assertEqual(result(text_arguments(QUARTER,'AVAILABLE_CAPACITY'))['value'],QUARTER)
        for text,kind,error in [
            ('In 2025, our production was disrupted by a supplier fire.','ACTUAL_PRODUCTION','PHYSICAL_QUANTITY_ROLE_NOT_ESTABLISHED'),
            ('The global automotive industry has excess manufacturing capacity.','CAPACITY_QUALITATIVE','INDUSTRY_CAPACITY_IS_NOT_TARGET_CAPACITY')]:
            args=text_arguments(text,kind)
            with self.assertRaisesRegex(ValueError,error):result(args)
            args['assessment']['proposed_branch']='DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
            reseal(args['assessment'],'assessment_set_id')
            with self.assertRaisesRegex(ValueError,error):
                project_defined_absence(case={'registered_input':{'assessment':args['assessment']},
                    'selection':{'status':'NOT_AVAILABLE_SEC'},'text_arguments':args},result=absence,row={},
                    company={'display_name':'Synthetic fixture','primary_cik':'1463101'})

    def test_mixed_company_assertion_keeps_target_capacity(self):
        _,_,request,response=assessment('The industry has excess production capacity. Our manufacturing capacity remains available.','CAPACITY_QUALITATIVE')
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])
