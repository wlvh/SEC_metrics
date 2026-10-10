"""Finite complete source frames; constructed examples create no business answer."""
from pathlib import Path
import copy
import tempfile
import unittest

from tests.vnext.test_instant_amendment_paragraph_api import filing_html
from vnext.risk_heading_amendment_input_v1 import inspect_risk_heading_amendment, INPUT_CLASS
from vnext.sources import raw_blob_record, source_reference_record
from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope


def original_html():
    return filing_html(False).replace(b'<p>Original annual filing.</p>',
        b'<p>ITEM 1A. RISK FACTORS</p><p><b>Supplier constraints.</b> Supplies may be limited.</p>'
        b'<p>ITEM 1B. UNRESOLVED STAFF COMMENTS</p><p>None.</p>')


def sources(root, original=None, amended=None):
    frames=[]
    for is_amended in (False,True):
        raw=(filing_html(True) if amended is None else amended) if is_amended else (original_html() if original is None else original)
        name='amended.htm' if is_amended else 'original.htm'
        (root/name).write_bytes(raw)
        blob=raw_blob_record(repo_root=root,repo_relative_path=name,media_type='text/html')
        accession='0000000001-25-00000'+('2' if is_amended else '1')
        ref=source_reference_record(raw_blob=blob,company_id='constructed',
            source_url='https://www.sec.gov/Archives/edgar/data/1/'+accession.replace('-','')+'/'+name,
            accession=accession,document_name=name,source_role='target_primary',request_attempt_id='constructed-source-only')
        filing={'form':'10-K/A' if is_amended else '10-K','reportDate':'2024-12-31',
                'filingDate':'2025-04-25' if is_amended else '2025-02-26',
                'accessionNumber':accession,'primaryDocument':name}
        frames.append({'raw':raw,'blob':blob,'reference':ref,'filing':filing})
    return frames


