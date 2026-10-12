"""Current C04 thin dispatch and dependency checks; no synthetic business approval."""
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from tests.vnext.common import REPO_ROOT
from vnext import current_auditor_case as current, ordinary_saved_result as saved
from vnext import ordinary_current_update as update


class CurrentAuditorCaseTest(TestCase):
    def failed_base(self, limitations, conflicts=()):
        annual,_=self.fixture()
        base={'input_binding':{'metric_input_status':{'C04':'BLOCKED'},
            'limitations':limitations,'history_alignment_conflicts':list(conflicts)},'resolver_inputs':{}}
        with patch.object(current,'prepare_saved_annual_input',return_value=annual), \
             patch('vnext.normal_governance_input.prepare_saved_governance_input',return_value=base):
            with self.assertRaises(ValueError) as raised:
                current.prepare_current_auditor_case(source_root=Path('/source'),company_id='sample')
        return raised.exception

    def test_failed_request_c04_limitation_is_visible_without_c03_misattribution(self):
        error=self.failed_base([
            {'metric_id':'C03','category':'IMPLEMENTATION_GAP','reason':'UNRELATED_PROXY_CONTROL'},
            {'metric_id':'C04','category':'SOURCE_ACCESS_FAILED',
             'reason':'LATEST_SOURCE_REQUEST_FAILED:https://www.sec.gov/Archives/test.hdr.sgml'}])
        self.assertIn('C04_REGISTRATION_BASE_INPUT_UNRESOLVED',str(error))
        self.assertIn('LATEST_SOURCE_REQUEST_FAILED',str(error))
        self.assertIn('https://www.sec.gov/Archives/test.hdr.sgml',str(error))
        self.assertNotIn('UNRELATED_PROXY_CONTROL',str(error))
        self.assertEqual(error.category,'SOURCE_ACCESS_FAILED')

    def test_snapshot_conflict_summary_keeps_file_and_ranges_without_entire_filing_inventory(self):
        conflict={'history_name':'CIK0000019617-submissions-001.json',
            'reason':'SAVED_HISTORY_INDEX_AND_BODY_ARE_NOT_A_COHERENT_SNAPSHOT',
            'declared_filing_from':'2025-07-15','declared_filing_to':'2025-08-13',
            'block_last_day':'2025-08-13','declared_filing_count':10,'saved_filing_count':12,
            'failed_checks':['FILINGS_OUTSIDE_THE_BLOCK'],
            'out_of_range_filings':[{'accessionNumber':'not-needed-in-user-failure-summary'}]}
        error=self.failed_base([{'metric_id':'C04','category':'SOURCE_COVERAGE_CONFLICT',
            'reason':'GOVERNANCE_HISTORY_SNAPSHOT_COVERAGE_CONFLICT'}],[conflict])
        for value in ('SAVED_HISTORY_INDEX_AND_BODY_ARE_NOT_A_COHERENT_SNAPSHOT',
                      'CIK0000019617-submissions-001.json','2025-07-15','2025-08-13'):
            self.assertIn(value,str(error))
        self.assertNotIn('not-needed-in-user-failure-summary',str(error))
        self.assertEqual(error.category,'SOURCE_COVERAGE_CONFLICT')

    def test_no_c04_limitation_does_not_invent_another_metric_cause(self):
        error=self.failed_base([{'metric_id':'C03','category':'IMPLEMENTATION_GAP','reason':'OTHER_METRIC_ONLY'}])
        self.assertEqual(str(error),'C04_REGISTRATION_BASE_INPUT_UNRESOLVED')

    def fixture(self):
        period={'fiscal_year':2026,'period_start':'2025-02-01','period_end':'2026-01-31'}
        annual={'company_id':'sample','entity':'12345','table_input':{'target_period':period}}
        case={'results':{'C04':{'period_start':period['period_start'],'period_end':period['period_end']}},
            'target_period':period,'selection':{'selection_id':'constructed','event_forms':current.EVENT_FORMS,
                'event_source_sets':[{'manifest':{'source_set_manifest_id':'source-set'}}],
                'same_cik_prior_status':'MISSING','reason_code':'C04_COMPARABLE_AUDITOR_FACTS_MISSING'}}
        return annual,case

    def test_current_case_selects_explicit_core_and_keeps_noncalendar_period(self):
        annual,case=self.fixture();base={'constructed_base':True}
        with patch.object(current,'prepare_saved_annual_input',return_value=annual) as selection, \
             patch('vnext.normal_governance_input.prepare_saved_governance_input',return_value=base) as input_base, \
             patch.object(current,'prepare_c04_registration_case',return_value=case) as core:
            v=current.prepare_current_auditor_case(source_root=Path('/source'),company_id='sample')
        self.assertEqual(v['target_period']['fiscal_year'],2026)
        self.assertEqual(core.call_args.kwargs['event_forms'],current.EVENT_FORMS)
        self.assertIs(core.call_args.kwargs['labelled_annual'],annual)
        self.assertIs(core.call_args.kwargs['selected_base'],base)
        self.assertEqual(input_base.call_args.kwargs['rules_root'],current.ROOT)
        self.assertTrue(selection.call_args.kwargs['ordinary_registered'])
        self.assertEqual(v['input_assessments']['current_auditor'],case['selection'])
        self.assertNotIn('event_source_sets',v['selection'])
        self.assertEqual(v['selection']['event_source_set_ids'],['source-set'])

    def test_changed_period_not_projected_as_current(self):
        annual,case=self.fixture();case=deepcopy(case);case['target_period']['fiscal_year']=2025
        with patch.object(current,'prepare_saved_annual_input',return_value=annual), \
             patch('vnext.normal_governance_input.prepare_saved_governance_input',return_value={}), \
             patch.object(current,'prepare_c04_registration_case',return_value=case):
            with self.assertRaisesRegex(ValueError,'CURRENT_C04_SOURCE_PERIOD_CHANGED'):
                current.prepare_current_auditor_case(source_root=Path('/source'),company_id='sample')

    def test_writer_selects_current_c04_without_zero_ai_formula(self):
        with patch.object(saved,'_save_case',side_effect=lambda **kw:kw['factory'](Path('/source'))), \
             patch.object(current,'prepare_current_auditor_case',return_value={'current_c04':True}) as core, \
             patch.object(saved,'_ordinary_case',side_effect=AssertionError('No unsupported zeroAI graph')):
            self.assertEqual(saved.create_saved_result(source_root=Path('/source'),output_root=Path('/new'),
                company_id='sample',metric_id='C04'),{'current_c04':True})
        core.assert_called_once_with(source_root=Path('/source'),company_id='sample')

    def test_only_c04_consumes_new_wrapper_dependency(self):
        before={m:update._configuration(REPO_ROOT,'marriott_international',m) for m in ('B01','C04')}
        original=update.sha256_file
        with patch.object(update,'sha256_file',side_effect=lambda *,path:
            'new-current-c04-version' if path==REPO_ROOT/'scripts/vnext/current_auditor_case.py' else original(path=path)):
            after={m:update._configuration(REPO_ROOT,'marriott_international',m) for m in before}
        self.assertEqual(before['B01'],after['B01']);self.assertNotEqual(before['C04'],after['C04'])
        self.assertIn('scripts/vnext/c04_registration_successor.py',after['C04']['processing_files'])


