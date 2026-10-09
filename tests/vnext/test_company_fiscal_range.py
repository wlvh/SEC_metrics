"""Actual small recorded source originals plus explicit lazy-factory controls."""
import hashlib
import io
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from tests.vnext import test_selected_source_requirements as source_fixtures
from tests.vnext.test_selected_source_requirements import COMPANY, CIK
from tests.vnext.test_selected_historical_fiscal_label import annual
from sec_urls import companyfacts_url
from vnext import company_fiscal_range as ranges
from vnext import company_local as local
from tools.vnext_company import main


class CompanyFiscalRangeTest(TestCase):
    def setUp(self):
        self.fixture=source_fixtures.SelectedSourceRequirementsTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.source=self.fixture.root
        rows=[]
        for year,filing in zip((2025,2024),self.fixture.filings):
            raw=annual().replace(b'19617',str(CIK).encode()).replace(b'2021',str(year).encode())
            self.fixture.record(self.fixture.urls[year],raw)
            rows.append({'accn':filing['accessionNumber'],'fy':year,'start':f'{year}-01-01',
                         'end':f'{year}-12-31','form':'10-K','fp':'FY','filed':filing['filingDate'],'val':100})
        self.cf={'cik':CIK,'facts':{'us-gaap':{'Revenues':{'units':{'USD':rows}}}}}
        self.fixture.record(companyfacts_url(cik=CIK),json.dumps(self.cf).encode())

    def discover(self,first=2024,last=2025):
        with patch('vnext.historical_annual_input.prepare_historical_annual_input',side_effect=AssertionError('No complete annual preparation')):
            return ranges.discover_fiscal_range(repo_root=self.source,company_id=COMPANY,
                fiscal_year_start=first,fiscal_year_end=last,metric_ids=['B01','B02'])

    def test_originals_resolve_requested_range_and_do_not_claim_metric_acceptance(self):
        before=self.fixture.digest_tree();r=self.discover()
        self.assertEqual(r['status'],'FISCAL_RANGE_RESOLVED')
        self.assertEqual([t['report_end'] for t in r['tasks']],['2024-12-31','2025-12-31'])
        self.assertEqual([t['period_selection']['requested_fiscal_year'] for t in r['tasks']],[2024,2025])
        self.assertFalse(r['metric_executed']);self.assertFalse(r['fetch_authorized'])
        self.assertEqual(before,self.fixture.digest_tree())

    def test_explicit_issuer_year_is_not_discarded_by_report_end_year(self):
        raw=annual().replace(b'19617',str(CIK).encode()).replace(b'2021',b'2025')
        raw=raw.replace(b'</body></html>',b'<p>Our fiscal year ends on December 31. References to fiscal 2026, for example, refer to the fiscal year ending December 31, 2025.</p></body></html>')
        self.fixture.record(self.fixture.urls[2025],raw)
        r=self.discover(2026,2026);task=r['tasks'][0]
        self.assertEqual(task['status'],'FISCAL_YEAR_RESOLVED')
        self.assertEqual(task['report_end'],'2025-12-31')
        self.assertEqual(task['label']['fiscal_year'],2026)
        self.assertEqual(task['label']['original_dei_fiscal_year'],2025)
        self.assertEqual(task['label']['actual_period']['period_end'],'2025-12-31')

    def test_duplicate_label_does_not_pick_first_candidate(self):
        self.cf['facts']['us-gaap']['Revenues']['units']['USD'][0]['fy']=2024
        self.fixture.record(companyfacts_url(cik=CIK),json.dumps(self.cf).encode())
        # Same valid explicit issuer label on both originals.
        raw=annual().replace(b'19617',str(CIK).encode()).replace(b'2021',b'2025')
        raw=raw.replace(b'</body></html>',b'<p>Our fiscal year ends on December 31. References to fiscal 2024, for example, refer to the fiscal year ending December 31, 2025.</p></body></html>')
        self.fixture.record(self.fixture.urls[2025],raw)
        r=self.discover(2024,2024)
        self.assertEqual(r['status'],'FISCAL_RANGE_UNRESOLVED')
        issue=r['tasks'][0]['limitations'][0]
        self.assertEqual(issue['reason'],'FISCAL_YEAR_MISSING_OR_AMBIGUOUS')
        self.assertEqual(set(issue['matching_report_ends']),{'2024-12-31','2025-12-31'})

    def test_nonactual_issuer_definitions_do_not_resolve_public_range(self):
        definitions=[
            'If the proposed naming convention is approved, References to fiscal 2026, for example, refer to the fiscal year ending December 31, 2025.',
            'The following is a hypothetical example, not our actual naming convention: "References to fiscal 2026, for example, refer to the fiscal year ending December 31, 2025."',
            'If the proposed naming convention is approved, Fiscal years 2026 and 2025 ended on December 31, 2025 and December 31, 2024, respectively, and included 52 weeks.',
        ]
        for text in definitions:
            raw=annual().replace(b'19617',str(CIK).encode()).replace(b'2021',b'2025')
            raw=raw.replace(b'</body></html>',('<p>Our fiscal year ends on December 31. '+text+'</p></body></html>').encode())
            self.fixture.record(self.fixture.urls[2025],raw)
            with self.subTest(text=text):
                r=self.discover(2026,2026)
                self.assertEqual(r['status'],'FISCAL_RANGE_UNRESOLVED')
                self.assertFalse(r['all_source_bytes_available'])
                self.assertTrue(r['tasks'][0]['limitations'])
                self.assertFalse(r['metric_executed'])

    def test_missing_candidate_cannot_be_silently_excluded_for_label_uniqueness(self):
        self.fixture.remove_get(self.fixture.urls[2025]);r=self.discover(2024,2024)
        self.assertEqual(r['status'],'FISCAL_RANGE_UNRESOLVED')
        self.assertTrue(r['tasks'][0]['limitations'])
        self.assertTrue(any(not e['source_fiscal_year_resolved'] for e in r['candidates']))

    def test_malformed_metadata_is_a_source_limit_not_a_fiscal_guess(self):
        from sec_urls import submissions_url
        self.fixture.record(submissions_url(cik=CIK),b'{"cik":1048286}')
        r=self.discover();self.assertEqual(r['status'],'FISCAL_RANGE_UNRESOLVED')
        self.assertTrue(all(t['limitations'] for t in r['tasks']))
        self.assertEqual(r['candidates'],[])

    def test_public_sources_year_range_runs_actual_discovery_and_invalid_scope_is_early(self):
        args=['sources','--company',COMPANY,'--source-root',str(self.source),
              '--fiscal-year-start','2024','--fiscal-year-end','2025','--metric','B01']
        with patch('sys.stdout',new_callable=io.StringIO) as output:code=main(args)
        self.assertEqual(code,0);r=json.loads(output.getvalue())
        self.assertEqual(r['fiscal_years'],[2024,2025]);self.assertEqual(r['status'],'FISCAL_RANGE_RESOLVED')
        with patch('sys.stderr',new_callable=io.StringIO),self.assertRaises(SystemExit) as e:
            main(args+['--report-end','2025-12-31'])
        self.assertEqual(e.exception.code,2)

    def test_new_run_dispatch_is_lazy_and_declares_actual_range_and_business_dependencies(self):
        with patch('vnext.company_current_records.run_saved_company',return_value={}) as shared, \
             patch.object(ranges,'discover_fiscal_range',side_effect=AssertionError('No upfront discovery')):
            local.run_local(company_id=COMPANY,source_root=self.source,work_dir=self.source.parent/'work',
                output_dir=self.source.parent/'out',period='fiscal-years',metric_ids=['B01','B02'],
                fiscal_year_start=2024,fiscal_year_end=2025)
        args=shared.call_args.kwargs
        self.assertEqual(set(args['case_factories']),{'B01','B02'})
        for metric in args['case_factories']:
            self.assertIn('scripts/vnext/company_fiscal_range.py',args['processing_files_by_metric'][metric])
            self.assertIn('scripts/vnext/historical_statement_cases.py',args['processing_files_by_metric'][metric])
            self.assertIn('scripts/vnext/historical_fiscal_labels.py',args['processing_files_by_metric'][metric])

    def test_lazy_factories_share_one_plan_and_preserve_unrelated_producers(self):
        called=[]
        def producer(**kwargs):called.append(kwargs);return {'prepared':True}
        plan={'tasks':[{'fiscal_year':y,'status':'FISCAL_YEAR_RESOLVED',
                        'period_selection':{'requested_fiscal_year':y},'limitations':[]} for y in (2024,2025)]}
        other=lambda **kwargs:None
        with patch.object(ranges,'discover_fiscal_range',return_value=plan) as discovery:
            factories=ranges.range_case_factories(company_id=COMPANY,fiscal_years=[2024,2025],
                metric_ids=['B01','B02','B04'],case_factories={'B01':producer,'B02':producer,'B04':other})
            discovery.assert_not_called();self.assertIs(factories['B04'],other)
            for metric in ('B01','B02'):
                factories[metric](repo_root=self.source,company_id=COMPANY,metric_id=metric,fiscal_year=2025)
            self.assertEqual(discovery.call_count,1)
            self.assertTrue(all(c['period_selection']=={'requested_fiscal_year':2025} for c in called))
            with self.assertRaisesRegex(ValueError,'FACTORY_SCOPE_CHANGED'):
                factories['B01'](repo_root=self.source,company_id='salesforce',metric_id='B01',fiscal_year=2025)

    def test_unresolved_year_never_calls_business_producer(self):
        with patch.object(ranges,'discover_fiscal_range',return_value={'tasks':[{'fiscal_year':2025,'status':'FISCAL_YEAR_SOURCE_UNRESOLVED','limitations':['missing']}]}) as discover:
            with patch('vnext.historical_statement_cases.prepare_historical_statement_year_case',side_effect=AssertionError('No business case')) as producer:
                factory=ranges.range_case_factories(company_id=COMPANY,fiscal_years=[2025],metric_ids=['B01'],case_factories={'B01':producer})['B01']
                with self.assertRaisesRegex(ValueError,'YEAR_UNRESOLVED'):
                    factory(repo_root=self.source,company_id=COMPANY,metric_id='B01',fiscal_year=2025)
                producer.assert_not_called()

    def test_lazy_factory_freezes_the_callers_year_scope(self):
        years=[2024,2025]
        plan={'tasks':[{'fiscal_year':y,'status':'FISCAL_YEAR_RESOLVED',
                       'period_selection':{'requested_fiscal_year':y},'limitations':[]} for y in years]}
        with patch.object(ranges,'discover_fiscal_range',return_value=plan) as discovery:
            with patch('vnext.historical_statement_cases.prepare_historical_statement_year_case') as producer:
                factory=ranges.range_case_factories(company_id=COMPANY,fiscal_years=years,
                    metric_ids=['B01'],case_factories={'B01':producer})['B01']
                years.append(2026)
                with self.assertRaisesRegex(ValueError,'FACTORY_SCOPE_CHANGED'):
                    factory(repo_root=self.source,company_id=COMPANY,metric_id='B01',fiscal_year=2026)
                discovery.assert_not_called();producer.assert_not_called()
                # Replacing/reordering the caller's list cannot narrow or change
                # the original discovery window either.
                years[:]=[2027,2026]
                factory(repo_root=self.source,company_id=COMPANY,metric_id='B01',fiscal_year=2024)
                factory(repo_root=self.source,company_id=COMPANY,metric_id='B01',fiscal_year=2025)
                self.assertEqual(discovery.call_count,1)
                self.assertEqual(discovery.call_args.kwargs['fiscal_year_start'],2024)
                self.assertEqual(discovery.call_args.kwargs['fiscal_year_end'],2025)
                self.assertEqual([c.kwargs['fiscal_year'] for c in producer.call_args_list],[2024,2025])

    def test_invalid_five_year_bounds_and_metric_scope_are_rejected(self):
        for first,last in [(True,2025),(2025,2024),(2020,2025),(1899,1900)]:
            with self.subTest(first=first,last=last),self.assertRaises(ValueError):self.discover(first,last)
        with self.assertRaisesRegex(ValueError,'METRIC_NOT_CONNECTED'):
            ranges.discover_fiscal_range(repo_root=self.source,company_id=COMPANY,
                fiscal_year_start=2025,fiscal_year_end=2025,metric_ids=['D04'])
