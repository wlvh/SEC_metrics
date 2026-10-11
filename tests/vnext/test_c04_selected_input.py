"""Explicit selected C04 input keeps the latest default and annual scope checks."""
import unittest
from unittest.mock import patch
from vnext.c04_registration_successor import EVENT_FORMS, prepare_c04_registration_case
from vnext.c04_verified_document_alias import _checked_filing
from vnext.sources import source_reference_record
from vnext.canonical import content_hash
from vnext.normal_source_authority import ROOT
from tests.vnext.test_governance_signals import c04_filing
from tests.vnext.test_text_coverage import binding


def filing_with_release(release, *, entity='12345'):
    old=c04_filing('Example Audit LLP', entity=entity, year='2024')
    raw=old['raw_bytes'].replace(b'xbrl.sec.gov/dei/2025', ('xbrl.sec.gov/dei/'+release).encode())
    args=binding(raw)
    ref=old['source_reference']
    args['source_reference']=source_reference_record(raw_blob=args['raw_blob'], company_id='sample_entity',
        source_url=ref['source_url'],accession=ref['accession'],document_name=ref['document_name'],
        source_role=ref['source_role'],request_attempt_id=ref['request_attempt_id'])
    return {k:args[k] for k in ('raw_bytes','raw_blob','source_reference')}


