"""Small record-grain checks using the saved, known-conflicting source case."""
import copy
import json
from pathlib import Path
from unittest import TestCase

from vnext.historical_saved_case import case_from_historical_component

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT/'docs/evidence/issue47_history/historical-income-receiving-2026-10-08/B03-component.json'


class HistoricalSavedCaseTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(FIXTURE.read_text())

    def case(self, component=None):
        return case_from_historical_component(component=component or self.original, rules_root=ROOT)

    def test_preserves_ids_dependency_and_both_conflicting_dates(self):
        case = self.case()
        self.assertEqual({'B01', 'B03'}, set(case['results']))
        self.assertEqual(self.original['result']['result_id'], case['results']['B03']['result_id'])
        self.assertEqual(self.original['source_proofs'], case['source_proofs'])
        self.assertEqual(self.original['target_period'], case['target_period'])
        evidence = case['input_assessments']['income_period']['evidence']
        self.assertEqual('2025-08-08', evidence['native_period'][0])
        self.assertEqual('2025-08-07', evidence['visible_periods'][0][0])
        self.assertIsNone(case['results']['B03']['value'])

    def test_missing_dependency_is_not_synthesized(self):
        component = copy.deepcopy(self.original)
        component['records'] = [r for r in component['records']
            if not (r['record_type'] == 'METRIC_RESULT' and r['metric_id'] == 'B01')]
        with self.assertRaisesRegex(ValueError, 'DEPENDENCY_SET_INCOMPLETE'):
            self.case(component)

    def test_duplicate_primary_record_is_rejected(self):
        component = copy.deepcopy(self.original)
        component['records'].append(component['result'])
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_RESULT_OR_TRACE'):
            self.case(component)

    def test_wrong_company_and_period_cannot_become_saved_case(self):
        for field, value in [('company_id', 'CONSTRUCTED_WRONG_COMPANY'), ('period_start', '2024-01-01')]:
            component = copy.deepcopy(self.original)
            component['result'][field] = value
            for record in component['records']:
                if record['record_type'] == 'METRIC_RESULT' and record['metric_id'] == 'B03':
                    record[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'COORDINATE_OR_SPEC_CHANGED'):
                self.case(component)

    def test_trace_id_and_spec_closure_are_checked(self):
        for field, value in [('trace_id', 'sha256:'+'0'*64), ('spec_closure_hash', 'sha256:'+'0'*64)]:
            component = copy.deepcopy(self.original)
            component['result'][field] = value
            for record in component['records']:
                if record['record_type'] == 'METRIC_RESULT' and record['metric_id'] == 'B03':
                    record[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'COORDINATE_OR_SPEC_CHANGED'):
                self.case(component)

    def test_unreceived_family_is_explicit(self):
        component = {**self.original, 'metric_id': 'D04'}
        with self.assertRaisesRegex(ValueError, 'FAMILY_NOT_RECEIVED'):
            self.case(component)
