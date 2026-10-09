"""Prepared case persistence/period regressions, one shared real B01 input."""
import copy
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext import ordinary_saved_result as saved
from vnext import ordinary_projection as projection
from vnext.table_grid import build_table_grid


class PrecalculatedCaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = saved._ordinary_case(REPO_ROOT, 'marriott_international', 'B01')

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def save(self, case):
        return saved.save_calculated_case(source_root=REPO_ROOT,output_root=self.root/'result',
            company_id='marriott_international',metric_id='B01',case=case)

    def test_real_precalculated_case_reaches_rows_without_selector_or_calculator(self):
        with patch.object(saved,'prepare_ordinary_zero_ai_run_input',side_effect=AssertionError('No extraction')):
            result=self.save(self.case)
        self.assertEqual(result['result']['value'],'26186000000')
        self.assertEqual(result['result']['result_id'],self.case['results']['B01']['result_id'])
        self.assertFalse(result['manifest']['calculation_performed_by_writer'])
        self.assertIn('SAVED_PRECALCULATED_CASE',str(result['receipt']))
        self.assertTrue((self.root/'result/metric_evidence.csv').exists())

    def test_projection_consumes_selected_annual_input_without_latest_reselection(self):
        original=saved.prepare_ordinary_zero_ai_run_input
        with patch.object(projection,'prepare_saved_annual_input',side_effect=AssertionError('Do not reselect latest')):
            result=self.save(self.case)
        self.assertEqual(result['manifest']['target_period']['fiscal_year'],2025)

    def test_current_metric_and_evidence_rows_keep_the_actual_reporter(self):
        result=self.save(self.case)
        for filename in ('metrics_matrix.csv', 'metric_evidence.csv'):
            rows=list(csv.DictReader(io.StringIO(result['files'][filename].decode())))
            self.assertTrue(rows)
            self.assertTrue(all(r['cik']=='1048286' for r in rows))
        self.assertEqual(result['result'],self.case['results']['B01'])

    def test_modified_trace_is_rejected_before_completion(self):
        case=copy.deepcopy(self.case)
        trace=next(r for r in case['expected_records'] if r['record_type']=='EXECUTION_TRACE'
                   and r['trace_id']==case['results']['B01']['trace_id'])
        trace['calculation_target']['entity']='813828'
        # The ordinary record consistency check rejects an in-place trace
        # edit before rendering. Reporter mismatch for independently supplied
        # targets is tested through the small reporting-view entry.
        with self.assertRaisesRegex(ValueError,'EXECUTION_TRACE content identity differs'):self.save(case)
        self.assertFalse((self.root/'result/manifest.json').exists())

    def test_wrong_target_period_has_no_completion_manifest(self):
        case=copy.deepcopy(self.case);case['target_period']={**case['target_period'],'period_end':'2024-12-31'}
        with self.assertRaisesRegex(ValueError,'PERIOD_CHANGED'):self.save(case)
        self.assertFalse((self.root/'result/manifest.json').exists())
        self.assertTrue((self.root/'result/failure.json').exists())

    def test_wrong_spec_has_no_completion_manifest(self):
        case=copy.deepcopy(self.case)
        case['compiled_specs']['B01']['spec_closure_hash']='sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError,'SPEC_CHANGED'):self.save(case)
        self.assertFalse((self.root/'result/manifest.json').exists())

    def test_wrong_prepared_subject_is_rejected_before_completion(self):
        case=copy.deepcopy(self.case);case['prepared_annual_input']['entity']='19617'
        with self.assertRaisesRegex(ValueError,'PREPARED_SUBJECT_CHANGED'):self.save(case)
        self.assertFalse((self.root/'result/manifest.json').exists())

    def test_wrong_prepared_fiscal_label_is_rejected_without_latest_fallback(self):
        case=copy.deepcopy(self.case)
        case['prepared_annual_input']['table_input']['target_period']['fiscal_year']=2024
        with patch.object(projection,'prepare_saved_annual_input',side_effect=AssertionError('No fallback')):
            with self.assertRaisesRegex(ValueError,'FISCAL_LABEL_CHANGED'):self.save(case)
        self.assertFalse((self.root/'result/manifest.json').exists())

    def shared_case(self):
        # Small synthetic extra asset tests storage only, not a business fact.
        case=copy.deepcopy(self.case)
        case['expected_records'].append(build_table_grid(html_bytes=b'<table><tr><td>test storage</td></tr></table>',
            parent_raw_asset_ids=[case['references'][0]['raw_asset_id']],storage_uri='test-only/unused-grid.json'))
        return case

    def test_shared_asset_is_stored_once_and_both_records_remain_readable(self):
        case=self.shared_case();shared=self.root/'shared'
        for name in ('one','two'):
            result=saved.save_calculated_case(source_root=REPO_ROOT,output_root=self.root/name,
                company_id='marriott_international',metric_id='B01',case=case,shared_input_root=shared)
            self.assertEqual(result['result']['result_id'],case['results']['B01']['result_id'])
            self.assertIn('ORDINARY_SHARED_DERIVED_ASSET_REFERENCE',(self.root/name/'records.jsonl').read_text())
        self.assertEqual(len(list(shared.glob('*.json'))),1)

    def test_independent_read_checks_changed_or_missing_shared_material(self):
        case=self.shared_case();shared=self.root/'shared'
        saved.save_calculated_case(source_root=REPO_ROOT,output_root=self.root/'one',
            company_id='marriott_international',metric_id='B01',case=case,shared_input_root=shared)
        path=next(shared.glob('*.json'));original=path.read_bytes();path.write_bytes(original+b' ')
        with self.assertRaisesRegex(ValueError,'SHARED_RECORD_CHANGED'):
            saved.read_saved_result(output_root=self.root/'one')
        path.unlink()
        with self.assertRaisesRegex(ValueError,'SHARED_RECORD_MISSING'):
            saved.read_saved_result(output_root=self.root/'one')

    def test_shared_material_cannot_be_written_into_readonly_source(self):
        with self.assertRaisesRegex(ValueError,'SHARED_INPUT_ROOT_OVERLAP'):
            saved.save_calculated_case(source_root=REPO_ROOT,output_root=self.root/'one',
                company_id='marriott_international',metric_id='B01',case=self.shared_case(),
                shared_input_root=REPO_ROOT/'accidental-cache')
        self.assertFalse((self.root/'one/manifest.json').exists())


if __name__=='__main__':unittest.main()
