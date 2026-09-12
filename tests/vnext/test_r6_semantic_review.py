"""Actual-source response protocol; positive shape is not semantic approval."""
import copy
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.r6_semantic_source import prepare_d04_semantic_source
from vnext.r6_semantic_review import requests_from_source,validate_response,assemble_recorded_responses,inspect_recorded_responses
from vnext.canonical import content_hash,sha256_bytes
from vnext.r6_semantic_source import _bytes,_compact_supplements


def encoded(value):return json.dumps(value,ensure_ascii=False).encode('utf-8')


class R6SemanticReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():cls.source=prepare_d04_semantic_source(repo_root=ROOT,company_id='enphase_energy')
        cls.requests=requests_from_source(cls.source);cls.responses={};cls.signal=None
        for request in cls.requests:
            rows=[]
            for unit in request['units']:
                findings=[]
                if unit['kind']=='VISIBLE_TEXT':
                    for block in unit['payload']['blocks']:
                        if block['block_index'] in request['document_context']['language_candidate_block_indices']:
                            # Inspectable original describes suppliers/distributors,
                            # not the target's own ability to continue operating.
                            assert 'our suppliers, distributors or other partners' in block['text']
                            findings.append({'kind':'OTHER_ENTITY','subject':'OTHER_ENTITY','timing':'CONDITIONAL',
                                'evidence':[{'kind':'VISIBLE_BLOCK','source_index':block['block_index'],'text':block['text']}],
                                'reason':'Recorded test interpretation of the explicitly named suppliers and partners.'})
                            cls.signal=(request['request_id'],unit['unit_id'],block['block_index'])
                rows.append({'unit_id':unit['unit_id'],'reviewed':True,'findings':findings,'unresolved':[]})
            cls.responses[request['request_id']]={'request_id':request['request_id'],'units':rows}
        assert cls.signal is not None

    def signal_case(self):
        rid,uid,index=self.signal
        request=next(r for r in self.requests if r['request_id']==rid)
        response=copy.deepcopy(self.responses[rid]);row=next(r for r in response['units'] if r['unit_id']==uid)
        return request,response,row

    def test_every_visible_block_and_native_fact_is_supplied_without_keyword_selection(self):
        source=self.source;native=[u for u in source['units'] if u['kind']=='NATIVE_FACTS']
        self.assertEqual(1839,sum(len(u['payload']['facts']) for u in native))
        self.assertTrue(any(u['kind']=='NATIVE_SUPPLEMENTS' for u in source['units']))
        self.assertEqual(source['required_unit_ids'],[u['unit_id'] for r in self.requests for u in r['units']])
        self.assertFalse(source['semantic_coverage_verified']);self.assertFalse(source['provider_request_created'])
        for request in self.requests:
            self.assertEqual(request['target_period']['fiscal_year'],request['fiscal_label_context']['selected_fiscal_year'])
            self.assertEqual(source['prepared_annual_input']['fiscal_year_label_resolution']['original_dei_fiscal_year'],
                             request['fiscal_label_context']['original_dei_fiscal_year'])
        for unit in native:
            for f in unit['payload']['facts']:
                self.assertIn(f['fact']['context_ref'],unit['payload']['contexts'])
                if f['fact']['unit_ref']:self.assertIn(f['fact']['unit_ref'],unit['payload']['units'])

    def test_complete_recorded_responses_remain_unqualified_proposals(self):
        raw={key:encoded(value) for key,value in self.responses.items()}
        with original_sources_only():result=inspect_recorded_responses(repo_root=ROOT,company_id='enphase_energy',response_bytes_by_request_id=raw)
        self.assertTrue(result['all_source_units_responded'])
        self.assertEqual('NO_DOUBT_DISCLOSED',result['model_proposed_interpretation'])
        for key in ['semantic_correctness_verified','semantic_qualification_passed','provider_execution_proven','native_result_created','production_authorized']:
            self.assertFalse(result[key])
        self.assertEqual({'provider':0,'paid':0,'sec':0},result['calls'])

    def test_missing_request_unit_or_duplicate_review_cannot_create_absence(self):
        raw={key:encoded(value) for key,value in self.responses.items()};raw.pop(next(iter(raw)))
        with self.assertRaisesRegex(ValueError,'REQUEST_SET_INCOMPLETE'):
            assemble_recorded_responses(source=self.source,response_bytes_by_request_id=raw)
        request,response,row=self.signal_case();response['units'].pop()
        with self.assertRaisesRegex(ValueError,'UNIT_SET_INCOMPLETE'):validate_response(request=request,raw_response=encoded(response))
        request,response,row=self.signal_case();response['units'].append(copy.deepcopy(row))
        with self.assertRaisesRegex(ValueError,'UNIT_SET_INCOMPLETE'):validate_response(request=request,raw_response=encoded(response))

    def test_known_source_language_cannot_be_hidden_in_a_no_finding_response(self):
        request,response,row=self.signal_case();row['findings']=[]
        with self.assertRaisesRegex(ValueError,'KNOWN_SOURCE_CANDIDATE_NOT_ASSESSED'):
            validate_response(request=request,raw_response=encoded(response))

    def test_changed_text_or_foreign_source_index_is_rejected(self):
        for field,value in [('text','The target has no substantial doubt.'),('source_index',999999)]:
            request,response,row=self.signal_case();row['findings'][0]['evidence'][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'EXACT_SOURCE_TEXT_CHANGED|EVIDENCE_OUTSIDE_SUPPLIED_UNIT'):
                validate_response(request=request,raw_response=encoded(response))

    def test_exact_substring_uses_character_offsets_and_cannot_escape_the_source(self):
        request,response,row=self.signal_case();evidence=row['findings'][0]['evidence'][0]
        text=evidence['text'];start=text.index('our suppliers');end=text.index(', including')
        evidence.update(text=text[start:end])
        checked=validate_response(request=request,raw_response=encoded(response))
        found=checked['findings'][0]['resolved_evidence'][0]
        self.assertEqual((start,end),(found['start_character'],found['end_character']))
        self.assertFalse(checked['semantic_correctness_verified'])
        evidence['text']='ability to'
        with self.assertRaisesRegex(ValueError,'QUOTE_NOT_UNIQUE'):validate_response(request=request,raw_response=encoded(response))

    def test_contained_native_xml_is_retained_once_with_exact_child_reconstruction(self):
        xml='<ix:continuation id="outer"><ix:continuation id="inner">a;b</ix:continuation></ix:continuation>'
        child='<ix:continuation id="inner">a;b</ix:continuation>';start=xml.index(child)
        objects=[{'start_character':100,'end_character':100+len(xml),'raw_xml':xml},
                 {'start_character':100+start,'end_character':100+start+len(child),'raw_xml':child}]
        packed=_compact_supplements(objects);self.assertEqual(1,len(packed))
        nested=packed[0]['nested_objects'][0]
        self.assertEqual(child,packed[0]['raw_xml'][nested['relative_start_character']:nested['relative_end_character']])
        wrong=copy.deepcopy(objects);wrong[1]['raw_xml']=child.replace(';',';')
        with self.assertRaisesRegex(ValueError,'NESTED_NATIVE_XML_CHANGED'):_compact_supplements(wrong)

    def test_current_target_classification_cannot_use_other_entity_or_historical_scope(self):
        for changed in [{'kind':'DOUBT_DISCLOSED'},{'kind':'DOUBT_DISCLOSED','subject':'TARGET_REGISTRANT','timing':'HISTORICAL'}]:
            request,response,row=self.signal_case();row['findings'][0].update(changed)
            with self.assertRaisesRegex(ValueError,'CURRENT_TARGET_CATEGORY_CONFLICT'):
                validate_response(request=request,raw_response=encoded(response))

    def test_quoted_current_assertion_is_rejected_by_host_owned_source_context(self):
        # Protocol branch only; quotation ranges are produced by the source
        # parser, never accepted from a provider response or used as SEC credit.
        request,response,row=self.signal_case();request=copy.deepcopy(request)
        _,uid,index=self.signal;unit=next(u for u in request['units'] if u['unit_id']==uid)
        next(b for b in unit['payload']['blocks'] if b['block_index']==index)['html_quotation_context']=True
        raw=_bytes(unit['payload']);unit['payload_sha256']=sha256_bytes(content=raw);unit['payload_bytes']=len(raw)
        unit['unit_id']=content_hash(value={k:v for k,v in unit.items() if k!='unit_id'})
        row['unit_id']=unit['unit_id']
        request['request_id']=content_hash(value={k:v for k,v in request.items() if k!='request_id'})
        response['request_id']=request['request_id']
        row['findings'][0].update(kind='DOUBT_DISCLOSED',subject='TARGET_REGISTRANT',timing='CURRENT_REPORT')
        with self.assertRaisesRegex(ValueError,'QUOTED_TEXT_CANNOT_ALONE'):
            validate_response(request=request,raw_response=encoded(response))

    def test_conflicting_current_categories_require_joint_interpretation(self):
        changed=copy.deepcopy(self.responses);rid,uid,index=self.signal
        row=next(r for r in changed[rid]['units'] if r['unit_id']==uid)
        first=row['findings'][0];first.update(kind='DOUBT_DISCLOSED',subject='TARGET_REGISTRANT',timing='CURRENT_REPORT')
        second=copy.deepcopy(first);second['kind']='NO_DOUBT_DECLARATION';row['findings'].append(second)
        result=assemble_recorded_responses(source=self.source,response_bytes_by_request_id={k:encoded(v) for k,v in changed.items()})
        self.assertEqual('UNRESOLVED',result['model_proposed_interpretation'])
        self.assertEqual('MULTIPLE_CURRENT_CLASSIFICATIONS_REQUIRE_JOINT_INTERPRETATION',result['unresolved'][0]['reason'])
        self.assertFalse(result['semantic_correctness_verified'])

    def test_wrong_request_or_duplicate_json_keys_is_not_an_interpretation(self):
        request,response,row=self.signal_case();response['request_id']='sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError,'REQUEST_BINDING'):validate_response(request=request,raw_response=encoded(response))
        raw=b'{"request_id":"x","request_id":"x","units":[]}'
        with self.assertRaisesRegex(ValueError,'Duplicate JSON key'):validate_response(request=request,raw_response=raw)

    def test_changed_host_request_or_unit_cannot_keep_its_old_binding(self):
        request,response,row=self.signal_case();request=copy.deepcopy(request)
        request['target_cik']='1'
        with self.assertRaisesRegex(ValueError,'HOST_REQUEST_CHANGED'):
            validate_response(request=request,raw_response=encoded(response))
        request,response,row=self.signal_case();request=copy.deepcopy(request)
        request['units'][0]['payload_bytes']+=1
        request['request_id']=content_hash(value={k:v for k,v in request.items() if k!='request_id'})
        response['request_id']=request['request_id']
        with self.assertRaisesRegex(ValueError,'HOST_SOURCE_UNIT_CHANGED'):
            validate_response(request=request,raw_response=encoded(response))

    def test_invalid_unit_id_type_and_blank_quote_are_schema_failures(self):
        request,response,row=self.signal_case();row['unit_id']=[]
        with self.assertRaisesRegex(ValueError,'UNIT_REVIEW_MISSING_OR_DUPLICATE'):
            validate_response(request=request,raw_response=encoded(response))
        request,response,row=self.signal_case();row['findings'][0]['evidence'][0]['text']=' '
        with self.assertRaisesRegex(ValueError,'QUOTE_RANGE_INVALID'):
            validate_response(request=request,raw_response=encoded(response))


if __name__=='__main__':unittest.main()
