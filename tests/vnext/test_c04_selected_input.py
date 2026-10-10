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

    def test_year_only_checked_filing_default_dictionary_matches_main(self):
        import subprocess,types
        raw=subprocess.check_output(['git','show','84d15f35eb3f0a7b6dc9e0b06100ceba738c7adf:scripts/vnext/c04_verified_document_alias.py'],cwd=ROOT)
        old=types.ModuleType('vnext._old_c04_alias_control');old.__package__='vnext'
        exec(compile(raw,'main84:c04_verified_document_alias.py','exec'),old.__dict__)
        source=c04_filing('Example Audit LLP',year='2024')
        kwargs=dict(sources=[source],company_id='sample_entity',cik='12345',period_end='2024-12-31',source_proofs=[],aliases=[])
        self.assertEqual(old._checked_filing(**kwargs),_checked_filing(**kwargs))

    def test_selected_gate_does_not_open_default_current_producer(self):
        from vnext.ordinary_saved_result import EXPLICIT_CASE_METRICS, SAVED_METRIC_IDS
        from vnext.ordinary_current_update import run_once
        self.assertIn('C04',EXPLICIT_CASE_METRICS)
        self.assertNotIn('C04',SAVED_METRIC_IDS)
        with self.assertRaisesRegex(ValueError,'CURRENT_UPDATE_METRIC_UNSUPPORTED'):
            run_once(state_root='/unused-state',source_root=ROOT,
                company_id='sample_entity',metric_id='C04')
