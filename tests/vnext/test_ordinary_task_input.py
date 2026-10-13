"""Small parsed-input boundaries; actual saved raw pair is separate evidence."""
import unittest
from pathlib import Path
import tempfile
import copy

from tests.vnext.test_text_coverage import annual, binding, BODY
from vnext.ordinary_task_input import parsed_d04_document
from vnext.canonical import sha256_bytes


class ParsedTaskInputTest(unittest.TestCase):
    def parse(self, raw):
        return parsed_d04_document(**binding(raw))

    def test_empty_external_script_change_is_task_equivalent_with_original_spans(self):
        raw=annual(BODY);new=raw.replace(b'</body>',b'<script src="/extra.js"></script></body>')
        old,current=self.parse(raw),self.parse(new)
        self.assertEqual(old['parsed_input_sha256'],current['parsed_input_sha256'])
        self.assertNotEqual(old['raw_source_sha256'],current['raw_source_sha256'])
        for span in current['original_locators']:
            self.assertEqual(sha256_bytes(content=new[span['raw_start_byte']:span['raw_end_byte']]),span['raw_span_sha256'])
        self.assertFalse(current['source_admission_or_result_credit'])

    def test_visible_disclosure_and_embedded_script_data_cannot_disappear(self):
        original=self.parse(annual(BODY))['parsed_input_sha256']
        for extra in ('<p>Substantial doubt exists about our ability to continue.</p>',
                      '<script type="application/json">{"debt":123}</script>'):
            self.assertNotEqual(original,self.parse(annual(BODY+extra))['parsed_input_sha256'])

    def test_table_number_unit_and_header_relation_are_changes(self):
        table='<table><tr><th id="unit" scope="col">USD millions</th><th>2025</th></tr><tr><td headers="unit">100</td><td>2</td></tr></table>'
        original=self.parse(annual(BODY+table))['parsed_input_sha256']
        for changed in (table.replace('>100<','>101<'),table.replace('USD','EUR'),
                        table.replace('headers="unit"','headers="other"'),table.replace('scope="col"','scope="row"')):
            self.assertNotEqual(original,self.parse(annual(BODY+changed))['parsed_input_sha256'])

    def test_native_context_and_unit_changes_are_retained(self):
        native='<xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><ix:nonFraction name="dei:TestAmount" contextRef="annual" unitRef="u">100</ix:nonFraction>'
        raw=annual(BODY+native);original=self.parse(raw)['parsed_input_sha256']
        for changed in (raw.replace(b'iso4217:USD',b'iso4217:EUR'),raw.replace(b'>100<',b'>101<')):
            self.assertNotEqual(original,self.parse(changed)['parsed_input_sha256'])

    def test_media_target_and_ids_are_not_globally_masked(self):
        body=BODY+'<img src="table.png" id="image-1" alt="Debt table"><a href="#image-1">table</a>'
        original=self.parse(annual(body))['parsed_input_sha256']
        for changed in (body.replace('table.png','different.png'),body.replace('#image-1','#missing'),
                        body.replace('id="image-1"','id="image-2"')):
            self.assertNotEqual(original,self.parse(annual(changed))['parsed_input_sha256'])

    def test_inline_svg_complete_drawing_styles_and_nested_content_are_not_lost(self):
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><style>.a{fill:red}</style><g transform="scale(2)"><path class="a" d="M0 0 L10 10"/><svg><text>USD 10</text></svg></g></svg>'
        original=self.parse(annual(BODY+svg))
        self.assertTrue(original['parsed_input']['svg_subtrees'])
        for changed in (svg.replace('L10 10','L90 90'),svg.replace('fill:red','fill:blue'),
                        svg.replace('scale(2)','scale(3)'),svg.replace('USD 10','USD 20')):
            self.assertNotEqual(original['parsed_input_sha256'],self.parse(annual(BODY+changed))['parsed_input_sha256'])

    def test_period_and_subject_mismatch_are_errors(self):
        for changed in (annual(BODY,cik='67890'),annual(BODY,period='2024-12-31')):
            args=binding(changed)
            with self.assertRaises(ValueError):parsed_d04_document(**args)

    def test_amendment_comparison_keeps_single_document_coverage_incomplete(self):
        args=binding(annual(BODY,form='10-K/A'))
        from vnext.sources import source_reference_record
        args['source_reference']=source_reference_record(raw_blob=args['raw_blob'],
            company_id='sample_entity',source_url=args['source_reference']['source_url'],
            accession=args['source_reference']['accession'],document_name='source.htm',
            source_role='annual_amendment',request_attempt_id='test-only-source-attempt')
        with self.assertRaisesRegex(ValueError,'TEXT_AMENDMENT_SOURCE_SET_REQUIRED'):
            parsed_d04_document(**args)
        compared=parsed_d04_document(**args,allow_annual_amendment=True)
        self.assertEqual(compared['parsed_input']['identity']['source_state'],'INCOMPLETE')
        self.assertEqual(compared['parsed_input']['identity']['source_reasons'],
                         ['TEXT_AMENDMENT_SOURCE_SET_REQUIRED'])
        self.assertFalse(compared['source_admission_or_result_credit'])
        self.assertFalse(compared['semantic_disclosure_verified'])
        truncated={**args,**binding(annual(BODY,form='10-K/A')[:-14])}
        with self.assertRaisesRegex(ValueError,'PARSED_D04_INPUT_INCOMPLETE'):
            parsed_d04_document(**truncated,allow_annual_amendment=True)

    def test_same_words_in_quotation_container_change_model_input(self):
        first=self.parse(annual(BODY+'<p>We may have substantial doubt.</p>'))
        quoted=self.parse(annual(BODY+'<blockquote><p>We may have substantial doubt.</p></blockquote>'))
        self.assertNotEqual(first['parsed_input_sha256'],quoted['parsed_input_sha256'])
        self.assertTrue(any(b['html_quotation_context'] for b in quoted['parsed_input']['quotation_context']))

    def test_verbatim_unicode_is_not_nfc_collapsed(self):
        a=self.parse(annual(BODY+'<p>Text\u037e</p>'))
        b=self.parse(annual(BODY+'<p>Text;</p>'))
        self.assertNotEqual(a['parsed_input_sha256'],b['parsed_input_sha256'])

    def test_existing_annual_comparison_uses_task_parse_only_for_changed_html(self):
        from vnext.ordinary_source_session import compare_annual_inputs
        original=annual(BODY);changed=original.replace(b'</body>',b'<script src="/extra.js"></script></body>')
        args=binding(original);ref=args['source_reference']
        filing={'accessionNumber':ref['accession'],'form':'10-K','reportDate':'2025-12-31',
                'filingDate':'2026-02-01','primaryDocument':'source.htm'}
        def inputs(raw):
            proof={'source_url':ref['source_url'],'accession':ref['accession'],'document_name':'source.htm',
                'content_sha256':sha256_bytes(content=raw),'request_repo_relative_path':'source.htm',
                'request_attempt_id':'offline-test-source'}
            return {'company_id':'sample_entity','entity':'12345','filing':filing,'amendments':[],
                    'table_input':{'target_period':{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}},
                    'source_proofs':[proof]}
        with tempfile.TemporaryDirectory() as before,tempfile.TemporaryDirectory() as after:
            left,right=Path(before),Path(after)
            (left/'source.htm').write_bytes(original);(right/'source.htm').write_bytes(changed)
            previous,current=inputs(original),inputs(changed)
            self.assertTrue(compare_annual_inputs(previous=previous,current=current)['requires_candidate_processing'])
            result=compare_annual_inputs(previous=previous,current=current,task_metric_id='D04',
                previous_root=left,current_root=right)
            self.assertEqual(result['status'],'PARSED_TASK_INPUT_UNCHANGED')
            self.assertFalse(result['requires_candidate_processing'])
            self.assertFalse(result['input_authenticity_verified_by_comparison'])
            # Actual D04 annual selections may stay fixed while unrelated
            # newer 8-K metadata changes the submissions body.
            meta={'source_url':'https://data.sec.gov/submissions/CIK0000012345.json','accession':'',
                  'document_name':'CIK0000012345.json','content_sha256':'old'}
            before=copy.deepcopy(previous);after=copy.deepcopy(current)
            before['source_proofs'].append(meta);after['source_proofs'].append({**meta,'content_sha256':'new'})
            self.assertEqual(compare_annual_inputs(previous=before,current=after,task_metric_id='D04',
                previous_root=left,current_root=right)['status'],'PARSED_TASK_INPUT_UNCHANGED')
            new_filing=copy.deepcopy(after);new_filing['filing']={**filing,'filingDate':'2026-03-01'}
            self.assertTrue(compare_annual_inputs(previous=before,current=new_filing,task_metric_id='D04',
                previous_root=left,current_root=right)['requires_candidate_processing'])
            business=annual(BODY+'<p>Substantial doubt exists.</p>')
            (right/'source.htm').write_bytes(business)
            self.assertTrue(compare_annual_inputs(previous=previous,current=inputs(business),task_metric_id='D04',
                previous_root=left,current_root=right)['requires_candidate_processing'])


