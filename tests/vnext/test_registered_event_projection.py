"""Small approved event-window checks; no annual installation or egress."""
import copy
from pathlib import Path
import unittest
from sec_urls import submissions_url
from scripts.vnext.canonical import sha256_file
from scripts.vnext import ordinary_projection as projection

ROOT = Path(__file__).resolve().parents[2]
COMPANY = 'paramount_skydance_paramount_global'
ANNUAL = {'fiscal_year': 2025, 'period_start': '2025-01-01', 'period_end': '2025-12-31'}
WINDOW = {**ANNUAL, 'period_start': '2024-01-01'}


class RegisteredEventProjectionTest(unittest.TestCase):
    def setUp(self):
        self.annual = {'company_id': COMPANY, 'entity': '2041610', 'filing': {'reportDate': '2025-12-31'},
            'subject_policy': {'mode': 'SUCCESSOR_REGISTRANT_ONLY'}, 'table_input': {'target_period': ANNUAL}}
        sources = []; references = []; sets = []
        for cik in ('2041610', '813828'):
            reference = {'source_reference_id': 'small-inventory-' + cik, 'company_id': COMPANY,
                         'source_url': submissions_url(cik=int(cik)), 'source_role': 'sec_submissions_inventory'}
            references.append(reference)
            sets.append({'source_set_manifest_id': 'small-set-' + cik, 'company_id': COMPANY,
                'inventory_source_reference_id': reference['source_reference_id'],
                'fiscal_or_date_window': {key: WINDOW[key] for key in ('period_start', 'period_end')}})
            sources.append({'cik': cik, 'source_window': WINDOW, 'inventory_source_reference': reference,
                            'source_set_manifest_ids': ['small-set-' + cik], 'accessions': []})
        scope = {'registered_ciks': ['2041610', '813828'], 'window': WINDOW, 'per_cik_sources': sources,
            'event_projection_catalog_sha256': sha256_file(path=ROOT / 'catalog/zero_ai_public_projection.json'),
            'company_registry_sha256': sha256_file(path=ROOT / 'config/company_registry.csv'),
            'financial_cross_entity_combination_authorized': False}
        self.case = {'primary_metric_id': 'C01', 'references': references, 'rules_root': str(ROOT),
            'input_binding': {'registered_event_scope': scope, 'event_window': WINDOW,
                              'source_set_manifests': sets}}
        self.manifest = {'company_id': COMPANY, 'target_period': WINDOW}
        self.result = {'period_start': WINDOW['period_start'], 'period_end': WINDOW['period_end']}

    def proven(self):
        return projection._registered_event_period(data_root=ROOT, manifest=self.manifest,
                                                   annual=self.annual, case=self.case, result=self.result)

    def test_approved_wide_window_retains_the_original_annual_period(self):
        before = copy.deepcopy(self.annual)
        self.assertTrue(self.proven()); self.assertEqual(self.annual, before)
        # Old native Runs retain the annual reporting coordinate separately.
        self.manifest['target_period'] = ANNUAL
        self.assertTrue(self.proven())

    def test_financial_and_unreceived_e01_do_not_receive_wide_period_exception(self):
        for metric in ('B01', 'B03', 'B08', 'E01'):
            self.case['primary_metric_id'] = metric
            self.assertFalse(self.proven())

    def test_arbitrary_wider_period_or_wrong_label_is_rejected(self):
        for change in ('period_start', 'fiscal_year'):
            case = copy.deepcopy(self.case)
            changed = {**WINDOW, change: '2023-01-01' if change == 'period_start' else 2024}
            case['input_binding']['registered_event_scope']['window'] = changed
            with self.assertRaisesRegex(ValueError, 'EVENT_PERIOD_PROOF_CHANGED'):
                projection._registered_event_period(data_root=ROOT, manifest=self.manifest,
                    annual=self.annual, case=case, result=self.result)

    def test_missing_registrant_or_wrong_inventory_cannot_complete_union(self):
        for change in ('missing', 'inventory', 'source_window', 'manifest'):
            case = copy.deepcopy(self.case); scope = case['input_binding']['registered_event_scope']
            if change == 'missing': scope['per_cik_sources'].pop()
            elif change == 'inventory': scope['per_cik_sources'][0]['inventory_source_reference']['source_url'] = submissions_url(cik=813828)
            elif change == 'source_window': scope['per_cik_sources'][0]['source_window'] = ANNUAL
            else: case['input_binding']['source_set_manifests'][0]['fiscal_or_date_window']['period_start'] = '2023-01-01'
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'EVENT_SCOPE_CHANGED'):
                projection._registered_event_period(data_root=ROOT, manifest=self.manifest,
                    annual=self.annual, case=case, result=self.result)

    def test_wrong_registry_catalog_or_financial_combination_is_rejected(self):
        for field in ('event_projection_catalog_sha256', 'company_registry_sha256', 'financial_cross_entity_combination_authorized'):
            case = copy.deepcopy(self.case)
            case['input_binding']['registered_event_scope'][field] = True if field.endswith('authorized') else 'wrong'
            with self.assertRaisesRegex(ValueError, 'EVENT_SCOPE_CHANGED'):
                projection._registered_event_period(data_root=ROOT, manifest=self.manifest,
                    annual=self.annual, case=case, result=self.result)


if __name__ == '__main__': unittest.main()
