"""Small historical adapter/CLI controls, not filing content acceptance."""
import contextlib
import inspect
import io
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from tools.vnext_company import main
from vnext import company_local
from vnext import historical_d04_case as cases


class HistoricalD04CaseTest(TestCase):
    def test_unused_current_code_keeps_historical_withholding_but_used_replay_reprocesses(self):
        # Real configuration/controller; source and withheld result are constructed controls.
        from vnext import ordinary_current_update as update
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state';records={};calls=[]
            def factory(**kw):
                calls.append(kw)
                return {'target_period':{'fiscal_year':2024}}
            def save(**kw):
                path=kw['output_root'];path.mkdir(parents=True)
                result={'manifest':{'company_id':'marriott_international','metric_id':'D04','source_proofs':[]},
                    'result':{'company_id':'marriott_international','metric_id':'D04',
                        'publication':'WITHHELD','period_end':'2024-12-31',
                        'result_id':'constructed-history-d04-'+str(len(calls))}}
                records[str(path)]=result
                return result
            args=dict(state_root=state,source_root=update.ROOT,company_id='marriott_international',
                metric_id='D04',fiscal_year=2024,case_factory=factory,processing_files=cases.PROCESSING_FILES)
            with patch.object(update,'_source_census',return_value=[]), \
                 patch.object(update,'_current_sources',return_value=[]), \
                 patch.object(update,'save_calculated_case',side_effect=save), \
                 patch.object(update,'read_saved_result',side_effect=lambda **kw:records[str(kw['output_root'])]):
                first=update.run_once(**args);old_path=Path(next(iter(records)))
                actual_hash=update.sha256_file
                for changed in ('current_d04_result.py','capacity_update_input.py'):
                    with self.subTest(module=changed),patch.object(update,'sha256_file',side_effect=lambda *,path:
                            'CONSTRUCTED_UNUSED_CURRENT_CHANGE' if path.name==changed else actual_hash(path=path)), \
                         patch.object(update,'save_calculated_case',side_effect=AssertionError('No unused-current replay')):
                        again=update.run_once(**args)
                        self.assertEqual('PREVIOUS_INPUT_WITHHELD',again['status'])
                        self.assertFalse(again['calculation_performed'])
                        self.assertEqual(first['result_id'],again['result_id'])
                self.assertEqual(1,len(calls))
                used_changes = set()
                for module in ('saved_d04_replay.py', 'r6_semantic_review.py', 'text_results.py'):
                    used_changes.add(module)
                    with self.subTest(used_module=module), patch.object(
                            update, 'sha256_file', side_effect=lambda *, path:
                            'CONSTRUCTED_USED_RULE_CHANGE' if path.name in used_changes
                            else actual_hash(path=path)):
                        changed = update.run_once(**args)
                        self.assertTrue(changed['calculation_performed'])
                        with patch.object(update, 'save_calculated_case',
                                          side_effect=AssertionError('No repeated processing')):
                            repeated = update.run_once(**args)
                        self.assertEqual('PREVIOUS_INPUT_WITHHELD', repeated['status'])
                        self.assertEqual(1 + len(used_changes), len(calls))
                self.assertEqual(4, len(calls))
                self.assertTrue(old_path.is_dir())

    def test_used_historical_catalog_is_a_processing_dependency(self):
        # Constructed control state, not a financial conclusion. A changed
        # catalog must invalidate this producer's stable withholding once.
        from tests.vnext.test_ordinary_current_update import SelectedPeriodUpdateTest
        from scripts.vnext import ordinary_current_update as update
        fixture = SelectedPeriodUpdateTest(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.publication = 'WITHHELD'
        first = fixture.selected(2024, processing_files=cases.PROCESSING_FILES)
        original = update.sha256_file
        with patch.object(update, 'sha256_file', side_effect=lambda *, path:
                'b'*64 if path.name == 'normal_history_catalog.py' else original(path=path)):
            changed = fixture.selected(2024, processing_files=cases.PROCESSING_FILES)
            calls = fixture.factory_calls
            repeated = fixture.selected(2024, processing_files=cases.PROCESSING_FILES)
        self.assertNotEqual(first['version'], changed['version'])
        self.assertEqual(2, calls)
        self.assertEqual(calls, fixture.factory_calls)
        self.assertEqual('PREVIOUS_INPUT_WITHHELD', repeated['status'])
        self.assertFalse(repeated['calculation_performed'])

    def test_selected_annual_reaches_the_one_public_saved_replay(self):
        package = Path('/saved/original-model-ledger.tar.gz')
        selection = {'original_source_id':'constructed-original-source'}
        factory = cases.historical_d04_factory(saved_call_package=package)
        # The controller can record a normal function's code version; the
        # package is also passed explicitly as a processing input below.
        self.assertEqual(inspect.getsourcefile(cases.historical_d04_factory),
                         inspect.getsourcefile(factory))
        with patch.object(cases, 'prepare_historical_d04_selection', return_value=selection) as select, \
             patch.object(cases, 'prepare_selected_saved_d04_case', return_value={'checked':'constructed'}) as replay:
            self.assertEqual({'checked':'constructed'}, factory(repo_root=Path('/saved/source'),
                company_id='example', metric_id='D04', fiscal_year=2023))
        select.assert_called_once_with(source_root=Path('/saved/source'), company_id='example',
            fiscal_year=2023, saved_call_package=package)
        replay.assert_called_once_with(source_root=Path('/saved/source'), selection=selection)

    def test_other_metric_is_refused_before_source_or_answer_read(self):
        with patch.object(cases, 'prepare_historical_d04_selection') as select:
            with self.assertRaisesRegex(ValueError, 'D04_METRIC_REQUIRED'):
                cases.historical_d04_factory(saved_call_package='/saved/package')(repo_root=Path('/saved'),
                    company_id='example', metric_id='D02', fiscal_year=2023)
        select.assert_not_called()

    def test_same_company_dispatch_keeps_other_families_and_exposes_package_dependency(self):
        from vnext import historical_statement_cases as statements
        from vnext.company_fiscal_range import PROCESSING_FILES as range_files
        from vnext.historical_event_cases import prepare_historical_event_year_case
        from vnext.historical_auditor_case import prepare_historical_auditor_year_case, PROCESSING_FILES as auditor_files
        from vnext.historical_e01_company_case import prepare_historical_e01_year_case, PROCESSING_FILES as e01_files
        selection = {'constructed_control': True, 'report_end': '2023-12-31'}
        plan = {'tasks': [{'fiscal_year': 2023, 'status': 'FISCAL_YEAR_RESOLVED',
                           'period_selection': selection}]}
        with patch.object(statements, 'prepare_historical_statement_year_case',
                          return_value={'constructed_case': True}) as producer, \
             patch('vnext.company_current_records.run_saved_company', return_value={}) as shared:
            company_local.run_local(company_id='marriott_international', source_root=Path('/saved/source'),
                work_dir=Path('/new/state'), output_dir=Path('/new/out'), period='fiscal-years',
                fiscal_year_start=2023, fiscal_year_end=2024, metric_ids=['D04','E01','C04','B01','C01'],
                saved_call_package=Path('/saved/package'))
        args = shared.call_args.kwargs
        self.assertEqual([2023,2024], args['fiscal_years'])
        self.assertEqual(tuple(dict.fromkeys((*statements.INCOME_PROCESSING_FILES, *range_files))),
                         args['processing_files_by_metric']['B01'])
        with patch('vnext.company_fiscal_range.discover_fiscal_range', return_value=plan) as discover, \
             patch('vnext.company_fiscal_range.sha256_file', return_value='constructed-source-version'):
            self.assertEqual({'constructed_case': True}, args['case_factories']['B01'](
                repo_root=Path('/saved/source'), company_id='marriott_international',
                metric_id='B01', fiscal_year=2023))
        producer.assert_called_once_with(repo_root=Path('/saved/source').resolve(),
            company_id='marriott_international', metric_id='B01', fiscal_year=2023,
            period_selection=selection)
        discover.assert_called_once_with(repo_root=Path('/saved/source').resolve(),
            company_id='marriott_international', fiscal_year_start=2023,
            fiscal_year_end=2024, metric_ids=['B01'])
        self.assertIs(prepare_historical_e01_year_case, args['case_factories']['E01'])
        self.assertEqual(e01_files, args['processing_files_by_metric']['E01'])
        self.assertIs(prepare_historical_event_year_case, args['case_factories']['C01'])
        self.assertIs(prepare_historical_auditor_year_case, args['case_factories']['C04'])
        self.assertEqual(auditor_files, args['processing_files_by_metric']['C04'])
        self.assertEqual(cases.PROCESSING_FILES, args['processing_files_by_metric']['D04'])
        self.assertEqual({'D04':(Path('/saved/package'),)}, args['processing_inputs_by_metric'])
        self.assertTrue(all((company_local.ROOT/p).is_file() for p in cases.PROCESSING_FILES))

    def test_direct_api_requires_package_for_selected_d04(self):
        with patch('vnext.company_current_records.run_saved_company') as shared:
            with self.assertRaisesRegex(ValueError, 'D04_SAVED_PACKAGE_REQUIRED'):
                company_local.run_local(company_id='marriott_international', source_root=Path('/saved'),
                    work_dir=Path('/new/state'), output_dir=Path('/new/out'), period='fiscal-years',
                    fiscal_year_start=2023, fiscal_year_end=2023, metric_ids=['D04'])
        shared.assert_not_called()


class HistoricalD04CLIArgsTest(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.base = ['run','--company','marriott_international','--work-dir',str(root/'state'),
                     '--output-dir',str(root/'out')]
        self.history = ['--source-root',str(root/'source'),'--period','fiscal-years',
                        '--fiscal-year-start','2023','--fiscal-year-end','2023']
        self.package = ['--saved-call-package',str(root/'original.tar.gz')]
        self.root = root

    def test_saved_package_is_forwarded_only_in_explicit_history_d04_mode(self):
        with patch('vnext.company_local.run_local', return_value={'status':'FLOW_COMPLETED'}) as run, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(self.base+self.history+['--metric','D04']+self.package))
        self.assertEqual(Path(self.package[1]), run.call_args.kwargs['saved_call_package'])
        self.assertEqual('fiscal-years', run.call_args.kwargs['period'])

    def test_invalid_package_modes_refuse_before_any_controller_or_writes(self):
        variants = [self.package, self.history+self.package,
            self.history+['--metric','B01']+self.package,
            ['--source-root',str(self.root/'source'),'--metric','D04']+self.package,
            self.history+['--metric','D04','--call-context','/saved/context']+self.package,
            self.history+['--metric','D04']]
        with patch('vnext.company_local.run_local') as run, \
             patch('vnext.company_online.run_online_company') as online:
            for args in variants:
                with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    main(self.base+args)
                self.assertEqual(2, error.exception.code)
        run.assert_not_called(); online.assert_not_called()
        self.assertEqual([], list(self.root.iterdir()))
