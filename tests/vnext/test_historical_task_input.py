"""Historical caller coordinates; this comparison does not admit a source."""
import copy
from pathlib import Path
import unittest

from vnext.ordinary_source_session import compare_annual_inputs


class HistoricalTaskInputTest(unittest.TestCase):
    def setUp(self):
        self.previous = {'company_id': 'sample_entity', 'entity': '12345',
            'filing': {'accessionNumber': '0000012345-25-000001', 'form': '10-K',
                'reportDate': '2025-02-01', 'filingDate': '2025-03-21',
                'primaryDocument': 'source.htm'},
            'amendments': [], 'source_proofs': [],
            'table_input': {'target_period': {'fiscal_year': 2024,
                'period_start': '2024-02-04', 'period_end': '2025-02-01'}}}

    def compare(self, current):
        # These tests isolate already-selected coordinates. The real-source
        # probe separately checks complete raw/native/table input comparison.
        return compare_annual_inputs(previous=self.previous, current=current,
            task_metric_id='D04', previous_root=Path('.'), current_root=Path('.'))

    def test_fiscal_label_is_not_the_calendar_year_of_report_end(self):
        result = self.compare(copy.deepcopy(self.previous))
        self.assertEqual(result['status'], 'NO_SOURCE_CONTENT_CHANGE')
        self.assertFalse(result['input_authenticity_verified_by_comparison'])

    def test_changed_label_or_duration_is_not_unchanged_task_input(self):
        for field, value in (('fiscal_year', 2025), ('period_start', '2024-02-05')):
            with self.subTest(field=field):
                current = copy.deepcopy(self.previous)
                current['table_input']['target_period'][field] = value
                result = self.compare(current)
                self.assertEqual(result['status'], 'PERIOD_INTERPRETATION_CHANGED')
                self.assertTrue(result['requires_candidate_processing'])

    def test_different_entity_is_rejected_before_parsed_equivalence(self):
        current = copy.deepcopy(self.previous)
        current['entity'] = '67890'
        with self.assertRaisesRegex(ValueError, 'SOURCE_UPDATE_SUBJECT_CHANGED'):
            self.compare(current)

    def test_older_selection_is_explicit_stop_not_a_reuse_signal(self):
        current = copy.deepcopy(self.previous)
        current['filing']['reportDate'] = '2024-02-03'
        result = self.compare(current)
        self.assertEqual(result['status'], 'SOURCE_SELECTION_REGRESSED')
        self.assertNotIn(result['status'], {'NO_SOURCE_CONTENT_CHANGE',
                                         'PARSED_TASK_INPUT_UNCHANGED'})

    def test_inline_svg_drawing_change_is_not_unchanged_media_input(self):
        from tests.vnext.test_text_coverage import annual, binding, BODY
        from vnext.ordinary_task_input import parsed_d04_document
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
               '<path d="M0 0 L10 10"/></svg>')
        previous = parsed_d04_document(**binding(annual(BODY+svg)))
        current = parsed_d04_document(**binding(annual(BODY+svg.replace('L10 10', 'L90 90'))))
        self.assertNotEqual(previous['parsed_input_sha256'], current['parsed_input_sha256'])


if __name__ == '__main__':
    unittest.main()
