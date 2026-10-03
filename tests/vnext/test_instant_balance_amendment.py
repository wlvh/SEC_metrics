"""Actual limited amendments cannot approve changed balances or annual scope."""
import hashlib
import unittest

from tests.vnext import test_annual_amendment_scope as parent_tests
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.instant_balance_amendment import inspect_instant_balance_amendment
from vnext.sources import source_reference_record


class InstantBalanceAmendmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent_tests.AnnualAmendmentScopeTest.setUpClass()
        cls.helper=parent_tests.AnnualAmendmentScopeTest()
        cls.company='paramount_skydance_paramount_global'
        cls.arguments=cls.helper.arguments(cls.company)
        with original_sources_only():cls.result=inspect_instant_balance_amendment(**cls.arguments)

    def changed(self,transform):
        args=dict(self.arguments);source=args['amendment'];raw=transform(source['raw'])
        self.assertNotEqual(raw,source['raw'],'Mutation must change the actual original')
        blob={**source['blob'],'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        old=source['reference']
        ref=source_reference_record(raw_blob=blob,company_id=old['company_id'],source_url=old['source_url'],
            accession=old['accession'],document_name=old['document_name'],source_role=old['source_role'],request_attempt_id=old['request_attempt_id'])
        args['amendment']={**source,'raw':raw,'blob':blob,'reference':ref}
        with original_sources_only():return inspect_instant_balance_amendment(**args)

    def withheld(self,result):
        self.assertEqual('WITHHELD',result['decision'])
        self.assertTrue(result['issues'])

    def test_real_part_iii_and_link_correction_only_support_installed_instant_inputs(self):
        result=self.result
        self.assertEqual('INPUT_PROPERTY_PROVEN',result['decision'],result['issues'])
        self.assertEqual(['B08','B09'],result['metric_ids'])
        self.assertEqual('☐',result['details']['native_correction_flag']['fact']['text'])
        self.assertEqual(3,len(result['details']['conditional_compensation_references']))
        for key in ('source_acquisition_credit','annual_continuity_proven','debt_completeness_proven','metric_result_created','production_authorized'):
            self.assertFalse(result[key])
        with original_sources_only():
            other=inspect_instant_balance_amendment(**self.helper.arguments('southwest_airlines'))
        self.assertEqual('INPUT_PROPERTY_PROVEN',other['decision'])
        # The original, separately used amendment component remains unchanged.
        original=self.helper.pairs[self.company]['scopes'][0]
        self.assertEqual(['FISCAL_EVENT_WINDOW'],original['unchanged_input_classes'])

    def test_extra_note_purpose_and_wrong_original_identity_are_rejected(self):
        for before,after in [
            (b'to amend Part III',b'to correct reported cash and to amend Part III'),
            (b'originally filed with',b'originally restated and filed with'),
            (b'on February 25, 2026',b'on February 24, 2026'),
        ]:
            with self.subTest(after=after):self.withheld(self.changed(lambda raw:raw.replace(before,after,1)))

    def test_financial_correction_elsewhere_cannot_hide_behind_the_scope_note(self):
        for text in [b'We revised our cash balance to $9 billion.',
                     b'The financial statements contained an error that has now been corrected.',
                     b'As of December 31, 2025, current liabilities were $20 billion.',
                     b'Cash was $9 billion at December 31, 2025.']:
            with self.subTest(text=text):
                self.withheld(self.changed(lambda raw:raw.replace(b'</body>',b'<p>'+text+b'</p></body>',1)))

    def test_actual_restatement_cannot_be_disguised_as_a_conditional_compensation_clause(self):
        self.withheld(self.changed(lambda raw:raw.replace(b'without regard to misconduct',
            b'without regard to misconduct, which has occurred this year',1)))

    def test_explicit_cover_error_or_restatement_cannot_keep_original_balance_approval(self):
        scope=self.helper.pairs[self.company]['scopes'][0]
        for index in [48,49]:
            block=scope['amendment']['document']['blocks'][index];a,b=block['raw_start_byte'],block['raw_end_byte']
            def toggle(raw):
                changed=raw[a:b].replace('☐'.encode(),'☒'.encode()).replace(b'&#9744;',b'&#9746;').replace(b'&#x2610;',b'&#x2612;')
                return raw[:a]+changed+raw[b:]
            with self.subTest(index=index):self.withheld(self.changed(toggle))

    def test_quoted_no_statements_sentence_is_not_the_issuers_scope_declaration(self):
        block=self.helper.pairs[self.company]['scopes'][0]['details']['no_new_financial_statement_declarations'][0]
        a,b=block['raw_start_byte'],block['raw_end_byte']
        self.withheld(self.changed(lambda raw:raw[:a]+b'<q>'+raw[a:b]+b'</q>'+raw[b:]))

    def test_added_native_balance_fact_invalidates_the_limited_amendment(self):
        extra=b'<ix:nonFraction xmlns:new="http://fasb.org/us-gaap/2025" name="new:AssetsCurrent" contextRef="c20250101to20251231" unitRef="usd">900</ix:nonFraction>'
        self.withheld(self.changed(lambda raw:raw.replace(b'</body>',extra+b'</body>',1)))


if __name__=='__main__':unittest.main()
