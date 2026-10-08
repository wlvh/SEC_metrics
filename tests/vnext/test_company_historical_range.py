"""Period/source-version regressions; mocked computations grant no business credit."""
from contextlib import nullcontext
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.vnext import company_compute as compute, company_local as local
from scripts.vnext import company_result_view as view, normal_source_authority as authority
from tests.vnext import test_company_results as support


class HistoricalRangeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_lodging_range_uses_the_public_company_records_and_existing_year_factory(self):
        from scripts.vnext import company_current_records as current
        from scripts.vnext.historical_lodging_results import (
            prepare_historical_lodging_year_case, HISTORICAL_LODGING_PROCESSING_FILES)
        source = self.root/'source'; source.mkdir()
        expected = {'status': 'FLOW_COMPLETED', 'metrics': []}
        with patch.object(current, 'run_saved_company', return_value=expected) as run, \
             patch.object(local, '_history_program', side_effect=AssertionError('No native installation')):
            actual = local.run_local(company_id='marriott_international', work_dir=self.root/'work',
                output_dir=self.root/'output', period='fiscal-years', metric_ids=['B10', 'B11'],
                fiscal_year_start=2024, fiscal_year_end=2025, source_root=source)
        self.assertIs(actual, expected)
        self.assertEqual(run.call_args.kwargs['fiscal_years'], [2024, 2025])
        self.assertIs(run.call_args.kwargs['case_factory'], prepare_historical_lodging_year_case)
        self.assertEqual(run.call_args.kwargs['processing_files'], HISTORICAL_LODGING_PROCESSING_FILES)
        self.assertIn('config/normal_fiscal_year_labels_v1.json',run.call_args.kwargs['processing_files'])

    def test_b03_range_uses_existing_component_case_and_public_controller(self):
        from scripts.vnext import company_current_records as current
        from scripts.vnext.historical_saved_case import prepare_historical_income_year_case
        source = self.root/'source'; source.mkdir()
        with patch.object(current, 'run_saved_company', return_value={'metrics': []}) as run:
            local.run_local(company_id='marriott_international', work_dir=self.root/'work',
                output_dir=self.root/'output', period='fiscal-years', metric_ids=['B03'],
                fiscal_year_start=2024, fiscal_year_end=2025, source_root=source)
        self.assertEqual([2024, 2025], run.call_args.kwargs['fiscal_years'])
        self.assertIs(prepare_historical_income_year_case, run.call_args.kwargs['case_factory'])
        self.assertIn('scripts/vnext/historical_zero_ai_results.py', run.call_args.kwargs['processing_files'])
        self.assertFalse((self.root/'work').exists())

    def test_mixed_new_saved_families_are_rejected_before_writes(self):
        source = self.root/'source'; source.mkdir()
        with self.assertRaisesRegex(ValueError, 'MIXED_SAVED_FAMILY_NOT_RECEIVED'):
            local.run_local(company_id='marriott_international', work_dir=self.root/'work',
                output_dir=self.root/'output', period='fiscal-years', metric_ids=['B03', 'B10'],
                fiscal_year_start=2024, fiscal_year_end=2025, source_root=source)
        self.assertFalse((self.root/'work').exists())

    def test_retained_native_history_is_not_replaced_by_ordinary_storage(self):
        from scripts.vnext import company_current_records as current
        source = self.root/'source'; source.mkdir()
        work = self.root/'work'; (work/'historical-company-state').mkdir(parents=True)
        with patch.object(current, 'run_saved_company') as ordinary, \
             patch.object(local, '_history_program', side_effect=ValueError('retained native path')):
            report = local.run_local(company_id='marriott_international', work_dir=work,
                output_dir=self.root/'output', period='fiscal-years', metric_ids=['B11'],
                fiscal_year_start=2024, fiscal_year_end=2024, source_root=source)
        ordinary.assert_not_called()
        self.assertEqual(report['failure']['reason'], 'retained native path')
        self.assertFalse((work/'company-task.json').exists())

    def test_history_daily_export_uses_current_launcher_and_own_defects(self):
        work, output, creator = self.root/'task', self.root/'output', self.root/'old-creator'
        (work/'programs/old-creator').mkdir(parents=True)
        state = work/'historical-company-state'
        key = 'saved-range'
        with patch.object(local, '_invoke', return_value={'returncode': 0}) as invoke:
            report, destination = local._export_current(creator, work, output, 'test_company',
                key, {}, {}, state_root=state)
        args = invoke.call_args.args
        self.assertEqual(local.ROOT, args[0])
        self.assertEqual('results', args[1][0])
        self.assertEqual(state, args[1][args[1].index('--state-root')+1])
        self.assertEqual(local.ROOT/'docs/evidence/issue47_history/known_result_defects.json',
                         args[1][args[1].index('--defects-file')+1])
        self.assertNotIn('--processing-trust-root', args[1])
        self.assertEqual(work/'result-exports'/key, destination)
        self.assertEqual(0, report['returncode'])

    def test_missing_issuer_year_creates_no_partial_candidates(self):
        program = self.root/'program'
        (program/'requirements/issue_54_v3').mkdir(parents=True)
        state = self.root/'state'
        current = {'company_id': 'test_company', 'checkpoint_id': 'source-v1'}
        with patch.object(authority, 'ROOT', program), \
             patch.object(compute, 'recover_import', return_value=current), \
             patch('scripts.vnext.company_historical_compute.historical_compute_scope', return_value=nullcontext()), \
             patch('scripts.vnext.normal_period_selection.resolve_period_selection',
                   side_effect=[{'target_report_end': '2023-02-04'}, ValueError('missing issuer fiscal label')]), \
             patch.object(compute, '_compute_locked') as calculate:
            with self.assertRaisesRegex(ValueError, 'missing issuer fiscal label'):
                compute.compute_company_range(state_root=state, company_id='test_company',
                    metric_ids=['B01'], fiscal_year_start=2022, fiscal_year_end=2023)
        calculate.assert_not_called()
        self.assertFalse((state/'company-executions').exists())

    def test_invalid_range_or_current_year_history_arguments_fail_before_output(self):
        for start, end in [(2024, 2023), (2020, 2025), (True, 2023), (None, 2023)]:
            with self.assertRaisesRegex(ValueError, 'FISCAL_RANGE_INVALID'):
                local.run_local(company_id='test_company', work_dir=self.root/'work',
                    output_dir=self.root/'output', period='fiscal-years',
                    fiscal_year_start=start, fiscal_year_end=end, source_root=self.root/'source')
        with self.assertRaisesRegex(ValueError, 'HISTORY_ARGUMENTS_REQUIRE'):
            local.run_local(company_id='test_company', work_dir=self.root/'work',
                output_dir=self.root/'output', fiscal_year_start=2022)
        self.assertFalse((self.root/'output').exists())

    def test_multi_period_read_keeps_each_request_status_and_legacy_run_identity(self):
        fixture = support.CompanyResultsTest()
        fixture.setUp()
        # macOS exposes its temporary directory through /var -> /private/var.
        # Resolve the fixture before writing state so this business case reaches
        # period/result handling rather than the old path-alias guard.
        fixture.root = fixture.root.resolve()
        self.addCleanup(fixture.doCleanups)
        first = fixture.journal('B01', end='2022-12-31')
        second = fixture.journal('B01', end='2023-12-31')
        before = {p: p.read_bytes() for p in fixture.root.glob('updates/**/manifest.json')}
        report = {'company_id': 'test_company', 'source_checkpoint_id': 'source-v1',
            'period_request': {'fiscal_year_start': 2022, 'fiscal_year_end': 2023},
            'metrics': [{**first, 'period_request': {'fiscal_year': 2022}},
                        {**second, 'status': 'NO_SOURCE_CONTENT_CHANGE',
                         'period_request': {'fiscal_year': 2023}}]}
        view.save_execution(root=fixture.root, report=report)
        result = view.build_company_view(root=fixture.root, company_id='test_company', current=fixture.current)
        entries = {row['period']['fiscal_year']: row for row in result['metrics'] if row.get('run_id')}
        self.assertEqual(entries[2022]['latest_request_status'], 'CANDIDATE_READY')
        self.assertEqual(entries[2023]['latest_request_status'], 'NO_SOURCE_CONTENT_CHANGE')
        self.assertTrue(all(row['requested_in_latest_execution'] for row in entries.values()))
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        report['metrics'] = [{**first, 'status': 'UPDATE_BLOCKED',
                              'period_request': {'fiscal_year': 2022}}]
        report['period_request'] = {'fiscal_year': 2022}
        view.save_execution(root=fixture.root, report=report)
        result = view.build_company_view(root=fixture.root, company_id='test_company', current=fixture.current)
        entries = {row['period']['fiscal_year']: row for row in result['metrics'] if row.get('run_id')}
        self.assertEqual(entries[2023]['latest_request_status'], 'NO_SOURCE_CONTENT_CHANGE')
        self.assertFalse(entries[2023]['requested_in_latest_execution'])

    def test_missing_coordinates_and_old_out_of_range_rows_remain_distinct(self):
        output = self.root/'output'
        output.mkdir()
        (output/'metrics_matrix.csv').write_text('metric_id,period_end,fiscal_year,value,status\nB01,2021-12-31,2021,7,EXACT\nB01,2023-02-04,2022,9,EXACT\n')
        outcomes = [{'metric_id': 'B01', 'requested_fiscal_year': 2022,
                     'requested_report_end': '2023-02-04', 'status': 'NO_SOURCE_CONTENT_CHANGE'},
                    {'metric_id': 'B01', 'requested_fiscal_year': 2023,
                     'status': 'SOURCE_INPUT_REQUIRED', 'reason': 'annual primary unavailable'}]
        local._history_tables(output, 'test_company', outcomes,
                              {'run_id': 'test', 'status': 'FLOW_INCOMPLETE'})
        with (output/'metrics_matrix.csv').open(encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['value'], '7')
        self.assertEqual(rows[0]['local_metric_status'], 'NOT_REQUESTED')
        self.assertEqual(rows[1]['requested_fiscal_year'], '2022')
        self.assertEqual(rows[1]['value'], '9')
        self.assertEqual(rows[2]['status'], 'SOURCE_INPUT_REQUIRED')
        self.assertEqual(rows[2]['value'], '')

    def test_pinned_entry_is_checked_before_a_new_launcher_reuses_it(self):
        from scripts.vnext.company_handoff import binding
        program = self.root/'program'
        entry = program/'tools/vnext_company.py'
        entry.parent.mkdir(parents=True)
        entry.write_text("commands = ['compute-range', '--fiscal-year-start', '--fiscal-year-end', 'export-results']\n")
        baseline = program/'requirements/issue_54_v3/baseline_manifest.json'
        baseline.parent.mkdir(parents=True)
        baseline.write_text(json.dumps({'requirement_id': 'issue_54_v3',
            'execution_authority': {'files': {'tools/vnext_company.py': binding(entry)}}}))
        self.assertEqual(local._range_program_identity(program)['relation'],
                         'LAUNCHER_VERIFIES_AND_CALLS_PINNED_ENTRY')
        entry.write_text("commands = ['compute-range']\n")
        with self.assertRaisesRegex(ValueError, 'FIXED_ENTRY_CHANGED'):
            local._range_program_identity(program)

    def test_development_reviews_keep_their_own_period_and_pending_status(self):
        root = self.root/'state'
        root.mkdir()
        current = {'company_id': 'test_company', 'checkpoint_id': 'source-v1'}
        view.save_execution(root=root, report={'company_id': 'test_company',
            'source_checkpoint_id': current['checkpoint_id'],
            'period_request': {'fiscal_year_start': 2023, 'fiscal_year_end': 2024},
            'metrics': [{'metric_id': 'C02', 'status': 'REVIEW_REQUIRED',
                         'period_request': {'fiscal_year': year},
                         'development_review_id': 'pending-'+str(year)} for year in (2023, 2024)]})
        pending = view.build_company_view(root=root, company_id='test_company', current=current)['metrics']
        self.assertEqual({r['period_request']['fiscal_year']: r['development_review_id'] for r in pending},
                         {2023: 'pending-2023', 2024: 'pending-2024'})
        output = self.root/'output'
        output.mkdir()
        (output/'metrics_matrix.csv').write_text('metric_id,period_end,fiscal_year,status,value,development_review_id\nC02,2025-02-01,2024,REVIEW_REQUIRED,,pending-2024\n')
        local._history_tables(output, 'test_company', [{'metric_id': 'C02', 'requested_fiscal_year': 2024,
            'requested_report_end': '2025-02-01', 'status': 'CANDIDATE_READY'}],
            {'run_id': 'test', 'status': 'FLOW_COMPLETED_WITH_LIMITATIONS'})
        with (output/'metrics_matrix.csv').open(encoding='utf-8-sig') as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row['local_metric_status'], 'REVIEW_REQUIRED')
        self.assertEqual(row['value'], '')

    def test_daily_missing_years_follow_latest_range_outcomes(self):
        from scripts.vnext import company_daily_results as daily
        root = self.root/'state'
        root.mkdir()
        current = {'company_id': 'test_company', 'checkpoint_id': 'source-v1'}
        view.save_execution(root=root, report={'company_id': 'test_company',
            'source_checkpoint_id': current['checkpoint_id'],
            'period_request': {'fiscal_year': 2022},
            'metrics': [{'metric_id': 'B01', 'status': 'INPUT_FAILED'}]})
        view.save_execution(root=root, report={'company_id': 'test_company',
            'source_checkpoint_id': current['checkpoint_id'],
            'period_request': {'fiscal_year_start': 2023, 'fiscal_year_end': 2024},
            'metrics': [{'metric_id': 'B01', 'status': 'SOURCE_INPUT_REQUIRED',
                         'period_request': {'fiscal_year': year}} for year in (2023, 2024)]})
        output = self.root/'daily'
        with patch.object(daily, 'locked_company', side_effect=lambda p: nullcontext(p)), \
             patch.object(daily, 'recover_for_read', return_value=current):
            daily.write_daily_results(state_root=root, output_root=output, company_id='test_company')
        with (output/'metrics_matrix.csv').open(encoding='utf-8-sig') as stream:
            rows = {int(r['fiscal_year']): r for r in csv.DictReader(stream)}
        self.assertEqual(set(rows), {2022, 2023, 2024})
        self.assertEqual(rows[2022]['requested_in_latest_execution'], 'False')
        for year in (2023, 2024):
            self.assertEqual(rows[year]['requested_in_latest_execution'], 'True')
            self.assertEqual(rows[year]['period_role'], 'REQUESTED_WITHOUT_RESULT')
            self.assertEqual(rows[year]['status'], 'SOURCE_INPUT_REQUIRED')
            self.assertEqual(rows[year]['value'], '')


if __name__ == '__main__':
    unittest.main()
