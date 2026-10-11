"""Small historical proxy selection controls; no compensation acceptance."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path

from vnext.historical_compensation_case import select_first_reported_proxy


class HistoricalCompensationSelectionTest(TestCase):
    def fixture(self):
        annual={'accessionNumber':'annual','form':'10-K','primaryDocument':'annual.htm',
                'reportDate':'2022-12-31','filingDate':'2023-02-15'}
        prepared={'entity':'1048286','filing':annual,'table_input':{'target_period':{
            'fiscal_year':2022,'period_start':'2022-01-01','period_end':'2022-12-31'}}}
        rows=[annual,{'form':'DEF 14A','accessionNumber':'first','filingDate':'2023-03-20'},
                    {'form':'DEF 14A','accessionNumber':'later','filingDate':'2024-03-20'}]
        history={'window_proven':True,'limitations':[],'reporting_cik':'1048286',
                 'all_rows':rows,'loaded_inventories':['constructed']}
        return prepared,history

    def test_first_reported_proxy_is_not_replaced_by_later_compensation(self):
        prepared,history=self.fixture();before=deepcopy(history)
        selected=select_first_reported_proxy(prepared=prepared,history=history)
        self.assertEqual('first',selected['selected_proxy']['accessionNumber'])
        self.assertFalse(selected['value_selected']);self.assertEqual(before,history)

    def test_same_day_requires_acceptance_time_not_accession_rank(self):
        prepared,history=self.fixture();history['all_rows'][1]['acceptanceDateTime']='2023-03-20T10:00:00Z'
        history['all_rows'].append({'form':'DEF 14A','accessionNumber':'0000',
            'filingDate':'2023-03-20','acceptanceDateTime':'2023-03-20T11:00:00Z'})
        self.assertEqual('first',select_first_reported_proxy(prepared=prepared,
            history=history)['selected_proxy']['accessionNumber'])
        del history['all_rows'][-1]['acceptanceDateTime']
        with self.assertRaisesRegex(ValueError,'SAME_DAY_ORDER_NOT_PROVEN'):
            select_first_reported_proxy(prepared=prepared,history=history)

    def test_amendment_belongs_only_before_the_next_proxy(self):
        prepared,history=self.fixture();history['all_rows'].extend([
            {'form':'DEF 14A/A','accessionNumber':'first-amend','filingDate':'2023-04-01'},
            {'form':'DEF 14A/A','accessionNumber':'later-amend','filingDate':'2024-04-01'}])
        selected=select_first_reported_proxy(prepared=prepared,history=history)
        self.assertEqual(['first-amend'],[r['accessionNumber'] for r in selected['proxy_amendments']])

    def test_unproven_history_foreign_reporter_and_different_annual_refuse(self):
        for change in ('history','reporter','annual'):
            prepared,history=self.fixture()
            if change=='history':history['window_proven']=False
            elif change=='reporter':history['reporting_cik']='2041610'
            else:prepared['filing']={**prepared['filing'],'accessionNumber':'wrong'}
            with self.subTest(change=change),self.assertRaises(ValueError):
                select_first_reported_proxy(prepared=prepared,history=history)

    def test_no_proxy_does_not_become_zero_or_structural_na(self):
        prepared,history=self.fixture();history['all_rows']=history['all_rows'][:1]
        with self.assertRaisesRegex(ValueError,'FIRST_PROXY_NOT_SAVED') as error:
            select_first_reported_proxy(prepared=prepared,history=history)
        self.assertEqual('SOURCE_UNAVAILABLE',error.exception.category)


class HistoricalCompensationAdapterTest(TestCase):
    def test_untagged_proxy_uses_shared_sct_and_retains_derived_asset(self):
        from vnext import historical_compensation_case as cases
        from vnext.deterministic_router import DeterministicRouterError
        annual={'entity':'1048286','table_input':{'target_period':{'fiscal_year':2021,
                'period_start':'2021-01-01','period_end':'2021-12-31'}}}
        proxy={'raw_bytes':b'constructed untagged proxy','raw_blob':{},'source_reference':{}}
        selected={'accessionNumber':'proxy','form':'DEF 14A'}
        source={'prepared_annual_input':annual,'proxy_source':proxy,
            'selection':{'selected_proxy':selected},'records':[],'source_proofs':[],
            'proxy_inventory':{'name':'Example','formerNames':[]}}
        asset={'record_type':'DERIVED_ASSET','id':'constructed'}
        resolution={'selection':{'reason_code':'PASS'},'derived_assets':[asset],
            'observation':None,'trace':{},'result':{}}
        with patch.object(cases,'prepare_historical_compensation_sources',return_value=source), \
             patch.object(cases,'resolve_c03',side_effect=DeterministicRouterError('XBRL source contains no contexts')), \
             patch.object(cases,'resolve_proxy_compensation_table',return_value=resolution) as shared, \
             patch.object(cases,'verify_ordinary_source_proofs',return_value={}):
            case=cases.prepare_historical_compensation_year_case(repo_root=Path('/constructed'),
                company_id='example',metric_id='C03',fiscal_year=2021)
        self.assertIn(asset,case['expected_records'])
        self.assertEqual(cases.PROXY_SCT_SPEC_PATH,case['spec_paths']['C03'])
        self.assertIs(source['proxy_inventory'],shared.call_args.kwargs['inventory'])
        self.assertEqual(selected,shared.call_args.kwargs['filing'])
        self.assertTrue(case['input_assessments']['C03']['proxy_sct_route_used'])
        self.assertFalse(case['input_assessments']['C03']['proxy_sct_consumer_complete'])

    def test_broken_inline_and_non_context_errors_do_not_enter_sct(self):
        from vnext import historical_compensation_case as cases
        from vnext.deterministic_router import DeterministicRouterError
        from vnext.governance_signals import GovernanceSignalError
        annual={'entity':'1048286','table_input':{'target_period':{'fiscal_year':2021,
                'period_start':'2021-01-01','period_end':'2021-12-31'}}}
        for raw,error in [(b'<ix:nonNumeric>broken',DeterministicRouterError('XBRL source contains no contexts')),
                          (b'plain proxy',DeterministicRouterError('wrong entity')),
                          (b'plain proxy',GovernanceSignalError('C03_USD_UNIT_REQUIRED'))]:
            source={'prepared_annual_input':annual,'proxy_source':{'raw_bytes':raw,
                'raw_blob':{},'source_reference':{}},'selection':{'selected_proxy':{}}}
            with self.subTest(error=error), \
                 patch.object(cases,'prepare_historical_compensation_sources',return_value=source), \
                 patch.object(cases,'resolve_c03',side_effect=error), \
                 patch.object(cases,'resolve_proxy_compensation_table') as table:
                with self.assertRaises(type(error)) as caught:
                    cases.prepare_historical_compensation_year_case(repo_root=Path('/constructed'),
                        company_id='marriott_international',metric_id='C03',fiscal_year=2021)
                self.assertIs(error,caught.exception)
                table.assert_not_called()

    def test_source_preparer_retains_annual_primary_for_reporter_and_distinct_proxy(self):
        from vnext import historical_compensation_case as cases
        from unittest.mock import Mock
        annual={'entity':'1048286','filing':{'accessionNumber':'annual','form':'10-K'},
            'table_input':{'target_period':{'fiscal_year':2022,
                'period_start':'2022-01-01','period_end':'2022-12-31'}},'source_proofs':[]}
        selection={'selected_proxy':{'accessionNumber':'proxy','form':'DEF 14A'},'proxy_amendments':[]}
        reader=Mock();reader.proofs={};reader.records={}
        reader.primary.side_effect=[{'source':'annual'}, {'source':'proxy'}]
        with patch.object(cases,'resolve_period_selection',return_value={}), \
             patch.object(cases,'prepare_historical_annual_input',return_value=annual), \
             patch.object(cases,'_Sources',return_value=reader), \
             patch.object(cases,'load_history_for_period',return_value={
                 'inventory':{'raw_bytes':b'{"name":"Example","formerNames":[]}'}}), \
             patch.object(cases,'select_first_reported_proxy',return_value=selection):
            source=cases.prepare_historical_compensation_sources(repo_root=Path('/constructed'),
                company_id='marriott_international',fiscal_year=2022)
        self.assertEqual([annual['filing'],selection['selected_proxy']],
                         [call.args[0] for call in reader.primary.call_args_list])
        self.assertEqual({'source':'proxy'},source['proxy_source'])
        self.assertEqual({'name':'Example','formerNames':[]},source['proxy_inventory'])

    def test_history_dispatch_preserves_existing_factories_and_dependencies(self):
        from vnext import company_local
        from vnext.historical_compensation_case import prepare_historical_compensation_year_case, PROCESSING_FILES
        from vnext.historical_statement_cases import prepare_historical_statement_year_case
        from vnext.historical_event_cases import prepare_historical_event_year_case
        with patch('vnext.company_current_records.run_saved_company',return_value={}) as shared:
            company_local.run_local(company_id='marriott_international',source_root=Path('/saved'),
                work_dir=Path('/new/state'),output_dir=Path('/new/out'),period='fiscal-years',
                fiscal_year_start=2022,fiscal_year_end=2022,metric_ids=['C03','B01','C01'])
        args=shared.call_args.kwargs
        self.assertIs(prepare_historical_compensation_year_case,args['case_factories']['C03'])
        self.assertEqual(PROCESSING_FILES,args['processing_files_by_metric']['C03'])
        self.assertIs(prepare_historical_statement_year_case,args['case_factories']['B01'])
        self.assertIs(prepare_historical_event_year_case,args['case_factories']['C01'])
        self.assertEqual([2022],args['fiscal_years'])

    def test_selected_proxy_and_annual_identity_remain_distinct(self):
        from vnext import historical_compensation_case as cases
        annual={'entity':'1048286','filing':{'form':'10-K','accessionNumber':'annual'},
            'table_input':{'target_period':{'fiscal_year':2022,
                'period_start':'2022-01-01','period_end':'2022-12-31'}}}
        selection={'selected_proxy':{'form':'DEF 14A','accessionNumber':'proxy',
            'filingDate':'2023-03-28'},'proxy_amendments':[]}
        proxy={'raw_bytes':b'constructed','raw_blob':{'id':'constructed-blob'},
               'source_reference':{'record_type':'SOURCE_REFERENCE','accession':'proxy'}}
        source={'prepared_annual_input':annual,'selection':selection,'proxy_source':proxy,
            'records':[proxy['source_reference']], 'source_proofs':[]}
        for reason in ('PASS','C03_MULTIPLE_REPORTED_AMOUNTS','C03_TARGET_PERIOD_NOT_FOUND'):
            resolution={'selection':{'reason_code':reason}, 'observation':None,
                'trace':{'record_type':'EXECUTION_TRACE'},'result':{'record_type':'METRIC_RESULT'}}
            with self.subTest(reason=reason), \
                 patch.object(cases,'prepare_historical_compensation_sources',return_value=source), \
                 patch.object(cases,'resolve_c03',return_value=resolution) as shared, \
                 patch.object(cases,'verify_ordinary_source_proofs',return_value={}):
                case=cases.prepare_historical_compensation_year_case(repo_root=Path('/constructed'),
                    company_id='marriott_international',metric_id='C03',fiscal_year=2022)
                self.assertIs(annual,case['prepared_annual_input'])
                self.assertEqual('10-K',annual['filing']['form'])
                self.assertEqual('DEF 14A',case['selected_proxy']['form'])
                self.assertEqual(selection['selected_proxy'],case['input_binding']['selected_proxy'])
                self.assertIs(resolution['result'],case['results']['C03'])
                self.assertEqual('YEAR_QUARTER_OR_DATE',shared.call_args.kwargs['sec_namespace_release'])
                self.assertEqual('2022-01-01',shared.call_args.kwargs['target']['period_start'])
                self.assertFalse(case['input_assessments']['C03']['proxy_sct_consumer_complete'])

    def test_wrong_metric_rejects_before_proxy_read(self):
        from vnext import historical_compensation_case as cases
        with patch.object(cases,'prepare_historical_compensation_sources') as select:
            with self.assertRaisesRegex(ValueError,'C03_METRIC_REQUIRED'):
                cases.prepare_historical_compensation_year_case(repo_root=Path('/constructed'),
                    company_id='example',metric_id='C04',fiscal_year=2022)
        select.assert_not_called()
