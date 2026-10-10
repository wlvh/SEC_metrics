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
        from vnext.historical_statement_cases import prepare_historical_statement_year_case
        from vnext.historical_event_cases import prepare_historical_event_year_case
        with patch('vnext.company_current_records.run_saved_company', return_value={}) as shared:
            company_local.run_local(company_id='marriott_international', source_root=Path('/saved/source'),
                work_dir=Path('/new/state'), output_dir=Path('/new/out'), period='fiscal-years',
                fiscal_year_start=2023, fiscal_year_end=2024, metric_ids=['D04','B01','C01'],
                saved_call_package=Path('/saved/package'))
        args = shared.call_args.kwargs
        self.assertEqual([2023,2024], args['fiscal_years'])
        self.assertIs(prepare_historical_statement_year_case, args['case_factories']['B01'])
        self.assertIs(prepare_historical_event_year_case, args['case_factories']['C01'])
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
