"""Constructed selected C04 controls; no financial result credit."""
from unittest import TestCase
from unittest.mock import patch
from vnext import historical_auditor_case as cases


class HistoricalAuditorCaseTest(TestCase):
    def prepared(self):
        return {'base': {'constructed': 'selected-original-roles'},
                'labelled_annual': {'table_input': {'target_period': {
                    'fiscal_year': 2022, 'period_start': '2022-01-01', 'period_end': '2022-12-31'}}}}

    def case(self, changed=False):
        period=dict(self.prepared()['labelled_annual']['table_input']['target_period'])
        if changed:period['fiscal_year']=2025
        return {'target_period': period, 'selection': {
            'selection_id':'constructed-selection', 'resolver':'constructed-public-core',
            'selected_current_accession':'constructed-target', 'names_differ':False,
            'reason_code':'C04_EVENT_COVERAGE_REQUIRED', 'same_cik_prior_status':'constructed-prior',
            'event_item_claims':[{'large': 'kept in evidence'}],
            'event_source_sets':[{'manifest': {'source_set_manifest_id':'constructed-set'}}]}}

    def test_actual_selected_roles_use_one_public_core_and_complete_evidence_is_separate(self):
        prepared=self.prepared();shared=self.case()
        with patch.object(cases,'prepare_selected_auditor_base',return_value=prepared), \
             patch.object(cases,'prepare_c04_registration_case',return_value=shared) as core:
            result=cases.prepare_historical_auditor_year_case(repo_root='/constructed',
                company_id='sample',metric_id='C04',fiscal_year=2022)
        self.assertIs(core.call_args.kwargs['selected_base'],prepared['base'])
        self.assertIs(core.call_args.kwargs['labelled_annual'],prepared['labelled_annual'])
        self.assertEqual('YEAR_QUARTER_OR_DATE',core.call_args.kwargs['dei_release'])
        self.assertEqual(['8-K','8-K/A','8-K12B','8-K12B/A'],core.call_args.kwargs['event_forms'])
        self.assertIn('event_item_claims',result['input_assessments']['historical_auditor'])
        self.assertNotIn('event_item_claims',result['selection'])
        self.assertEqual(['constructed-set'],result['selection']['event_source_set_ids'])

    def test_public_case_cannot_silently_change_the_requested_year(self):
        with patch.object(cases,'prepare_selected_auditor_base',return_value=self.prepared()), \
             patch.object(cases,'prepare_c04_registration_case',return_value=self.case(True)), \
             self.assertRaisesRegex(ValueError,'SELECTED_PERIOD_CHANGED'):
            cases.prepare_historical_auditor_year_case(repo_root='/constructed',
                company_id='sample',metric_id='C04',fiscal_year=2022)

    def test_other_family_refuses_before_preparation(self):
        with patch.object(cases,'prepare_selected_auditor_base') as source, \
             self.assertRaisesRegex(ValueError,'FAMILY_NOT_RECEIVED'):
            cases.prepare_historical_auditor_year_case(repo_root='/constructed',
                company_id='sample',metric_id='C03',fiscal_year=2022)
        source.assert_not_called()

    def test_public_and_historical_read_dependencies_are_tracked_together(self):
        from vnext.c04_registration_successor import SELECTED_PROCESSING_FILES
        self.assertTrue(set(SELECTED_PROCESSING_FILES) <= set(cases.PROCESSING_FILES))
        self.assertEqual(len(cases.PROCESSING_FILES), len(set(cases.PROCESSING_FILES)))
        for filename in ('historical_governance_input', 'historical_annual_input',
                         'historical_fiscal_labels', 'normal_period_selection',
                         'normal_history_catalog'):
            self.assertIn('scripts/vnext/'+filename+'.py', cases.PROCESSING_FILES)