class SelectedC04InputTest(unittest.TestCase):
    def test_selected_history_reuses_index_derived_gap_boundary_and_all_row_count(self):
        from copy import deepcopy
        from vnext.c04_registration_successor import _checked_inventory_rows
        from vnext.normal_history_catalog import block_last_days
        name = 'CIK0000012345-submissions-001.json'
        shard = {'name':name, 'filingFrom':'2021-01-01',
                 'filingTo':'2022-12-30', 'filingCount':1}
        index = {'filings':{'recent':{'filingDate':['2023-01-02']}}}
        body = {'form':['8-K12B'], 'reportDate':['2022-12-31'],
                'filingDate':['2022-12-31'], 'accessionNumber':['0000012345-22-000007'],
                'primaryDocument':['event.htm']}
        last = block_last_days(payload=index, shards=[shard])[name]
        self.assertEqual('2023-01-01', last)
        with self.assertRaisesRegex(ValueError, 'HISTORY_BODY_ALIGNMENT_CONFLICT'):
            _checked_inventory_rows(body, inventory_name=name, shard=shard)
        rows = _checked_inventory_rows(body, inventory_name=name, shard=shard, block_last_day=last)
        self.assertEqual(('8-K12B', '2022-12-31'), (rows[0]['form'], rows[0]['filingDate']))
        for changed, meta in (({**body, 'filingDate':['2023-01-02']}, shard),
                              (body, {**shard, 'filingCount':2})):
            with self.subTest(changed=changed, meta=meta), \
                 self.assertRaisesRegex(ValueError, 'HISTORY_BODY_ALIGNMENT_CONFLICT'):
                _checked_inventory_rows(changed, inventory_name=name, shard=meta, block_last_day=last)

    def check(self, source, **kwargs):
        return _checked_filing(sources=[source],company_id='sample_entity',cik='12345',
            period_end='2024-12-31',source_proofs=[],aliases=[],**kwargs)

    def test_quarter_and_date_release_require_explicit_existing_policy(self):
        for release in ('2021q4','2024-01-31'):
            source=filing_with_release(release)
            with self.subTest(release=release):
                with self.assertRaisesRegex(ValueError,'C04_FILING_IDENTITY_OR_FORM_CONFLICT'):
                    self.check(source)
                checked=self.check(source,dei_release='YEAR_QUARTER_OR_DATE')
                self.assertEqual('FOUND',checked['status'])
                self.assertEqual('exampleauditllp',checked['canonical_names'][0])
                self.assertEqual(source['source_reference'],checked['source_references'][0])

    def test_fake_namespace_and_invalid_policy_are_not_releases(self):
        for release in ('2021q5','2024-01-31/extra'):
            with self.subTest(release=release),self.assertRaisesRegex(ValueError,'C04_FILING_IDENTITY_OR_FORM_CONFLICT'):
                self.check(filing_with_release(release),dei_release='YEAR_QUARTER_OR_DATE')
        with self.assertRaisesRegex(ValueError,'DEI_RELEASE_SELECTION_INVALID'):
            self.check(filing_with_release('2021q4'),dei_release='ANY_NAMESPACE')

    def test_explicit_release_still_rejects_wrong_entity_and_period(self):
        checked=self.check(filing_with_release('2021q4',entity='54321'),dei_release='YEAR_QUARTER_OR_DATE')
        self.assertEqual('CONFLICT',checked['status'])
        self.assertEqual('C04_AUDITOR_FACT_SCOPE_CONFLICT',checked['problems'][0]['reason'])
        source=filing_with_release('2021q4')
        checked=_checked_filing(sources=[source],company_id='sample_entity',cik='12345',
            period_end='2023-12-31',source_proofs=[],aliases=[],dei_release='YEAR_QUARTER_OR_DATE')
        self.assertEqual('CONFLICT',checked['status'])

    def test_selected_base_and_labelled_annual_are_a_pair_before_latest_read(self):
        for kwargs in ({'selected_base':{}},{'labelled_annual':{}}):
            with self.subTest(kwargs=kwargs),patch('vnext.c04_registration_successor.prepare_saved_governance_input',
                    side_effect=AssertionError('LATEST_MUST_NOT_BE_READ')):
                with self.assertRaisesRegex(ValueError,'C04_SELECTED_BASE_AND_ANNUAL_REQUIRED'):
                    prepare_c04_registration_case(repo_root=ROOT,company_id='sample_entity',
                        event_forms=EVENT_FORMS,**kwargs)

    def test_selected_coordinate_prior_and_label_changes_refuse_before_sources(self):
        from copy import deepcopy
        annual={'company_id':'sample_entity','entity':'12345',
            'table_input':{'target_period':{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}}}
        choice={'current_filing_chain':[{'accessionNumber':'0000012345-26-000001','reportDate':'2025-12-31'}]}
        body={'company_id':'sample_entity','prepared_annual_input':annual,
            'selection':choice,'metric_input_status':{'C04':'PREPARED'},
            'history_alignment_conflicts':[], 'source_proofs':[]}
        args={'target':{'company_id':'sample_entity','period_start':'2025-01-01','period_end':'2025-12-31'},
              'expected_cik':'12345','target_accession':'0000012345-26-000001',
              'current_filings':[], 'prior_filings':[[{}]],'prior_period_end':'2024-12-31'}
        def base(body,args):
            return {'input_binding':{**body,'input_binding_id':content_hash(value=body)},
                    'resolver_inputs':{'c04':{'arguments':args}}}
        labelled={'original_input':annual,'table_input':annual['table_input']}
        cases=[]
        for key,value in (('company_id','different_company'),('expected_cik','54321'),
                          ('target_accession','0000012345-26-000002')):
            altered=deepcopy(args)
            if key=='company_id':altered['target'][key]=value
            else:altered[key]=value
            cases.append((base(body,altered),labelled,'C04_SELECTED_BASE_COORDINATE_CHANGED'))
        altered=deepcopy(args);altered['prior_period_end']='2023-12-31'
        cases.append((base(body,altered),labelled,'C04_SELECTED_PRIOR_NOT_ADJACENT'))
        altered=base(body,args);altered['input_binding']['input_binding_id']='sha256:'+'0'*64
        cases.append((altered,labelled,'C04_SELECTED_BASE_BINDING_CHANGED'))
        altered=deepcopy(args);altered['prior_filings']=None
        altered['current_filings']=[[c04_filing('Example Audit LLP')]]
        cases.append((base(body,altered),labelled,'C04_SELECTED_ANNUAL_SOURCE_PROOF_MISSING'))
        for selected,labels,reason in cases:
            with self.subTest(reason=reason),patch('vnext.c04_registration_successor._Sources',
                    side_effect=AssertionError('NO_SOURCE_READ')):
                with self.assertRaisesRegex(ValueError,reason):
                    prepare_c04_registration_case(repo_root=ROOT,company_id='sample_entity',
                        event_forms=EVENT_FORMS,selected_base=selected,labelled_annual=labels)


    def test_selected_annual_census_cannot_omit_a_conflicting_document_or_filing(self):
        from copy import deepcopy
        current=c04_filing('Example Audit LLP',year='2025')
        extra=c04_filing('Different Audit LLP',year='2025')
        ref=extra['source_reference']
        extra['source_reference']={**ref,'source_reference_id':'test-conflicting-native-document',
            'document_name':'instance.xml','source_url':ref['source_url'].replace('source.htm','instance.xml')}
        prior=c04_filing('Example Audit LLP',year='2024',accession='0000012345-25-000001')
        annual={'company_id':'sample_entity','entity':'12345','table_input':{'target_period':
            {'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}}}
        current_filing={'accessionNumber':current['source_reference']['accession'],'reportDate':'2025-12-31'}
        prior_filing={'accessionNumber':prior['source_reference']['accession'],'reportDate':'2024-12-31'}
        selection={'current_filing_chain':[current_filing],'prior_filing_chain':[prior_filing]}
        sources=[current,extra,prior]
        proofs=[{**{k:source['source_reference'][k] for k in
            ('source_url','accession','document_name','request_attempt_id')},
            'content_sha256':source['source_reference']['raw_asset_id'][7:]} for source in sources]
        census=[{'filing':current_filing,'source_reference_ids':[s['source_reference']['source_reference_id'] for s in (current,extra)]},
                {'filing':prior_filing,'source_reference_ids':[prior['source_reference']['source_reference_id']]}]
        body={'company_id':'sample_entity','prepared_annual_input':annual,'selection':selection,
            'metric_input_status':{'C04':'PREPARED'},'history_alignment_conflicts':[],
            'source_proofs':proofs,'accession_source_sets':census}
        arguments={'target':{'company_id':'sample_entity','period_start':'2025-01-01','period_end':'2025-12-31'},
            'expected_cik':'12345','target_accession':current_filing['accessionNumber'],
            'current_filings':[[current,extra]],'prior_filings':[[prior]],'prior_sources':[],
            'prior_period_end':'2024-12-31'}
        labels={'original_input':annual,'table_input':annual['table_input'],
            'fiscal_year_label_resolution':{'metadata_conflict_retained':False}}
        for changed in ('missing-document','missing-filing','missing-current-filing','duplicate-document','wrong-accession'):
            args=deepcopy(arguments)
            if changed=='missing-document':args['current_filings']=[[current]]
            elif changed=='missing-filing':args['prior_filings']=[]
            elif changed=='missing-current-filing':args['current_filings']=[]
            elif changed=='duplicate-document':args['current_filings']=[[current,current,extra]]
            else:args['prior_filings']=[[current]]
            base={'input_binding':{**body,'input_binding_id':content_hash(value=body)},
                'resolver_inputs':{'c04':{'arguments':args}}}
            with self.subTest(changed=changed), patch('vnext.c04_registration_successor.verify_ordinary_source_proofs'), \
                 patch('vnext.c04_registration_successor._Sources',side_effect=AssertionError('Census omission reached source/calculation')):
                with self.assertRaisesRegex(ValueError,'C04_SELECTED_ANNUAL_(?:SOURCE|FILING)_CENSUS_CHANGED'):
                    prepare_c04_registration_case(repo_root=ROOT,company_id='sample_entity',event_forms=EVENT_FORMS,
                        selected_base=base,labelled_annual=labels)
        missing={k:v for k,v in body.items() if k!='accession_source_sets'}
        base={'input_binding':{**missing,'input_binding_id':content_hash(value=missing)},
              'resolver_inputs':{'c04':{'arguments':arguments}}}
        with patch('vnext.c04_registration_successor.verify_ordinary_source_proofs'), \
             patch('vnext.c04_registration_successor._Sources',side_effect=AssertionError('Incomplete binding reached reader')):
            with self.assertRaisesRegex(ValueError,'C04_SELECTED_ANNUAL_SOURCE_CENSUS_REQUIRED'):
                prepare_c04_registration_case(repo_root=ROOT,company_id='sample_entity',event_forms=EVENT_FORMS,
                    selected_base=base,labelled_annual=labels)
        # Complete selected input must pass the new census gate; the stopped
        # reader is a boundary signal, not a mocked successful company result.
        base={'input_binding':{**body,'input_binding_id':content_hash(value=body)},
              'resolver_inputs':{'c04':{'arguments':arguments}}}
        with patch('vnext.c04_registration_successor.verify_ordinary_source_proofs'), \
             patch('vnext.c04_registration_successor._Sources',side_effect=AssertionError('Complete census admitted')):
            with self.assertRaisesRegex(AssertionError,'Complete census admitted'):
                prepare_c04_registration_case(repo_root=ROOT,company_id='sample_entity',event_forms=EVENT_FORMS,
                    selected_base=base,labelled_annual=labels)

    def test_year_only_checked_filing_default_dictionary_matches_main(self):
        import json,hashlib
        baseline=json.loads((ROOT/'tests/vnext/fixtures/c04_year_only_base84.json').read_text())
        source=c04_filing('Example Audit LLP',year='2024')
        self.assertEqual(baseline['fixture_source_sha256'],hashlib.sha256(source['raw_bytes']).hexdigest())
        checked=_checked_filing(sources=[source],company_id='sample_entity',cik='12345',
            period_end='2024-12-31',source_proofs=[],aliases=[])
        self.assertEqual(baseline['checked_filing'],checked)

    def test_selected_gate_does_not_open_default_current_producer(self):
        from vnext.ordinary_saved_result import EXPLICIT_CASE_METRICS, SAVED_METRIC_IDS
        from vnext.ordinary_current_update import run_once
        self.assertIn('C04',EXPLICIT_CASE_METRICS)
        self.assertNotIn('C04',SAVED_METRIC_IDS)
        with self.assertRaisesRegex(ValueError,'CURRENT_UPDATE_METRIC_UNSUPPORTED'):
            run_once(state_root='/unused-state',source_root=ROOT,
                company_id='sample_entity',metric_id='C04')


class SharedAuditorShardBoundaryTest(unittest.TestCase):
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