if __name__=='__main__':unittest.main()


class D04CompleteTaskFingerprintTest(unittest.TestCase):
    """Actual source/log checking with a small recorded SEC package."""
    def setUp(self):
        from tests.vnext.test_selected_source_requirements import SelectedSourceRequirementsTest
        self.fixture=SelectedSourceRequirementsTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        from tests.vnext.test_text_coverage import BODY
        from tests.vnext.test_selected_historical_fiscal_label import annual
        from tests.vnext.test_selected_source_requirements import CIK
        self.raw=annual().replace(b'19617',str(CIK).encode()).replace(b'2021',b'2025').replace(b'/2025q4',b'/2025')
        self.raw=self.raw.replace(b'</body></html>',BODY.encode()+b'</body></html>')
        self.fixture.record(self.fixture.urls[2025],self.raw)
        from sec_urls import companyfacts_url
        import json
        f=self.fixture.filings[0]
        self.cf={'cik':CIK,'facts':{'us-gaap':{'Revenues':{'units':{'USD':[
            {'accn':f['accessionNumber'],'fy':2025,'start':'2025-01-01','end':'2025-12-31',
             'form':'10-K','fp':'FY','filed':f['filingDate'],'val':100}]}}}}}
        self.fixture.record(companyfacts_url(cik=CIK),json.dumps(self.cf).encode())

    def fingerprint(self):
        from vnext.ordinary_d04_task_input import fingerprint
        from tests.vnext.test_selected_source_requirements import COMPANY
        return fingerprint(source_root=self.fixture.root,company_id=COMPANY)

    def test_external_script_only_is_equal_but_original_citations_remain(self):
        first=self.fingerprint()
        changed=self.raw.replace(b'</body>',b'<script src="/additional.js"></script></body>')
        self.fixture.record(self.fixture.urls[2025],changed)
        second=self.fingerprint()
        self.assertEqual(first['task_input_id'],second['task_input_id'])
        self.assertNotEqual(first['source_proofs'],second['source_proofs'])
        self.assertFalse(second['source_admission_or_result_credit'])

    def test_new_visible_content_table_unit_and_media_relationship_change_task(self):
        first=self.fingerprint()
        for fragment in ('<p>Substantial doubt exists.</p>',
            '<table><tr><th>USD million</th></tr><tr><td>100</td></tr></table>',
            '<img id="new-diagram" src="new.png" alt="Financial statement">',
            '<script type="application/json">{"debt":100}</script>'):
            with self.subTest(fragment=fragment):
                self.fixture.record(self.fixture.urls[2025],self.raw.replace(b'</body>',fragment.encode()+b'</body>'))
                self.assertNotEqual(first['task_input_id'],self.fingerprint()['task_input_id'])

    def test_changed_companyfacts_and_filing_identity_are_changes(self):
        from sec_urls import companyfacts_url,submissions_url
        from tests.vnext.test_selected_source_requirements import CIK
        import json
        first=self.fingerprint()
        self.fixture.record(companyfacts_url(cik=CIK),json.dumps({**self.cf,'changed':True}).encode())
        self.assertNotEqual(first['task_input_id'],self.fingerprint()['task_input_id'])
        self.fixture.record(companyfacts_url(cik=CIK),json.dumps(self.cf).encode())
        self.fixture.metadata['filings']['recent']['filingDate'][0]='2026-02-11'
        self.fixture.record(submissions_url(cik=CIK),json.dumps(self.fixture.metadata).encode())
        self.assertNotEqual(first['task_input_id'],self.fingerprint()['task_input_id'])

    def test_latest_failed_original_never_uses_equivalent_old_body(self):
        first=self.fingerprint()
        self.fixture.record(self.fixture.urls[2025],b'failed',503,'recorded failure')
        with self.assertRaises(ValueError):self.fingerprint()

    def add_amendment(self,raw=None):
        from sec_urls import accession_document_url,submissions_url
        from tests.vnext.test_selected_source_requirements import CIK
        import json
        self.amendment={**self.fixture.filings[0],'form':'10-K/A','filingDate':'2026-03-01',
            'accessionNumber':'0001048286-26-000008','primaryDocument':'amended-2025.htm'}
        for key,values in self.fixture.metadata['filings']['recent'].items():
            values.append(self.amendment[key])
        self.fixture.record(submissions_url(cik=CIK),json.dumps(self.fixture.metadata).encode())
        self.amendment_url=accession_document_url(cik=CIK,
            accession=self.amendment['accessionNumber'],document_name=self.amendment['primaryDocument'])
        self.amendment_raw=raw or self.raw.replace(b'>10-K<',b'>10-K/A<')
        self.fixture.record(self.amendment_url,self.amendment_raw)

    def test_full_amendment_set_can_compare_nonbusiness_and_business_changes(self):
        self.add_amendment();first=self.fingerprint()
        self.assertEqual([d['filing']['form'] for d in first['documents']],['10-K','10-K/A'])
        changed=self.amendment_raw.replace(b'</body>',b'<script src="/extra.js"></script></body>')
        self.fixture.record(self.amendment_url,changed)
        same=self.fingerprint()
        self.assertEqual(first['task_input_id'],same['task_input_id'])
        self.assertNotEqual(first['source_proofs'],same['source_proofs'])
        self.fixture.record(self.amendment_url,self.amendment_raw.replace(
            b'</body>',b'<p>Substantial doubt exists.</p></body>'))
        self.assertNotEqual(first['task_input_id'],self.fingerprint()['task_input_id'])

    def test_caller_cannot_omit_a_selected_amendment(self):
        from vnext.normal_annual_input_v2 import prepare_saved_annual_input
        from vnext.ordinary_d04_task_input import fingerprint
        from tests.vnext.test_selected_source_requirements import COMPANY
        self.add_amendment()
        prepared=prepare_saved_annual_input(repo_root=self.fixture.root,company_id=COMPANY,ordinary_registered=True)
        prepared['amendments']=[]
        with self.assertRaisesRegex(ValueError,'D04_TASK_INPUT_SELECTION_CHANGED'):
            fingerprint(source_root=self.fixture.root,company_id=COMPANY,prepared_annual_input=prepared)

    def test_missing_failed_truncated_and_wrong_identity_amendments_are_not_equivalent(self):
        from tests.vnext.test_selected_source_requirements import CIK
        self.add_amendment()
        for raw,status,error in (
            (b'failed',503,'recorded failure'),
            (self.amendment_raw[:-14],200,''),
            (self.amendment_raw.replace(str(CIK).encode(),b'12345'),200,''),
            (self.amendment_raw.replace(b'2025-12-31',b'2024-12-31'),200,''),
            (self.raw,200,'')):
            with self.subTest(status=status,raw_tail=raw[-30:]):
                self.fixture.record(self.amendment_url,raw,status,error)
                with self.assertRaises(ValueError):self.fingerprint()
        self.fixture.remove_get(self.amendment_url)
        with self.assertRaises(ValueError):self.fingerprint()
