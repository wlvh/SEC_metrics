"""Known unimplemented IDs reach explicit gaps; typos remain invalid."""
from unittest import TestCase
from unittest.mock import patch

from tests.vnext import test_history_company_dispatch as fixtures
from vnext.historical_lodging_results import prepare_historical_lodging_year_case


class KnownHistoryPartialScopeTest(TestCase):
    setUp=fixtures.HistoryCompanyDispatchTest.setUp
    run_history=fixtures.HistoryCompanyDispatchTest.run_history

    def test_supported_neighbour_is_dispatched_without_a_fake_missing_producer(self):
        with patch('vnext.company_current_records.run_saved_company',return_value={}) as shared:
            self.run_history(metric_ids=['B10','D02'])
        args=shared.call_args.kwargs
        self.assertEqual(args['metric_ids'],['B10','D02'])
        self.assertEqual(set(args['case_factories']),{'B10'})
        self.assertEqual(set(args['processing_files_by_metric']),{'B10'})
        self.assertIs(args['case_factories']['B10'],prepare_historical_lodging_year_case)

    def test_known_missing_only_has_no_fabricated_case(self):
        with patch('vnext.company_current_records.run_saved_company',return_value={}) as shared:
            self.run_history(metric_ids=['D03'])
        self.assertEqual(shared.call_args.kwargs['case_factories'],{})
        self.assertEqual(shared.call_args.kwargs['processing_files_by_metric'],{})

    def test_unknown_duplicate_or_empty_scope_stops_before_shared_writes(self):
        for metrics in (['B10','D99'],['B10','B10'],[]):
            with self.subTest(metrics=metrics), \
                 patch('vnext.company_current_records.run_saved_company') as shared, \
                 self.assertRaisesRegex(ValueError,'METRIC_SCOPE_INVALID'):
                self.run_history(metric_ids=metrics)
            shared.assert_not_called()
        self.assertFalse((self.root/'state').exists())


if __name__=='__main__':
    import unittest
    unittest.main()
