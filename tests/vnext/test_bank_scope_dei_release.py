"""Finite release plumbing and A09 route controls, not financial acceptance."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.test_dei_release_selection import annual, PERIOD, SUCCESSOR
from vnext import financial_relationships as relationships
from vnext import financial_structured as structured
from vnext import ordinary_current_update as update
from vnext.financial_balance_scope import inspect_aum_balance
from vnext.canonical import sha256_bytes
from vnext.normal_annual_input import NormalAnnualInputError
from vnext.ordinary_saved_result import EXPLICIT_CASE_METRICS
from vnext.company_current_records import CURRENT_METRICS

ROOT = Path(__file__).resolve().parents[2]


def source(namespace='http://xbrl.sec.gov/dei/2021q4'):
    return annual(namespace).replace(b'</html>', b'<ix:nonNumeric '
        b'name="dei:EntityRegistrantName" contextRef="annual">Example Bank Inc.'
        b'</ix:nonNumeric></html>')


class BankScopeDeiReleaseTest(unittest.TestCase):
    readers = (relationships.inspect_nim_relationships,
               relationships.inspect_nonaccrual_loan_ratio, inspect_aum_balance)

    def args(self, raw):
        return dict(repo_root=ROOT, source_bytes=raw,
                    expected_source_sha256=sha256_bytes(content=raw),
                    expected_cik='19617', target_period=PERIOD)

    def test_all_three_real_parsers_require_explicit_old_release(self):
        raw = source()
        for reader in self.readers:
            with self.subTest(reader=reader.__name__):
                with self.assertRaisesRegex(NormalAnnualInputError, 'DEI_MISSING_OR_AMBIGUOUS'):
                    reader(**self.args(raw))
                component = reader(**self.args(raw), dei_release=SUCCESSOR)
                self.assertEqual(component['source_sha256'], sha256_bytes(content=raw))
                # No relevant table is present. Plumbing cannot create a value.
                self.assertIsNone(component.get('value'))

    def test_original_year_default_returns_same_components(self):
        raw = source('http://xbrl.sec.gov/dei/2021')
        for reader in self.readers:
            with self.subTest(reader=reader.__name__):
                self.assertEqual(reader(**self.args(raw)),
                                 reader(**self.args(raw), dei_release='YEAR_ONLY'))

    def test_wrong_source_subject_period_and_option_still_reject(self):
        raw = source()
        for reader in self.readers:
            with self.subTest(reader=reader.__name__):
                with self.assertRaisesRegex(ValueError, 'SOURCE_BYTES_DIFFER'):
                    reader(**{**self.args(raw), 'expected_source_sha256': '0'*64}, dei_release=SUCCESSOR)
                with self.assertRaisesRegex(NormalAnnualInputError, 'DEI_SUBJECT_CONFLICT'):
                    reader(**{**self.args(raw), 'expected_cik': '1'}, dei_release=SUCCESSOR)
                with self.assertRaisesRegex(NormalAnnualInputError, 'DEI_RELEASE_SELECTION_INVALID'):
                    reader(**self.args(raw), dei_release='.*')
                wrong = source().replace(b'2021-12-31', b'2021-09-30')
                with self.assertRaisesRegex(NormalAnnualInputError, 'DEI_FISCAL_YEAR_CONFLICT|DEI_REPORT_DATE_CONFLICT'):
                    reader(**self.args(wrong), dei_release=SUCCESSOR)

    def test_a09_primary_has_priority_and_forwards_selection(self):
        args = dict(repo_root=ROOT, source_bytes=source(), source_reference={},
                    source_set_manifest={}, expected_cik='19617', target_period=PERIOD)
        primary = {'outcome': 'STRUCTURED_PRIMARY_RESOLVED', 'value': '0.001'}
        with patch.object(structured, 'inspect_inline_financial_claims', return_value=primary) as native, \
                patch.object(relationships, 'inspect_nonaccrual_loan_ratio') as fallback:
            result = structured.inspect_ordinary_a09_source_fact(**args, dei_release=SUCCESSOR)
        self.assertEqual(result['value'], '0.001')
        self.assertEqual(native.call_args.kwargs['dei_release'], SUCCESSOR)
        fallback.assert_not_called()

    def test_a09_only_complete_ambiguity_enters_html_with_same_option(self):
        args = dict(repo_root=ROOT, source_bytes=source(), source_reference={},
                    source_set_manifest={}, expected_cik='19617', target_period=PERIOD)
        for outcome, scope, allowed in (
            ('STRUCTURED_SOURCE_AMBIGUOUS', 'NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET', True),
            ('STRUCTURED_SOURCE_AMBIGUOUS', 'INCOMPLETE', False),
            ('STRUCTURED_IMPLEMENTATION_GAP', 'NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET', False)):
            with self.subTest(outcome=outcome, scope=scope), \
                    patch.object(structured, 'inspect_inline_financial_claims',
                        return_value={'outcome': outcome, 'source_set_scope': scope}), \
                    patch.object(relationships, 'inspect_nonaccrual_loan_ratio',
                        return_value={'status': 'UNRESOLVED', 'value': None}) as fallback:
                result = structured.inspect_ordinary_a09_source_fact(**args, dei_release=SUCCESSOR)
                self.assertIsNone(result['value'])
                self.assertEqual(fallback.call_count, int(allowed))
                if allowed:
                    self.assertEqual(fallback.call_args.kwargs['dei_release'], SUCCESSOR)

    def test_a09_source_failure_cannot_become_ambiguity(self):
        with patch.object(structured, 'inspect_inline_financial_claims',
                side_effect=ValueError('SOURCE_BYTES_DIFFER')), \
                patch.object(relationships, 'inspect_nonaccrual_loan_ratio') as fallback:
            with self.assertRaisesRegex(ValueError, 'SOURCE_BYTES_DIFFER'):
                structured.inspect_ordinary_a09_source_fact(repo_root=ROOT, source_bytes=source(),
                    source_reference={}, source_set_manifest={}, expected_cik='19617',
                    target_period=PERIOD, dei_release=SUCCESSOR)
        fallback.assert_not_called()

    def test_selected_case_set_does_not_expand_default_or_bypass_factory(self):
        for metric in ('A04', 'A09', 'A11'):
            self.assertIn(metric, EXPLICIT_CASE_METRICS)
            self.assertNotIn(metric, CURRENT_METRICS)
            with tempfile.TemporaryDirectory() as tmp, self.subTest(metric=metric):
                with self.assertRaisesRegex(ValueError, 'CURRENT_UPDATE_METRIC_UNSUPPORTED'):
                    update.run_once(state_root=Path(tmp)/'state', source_root=Path(tmp)/'source',
                        company_id='constructed', metric_id=metric, fiscal_year=2021)
                self.assertFalse((Path(tmp)/'state').exists())


if __name__ == '__main__':
    unittest.main()
