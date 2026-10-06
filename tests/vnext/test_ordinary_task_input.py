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

    def test_period_and_subject_mismatch_are_errors(self):
        for changed in (annual(BODY,cik='67890'),annual(BODY,period='2024-12-31')):
            args=binding(changed)
            with self.assertRaises(ValueError):parsed_d04_document(**args)

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
