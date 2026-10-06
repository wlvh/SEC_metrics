"""Fiscal-label failures retain their cause instead of manufacturing a source gap."""
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

from vnext import normal_period_selection as selection
from vnext.normal_annual_input import NormalAnnualInputError
from vnext.ordinary_source_authority import OrdinarySourceAuthorityError


class HistoricalPeriodInputFailureTest(unittest.TestCase):
    def resolve_failure(self, errors, periods=('2024-12-31',)):
        with ExitStack() as stack:
            stack.enter_context(patch.object(selection,'load_history_for_period',return_value={'limitations':[]}))
            stack.enter_context(patch.object(selection,'annual_periods',return_value=[
                {'original':{'form':'10-K'},'report_date':end} for end in periods]))
            stack.enter_context(patch.object(selection,'_registry_rows',return_value=[
                {'company_id':'example','primary_cik':'1'}]))
            stack.enter_context(patch.object(selection,'_subject_policy',return_value={'related_predecessor_ciks':[]}))
            stack.enter_context(patch.object(selection,'_derive',side_effect=AssertionError('Cannot select unread candidate')))
            stack.enter_context(patch.object(selection,'issuer_fiscal_year',side_effect=errors))
            with self.assertRaises(selection.PeriodSelectionError) as caught:
                selection.resolve_period_selection(repo_root=Path('/unused'),company_id='example',fiscal_year=2024)
            return caught.exception

    def test_old_journal_dependency_is_an_implementation_gap_with_its_real_cause(self):
        e=self.resolve_failure([OrdinarySourceAuthorityError('ORDINARY_SOURCE_TRUSTED_JOURNAL_REQUIRED')])
        self.assertEqual(e.category,'IMPLEMENTATION_GAP')
        self.assertIn('TRUSTED_JOURNAL_REQUIRED',str(e))
        self.assertEqual(e.candidate_failures[0]['error_type'],'OrdinarySourceAuthorityError')

    def test_actual_missing_source_retains_the_source_unavailable_class(self):
        e=self.resolve_failure([NormalAnnualInputError('SAVED_SOURCE_MISSING:annual','SOURCE_UNAVAILABLE')])
        self.assertEqual(e.category,'SOURCE_UNAVAILABLE')
        self.assertTrue(str(e).startswith('ORDINARY_PERIOD_SELECTION_CANDIDATE_SOURCE_UNAVAILABLE:'))
        self.assertIn('SAVED_SOURCE_MISSING:annual',str(e))

    def test_subject_conflict_and_unsupported_interval_keep_their_distinct_classes(self):
        for reason,category in [('DEI_SUBJECT_CONFLICT','SOURCE_INTEGRITY_ERROR'),
                                ('ANNUAL_DURATION_NOT_IMPLEMENTED','IMPLEMENTATION_GAP')]:
            with self.subTest(reason=reason):
                e=self.resolve_failure([NormalAnnualInputError(reason,category)])
                self.assertEqual(e.category,category);self.assertIn(reason,str(e))

    def test_unclassified_input_error_does_not_authorize_missing_source_fetch(self):
        e=self.resolve_failure([ValueError('Malformed annual input')])
        self.assertEqual(e.category,'SOURCE_INTEGRITY_ERROR')
        self.assertEqual(e.candidate_failures[0]['reason'],'Malformed annual input')

    def test_matching_label_cannot_hide_an_unread_neighbour(self):
        e=self.resolve_failure([2024,NormalAnnualInputError('SAVED_SOURCE_MISSING:next','SOURCE_UNAVAILABLE')],
                               ('2024-12-31','2025-12-31'))
        self.assertEqual(e.category,'SOURCE_UNAVAILABLE')
        self.assertEqual([f['report_end'] for f in e.candidate_failures],['2025-12-31'])


if __name__=='__main__':unittest.main()
