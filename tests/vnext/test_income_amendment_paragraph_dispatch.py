"""Reuse the explicit paragraph property; constructed filings have no source credit."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.vnext.test_instant_amendment_paragraph_api import filing_html
from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope
from vnext.ordinary_income_input import inspect_income_amendment
from vnext.sources import raw_blob_record,source_reference_record
from vnext.normal_source_authority import ROOT
RULES=json.loads((ROOT/'config/ordinary_income_input_v1.json').read_text())

class IncomeParagraphDispatchTest(unittest.TestCase):
    def scope(self,extra='',layout='inline-paragraphs-v2',transform=lambda raw:raw):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sources=[]
            for amended in (False,True):
                name='amended.htm' if amended else 'original.htm';raw=filing_html(amended,extra if amended else '')
                if amended:raw=transform(raw)
                (root/name).write_bytes(raw);blob=raw_blob_record(repo_root=root,repo_relative_path=name,media_type='text/html')
                accession='0000000001-25-00000'+('2' if amended else '1')
                ref=source_reference_record(raw_blob=blob,company_id='constructed',source_url='https://www.sec.gov/Archives/edgar/data/1/'+accession.replace('-','')+'/'+name,accession=accession,document_name=name,source_role='target_primary',request_attempt_id='constructed-no-credit')
                filing={'form':'10-K/A' if amended else '10-K','reportDate':'2024-12-31','filingDate':'2025-04-25' if amended else '2025-02-26','accessionNumber':accession,'primaryDocument':name}
                sources.append({'raw':raw,'blob':blob,'reference':ref,'filing':filing})
            scope=inspect_annual_amendment_scope(original=sources[0],amendment=sources[1],company_id='constructed',cik='1',note_layout=layout)
            return scope,sources[1]['raw']

    def test_explicit_existing_paragraph_property_is_used(self):
        def formatting(raw):
            return raw.replace(b' to amend Part III',b' solely to amend Part III').replace(b'References to ',b'References in this document to ').replace(b'such Items.',b'such Items, rather than incorporate such information into Part III by reference to a proxy statement.')
        scope,raw=self.scope(transform=formatting)
        self.assertEqual(scope['issues'],[])
        result=inspect_income_amendment(scope,raw,RULES)
        self.assertEqual(result['original_scope_id'],scope['scope_id'])
        self.assertEqual(result['income_correction_blocks'],[])
        self.assertEqual(result['input_class'],RULES['input_class'])
        self.assertTrue(result['part_iii_details']['native_correction_flag'])

    def test_inline_income_correction_and_unknown_layout_do_not_gain_credit(self):
        for extra in ('<p>Our revenue has been revised.</p>',
                      '<div>Our reve<div style="display:inline">nue</div> has been rev<div style="display:inline">ised</div>.</div>'):
            scope,raw=self.scope(extra)
            with self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'CORRECTION.*UNRESOLVED'):
                inspect_income_amendment(scope,raw,RULES)
        scope,raw=self.scope();scope['note_layout']='unknown'
        with self.assertRaisesRegex(ValueError,'NOTE_LAYOUT_UNSUPPORTED'):
            inspect_income_amendment(scope,raw,RULES)

    def test_default_legacy_scope_still_uses_the_same_helper(self):
        from vnext import ordinary_income_input as current
        scope,raw=self.scope(layout='blocks-v1')
        original=current._part_iii_details
        with patch.object(current,'_part_iii_details',wraps=original) as old:
            observed=inspect_income_amendment(scope,raw,RULES);old.assert_called_once_with(scope,raw)
        self.assertEqual(observed,inspect_income_amendment(scope,raw,RULES))

    def test_real_correction_flag_and_quoted_note_stay_refused(self):
        for transformation in (lambda raw:raw.replace('☐'.encode(),'☒'.encode()),
                               lambda raw:raw.replace(b'Example Corp (the',b'<q>Example Corp (the').replace(b'otherwise requires.</p>',b'otherwise requires.</q></p>')):
            scope,raw=self.scope(transform=transformation)
            with self.subTest(transformation=transformation),self.assertRaises(ValueError):
                inspect_income_amendment(scope,raw,RULES)
