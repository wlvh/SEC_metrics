"""Small full-API correction checks; constructed filings have no source credit."""
from pathlib import Path
import tempfile
import unittest

from vnext.instant_balance_amendment_v2 import POLICY, inspect_instant_balance_amendment
from vnext.sources import raw_blob_record, source_reference_record


def filing_html(amended,extra=''):
    form='10-K/A' if amended else '10-K'
    facts={'EntityCentralIndexKey':'0000000001','DocumentType':form,
           'DocumentPeriodEndDate':'2024-12-31','DocumentFiscalYearFocus':'2024',
           'DocumentFiscalPeriodFocus':'FY','EntityRegistrantName':'Example Corp'}
    hidden=''.join('<ix:nonNumeric name="dei:'+name+'" contextRef="C">'+value+'</ix:nonNumeric>' for name,value in facts.items())
    hidden+='<ix:nonNumeric name="dei:DocumentFinStmtErrorCorrectionFlag" contextRef="C" format="ixt:boolballotbox">☐</ix:nonNumeric>'
    body='<p>Original annual filing.</p>'
    if amended:
        body='<p>Amendment No. 1</p><p>'+POLICY['error_correction_cover_pattern'].replace('\\','')+'</p>'
        body+='<p>'+POLICY['restatement_cover_pattern'].replace('\\','')+'</p><p>EXPLANATORY NOTE</p>'
        body+='<p>Example Corp (the “Company”), a Delaware corporation, is filing this Amendment No. 1 on Form 10-K/A (this “Amendment”) to its Annual Report on Form 10-K for the year ended December 31, 2024, originally filed with the Securities and Exchange Commission (the “SEC”) on February 26, 2025 (the “Initial Form 10-K”), to amend Part III, Items 10, 11, 12, 13 and 14 of the Initial Form 10-K to include the information required by such Items. Except as explicitly set forth herein, this Amendment does not otherwise change, modify or update the disclosures in, or exhibits to, the Initial Form 10-K. References to “Example,” the “Company,” “we,” “us” and “our” refer to Example Corp and its consolidated subsidiaries, unless the context otherwise requires.</p>'
        body+='<p>PART III</p>'+''.join('<p>Item '+str(i)+'. Governance</p>' for i in range(10,15))
        body+='<p>PART IV</p><p>Item 15. Exhibits</p><p>No financial statements or supplemental data are filed with this Amendment. See Index to Financial Statements and Supplemental Data of the Initial Form 10-K.</p>'+extra
    return ('<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:dei="http://xbrl.sec.gov/dei/2024" xmlns:ixt="http://www.sec.gov/inlineXBRL/transformation/2015-08-31"><body><ix:header><ix:resources><xbrli:context id="C"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context></ix:resources><ix:hidden>'+hidden+'</ix:hidden></ix:header>'+body+'</body></html>').encode()


class InstantParagraphApiTest(unittest.TestCase):
    def inspect(self,extra,layout="inline-paragraphs-v2"):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sources=[]
            for amended in (False,True):
                name='amended.htm' if amended else 'original.htm';raw=filing_html(amended,extra if amended else '')
                (root/name).write_bytes(raw);blob=raw_blob_record(repo_root=root,repo_relative_path=name,media_type='text/html')
                accession='0000000001-25-00000'+('2' if amended else '1')
                reference=source_reference_record(raw_blob=blob,company_id='constructed',source_url='https://www.sec.gov/Archives/edgar/data/1/'+accession.replace('-','')+'/'+name,accession=accession,document_name=name,source_role='target_primary',request_attempt_id='constructed-no-acquisition-credit')
                filing={'form':'10-K/A' if amended else '10-K','reportDate':'2024-12-31','filingDate':'2025-04-25' if amended else '2025-02-26','accessionNumber':accession,'primaryDocument':name}
                sources.append({'raw':raw,'blob':blob,'reference':reference,'filing':filing})
            return inspect_instant_balance_amendment(original=sources[0],amendment=sources[1],company_id='constructed',cik='1',note_layout=layout)

    def test_clean_small_complete_filing_can_complete(self):
        result=self.inspect('');self.assertEqual(result['decision'],'INPUT_PROPERTY_PROVEN')
        self.assertEqual(result['issues'],[]);self.assertFalse(result['metric_result_created'])

    def test_current_correction_plain_and_inline_split_have_same_refusal(self):
        for text in ('<div>We have corrected our financial statements.</div>',
                     '<div>We have corrected our <div style="display:inline">financial statements</div>.</div>',
                     '<div>We have corrected our finan<div style="display:inline">cial statements</div>.</div>',
                     '<div>We have cor<div style="display:inline">rected</div> our financial statements.</div>',
                     '<div>Our current <div style="display:inline">assets</div> have been restated.</div>'):
            with self.subTest(text=text):
                result=self.inspect(text);self.assertEqual(result['decision'],'WITHHELD')
                self.assertIn('FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED',result['issues'][0]['reason'])

    def test_new_balance_disclosure_cannot_hide_in_inline_words(self):
        for text in ('<div>Our current <div style="display:inline">assets</div> are $42 million.</div>',
                     '<div>Our cur<div style="display:inline">rent assets</div> are $42 million.</div>'):
            with self.subTest(text=text):
                result=self.inspect(text)
                self.assertEqual(result['decision'],'WITHHELD')
                self.assertIn('FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED',result['issues'][0]['reason'])

    def test_hidden_inline_gap_does_not_break_visible_correction(self):
        for hidden in ('hidden', 'style="display:none"', 'style="visibility:hidden"'):
            with self.subTest(hidden=hidden):
                result=self.inspect('<div>We have cor<span '+hidden+'>draft</span><div style="display:inline">rected</div> our financial statements.</div>')
                self.assertEqual(result['decision'],'WITHHELD')
                self.assertIn('FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED',result['issues'][0]['reason'])
                hidden_only=self.inspect('<div><span '+hidden+'>We have corrected our financial statements.</span>Governance only.</div>')
                self.assertEqual(hidden_only['decision'],'INPUT_PROPERTY_PROVEN')

    def test_quoted_word_fragment_cannot_erase_conditional_review(self):
        text=('✓ Clawback Policy: In addition to maintaining a clawback policy as required by the Exchange Act Rule 10D-1 and Nasdaq listing standards '
              '(which we apply beyond executive officers to other senior executives of the Company), provide for forfeiture, repayment or adjustment '
              'of incentive compensation in the event of a financial restatement without regard to misconduct in our NEOs’ employment agreements')
        ordinary=self.inspect('<div>'+text+'</div>')
        self.assertEqual(ordinary['decision'],'INPUT_PROPERTY_PROVEN')
        self.assertEqual(len(ordinary['details']['conditional_compensation_references']),1)
        quoted=self.inspect('<div>'+text.replace('financial','finan<q><div style="display:inline">cial</div></q>')+'</div>')
        self.assertEqual(quoted['decision'],'WITHHELD')
        self.assertIn('FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED',quoted['issues'][0]['reason'])

    def test_default_successor_entry_preserves_legacy_saved_object(self):
        from unittest.mock import patch
        from vnext import instant_balance_amendment_v2 as successor
        original=successor.legacy.inspect_instant_balance_amendment
        with patch.object(successor.legacy,'inspect_instant_balance_amendment',wraps=original) as old:
            result=self.inspect('',layout='blocks-v1')
            old.assert_called_once()
        self.assertEqual(result['decision'],'INPUT_PROPERTY_PROVEN')
        self.assertNotIn('note_layout',result)
        self.assertEqual(original(**old.call_args.kwargs),result)
