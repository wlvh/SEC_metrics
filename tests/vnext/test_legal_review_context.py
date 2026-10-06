"""Full context, ownership and V1 quote compatibility; no semantic gold labels."""
import json
import unittest
import tarfile
from pathlib import Path

from vnext.legal_review_contract import review_request,validate_answer,LegalReviewContractError
from vnext.legal_review_context import (review_context_request,responsible_reviewed_blocks,
                                       validate_context_answer,CONTRACT)


class LegalContextTest(unittest.TestCase):
    def setUp(self):
        self.document={'source_reference_id':'ref','raw_asset_id':'raw','text_document_id':'doc',
            'blocks':[{'text':s} for s in ('Self-insurance','We accrue for uninsured claims.',
                'Pending litigation is discussed in Note 7.','Ordinary revenue from contracts.') ]}
        self.arguments=dict(company_id='test',target_cik='123',period_end='2024-02-03',document=self.document)
        self.request=review_context_request(**self.arguments,context_pool=[0,1,2,3],
                                           responsibility_pool=[0,1,3],keyword_admitted=[1])

    def answer(self):
        return json.dumps({'decisions':[{'block_id':'b1','decision':'IN_SCOPE',
            'quote':self.document['blocks'][1]['text']},{'block_id':'b2','decision':'IN_SCOPE',
            'quote':self.document['blocks'][2]['text']}],
            'also_in_scope':[{'block_id':'b0','quote':'Self-insurance'}]})

    def test_note_context_stays_visible_but_is_not_counted_twice(self):
        self.assertEqual([b['block_id'] for b in self.request['blocks']],['b0','b1','b2','b3'])
        value=responsible_reviewed_blocks(request=self.request,raw_output=self.answer())
        self.assertEqual(value['in_scope'],['b0','b1','b2'])
        self.assertEqual(value['owned_in_scope'],['b0','b1'])
        self.assertEqual(value['other_responsibility_in_scope'],['b2'])
        self.assertFalse(value['source_responsibility_completeness_proven'])

    def test_unsettled_other_context_cannot_become_a_complete_metric(self):
        answer=json.loads(self.answer());answer['decisions'][1]['decision']='CANNOT_TELL_FROM_THE_TEXT'
        value=responsible_reviewed_blocks(request=self.request,raw_output=json.dumps(answer))
        self.assertIsNone(value['in_scope']);self.assertIsNone(value['owned_in_scope'])
        self.assertEqual(value['unsettled'],['b2'])

    def test_old_checker_does_not_silently_accept_the_new_contract(self):
        with self.assertRaisesRegex(LegalReviewContractError,'REQUEST_IS_NOT_THIS_CONTRACT'):
            validate_answer(request=self.request,raw_output=self.answer())
        old=review_request(**self.arguments,pool=[0,1,2,3],keyword_admitted=[1])
        self.assertNotEqual(old['contract'],CONTRACT)
        validate_answer(request=old,raw_output=self.answer())

    def test_wrong_block_and_overlong_exact_quote_keep_distinct_causes(self):
        wrong=json.loads(self.answer());wrong['decisions'][0]['quote']=self.document['blocks'][2]['text']
        with self.assertRaisesRegex(LegalReviewContractError,'QUOTE_FROM_ANOTHER_BLOCK'):
            validate_context_answer(request=self.request,raw_output=json.dumps(wrong))
        doc={**self.document,'blocks':[{'text':'Legal claims '+('x'*320)}]}
        request=review_context_request(**{**self.arguments,'document':doc},context_pool=[0],
            responsibility_pool=[0],keyword_admitted=[0])
        raw=json.dumps({'decisions':[{'block_id':'b0','decision':'IN_SCOPE','quote':doc['blocks'][0]['text']}],
                        'also_in_scope':[]})
        with self.assertRaisesRegex(LegalReviewContractError,'QUOTE_TOO_LONG'):
            validate_context_answer(request=request,raw_output=raw)

    def test_ownership_outside_full_context_is_rejected(self):
        with self.assertRaisesRegex(LegalReviewContractError,'RESPONSIBILITY_OUTSIDE_CONTEXT'):
            review_context_request(**self.arguments,context_pool=[0,1],responsibility_pool=[2],keyword_admitted=[])


class SavedDeveloperAnswerTest(unittest.TestCase):
    def test_complete_saved_context_keeps_note_responsibility_and_exact_quotes(self):
        path=Path(__file__).parents[1]/'fixtures/d02-context/marriott2023-saved-context.tar.gz'
        with tarfile.open(path) as archive:
            full=json.load(archive.extractfile('full-request.json'))
            original=json.load(archive.extractfile('normal-request.json'))
            answer=archive.extractfile('developer-answer.json').read()
        indices=[int(b['block_id'][1:]) for b in full['blocks']]
        # Only the already supplied request text is used here. Raw HTML and
        # the historical preparer's source checks are a separate integration.
        blocks=[{'text':''} for _ in range(max(indices)+1)]
        for index,block in zip(indices,full['blocks']):blocks[index]={'text':block['text']}
        doc={**full['filing'],'blocks':blocks}
        request=review_context_request(company_id=full['company_id'],target_cik=full['target_cik'],
            period_end=full['period_end'],document=doc,context_pool=indices,
            responsibility_pool=[int(b['block_id'][1:]) for b in original['blocks']],
            keyword_admitted=[int(b[1:]) for b in original['must_decide']])
        self.assertEqual(request['blocks'],full['blocks'])
        self.assertEqual(request['must_decide'],full['must_decide'])
        result=responsible_reviewed_blocks(request=request,raw_output=answer)
        self.assertEqual(len(result['in_scope']),13)
        self.assertEqual(len(result['owned_in_scope']),8)
        self.assertEqual(result['other_responsibility_in_scope'],['b1247','b1248','b1249','b1250','b1253'])


if __name__=='__main__':unittest.main()