class RiskHeadingAmendmentInputTest(unittest.TestCase):
    def inspect(self, original=None, amended=None):
        with tempfile.TemporaryDirectory() as folder:
            old,new=sources(Path(folder),original,amended)
            return inspect_risk_heading_amendment(original=old,amendment=new,company_id='constructed',cik='1')

    def test_clean_complete_part_iii_addition_admits_only_selected_original_headings(self):
        result=self.inspect()
        self.assertEqual(result['decision'],'INPUT_PROPERTY_PROVEN')
        self.assertEqual(result['input_class'],INPUT_CLASS)
        self.assertEqual(result['metric_ids'],['D01']);self.assertEqual(result['issues'],[])
        self.assertEqual(result['details']['original_item_1a_section']['status'],'LOCATED')
        self.assertFalse(result['metric_result_created']);self.assertFalse(result['financial_input_clearance'])
        self.assertFalse(result['subject_continuity_proven'])
        self.assertFalse(result['whole_amendment_semantic_no_effect_asserted'])
        self.assertIn('D01',result['source_scope']['not_covered_metric_ids'])
        self.assertNotIn(INPUT_CLASS,result['source_scope']['unchanged_input_classes'])

    def test_caution_citation_retains_real_source_blocks_but_is_not_new_item_1a(self):
        caution=('<p>CAUTIONARY NOTE CONCERNING FORWARD-LOOKING STATEMENTS</p>'
                 '<p>These risks, uncertainties and other factors are discussed in “Item 1A. Risk Factors” in our Initial Form 10-K.</p>')
        amended=filing_html(True).replace(b'<p>PART III</p>',caution.encode()+b'<p>PART III</p>')
        result=self.inspect(amended=amended)
        self.assertEqual(result['decision'],'INPUT_PROPERTY_PROVEN')
        refs=result['details']['risk_section_references']
        self.assertEqual(len(refs),1);self.assertEqual(refs[0]['status'],'INITIAL_FILING_CROSS_REFERENCE')
        self.assertTrue(refs[0]['source_blocks']);self.assertTrue(refs[0]['initial_filing_citations'])

    def test_new_item_1a_and_direct_unheaded_risk_reference_are_not_cleared(self):
        for text in ('<p>ITEM 1A. RISK FACTORS</p><p>Changed risk.</p><p>ITEM 1B. Unresolved Staff Comments</p>',
                     '<p>We replace the Item 1A risk factors in the Initial Form 10-K.</p>',
                     '<p>New risk factors are disclosed by this Amendment.</p>'):
            with self.subTest(text=text):
                result=self.inspect(amended=filing_html(True,text))
                self.assertEqual(result['decision'],'WITHHELD');self.assertTrue(result['issues'])

    def test_correct_citation_cannot_hide_a_second_item_1a_statement(self):
        caution=('<p>CAUTIONARY NOTE CONCERNING FORWARD-LOOKING STATEMENTS</p><p>'
                 'These risks, uncertainties and other factors are discussed in “Item 1A. Risk Factors” in our Initial Form 10-K. '
                 'Item 1A is modified here.</p>')
        result=self.inspect(amended=filing_html(True).replace(b'<p>PART III</p>',caution.encode()+b'<p>PART III</p>'))
        self.assertEqual(result['decision'],'WITHHELD')
        self.assertIn('RISK_SECTION_REFERENCE_UNRESOLVED',result['issues'][0]['reason'])

    def test_unknown_note_extra_purpose_subject_date_and_number_remain_withheld(self):
        baseline=filing_html(True)
        variants=(baseline.replace(b'for the year ended December 31, 2024',b'for the year ended December 31, 2023'),
                  baseline.replace(b'on February 26, 2025',b'on February 25, 2025'),
                  baseline.replace(b'Example Corp (the',b'Other Corp (the'),
                  baseline.replace(b'<p>Amendment No. 1</p>',b'<p>Amendment No. 2</p>'),
                  baseline.replace(b'<p>PART III</p>',b'<p>We also change the original risk factors.</p><p>PART III</p>'))
        for raw in variants:
            with self.subTest(raw_sha=len(raw)):
                self.assertEqual(self.inspect(amended=raw)['decision'],'WITHHELD')

    def test_original_item_1a_missing_is_a_source_limitation_not_a_guessed_answer(self):
        result=self.inspect(original=filing_html(False))
        self.assertEqual(result['decision'],'WITHHELD')
        self.assertIn('ORIGINAL_ITEM_1A_NOT_UNIQUE',result['issues'][0]['reason'])

    def test_wrong_filing_reference_and_modified_bytes_fail_before_clearance(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new=sources(Path(folder))
            wrong=copy.deepcopy(new);wrong['reference']['accession']=old['filing']['accessionNumber']
            with self.assertRaisesRegex(ValueError,'FILING_REFERENCE_DIFFERS'):
                inspect_risk_heading_amendment(original=old,amendment=wrong,company_id='constructed',cik='1')
            wrong=copy.deepcopy(new);wrong['raw']=wrong['raw']+b'<p>changed</p>'
            with self.assertRaises(ValueError):
                inspect_risk_heading_amendment(original=old,amendment=wrong,company_id='constructed',cik='1')
            with self.assertRaises(ValueError):
                inspect_risk_heading_amendment(original=old,amendment=new,company_id='other',cik='1')
            with self.assertRaises(ValueError):
                inspect_risk_heading_amendment(original=old,amendment=new,company_id='constructed',cik='2')

    def test_old_source_scope_default_does_not_gain_d01_or_new_input_credit(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new=sources(Path(folder));args=dict(original=old,amendment=new,company_id='constructed',cik='1')
            before=inspect_annual_amendment_scope(**args)
            result=inspect_risk_heading_amendment(**args)
            after=inspect_annual_amendment_scope(**args)
            self.assertEqual(before,after);self.assertIn('D01',after['not_covered_metric_ids'])
            self.assertNotIn(INPUT_CLASS,after['unchanged_input_classes'])
            self.assertEqual(result['source_scope']['note_layout'],'inline-paragraphs-v2')

    def test_running_part_titles_do_not_shift_the_actual_caution_window(self):
        citation=('<p>CAUTIONARY NOTE CONCERNING FORWARD-LOOKING STATEMENTS</p><p>'
                  'These risks, uncertainties and other factors are discussed in “Item 1A. Risk Factors” in our Initial Form 10-K.</p>')
        raw=filing_html(True).replace(b'<p>PART III</p>',citation.encode()+b'<p>PART III</p>')
        raw=raw.replace(b'<p>Item 12.',b'<p>PART III</p><p>Item 12.')
        result=self.inspect(amended=raw)
        self.assertEqual(result['decision'],'INPUT_PROPERTY_PROVEN')
        ref=result['details']['risk_section_references'][0]
        self.assertLess(ref['caution_window']['heading_block'],ref['block_indices'][0])
        self.assertLess(ref['block_indices'][0],ref['caution_window']['end_block_exclusive'])
        outside=raw.replace(b'<p>PART IV</p>',citation.encode()+b'<p>PART IV</p>')
        self.assertEqual(self.inspect(amended=outside)['decision'],'WITHHELD')

    def test_appended_named_risk_changes_do_not_become_a_financial_or_event_clearance(self):
        amended=filing_html(True,'<p>Risk factors are revised for the current year.</p>')
        result=self.inspect(amended=amended)
        self.assertEqual(result['decision'],'WITHHELD')
        self.assertFalse(result['financial_input_clearance'])
        self.assertEqual(result['input_class'],INPUT_CLASS)
        self.assertEqual(result['metric_ids'],['D01'])

    def test_plural_item_list_changes_standalone_and_after_citation_are_unresolved(self):
        changes=('This Amendment replaces the disclosures in Items 1A and 1B of the Initial Form 10-K.',
                 'This Amendment replaces the disclosures in Items 1, 1A and 1B of the Initial Form 10-K.',
                 'This Amendment replaces the disclosures in Items 1 through 2 of the Initial Form 10-K.')
        for change in changes:
            with self.subTest(change=change):
                result=self.inspect(amended=filing_html(True,'<p>'+change+'</p>'))
                self.assertEqual(result['decision'],'WITHHELD')
                self.assertTrue(result['details']['unresolved_risk_section_references'])
                caution=('<p>CAUTIONARY NOTE CONCERNING FORWARD-LOOKING STATEMENTS</p><p>'
                    'These risks, uncertainties and other factors are discussed in “Item 1A. Risk Factors” in our Initial Form 10-K. '
                    +change+'</p>')
                result=self.inspect(amended=filing_html(True).replace(b'<p>PART III</p>',caution.encode()+b'<p>PART III</p>'))
                self.assertEqual(result['decision'],'WITHHELD')
                self.assertEqual(result['details']['risk_section_references'][0]['status'],
                                 'UNRESOLVED_RISK_SECTION_REFERENCE')

    def test_identifier_check_preserves_unrelated_items_exhibits_and_actual_dependencies(self):
        from vnext.risk_heading_amendment_input_v1 import _mentions_risk_section, PROCESSING_FILES
        for text in ('Items 10, 11, 12, 13 and 14','Exhibit 10.1A','Item 1B','Items 10 through 14'):
            with self.subTest(text=text):self.assertFalse(_mentions_risk_section(text))
        for text in ('Item 1A','Item1A','Items 1A and 1B','Items 1 and 1A','Items 1–2','Items 1B, 1A'):
            with self.subTest(text=text):self.assertTrue(_mentions_risk_section(text))
        for name in ('normal_annual_input_v2','canonical'):
            self.assertIn('scripts/vnext/'+name+'.py',PROCESSING_FILES)