class CurrentGovernanceRegistryCompatibilityTest(TestCase):
    def test_explicit_rule_root_ignores_valid_other_company_row_default_stays_old(self):
        import tempfile
        from vnext import normal_governance_input as inputs
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder);(source/'config').mkdir();(source/'evidence').mkdir()
            registry=(REPO_ROOT/'config/company_registry.csv').read_bytes()
            (source/'config/company_registry.csv').write_bytes(registry.replace(b'pfizer,Pfizer,',b'pfizer,Other display,'))
            (source/'evidence/requests_log.csv').write_bytes(b'constructed-test-only')
            with patch.object(inputs,'prepare_saved_annual_input',side_effect=ValueError('CONTROL_AFTER_REGISTRY_CHECK')):
                with self.assertRaisesRegex(ValueError,'GOVERNANCE_COMPANY_REGISTRY_DIFFERS'):
                    inputs.prepare_saved_governance_input(repo_root=source,company_id='marriott_international')
                with self.assertRaisesRegex(ValueError,'CONTROL_AFTER_REGISTRY_CHECK'):
                    inputs.prepare_saved_governance_input(repo_root=source,company_id='marriott_international',rules_root=REPO_ROOT)
                (source/'config/company_registry.csv').write_bytes(registry.replace(b'marriott_international,Marriott International,1048286,',b'marriott_international,Marriott International,19617,'))
                with self.assertRaisesRegex(ValueError,'GOVERNANCE_COMPANY_REGISTRY_DIFFERS'):
                    inputs.prepare_saved_governance_input(repo_root=source,company_id='marriott_international',rules_root=REPO_ROOT)
