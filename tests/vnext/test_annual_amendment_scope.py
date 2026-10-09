"""Actual amendment pairs and original-byte contradictory-scope probes."""
import copy
import hashlib
from pathlib import Path
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.annual_amendment_scope import (prepare_saved_amendment_scopes,inspect_annual_amendment_scope,
    prepare_saved_amendment_input, POLICY_PATH)
from vnext.sources import raw_blob_record,source_reference_record


class AnnualAmendmentScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.pairs={name:prepare_saved_amendment_scopes(repo_root=ROOT,company_id=name)
                for name in ('southwest_airlines','paramount_skydance_paramount_global')}

    def arguments(self,company='southwest_airlines'):
        packet=self.pairs[company];scope=packet['scopes'][0]
        result={}
        for key in ('original','amendment'):
            source=scope[key]
            proof=next(p for p in packet['source_proofs'] if p['content_sha256']==source['raw_sha256'])
            blob=raw_blob_record(repo_root=ROOT,repo_relative_path=proof['request_repo_relative_path'],media_type='text/html')
            result[key]={'raw':(ROOT/proof['request_repo_relative_path']).read_bytes(),'blob':blob,
                'reference':source['source_reference'],'filing':source['filing']}
        result.update(company_id=company,cik=packet['prepared_input']['entity'])
        return result

    def changed(self,transform,company='southwest_airlines'):
        args=self.arguments(company);item=args['amendment'];raw=transform(item['raw'])
        self.assertTrue(raw!=item['raw'],'Source mutation did not change the original bytes')
        blob={**item['blob'],'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        old=item['reference']
        reference=source_reference_record(raw_blob=blob,company_id=company,source_url=old['source_url'],
            accession=old['accession'],document_name=old['document_name'],source_role=old['source_role'],request_attempt_id=old['request_attempt_id'])
        args['amendment']={**item,'raw':raw,'blob':blob,'reference':reference}
        with original_sources_only():return inspect_annual_amendment_scope(**args)

    def assert_financial_scope_unproven(self,result):
        self.assertNotIn('ORIGINAL_STATEMENT_VALUES',result['unchanged_input_classes'])
        self.assertTrue(result['original_statement_admission_requires_further_review'])
        self.assertFalse(result['source_acquisition_credit'])
        self.assertFalse(result['native_run_created'])

    def test_real_link_correction_is_proved_by_cover_item15_links_and_signature(self):
        result=self.pairs['southwest_airlines']['scopes'][0]
        self.assertEqual('EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15',result['classification'])
        self.assertEqual({'FISCAL_EVENT_WINDOW','ORIGINAL_STATEMENT_VALUES'},set(result['unchanged_input_classes']))
        self.assertEqual(3,len(result['details']['changed_link_texts']))
        self.assertTrue(result['details']['item15_visible_text_equal'])
        self.assertTrue(result['details']['remaining_body_is_part_iv_and_bound_signature'])
        self.assertEqual(['false'],result['amendment']['raw_amendment_flag_values'])
        self.assertFalse(result['production_authorized'])

    def test_part_iii_is_not_blanket_financial_or_governance_approval(self):
        result=self.pairs['paramount_skydance_paramount_global']['scopes'][0]
        self.assertEqual('PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS',result['classification'])
        self.assertEqual(['FISCAL_EVENT_WINDOW'],result['unchanged_input_classes'])
        self.assert_financial_scope_unproven(result)
        self.assertTrue({'B06','C02','C03','C04'}<=set(result['not_covered_metric_ids']))

    def test_changed_credit_amount_in_copied_exhibit_text_cannot_inherit_no_change(self):
        result=self.changed(lambda raw:raw.replace(b'$1,000,000,000',b'$2,000,000,000',1))
        self.assertFalse(result['details']['item15_visible_text_equal'])
        self.assert_financial_scope_unproven(result)

    def test_an_additional_purpose_is_not_hidden_by_the_no_change_disclaimer(self):
        result=self.changed(lambda raw:raw.replace(b'Unless expressly stated,',b'This Amendment also corrects reported revenue. Unless expressly stated,',1))
        self.assertFalse(result['details']['complete_note_has_only_link_correction_and_certifications'])
        self.assert_financial_scope_unproven(result)

    def test_an_earlier_extra_purpose_cannot_hide_before_the_link_correction(self):
        result=self.changed(lambda raw:raw.replace(b'to correct the hyperlink',
            b'to revise reported revenue and to correct the hyperlink',1))
        self.assertFalse(result['details']['note_subject_period_and_amendment_number_match_source'])
        self.assert_financial_scope_unproven(result)

    def test_note_must_identify_the_changed_exhibit_and_actual_original_period(self):
        for before,after,field in [
            (b'for Exhibit 3.2,',b'for Exhibit 10.2,','declared_exhibit_matches_changed_link_row'),
            (b'for the fiscal year ended December 31, 2025',b'for the fiscal year ended December 31, 2024',
             'note_subject_period_and_amendment_number_match_source'),
            (b'is filing this Amendment No. 1',b'is filing this Amendment No. 2',
             'note_subject_period_and_amendment_number_match_source'),
        ]:
            with self.subTest(after=after):
                result=self.changed(lambda raw:raw.replace(before,after,1))
                self.assertFalse(result['details'][field])
                self.assert_financial_scope_unproven(result)

    def test_quoted_explanation_does_not_describe_current_amendment_scope(self):
        block=self.pairs['southwest_airlines']['scopes'][0]['explanatory_note']['blocks'][1]
        a,b=block['raw_start_byte'],block['raw_end_byte']
        result=self.changed(lambda raw:raw[:a]+b'<q>'+raw[a:b]+b'</q>'+raw[b:])
        self.assertEqual('UNRESOLVED',result['classification'])
        self.assert_financial_scope_unproven(result)

    def test_extra_body_or_signature_prose_is_not_discarded(self):
        part=next(b for b in self.pairs['southwest_airlines']['scopes'][0]['amendment']['document']['blocks'] if b['text']=='PART IV')
        def inserted_section(raw):
            start=raw.rfind(b'<div',0,part['raw_start_byte'])
            self.assertGreaterEqual(start,0)
            return raw[:start]+b'<div>PART II</div><p>Revenue is revised to ten million.</p>'+raw[start:]
        for transform in [
            inserted_section,
            lambda raw:raw.replace(b'</body>',b'<p>We also changed the financial statements.</p></body>',1),
        ]:
            result=self.changed(transform)
            self.assert_financial_scope_unproven(result)

    def test_other_exhibit_link_change_is_not_the_reported_single_link_correction(self):
        source=self.pairs['southwest_airlines']['scopes'][0]['amendment']
        link=next(x for x in source['links'] if 'Revolving Credit Facility Agreement' in x['text'])
        original=link['url'].encode()
        self.assert_financial_scope_unproven(self.changed(lambda raw:raw.replace(original,original+b'?different-source=1',1)))

    def test_foreign_note_subject_and_unreported_native_fact_do_not_pass(self):
        note=self.pairs['southwest_airlines']['scopes'][0]['explanatory_note']['blocks'][1]
        a,b=note['raw_start_byte'],note['raw_end_byte']
        result=self.changed(lambda raw:raw[:a]+raw[a:b].replace(b'Southwest Airlines Co.',b'Another Company',1)+raw[b:])
        self.assert_financial_scope_unproven(result)
        extra=b'<ix:nonFraction xmlns:new="http://fasb.org/us-gaap/2025" name="new:Revenues" contextRef="c-1" unitRef="usd">100</ix:nonFraction>'
        result=self.changed(lambda raw:raw.replace(b'</body>',extra+b'</body>',1))
        self.assertTrue(result['amendment']['non_dei_native_facts'])
        self.assert_financial_scope_unproven(result)

    def test_changed_source_hash_and_period_are_not_scope_evidence(self):
        args=self.arguments();args['amendment']['raw']+=b' '
        with self.assertRaises(ValueError):inspect_annual_amendment_scope(**args)
        args=self.arguments();args['amendment']['filing']={**args['amendment']['filing'],'reportDate':'2024-12-31'}
        with self.assertRaisesRegex(ValueError,'SAME_FILING_PERIOD_REQUIRED'):inspect_annual_amendment_scope(**args)

    def test_saved_input_admission_retains_sources_and_only_the_requested_property(self):
        with original_sources_only():
            financial=prepare_saved_amendment_input(repo_root=ROOT,company_id='southwest_airlines',
                input_class='ORIGINAL_STATEMENT_VALUES')
            event=prepare_saved_amendment_input(repo_root=ROOT,company_id='paramount_skydance_paramount_global',
                input_class='FISCAL_EVENT_WINDOW')
            withheld=prepare_saved_amendment_input(repo_root=ROOT,company_id='paramount_skydance_paramount_global',
                input_class='ORIGINAL_STATEMENT_VALUES')
        self.assertEqual('INPUT_PROPERTY_PROVEN',financial['decision'])
        self.assertEqual('INPUT_PROPERTY_PROVEN',event['decision'])
        self.assertEqual('WITHHELD',withheld['decision'])
        for packet in [financial,event,withheld]:
            self.assertFalse(packet['subject_continuity_proven'])
            self.assertFalse(packet['metric_result_created'])
            self.assertEqual({'provider':0,'paid':0,'sec':0},packet['calls'])
            amendments={s['amendment']['filing']['accessionNumber'] for s in packet['scopes']}
            references={r['accession'] for r in packet['source_records'] if r['record_type']=='SOURCE_REFERENCE'}
            self.assertTrue(amendments<=references)
        self.assertEqual(1,len(withheld['unresolved_scopes']))
        with self.assertRaisesRegex(ValueError,'INPUT_CLASS_UNSUPPORTED'):
            prepare_saved_amendment_input(repo_root=ROOT,company_id='southwest_airlines',input_class='B06')


if __name__=='__main__':unittest.main()
