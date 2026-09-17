"""B13 original heading hierarchy and same-block quantity qualifications."""
from copy import deepcopy
import unittest
from types import SimpleNamespace
from tests.vnext.test_capacity_utilization_source import quantity_source
from vnext.capacity_utilization_source import calculate_source_comparable_pair
from vnext.capacity_semantic_review import requests_from_source, validate_response
from vnext.capacity_native_assessment import build_acceptance
from vnext.canonical import content_hash
from vnext.r6_semantic_source import _bytes

P='For fiscal year 2025, we produced 80 widgets worldwide.'
C='For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.'
PAIR='<p>'+P+'</p><p>'+C+'</p>'


def response(source, request, current=True):
    rows=[]
    for unit in source['units']:
        findings=[]
        for block in unit['payload'].get('blocks', []):
            for statement, kind in [(P,'ACTUAL_PRODUCTION'),(C,'AVAILABLE_CAPACITY')]:
                if statement in block['text']:
                    findings.append({'kind':kind if current else 'CONDITIONAL_OR_BOILERPLATE',
                        'subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT' if current else 'CONDITIONAL',
                        'reason':'Synthetic quantity scope test.',
                        'evidence':[{'kind':'VISIBLE_BLOCK','source_index':block['block_index']}]})
        rows.append({'unit_id':unit['unit_id'],'reviewed':True,'findings':findings,'unresolved':[],'calculation_limits':[]})
    return {'request_id':request['request_id'],'units':rows}


