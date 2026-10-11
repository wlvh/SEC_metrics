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

    def test_selected_base_carries_the_readers_complete_filing_sets(self):
        from pathlib import Path
        from types import SimpleNamespace
        from vnext.historical_governance_input import prepare_selected_auditor_base
        from vnext.canonical import content_hash
        annual = {**self.prepared, 'company_id': 'constructed', 'entity': '12345',
                  'subject_policy': {'mode': 'CONTINUOUS_PRIMARY'}, 'source_proofs': []}
        history = {'all_rows': self.rows, 'loaded_inventories': ['main.json', 'saved-shard'],
                   'inventory': {'source_reference': {'document_name': 'main.json'}},
                   'limitations': [], 'reporting_cik': '12345'}
        reader = SimpleNamespace(file_sets=[], records={}, proofs={}, read=lambda *a, **k: None)

        def read_complete_filing(filing):
            # Constructed index-bound HTML and XML sets; no auditor value is
            # invented. The real source reader owns construction/verification.
            accession = filing['accessionNumber']
            refs = [{'source_reference_id': accession + ':html', 'accession': accession},
                    {'source_reference_id': accession + ':xml', 'accession': accession}]
            reader.file_sets.append({'filing': filing,
                                     'index_source_reference_id': accession + ':index',
                                     'source_reference_ids': [r['source_reference_id'] for r in refs],
                                     'expected_xml_documents': ['instance.xml'],
                                     'primary_saved': True})
            return [{'source_reference': ref} for ref in refs]

        reader.auditor_filing = read_complete_filing
        with patch('vnext.normal_period_selection.resolve_period_selection', return_value={}), \
             patch('vnext.historical_annual_input.prepare_historical_annual_input', return_value=annual), \
             patch('vnext.normal_history_catalog.load_history_for_period', return_value=history), \
             patch('vnext.normal_governance_input._Sources', return_value=reader):
            selected = prepare_selected_auditor_base(repo_root=Path('/constructed'),
                company_id='constructed', fiscal_year=2022)
        binding = selected['base']['input_binding']
        self.assertIs(reader.file_sets, binding['accession_source_sets'])
        self.assertEqual(['target-amendment', 'target', 'prior-amendment', 'prior'],
                         [s['filing']['accessionNumber'] for s in binding['accession_source_sets']])
        self.assertTrue(all(len(s['source_reference_ids']) == 2 for s in binding['accession_source_sets']))
        self.assertEqual(content_hash(value={k: v for k, v in binding.items()
                                            if k != 'input_binding_id'}), binding['input_binding_id'])
        from vnext.c04_registration_successor import _check_selected_annual_census
        arguments = selected['base']['resolver_inputs']['c04']['arguments']
        _check_selected_annual_census(binding, arguments)
        incomplete = deepcopy(arguments)
        incomplete['current_filings'][0].pop()
        with self.assertRaisesRegex(ValueError, 'C04_SELECTED_ANNUAL_SOURCE_CENSUS_CHANGED'):
            _check_selected_annual_census(binding, incomplete)
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


class HistoricalAuditorShardBoundaryTest(TestCase):
    """Constructed metadata, using the real loader and its coherence checks."""
    def setUp(self):
        self.name = 'CIK0000012345-submissions-001.json'
        self.older = 'CIK0000012345-submissions-002.json'
        self.shard = {'name': self.name, 'filingFrom': '2020-01-01',
                      'filingTo': '2021-12-28', 'filingCount': 1}
        self.older_shard = {'name': self.older, 'filingFrom': '2019-01-01',
                           'filingTo': '2019-12-30', 'filingCount': 1}
        self.target = ('0000012345-23-000001', '2023-02-01', '2022-12-31', '10-K', 'annual.htm')
        self.prior = ('0000012345-22-000001', '2022-02-01', '2021-12-31', '10-K', 'prior.htm')
        self.gap = ('0000012345-22-000003', '2022-01-02', '2022-01-02', '8-K', 'event.htm')

    def columns(self, *rows):
        keys = ('accessionNumber', 'filingDate', 'reportDate', 'form', 'primaryDocument')
        return {key: [row[index] for row in rows] for index, key in enumerate(keys)}

    def load(self, *, body=None, missing=False, target=None, prior=None, report_end='2022-12-31'):
        import json
        from pathlib import Path
        from vnext import normal_history_catalog as catalog
        main = 'CIK0000012345.json'
        documents = {main: {'cik': '12345', 'filings': {
            'recent': self.columns(target or self.target, prior or self.prior),
            'files': [self.shard, self.older_shard]}}}
        if not missing:
            documents[self.name] = body if body is not None else self.columns(self.gap)
        read_names = []

        class SavedMetadata:
            def read(self, url, *, required=True, **kwargs):
                name = url.rsplit('/', 1)[-1]
                read_names.append(name)
                if name not in documents:
                    if not required:
                        return None
                    raise AssertionError('Unrelated old metadata must not be loaded')
                return {'raw_bytes': json.dumps(documents[name]).encode(),
                        'source_reference': {'document_name': name}}

        with patch.object(catalog, '_company', return_value={
                'company_id': 'constructed', 'primary_cik': '12345'}), \
             patch.object(catalog, '_subject_policy', return_value={}):
            value = catalog.load_history_for_period(repo_root=Path('/constructed'),
                company_id='constructed', report_end=report_end, reader=SavedMetadata())
        return value, read_names

    def test_gap_day_shard_is_loaded_before_an_older_irrelevant_block(self):
        value, names = self.load()
        self.assertEqual(['CIK0000012345.json', self.name], names)
        self.assertIn(self.name, value['loaded_inventories'])
        self.assertIn(self.gap[0], {row['accessionNumber'] for row in value['all_rows']})
        self.assertTrue(value['window_proven'])
        self.assertEqual([], value['limitations'])

    def test_unread_derived_boundary_reaches_requested_end(self):
        # Metadata only: these dates exercise the declared gap, not a
        # claim about a real issuer's annual duration or fiscal-year label.
        target = ('0000012345-22-000002', '2022-02-01', '2022-01-01', '10-K', 'annual.htm')
        prior = ('0000012345-22-000001', '2022-01-15', '2020-12-31', '10-K', 'prior.htm')
        value, _ = self.load(missing=True, target=target, prior=prior, report_end='2022-01-01')
        self.assertEqual([self.name], value['unloaded_history_reaching_period'])
        self.assertFalse(value['window_proven'])
        self.assertEqual('HISTORY_SHARD_NOT_SAVED', value['limitations'][0]['kind'])

    def test_derived_boundary_does_not_relax_all_row_count_or_outside_dates(self):
        for change in ('count', 'outside'):
            with self.subTest(change=change):
                self.shard['filingCount'] = 2 if change == 'count' else 1
                row = self.gap if change == 'count' else (
                    self.gap[0], '2022-02-01', self.gap[2], self.gap[3], self.gap[4])
                value, _ = self.load(body=self.columns(row))
                self.assertFalse(value['window_proven'])
                issue = value['limitations'][0]
                self.assertEqual('HISTORY_SHARD_SNAPSHOT_CONFLICT', issue['kind'])
                self.assertIn('FILING_COUNT_DIFFERS_FROM_DECLARED' if change == 'count'
                              else 'FILINGS_OUTSIDE_THE_BLOCK', issue['failed_checks'])

    def test_wrong_shard_entity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'HISTORY_SHARD_ENTITY_CONFLICT'):
            self.load(body={**self.columns(self.gap), 'cik': '54321'})
