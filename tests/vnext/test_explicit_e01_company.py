"""Finite successor dispatch/scope controls, not model-content evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext import test_company_current_records as company_tests
from vnext import company_current_records as company
from vnext import ordinary_current_update as update
from vnext.ordinary_saved_result import CURRENT_E01_SPEC_PATH, current_e01_scope


class ExplicitE01CompanyTest(unittest.TestCase):
    setUp=company_tests.CurrentCompanyTest.setUp

    def test_default_e01_remains_closed(self):
        with patch.object(company,'run_once',side_effect=AssertionError('No old default E01')):
            report=company.run_saved_company(company_id='marriott_international',source_root=self.source,
                work_dir=self.work,output_dir=self.outputs,metric_ids=['E01'])
        self.assertEqual(report['metrics'][0]['status'],'PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED')

    def test_selected_per_metric_factory_reaches_existing_controller(self):
        def factory(**kwargs):raise AssertionError('Dispatch test only')
        with patch.object(company,'run_once',return_value={'status':'INPUT_OR_EXECUTION_FAILED',
                'reason':'Constructed dispatch control'}) as control:
            company.run_saved_company(company_id='marriott_international',source_root=self.source,
                work_dir=self.work,output_dir=self.outputs,metric_ids=['E01'],fiscal_years=[2024],
                case_factories={'E01':factory},processing_files_by_metric={'E01':('e01-consumer.py',)})
        self.assertEqual(control.call_count,1)
        self.assertIs(control.call_args.kwargs['case_factory'],factory)
        self.assertEqual(control.call_args.kwargs['fiscal_year'],2024)
        self.assertEqual(control.call_args.kwargs['processing_files'],('e01-consumer.py',))

    def test_explicit_factory_without_year_cannot_start(self):
        with self.assertRaisesRegex(ValueError,'SELECTED_YEARS_REQUIRE_CASE_FACTORY'):
            company.run_saved_company(company_id='marriott_international',source_root=self.source,
                work_dir=self.work,output_dir=self.outputs,metric_ids=['E01'],
                case_factories={'E01':lambda **kwargs:None})
        self.assertFalse(self.work.exists())

    def saved_e01(self,*,successor):
        original=company.run_once
        def selected(**kwargs):
            # Save a tiny synthetic record at the actual selected-period read
            # location, while keeping company reporting and results real.
            period=kwargs['state_root']/'periods/FY2024'
            observation=original(**{**kwargs,'state_root':period})
            value=self.values[observation['result_root']]
            value['result'].update(value=None,unit='count',publication='WITHHELD',
                reason_code='E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST')
            value['manifest']['target_period']['fiscal_year']=2024
            row=company._rows(value['files']['metrics_matrix.csv'])[0]
            row.update(value='',unit='count',status='WITHHELD',fiscal_year='2024',
                notes='Constructed missing-response state; not an accepted business answer')
            value['files']['metrics_matrix.csv']=company._csv_bytes(rows=[row],fieldnames=company.METRIC_FIELDS)
            if successor:value['manifest']['selected_spec_path']=CURRENT_E01_SPEC_PATH
            pointer=period/'current-result.json'
            state=json.loads(pointer.read_text());pointer.unlink()
            state.update(requested_fiscal_year=2024,status='CANDIDATE_WITHHELD')
            (period/'completed-check.json').write_text(json.dumps(state))
            observation.update(status='CANDIDATE_WITHHELD',version='first',result_id='E01-result')
            return observation
        with patch.object(company,'run_once',side_effect=selected):
            return company.run_saved_company(company_id='marriott_international',source_root=self.source,
                work_dir=self.work,output_dir=self.outputs,metric_ids=['E01'],fiscal_years=[2024],
                case_factories={'E01':lambda **kwargs:None})

    def test_successor_withheld_can_be_read_without_legacy_scope_credit(self):
        report=self.saved_e01(successor=True)
        self.assertEqual(company_tests.CurrentCompanyTest.rows(self,report)[0]['value'],'')
        with patch.object(company,'run_once',side_effect=AssertionError('Results never calculates')):
            view=company.read_current_company(state_root=self.work,company_id='marriott_international')
        row=view['metrics'][0]
        self.assertEqual(row['reason_code'],'E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST')
        self.assertEqual(row['result_validity'],'SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED')
        self.assertIsNone(row['value'])
        self.assertEqual(row['fiscal_year'],2024)

    def test_old_item_code_result_still_has_no_current_scope(self):
        report=self.saved_e01(successor=False)
        self.assertEqual(company_tests.CurrentCompanyTest.rows(self,report)[0]['result_validity'],'CURRENT_SCOPE_NOT_READY')
        view=company.read_current_company(state_root=self.work,company_id='marriott_international')
        self.assertEqual(view['metrics'][0]['result_validity'],'CURRENT_SCOPE_NOT_READY')
        self.assertIsNone(view['metrics'][0]['value'])


class E01ContractUpdateTest(unittest.TestCase):
    def test_old_contract_rejected_before_save(self):
        root=Path(__file__).resolve().parents[2]
        def factory(**kwargs):
            return {'target_period':{'fiscal_year':2024},'spec_paths':{'E01':'catalog/ordinary_zero_ai/E01.md'}}
        with tempfile.TemporaryDirectory() as folder,patch.object(update,'_configuration',return_value={}), \
             patch.object(update,'_source_census',return_value=[]), \
             patch.object(update,'save_calculated_case',side_effect=AssertionError('No old-contract save')) as save:
            report=update.run_once(state_root=Path(folder)/'state',source_root=root,
                company_id='marriott_international',metric_id='E01',fiscal_year=2024,case_factory=factory)
        self.assertEqual(report['status'],'INPUT_OR_EXECUTION_FAILED')
        self.assertIn('E01_CONTENT_SPEC_REQUIRED',report['reason']);save.assert_not_called()

    def test_scope_marker_and_successor_note_do_not_change_old_projection(self):
        root=Path(__file__).resolve().parents[2]
        policy=json.loads((root/'config/ordinary_public_projection_v1.json').read_text())['metrics']['E01']
        self.assertIn('filing items',policy['projection']['notes'])
        self.assertIn('Content-confirmed',policy['spec_overrides'][CURRENT_E01_SPEC_PATH]['notes'])
        self.assertFalse(current_e01_scope({'manifest':{}}))
        self.assertFalse(current_e01_scope({'manifest':{'selected_spec_path':'catalog/ordinary_zero_ai/E01.md'}}))
        self.assertTrue(current_e01_scope({'manifest':{'selected_spec_path':CURRENT_E01_SPEC_PATH}}))


if __name__=='__main__':unittest.main()
