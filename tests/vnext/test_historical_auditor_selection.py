"""Pinned governance metadata controls; no financial content credit."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from vnext.historical_governance_input import select_historical_governance_metadata as select

FORMS=['8-K','8-K/A','8-K12B','8-K12B/A']
class HistoricalAuditorSelectionTest(TestCase):
    def setUp(self):
        def row(acc,report,filing,form='10-K'):
            return {'accessionNumber':acc,'primaryDocument':acc+'.htm','reportDate':report,
                    'filingDate':filing,'form':form}
        self.target=row('target','2022-12-31','2023-02-01')
        self.rows=[row('prior','2021-12-31','2022-02-01'),self.target,
            row('latest','2025-12-31','2026-02-01'),row('target-amendment','2022-12-31','2023-03-01','10-K/A'),
            row('prior-amendment','2021-12-31','2022-03-01','10-K/A'),
            row('inside','2022-02-01','2022-03-01','8-K'),row('registration','2022-03-01','2022-03-02','8-K12B'),
            row('outside','2023-03-01','2023-03-02','8-K'),
            row('proxy','2022-12-31','2023-04-01','DEF 14A'),row('latest-proxy','2025-12-31','2026-04-01','DEF 14A')]
        self.prepared={'table_input':{'target_period':{'fiscal_year':2022,'period_start':'2022-01-01','period_end':'2022-12-31'}},'filing':self.target}
    def check(self,**kw):return select(prepared=self.prepared,history={'all_rows':self.rows,'loaded_inventories':['saved-shard']},**kw)
    def test_selected_year_and_ordered_amendments_do_not_use_latest(self):
        chosen=self.check(event_forms=FORMS)
        self.assertEqual(['target-amendment','target'],[r['accessionNumber'] for r in chosen['current_filing_chain']])
        self.assertEqual(['prior-amendment','prior'],[r['accessionNumber'] for r in chosen['prior_filing_chain']])
        self.assertNotIn('pinned_def14a',chosen)
    def test_explicit_registration_scope_keeps_only_actual_period_events(self):
        self.assertEqual(['inside','registration'],[r['accessionNumber'] for r in self.check(event_forms=FORMS)['events']])
        self.assertEqual(['inside'],[r['accessionNumber'] for r in self.check()['events']])
    def test_absent_prior_is_named_and_never_borrowed_from_successor(self):
        self.rows=[r for r in self.rows if not r['accessionNumber'].startswith('prior')]
        chosen=self.check(event_forms=FORMS)
        self.assertEqual('NO_ADJACENT_SAME_CIK_PRIOR_IN_LOADED_BLOCKS',chosen['prior_status'])
        self.assertEqual([],chosen['prior_filing_chain'])
    def test_same_date_wrong_accession_and_ambiguous_prior_refuse(self):
        self.prepared['filing']={**self.target,'accessionNumber':'wrong'}
        with self.assertRaisesRegex(ValueError,'PINNED_ANNUAL_DIVERGED'):self.check()
        self.prepared['filing']=self.target
        self.rows.append({**self.rows[0],'accessionNumber':'duplicate-prior'})
        with self.assertRaisesRegex(ValueError,'PRIOR_ANNUAL_AMBIGUOUS'):self.check()
    def test_arbitrary_event_forms_cannot_expand_scope(self):
        for forms in (['8-K','6-K'],['8-K','8-K'], '8-K'):
            with self.subTest(forms=forms),self.assertRaisesRegex(ValueError,'EVENT_FORMS_UNSUPPORTED'):self.check(event_forms=forms)
    def test_selection_does_not_change_original_rows_or_dates(self):
        before=deepcopy((self.prepared,self.rows));self.check(event_forms=FORMS)
        self.assertEqual(before,(self.prepared,self.rows))
    def test_unread_or_rejected_metadata_is_not_a_complete_auditor_window(self):
        for change in ({'limitations':[{'kind':'CONSTRUCTED_MISSING_SHARD'}]},
                       {'unloaded_history_reaching_period':['unread-shard']}):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'WINDOW_INCOMPLETE'):
                select(prepared=self.prepared,history={'all_rows':self.rows,
                    'loaded_inventories':['saved-shard'],**change},event_forms=FORMS)
    def test_selected_cik_cannot_borrow_current_registry_subject(self):
        self.prepared['entity']='1'
        with self.assertRaisesRegex(ValueError,'SELECTED_CIK_CHANGED'):
            select(prepared=self.prepared,history={'all_rows':self.rows,
                'loaded_inventories':['saved-shard'],'reporting_cik':'2'},event_forms=FORMS)
    def test_selected_base_rebuilds_source_and_refuses_successor_before_auditor_read(self):
        from vnext.historical_governance_input import prepare_selected_auditor_base
        prepared={'subject_policy':{'mode':'SUCCESSOR_REGISTRANT_ONLY'}}
        with patch('vnext.normal_period_selection.resolve_period_selection',return_value={'selected':'constructed'}) as select, \
             patch('vnext.historical_annual_input.prepare_historical_annual_input',return_value=prepared) as rebuild, \
             patch('vnext.normal_governance_input._Sources') as read:
            with self.assertRaisesRegex(ValueError,'SUBJECT_NOT_COMPARABLE'):
                prepare_selected_auditor_base(repo_root='/constructed',company_id='sample',fiscal_year=2025)
        self.assertEqual(rebuild.call_args.kwargs['period_selection'],select.return_value)
        read.assert_not_called()
    def test_older_annual_is_not_substituted_for_missing_actual_prior(self):
        self.rows[0]['reportDate']='2020-12-31'
        with self.assertRaisesRegex(ValueError,'PRIOR_ORIGINAL_MISSING'):
            self.check(event_forms=FORMS)
        self.rows=[r for r in self.rows if r['accessionNumber']!='prior-amendment']
        chosen=self.check(event_forms=FORMS)
        self.assertIsNone(chosen['prior_ordinary'])
        self.assertEqual('2021-12-31',chosen['expected_prior_period_end'])
        self.assertEqual([],chosen['prior_filing_chain'])
    def test_noncalendar_and_53_week_period_use_actual_start_not_year_arithmetic(self):
        self.prepared['table_input']['target_period'].update(period_start='2023-01-29',period_end='2024-02-03',fiscal_year=2023)
        self.target['reportDate']='2024-02-03'
        self.target['filingDate']='2024-03-01'
        self.rows[0]['reportDate']='2023-01-28'
        self.rows[0]['filingDate']='2023-03-01'
        chosen=self.check(event_forms=FORMS)
        self.assertEqual('2023-01-28',chosen['expected_prior_period_end'])
        self.assertEqual('prior',chosen['prior_ordinary']['accessionNumber'])
