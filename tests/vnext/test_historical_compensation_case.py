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
    def test_plain_proxy_with_duplicate_units_still_reaches_shared_sct(self):
        from vnext import historical_compensation_case as cases
        from vnext.deterministic_router import parse_accession_xbrl_source
        raw=(b'<html xmlns:xbrli="http://www.xbrl.org/2003/instance">'
             b'<xbrli:unit id="unused"/><xbrli:unit id="unused"/>'
             b'<table><tr><td>Summary compensation table</td></tr></table></html>')
        annual={'entity':'1048286','table_input':{'target_period':{'fiscal_year':2021,
                'period_start':'2021-01-01','period_end':'2021-12-31'}}}
        selected={'accessionNumber':'proxy','form':'DEF 14A'}
        source={'prepared_annual_input':annual,'proxy_source':{'raw_bytes':raw,
                'raw_blob':{},'source_reference':{}},
            'selection':{'selected_proxy':selected},'records':[],'source_proofs':[],
            'proxy_inventory':{'name':'Example','formerNames':[]}}
        resolution={'selection':{'reason_code':'PASS'},'derived_assets':[],
            'observation':None,'trace':{},'result':{}}
        with patch.object(cases,'prepare_historical_compensation_sources',return_value=source), \
             patch.object(cases,'resolve_c03',side_effect=lambda **kw:
                          parse_accession_xbrl_source(raw_bytes=kw['raw_bytes'])), \
             patch.object(cases,'resolve_proxy_compensation_table',return_value=resolution) as table, \
             patch.object(cases,'verify_ordinary_source_proofs',return_value={}):
            case=cases.prepare_historical_compensation_year_case(repo_root=Path('/constructed'),
                company_id='example',metric_id='C03',fiscal_year=2021)
        self.assertEqual(raw,table.call_args.kwargs['raw_bytes'])
        self.assertTrue(case['input_assessments']['C03']['proxy_sct_route_used'])

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

    def test_alternative_inline_prefix_and_native_fact_without_context_do_not_enter_sct(self):
        from vnext import historical_compensation_case as cases
        from vnext.deterministic_router import DeterministicRouterError, parse_accession_xbrl_source
        annual = {'entity':'1048286','table_input':{'target_period':{'fiscal_year':2021,
            'period_start':'2021-01-01','period_end':'2021-12-31'}}}
        originals = (
            b'<html xmlns:alt="http://www.xbrl.org/2013/inlineXBRL"><body><alt:nonFraction name="ecd:PeoTotalCompAmt" contextRef="missing">100</alt:nonFraction></body></html>',
            b'<html xmlns:i="http://www.xbrl.org/2008/inlineXBRL"><body><i:nonNumeric name="ecd:PeoName" contextRef="missing">Person</i:nonNumeric></body></html>',
            b'<html xmlns:alt="http://www.xbrl.org/2013/inlineXBRL"><body><alt:nonFraction>100</alt:nonFraction></body></html>',
            b'<nonFraction xmlns="http://www.xbrl.org/2013/inlineXBRL">100</nonFraction>',
            b'<xbrli:xbrl><ecd:PeoTotalCompAmt contextRef="missing">100</ecd:PeoTotalCompAmt></xbrli:xbrl>',
        )
        for raw in originals:
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(DeterministicRouterError, 'no contexts') as parsed:
                    parse_accession_xbrl_source(raw_bytes=raw)
                source = {'prepared_annual_input':annual,'proxy_source':{'raw_bytes':raw,
                    'raw_blob':{},'source_reference':{}},'selection':{'selected_proxy':{}},
                    'proxy_inventory':{}}
                with patch.object(cases,'prepare_historical_compensation_sources',return_value=source), \
                     patch.object(cases,'resolve_c03',side_effect=parsed.exception), \
                     patch.object(cases,'resolve_proxy_compensation_table',
                         side_effect=AssertionError('SCT_FALLBACK_MUST_NOT_RUN')) as table:
                    with self.assertRaises(DeterministicRouterError) as rejected:
                        cases.prepare_historical_compensation_year_case(repo_root=Path('/constructed'),
                            company_id='marriott_international',metric_id='C03',fiscal_year=2021)
                self.assertIs(parsed.exception, rejected.exception)
                table.assert_not_called()

    def test_markup_guard_does_not_treat_namespace_declarations_or_quoted_examples_as_facts(self):
        from vnext import historical_compensation_case as cases
        for raw in (
                b'<html xmlns:alt="http://www.xbrl.org/2013/inlineXBRL"><body><table><tr><td>Total</td></tr></table></body></html>',
                b'<html><!-- <ix:nonFraction> --><script>"<ix:nonNumeric>"</script><p>&lt;ix:nonFraction&gt;</p></html>'):
            with self.subTest(raw=raw):
                self.assertFalse(cases._proxy_has_structured_markup(raw))

    def test_markup_guard_tracks_namespace_scope_without_fact_or_unit_validation(self):
        from vnext import historical_compensation_case as cases
        inline=b'http://www.xbrl.org/2013/inlineXBRL'
        ordinary=b'<html>'+b'<div>'*600+b'<p>Plain compensation table</p>'+b'</div>'*600+b'</html>'
        self.assertFalse(cases._proxy_has_structured_markup(ordinary))
        shadow=(b'<html xmlns:a="'+inline+b'"><div xmlns:a="urn:plain">'
                b'<a:label>Not a fact</a:label></div></html>')
        self.assertFalse(cases._proxy_has_structured_markup(shadow))
        restored=shadow.replace(b'</div></html>',b'</div><a:nonFraction>100</a:nonFraction></html>')
        self.assertTrue(cases._proxy_has_structured_markup(restored))
        closed=(b'<html><div xmlns:a="'+inline+b'"></div>'
                b'<a:label>Outside the declaration</a:label></html>')
        self.assertFalse(cases._proxy_has_structured_markup(closed))
        # Unrelated duplicate units cannot hide an actual broken inline fact.
        broken=(b'<html xmlns:x="http://www.xbrl.org/2003/instance" xmlns:a="'+inline+b'">'
                b'<x:unit id="u"/><x:unit id="u"/><a:nonFraction contextRef="missing">'
                b'100</a:nonFraction></html>')
        self.assertTrue(cases._proxy_has_structured_markup(broken))

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
        from vnext import historical_statement_cases as statements
        from vnext.company_fiscal_range import PROCESSING_FILES as range_files
        from vnext.historical_compensation_case import prepare_historical_compensation_year_case, PROCESSING_FILES
        from vnext.historical_event_cases import prepare_historical_event_year_case
        selection = {'constructed_control': True, 'report_end': '2022-12-31'}
        plan = {'tasks': [{'fiscal_year': 2022, 'status': 'FISCAL_YEAR_RESOLVED',
                           'period_selection': selection}]}
        with patch.object(statements, 'prepare_historical_statement_year_case',
                          return_value={'constructed_case': True}) as producer, \
             patch('vnext.company_current_records.run_saved_company',return_value={}) as shared:
            company_local.run_local(company_id='marriott_international',source_root=Path('/saved'),
                work_dir=Path('/new/state'),output_dir=Path('/new/out'),period='fiscal-years',
                fiscal_year_start=2022,fiscal_year_end=2022,metric_ids=['C03','B01','C01'])
        args=shared.call_args.kwargs
        self.assertIs(prepare_historical_compensation_year_case,args['case_factories']['C03'])
        self.assertEqual(PROCESSING_FILES,args['processing_files_by_metric']['C03'])
        self.assertEqual(tuple(dict.fromkeys((*statements.INCOME_PROCESSING_FILES, *range_files))),
                         args['processing_files_by_metric']['B01'])
        with patch('vnext.company_fiscal_range.discover_fiscal_range', return_value=plan) as discover, \
             patch('vnext.company_fiscal_range.sha256_file', return_value='constructed-source-version'):
            result = args['case_factories']['B01'](repo_root=Path('/saved'),
                company_id='marriott_international', metric_id='B01', fiscal_year=2022)
        self.assertEqual({'constructed_case': True}, result)
        producer.assert_called_once_with(repo_root=Path('/saved').resolve(),
            company_id='marriott_international', metric_id='B01', fiscal_year=2022,
            period_selection=selection)
        discover.assert_called_once_with(repo_root=Path('/saved').resolve(),
            company_id='marriott_international', fiscal_year_start=2022,
            fiscal_year_end=2022, metric_ids=['B01'])
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
