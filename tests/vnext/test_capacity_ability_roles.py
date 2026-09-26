"""Finite current facility capability stays distinct from annual comparison."""
from copy import deepcopy
import unittest
from tests.vnext.test_capacity_utilization_source import quantity_source
from vnext.capacity_semantic_review import requests_from_source,validate_response
from vnext.capacity_utilization_source import calculate_source_comparable_pair
from vnext.r6_semantic_source import _bytes


def case(text,kind='AVAILABLE_CAPACITY',timing='CURRENT_REPORT',prefix=''):
    source,raw=quantity_source(prefix+'<p>'+text+'</p>');request=requests_from_source(source)[0]
    units=[]
    for unit in source['units']:
        units.append({'unit_id':unit['unit_id'],'reviewed':True,'unresolved':[],'calculation_limits':[],
            'findings':[{'kind':kind,'subject':'TARGET_REGISTRANT','timing':timing,
                'reason':'Synthetic complete original facility capability assertion.',
                'evidence':[{'kind':'VISIBLE_BLOCK','source_index':b['block_index']}]} for b in unit['payload'].get('blocks',[]) if b['text']==text]})
    return source,raw,request,{'request_id':request['request_id'],'units':units}


class CapacityAbilityRolesTest(unittest.TestCase):
    def test_clear_current_ability_preserves_quarterly_capacity_without_ratio(self):
        for text in ['Our plant can manufacture 100 widgets per quarter.',
                     'Our domestic facilities can produce approximately five-million microinverters per month.']:
            source,raw,request,response=case(text)
            self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])
            with self.assertRaisesRegex(ValueError,'RELATION_NOT_UNIQUE_OR_UNSUPPORTED'):
                calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)

    def test_historical_ability_does_not_become_current(self):
        text='In 2024, our plant can manufacture 100 widgets per quarter.'
        _,_,request,response=case(text,timing='HISTORICAL')
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])
        response['units'][0]['findings'][0]['timing']='CURRENT_REPORT'
        with self.assertRaisesRegex(ValueError,'CLASSIFICATION_CONFLICT'):
            validate_response(request=request,raw_response=_bytes(response))

    def test_noncurrent_facility_and_unknown_modifiers_do_not_become_current(self):
        for modifier in ['planned','proposed','future']:
            text='Our '+modifier+' plant can manufacture 100 widgets per quarter.'
            _,_,request,response=case(text,kind='PLANNED_CAPACITY')
            self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])
            response['units'][0]['findings'][0].update(kind='CONDITIONAL_OR_BOILERPLATE',timing='CONDITIONAL')
            with self.assertRaisesRegex(ValueError,'CLASSIFICATION_CONFLICT'):
                validate_response(request=request,raw_response=_bytes(response))
            response['units'][0]['findings'][0].update(kind='AVAILABLE_CAPACITY',timing='CURRENT_REPORT')
            with self.assertRaisesRegex(ValueError,'PHYSICAL_QUANTITY_ROLE_NOT_ESTABLISHED'):
                validate_response(request=request,raw_response=_bytes(response))
        text='Our demonstration plant can manufacture 100 widgets per quarter.'
        for kind in ['AVAILABLE_CAPACITY','OTHER_CONTEXT',None]:
            _,_,request,response=case(text,kind=kind or 'OTHER_CONTEXT')
            if kind is None:response['units'][0]['findings']=[]
            self.assertTrue(validate_response(request=request,raw_response=_bytes(response))['unresolved'])

    def test_firm_plan_native_text_cannot_be_relabelled_as_public_absence(self):
        from tests.vnext.test_capacity_quantity_roles import text_arguments
        from tests.vnext.test_capacity_text_results import CapacityTextResultTest,reseal
        from vnext import capacity_text_results as api
        from vnext.capacity_run import project_defined_absence
        def result(args):return api.replay_text_result(**CapacityTextResultTest.reviewed(self,args))[0]
        text='Our planned plant can manufacture 100 widgets per quarter.'
        self.assertEqual(result(text_arguments(text,'PLANNED_CAPACITY'))['value'],text)
        absence=result(text_arguments('Revenue is recognized when services are delivered.',None))
        args=text_arguments(text,'CONDITIONAL_OR_BOILERPLATE')
        for f in args['assessment']['source_findings']:f['timing']='CONDITIONAL'
        args['assessment']['proposed_branch']='DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
        reseal(args['assessment'],'assessment_set_id')
        with self.assertRaisesRegex(ValueError,'CLASSIFICATION_CONFLICT'):result(args)
        with self.assertRaisesRegex(ValueError,'CLASSIFICATION_CONFLICT'):
            project_defined_absence(case={'registered_input':{'assessment':args['assessment']},
                'selection':{'status':'NOT_AVAILABLE_SEC'},'text_arguments':args},result=absence,row={},
                company={'display_name':'Synthetic fixture','primary_cik':'1463101'})
        _,_,request,response=case(text,kind='CONDITIONAL_OR_BOILERPLATE',timing='CONDITIONAL',prefix='<h2>Hypothetical example:</h2>')
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])

    def test_hypothetical_ability_cannot_become_a_current_plan_or_qualitative_result(self):
        text='Our plant can manufacture 100 widgets per quarter.'
        for kind in ['PLANNED_CAPACITY','CAPACITY_QUALITATIVE','ACTUAL_PRODUCTION']:
            _,_,request,response=case(text,kind=kind,prefix='<h2>Hypothetical example:</h2>')
            with self.assertRaises(ValueError):
                validate_response(request=request,raw_response=_bytes(response))
        from tests.vnext.test_capacity_quantity_roles import text_arguments
        from tests.vnext.test_capacity_text_results import CapacityTextResultTest,reseal
        from vnext import capacity_text_results as api
        from vnext.canonical import content_hash
        args=text_arguments(text,'PLANNED_CAPACITY')
        source,raw,_,_=case(text,prefix='<h2>Hypothetical example:</h2>')
        request=requests_from_source(source)[0]
        source['source_check_scope']='SYNTHETIC_COMPLETE_PRIMARY_TEST_ONLY'
        source['semantic_source_id']=content_hash(value={k:v for k,v in source.items() if k!='semantic_source_id'})
        request=requests_from_source(source)[0]
        unit=source['units'][0];block=next(b for b in unit['payload']['blocks'] if b['text']==text)
        f=args['assessment']['source_findings'][0]
        f.update(unit_id=unit['unit_id'],resolved_evidence=[{'kind':'VISIBLE_BLOCK','source_index':block['block_index'],'text':text}])
        args['assessment'].update(source_id=source['semantic_source_id'],required_request_ids=[request['request_id']],
            completed=[{'request_id':request['request_id'],'candidate':{'selected':{'source_assessment':{'findings':[f]}}}}])
        reseal(args['assessment'],'assessment_set_id')
        args.update(source=source,raw_bytes_by_id=raw,source_references=[d['source_reference'] for d in source['documents']])
        with self.assertRaisesRegex(ValueError,'QUALIFIED_QUANTITY_CANNOT_ESTABLISH_CURRENT_SOURCE'):
            CapacityTextResultTest.reviewed(self,args)

    def test_hypothetical_and_negated_ability_cannot_establish_current_capacity(self):
        text='Our plant can manufacture 100 widgets per quarter.'
        _,_,request,response=case(text,kind='CONDITIONAL_OR_BOILERPLATE',timing='CONDITIONAL',prefix='<h2>Hypothetical example:</h2>')
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response))['unresolved'],[])
        wrong=deepcopy(response);wrong['units'][0]['findings'][0].update(kind='AVAILABLE_CAPACITY',timing='CURRENT_REPORT')
        with self.assertRaisesRegex(ValueError,'QUALIFIED_QUANTITY_CANNOT_ESTABLISH_CURRENT_SOURCE'):
            validate_response(request=request,raw_response=_bytes(wrong))
        _,_,request,response=case('Our plant cannot manufacture 100 widgets per quarter.')
        with self.assertRaisesRegex(ValueError,'PHYSICAL_QUANTITY_ROLE_NOT_ESTABLISHED'):
            validate_response(request=request,raw_response=_bytes(response))
        _,_,request,response=case('If demand increases, our plant can manufacture 100 widgets per quarter.')
        self.assertTrue(validate_response(request=request,raw_response=_bytes(response))['unresolved'])
