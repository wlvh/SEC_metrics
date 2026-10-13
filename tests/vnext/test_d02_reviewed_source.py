"""D02 source and aggregation controls; constructed answers are not business findings."""
import copy
import json
import unittest

from tests.vnext.test_text_results_v2 import inputs
from tests.vnext.test_text_business_candidates import BODY
from vnext import d02_text_results_v3 as core
from vnext import d02_reviewed_source as consumer
from vnext import legal_review_contract as contract


def fixture(item8=None):
    body=BODY if item8 is None else BODY.replace(
        '<p>The financial statements follow the numbered form items.</p>',item8)
    args=inputs('D02',annual_body=body)
    p=core.prepare_business_text_sources(metric_id='D02',d02_page_furniture=True,**args)
    return args,p


def constructed_review(request,answer):
    decisions,added=contract.validate_answer(request=request,raw_output=json.dumps(answer))
    included,reason,unsettled=contract.reviewed_blocks(request=request,decisions=decisions,added=added)
    return {'record_type':'SAVED_D02_ITEM8_REVIEW_READ',
        **{k:request[k] for k in ('request_id','source_id','company_id','target_cik','period_end','filing')},
        'decisions':decisions,'also_in_scope':added,'included_block_ids':included,
        'withheld_reason':reason,'unsettled_block_ids':unsettled,
        'original_execution_id':'CONSTRUCTED_CONTROL','original_execution_mode':'CONSTRUCTED_CONTROL'}


class ReviewedD02SourceTest(unittest.TestCase):
    def test_changed_company_cik_or_report_end_cannot_retarget_source(self):
        args,p=fixture()
        for key,value in (('company_id','wrong'),('entity','98765'),('period_end','2024-12-31')):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'DOCUMENT_COORDINATE_CHANGED'):
                consumer.item8_requests(prepared=p,target={**args['target'],key:value})
    def test_full_item8_pool_contains_non_keyword_blocks(self):
        args,p=fixture('<p>We face litigation pending in court.</p><p>Our operating lease terms are described here.</p>')
        request=consumer.item8_requests(prepared=p,target=args['target'])[0]
        self.assertEqual(2,len(request['blocks']))
        self.assertEqual(1,len(request['must_decide']))

    def test_empty_subanswer_preserves_complete_item3_and_notes(self):
        args,p=fixture();before=copy.deepcopy(p)
        request=consumer.item8_requests(prepared=p,target=args['target'])[0]
        answer=constructed_review(request,{'decisions':[],'also_in_scope':[]})
        after=consumer.apply_saved_reviews(prepared=p,target=args['target'],reviews=[answer])
        sid=next(iter(p['proposals']))
        self.assertEqual(p['proposals'][sid]['D02']['candidates'],after['proposals'][sid]['D02']['candidates'])
        self.assertTrue(after['proposals'][sid]['D02']['candidates'])
        self.assertEqual(p['proposals'][sid]['D03'],after['proposals'][sid]['D03'])
        self.assertEqual(before,p)
        prepared=core.prepare_business_text_sources(metric_id='D02',d02_page_furniture=True,
            d02_saved_reviews=[answer],**args)
        self.assertEqual(after,prepared)
        from pathlib import Path
        from vnext.specs import compile_spec_file
        spec=compile_spec_file(path=Path(core.__file__).resolve().parents[2]/
            'catalog/r6/D02_legal_disclosures_v1.md',dependency_specs={})
        candidate=core.create_deterministic_text_candidate(compiled_spec=spec,
            d02_page_furniture=True,d02_saved_reviews=[answer],**args)
        evidence=core.build_text_evidence(compiled_spec=spec,candidate=candidate,
            d02_page_furniture=True,d02_saved_reviews=[answer],**args)
        self.assertEqual('PASS',evidence['status'])
        with self.assertRaisesRegex(ValueError,'CANDIDATE_REPLAY_CHANGED'):
            core.build_text_evidence(compiled_spec=spec,candidate=candidate,
                d02_page_furniture=True,**args)

    def test_in_out_and_additional_blocks_replace_only_item8(self):
        args,p=fixture('<p>We face litigation pending in court.</p><p>Our operating lease terms are described here.</p>')
        request=consumer.item8_requests(prepared=p,target=args['target'])[0]
        first,second=request['blocks']
        # This intentionally constructed addition tests mechanics, not legal relevance.
        answer=constructed_review(request,{'decisions':[{'block_id':first['block_id'],
            'decision':'OUT_OF_SCOPE','quote':None}],
            'also_in_scope':[{'block_id':second['block_id'],'quote':second['text']}]})
        after=consumer.apply_saved_reviews(prepared=p,target=args['target'],reviews=[answer])
        sid=next(iter(p['proposals']))
        old=[c for c in p['proposals'][sid]['D02']['candidates'] if c['section_id']!='ITEM_8']
        new=[c for c in after['proposals'][sid]['D02']['candidates'] if c['section_id']!='ITEM_8']
        self.assertEqual(old,new)
        self.assertEqual([second['text']],[c['text'] for c in after['proposals'][sid]['D02']['candidates'] if c['section_id']=='ITEM_8'])

    def test_missing_duplicate_foreign_and_unsettled_refuse_partial_aggregation(self):
        args,p=fixture();request=consumer.item8_requests(prepared=p,target=args['target'])[0]
        answer=constructed_review(request,{'decisions':[],'also_in_scope':[]})
        for answers,reason in (([],'COMPLETE_ANSWER_SET'),([answer,answer],'DUPLICATED'),
                ([{**answer,'company_id':'wrong'}],'CURRENT_REQUEST_DIFFERS')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):
                consumer.apply_saved_reviews(prepared=p,target=args['target'],reviews=answers)
        args,p=fixture('<p>We face litigation pending in court.</p>')
        request=consumer.item8_requests(prepared=p,target=args['target'])[0];block=request['blocks'][0]
        answer=constructed_review(request,{'decisions':[{'block_id':block['block_id'],
            'decision':'CANNOT_TELL_FROM_THE_TEXT','quote':block['text']}],'also_in_scope':[]})
        with self.assertRaises(contract.LegalReviewUnsettled):
            consumer.apply_saved_reviews(prepared=p,target=args['target'],reviews=[answer])

    def test_note_inside_item8_requires_exact_note_ownership(self):
        body=BODY.replace('<h2>Item 9. Changes in and Disagreements with Accountants</h2><p>None.</p>','')
        body+='<h2>Item 9. Changes in and Disagreements with Accountants</h2><p>None.</p>'
        args=inputs('D02',annual_body=body)
        p=core.prepare_business_text_sources(metric_id='D02',**args)
        with self.assertRaisesRegex(ValueError,'OWNERSHIP_NOT_MIGRATED') as error:
            consumer.item8_requests(prepared=p,target=args['target'])
        self.assertEqual('IMPLEMENTATION_REQUIRED',error.exception.category)