class CapacityQuantityScopeTest(unittest.TestCase):
    def assert_nonactual(self, body):
        source,raw=quantity_source(body)
        request=requests_from_source(source)[0]
        good=response(source,request,current=False)
        self.assertEqual(validate_response(request=request,raw_response=_bytes(good))['unresolved'],[])
        prepared=SimpleNamespace(request_bytes=_bytes(request),source_bytes=_bytes(source))
        plan={k:content_hash(value=k) for k in ('selected_representation_hash','ai_invocation_plan_id','source_identity_hash','task_contract_hash')}
        self.assertEqual(build_acceptance(prepared=prepared,plan=plan,response_body=_bytes(good))['evidence_status'],'PASS')
        with self.assertRaisesRegex(ValueError,'QUALIFIED_QUANTITY_CANNOT_ESTABLISH_CURRENT_SOURCE'):
            build_acceptance(prepared=prepared,plan=plan,response_body=_bytes(response(source,request)))
        with self.assertRaisesRegex(ValueError,'RELATION_NOT_UNIQUE_OR_UNSUPPORTED'):
            calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)

    def test_heading_survives_intervening_blocks_lower_heading_and_emphasis(self):
        lead='<h2>Hypothetical example:</h2><p>The following example shows the calculation.</p><p>All figures in this example are assumed.</p>'
        for between in ['', '<h3>Production detail</h3>', '<p><strong>Production detail</strong></p>']:
            with self.subTest(between=between):self.assert_nonactual(lead+between+PAIR)

    def test_same_block_post_qualifier_applies_to_preceding_quantities(self):
        self.assert_nonactual('<p>'+P+' '+C+' These quantities are hypothetical examples, not actual production or available capacity.</p>')

    def test_equal_or_higher_heading_preserves_independent_actual_section(self):
        for closing in ['h2','h1']:
            immediate,immediate_raw=quantity_source('<h2>Hypothetical example:</h2><'+closing+'>Actual production</'+closing+'>'+PAIR)
            self.assertEqual(calculate_source_comparable_pair(source=immediate,raw_bytes_by_id=immediate_raw)['result']['value'],'0.8')
            immediate_request=requests_from_source(immediate)[0]
            self.assertEqual(validate_response(request=immediate_request,raw_response=_bytes(response(immediate,immediate_request)))['unresolved'],[])
            body='<h2>Hypothetical example:</h2><p>For fiscal year 2025, we produced 7 widgets worldwide.</p>'
            body+='<'+closing+'>Actual reported production</'+closing+'>'+PAIR
            source,raw=quantity_source(body)
            result=calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)
            self.assertEqual(result['result']['value'],'0.8')
            request=requests_from_source(source)[0];reply=response(source,request)
            # The earlier 7-widget example is explicitly assessed as conditional.
            unit=source['units'][0]
            b=next(b for b in unit['payload']['blocks'] if '7 widgets' in b['text'])
            reply['units'][0]['findings'].append({'kind':'CONDITIONAL_OR_BOILERPLATE','subject':'TARGET_REGISTRANT',
                'timing':'CONDITIONAL','reason':'Original hypothetical section.',
                'evidence':[{'kind':'VISIBLE_BLOCK','source_index':b['block_index']}]})
            self.assertEqual(validate_response(request=request,raw_response=_bytes(reply))['unresolved'],[])

    def test_legacy_request_is_not_given_new_heading_identity_or_quantity_credit(self):
        source,raw=quantity_source(PAIR)
        old=deepcopy(source);old.pop('quantity_scope_context')
        old['semantic_source_id']=content_hash(value={k:v for k,v in old.items() if k!='semantic_source_id'})
        old_request=requests_from_source(old)[0];new_request=requests_from_source(source)[0]
        self.assertNotIn('quantity_scope_context',old_request)
        self.assertNotEqual(old_request['request_id'],new_request['request_id'])
        self.assertEqual(old['units'],source['units'])
        from vnext.capacity_semantic_review import _restore_units
        self.assertEqual(_restore_units(new_request['units'],new_request['shared_source_dictionaries']),source['units'])
        self.assertEqual(new_request['quantity_scope_context'],source['quantity_scope_context'])
        self.assertTrue(validate_response(request=old_request,raw_response=_bytes(response(old,old_request)))['unresolved'])
        self.assertEqual(validate_response(request=new_request,raw_response=_bytes(response(source,new_request)))['unresolved'],[])
        self.assertEqual(calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)['result']['value'],'0.8')

    def test_post_qualification_does_not_erase_later_actual_quantities_in_same_block(self):
        body='<p>'+P+' '+C+' These quantities are hypothetical examples, not actual production or available capacity. '
        body+=P.replace('80 widgets','90 widgets')+' '+C+'</p>'
        source,raw=quantity_source(body);request=requests_from_source(source)[0]
        self.assertEqual(calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)['result']['value'],'0.9')
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response(source,request)))['unresolved'],[])
        with self.assertRaisesRegex(ValueError,'SOURCE_QUANTITY_CLASSIFICATION_CONFLICT'):
            validate_response(request=request,raw_response=_bytes(response(source,request,current=False)))

    def test_comparison_heading_keeps_scope_unresolved_instead_of_excluding_real_data(self):
        source,raw=quantity_source('<h2>Actual results compared with hypothetical examples</h2>'+PAIR)
        request=requests_from_source(source)[0]
        checked=validate_response(request=request,raw_response=_bytes(response(source,request,current=False)))
        self.assertTrue(checked['unresolved'])
        self.assertEqual(checked['unresolved'][0]['reason'],'B13_QUANTITY_HEADING_SCOPE_UNRESOLVED')
        with self.assertRaisesRegex(ValueError,'HEADING_SCOPE_UNRESOLVED'):
            calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)

    def test_nonheading_introduction_remains_unresolved_until_new_real_section(self):
        lead='<p><strong>Hypothetical example:</strong></p><p>Example setup.</p><p>Assumed figures follow.</p>'
        for extra in ['', '<p><strong>Production detail</strong></p>']:
            source,raw=quantity_source(lead+extra+PAIR);request=requests_from_source(source)[0]
            for current in [True,False]:
                checked=validate_response(request=request,raw_response=_bytes(response(source,request,current=current)))
                self.assertTrue(checked['unresolved'])
                self.assertEqual(checked['unresolved'][0]['reason'],'B13_QUANTITY_NONHEADING_INTRODUCTION_SCOPE_UNRESOLVED')
            with self.assertRaisesRegex(ValueError,'NONHEADING_INTRODUCTION_SCOPE_UNRESOLVED'):
                calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)
        source,raw=quantity_source(lead+'<h2>Actual production</h2>'+PAIR)
        request=requests_from_source(source)[0]
        self.assertEqual(calculate_source_comparable_pair(source=source,raw_bytes_by_id=raw)['result']['value'],'0.8')
        self.assertEqual(validate_response(request=request,raw_response=_bytes(response(source,request)))['unresolved'],[])

    def test_resealed_heading_range_or_text_cannot_pass_original_rebuild(self):
        source,raw=quantity_source('<h2>Actual production</h2>'+PAIR)
        for field,value in [('text','Hypothetical example:'),('level',1),('scope_end_byte',999999)]:
            bad=deepcopy(source)
            next(iter(bad['quantity_scope_context']['documents'].values()))['headings'][0][field]=value
            bad['semantic_source_id']=content_hash(value={k:v for k,v in bad.items() if k!='semantic_source_id'})
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'SCOPE_ORIGINAL_MISMATCH'):
                calculate_source_comparable_pair(source=bad,raw_bytes_by_id=raw)

if __name__=='__main__':unittest.main()
