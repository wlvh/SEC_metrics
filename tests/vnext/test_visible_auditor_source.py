"""Visible report candidates retain their source boundaries and no C04 credit."""
import copy
import unittest

from tests.vnext.test_text_coverage import annual, binding
from vnext.canonical import content_hash, sha256_bytes
from vnext.text_coverage import TextCoverageError
from vnext.visible_auditor_source import (inspect_visible_auditor_report,
                                         verify_visible_auditor_report)


REPORT = '''<h2>Report of Independent Registered Public Accounting Firm</h2>
<p>To the Board of Directors and Stockholders of Example Company</p>
<p>We have audited the accompanying consolidated balance sheets of Example Company
and its subsidiaries (the “Company”) as of December 31, 2025 and 2024, and the
related consolidated statements of income for the years then ended.</p>
<p>In our opinion, these financial statements present fairly the financial position.</p>
<p>/s/ Example Audit LLP</p><p>February 4, 2026</p>
<h2>CONSOLIDATED STATEMENTS OF CASH FLOWS</h2>'''
CHARTER_COVER = '''<p>SECURITIES AND EXCHANGE COMMISSION</p><p>FORM 10-K</p>
<p>Example Company</p><p>(Exact name of registrant as specified in its charter)</p>'''


def arguments(body=REPORT):
    raw = annual(body).replace(b'</ix:hidden>',
        b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">'
        b'Example Company</ix:nonNumeric></ix:hidden>')
    return binding(raw)


class VisibleAuditorSourceTest(unittest.TestCase):
    def test_nonempty_report_and_exact_replay_without_result_credit(self):
        args = arguments()
        got = inspect_visible_auditor_report(**args)
        self.assertEqual('BOUND_REPORT_CANDIDATE', got['status'])
        self.assertEqual('Example Company', got['registrant_name'])
        report = got['reports'][0]
        self.assertEqual('/s/ Example Audit LLP', report['signatures'][0]['text'])
        for span in [report, report['heading'], *report['auditee'],
                     *report['opinions'], *report['signatures'], *report['report_dates']]:
            self.assertEqual(sha256_bytes(content=args['raw_bytes'][
                span['raw_start_byte']:span['raw_end_byte']]), span['raw_span_sha256'])
        self.assertEqual(got, verify_visible_auditor_report(inspection=got, **args))
        self.assertFalse(got['native_fact_credit'])
        self.assertFalse(got['metric_result_credit'])
        self.assertFalse(got['publication_credit'])

    def test_contents_link_and_elsewhere_signature_are_not_reports(self):
        toc = '<p><a href="#audit">Report of Independent Registered Public Accounting Firm</a></p>'
        body = toc + REPORT
        got = inspect_visible_auditor_report(**arguments(body))
        self.assertEqual(1, len(got['reports']))
        body = REPORT.replace('<p>/s/ Example Audit LLP</p>', '') + '<p>/s/ Company CEO</p>'
        got = inspect_visible_auditor_report(**arguments(body))
        self.assertEqual('UNRESOLVED', got['status'])
        self.assertIn('VISIBLE_AUDITOR_REPORT_SIGNATURE_NOT_UNIQUE', got['reports'][0]['reasons'])
        self.assertEqual([], got['reports'][0]['signatures'])

    def test_subject_period_and_signature_each_must_be_established(self):
        variants = [
            (REPORT.replace('Stockholders of Example Company', 'Stockholders of Another Company'),
             'AUDITEE_NOT_ESTABLISHED'),
            (REPORT.replace('balance sheets of Example Company', 'balance sheets of Another Company'),
             'OPINION_SUBJECT_NOT_ESTABLISHED'),
            (REPORT.replace('as of December 31, 2025', 'as of December 31, 2024'),
             'OPINION_PERIOD_NOT_ESTABLISHED'),
            (REPORT.replace('<p>/s/ Example Audit LLP</p>', '<p style="display:none">/s/ Example Audit LLP</p>'),
             'REPORT_SIGNATURE_NOT_UNIQUE'),
            (REPORT.replace('February 4, 2026', 'February 4, 2025'),
             'REPORT_DATE_NOT_ESTABLISHED'),
        ]
        for body, reason in variants:
            with self.subTest(reason=reason):
                got = inspect_visible_auditor_report(**arguments(body))
                self.assertEqual('UNRESOLVED', got['status'])
                self.assertIn('VISIBLE_AUDITOR_' + reason, got['reports'][0]['reasons'])

    def test_report_conflicts_are_not_resolved_by_first_match(self):
        for body in [REPORT + REPORT.replace('Example Audit LLP', 'Other Audit LLP'),
                     REPORT.replace('<p>/s/ Example Audit LLP</p>',
                        '<p>/s/ Example Audit LLP</p><p>/s/ Other Audit LLP</p>')]:
            got = inspect_visible_auditor_report(**arguments(body))
            self.assertEqual('UNRESOLVED', got['status'])

    def test_unsupported_layout_and_truncation_are_never_absence(self):
        got = inspect_visible_auditor_report(**arguments('<p>No located report.</p>'))
        self.assertEqual('UNRESOLVED', got['status'])
        args = arguments()
        args['raw_bytes'] = args['raw_bytes'].replace(b'</body></html>', b'')
        args = binding(args['raw_bytes'])
        got = inspect_visible_auditor_report(**args)
        self.assertEqual('UNRESOLVED', got['status'])
        self.assertIn('TEXT_FRAGMENT_OR_TRUNCATED_DOCUMENT', got['reasons'])

    def test_identity_and_rehashed_locator_mutation_rejected(self):
        args = arguments()
        changed = copy.deepcopy(inspect_visible_auditor_report(**args))
        changed['reports'][0]['signatures'][0]['raw_start_byte'] += 1
        changed['inspection_id'] = content_hash(value={
            k: v for k, v in changed.items() if k != 'inspection_id'})
        with self.assertRaisesRegex(ValueError, 'REPLAY_MISMATCH'):
            verify_visible_auditor_report(inspection=changed, **args)
        args['expected_cik'] = '54321'
        with self.assertRaises(ValueError):
            inspect_visible_auditor_report(**args)
        args = arguments()
        args['raw_bytes'] += b'changed'
        with self.assertRaisesRegex(TextCoverageError, 'BYTES_CHANGED'):
            inspect_visible_auditor_report(**args)

    def test_fake_name_namespace_or_missing_name_unresolved(self):
        for raw in [arguments()['raw_bytes'].replace(b'dei:EntityRegistrantName', b'custom:EntityRegistrantName'),
                    annual(REPORT)]:
            got = inspect_visible_auditor_report(**binding(raw))
            self.assertEqual('UNRESOLVED', got['status'])
            self.assertIn('VISIBLE_AUDITOR_REGISTRANT_NAME_NOT_UNIQUE', got['reasons'])

    def test_shared_text_reader_default_remains_unmodified(self):
        # This adapter is explicit; old text input remains the same document.
        from vnext.text_coverage import build_text_document
        args = arguments()
        before = build_text_document(**args)
        inspect_visible_auditor_report(**args)
        self.assertEqual(before, build_text_document(**args))

    def test_date_namespace_explicit_and_no_lookalike(self):
        from vnext.text_coverage import build_text_document
        raw = arguments()['raw_bytes'].replace(b'dei/2025', b'dei/2020-01-31')
        args = binding(raw)
        with self.assertRaisesRegex(TextCoverageError, 'ENTITY_MISMATCH_OR_MISSING'):
            build_text_document(**args)
        self.assertEqual('BOUND_REPORT_CANDIDATE', inspect_visible_auditor_report(**args)['status'])
        for uri in [b'dei/2020q5', b'dei/2020-01-31-custom']:
            with self.assertRaises(ValueError):
                inspect_visible_auditor_report(**binding(raw.replace(b'dei/2020-01-31', uri)))

    def test_icfr_report_cannot_supply_financial_report_signature(self):
        icfr = REPORT.replace('We have audited the accompanying consolidated balance sheets of Example Company\n'
            'and its subsidiaries (the “Company”) as of December 31, 2025 and 2024, and the\n'
            'related consolidated statements of income for the years then ended.',
            'Opinion on Internal Control over Financial Reporting</p><p>'
            'We have audited Example Company internal control over financial reporting.')
        got = inspect_visible_auditor_report(**arguments(icfr + REPORT))
        self.assertEqual('BOUND_REPORT_CANDIDATE', got['status'])
        self.assertEqual(['INTERNAL_CONTROL_REPORT', 'FINANCIAL_STATEMENT_REPORT'],
                         [r['report_purpose'] for r in got['reports']])
        got = inspect_visible_auditor_report(**arguments(icfr + REPORT.replace(
            '<p>/s/ Example Audit LLP</p>', '')))
        self.assertEqual('UNRESOLVED', got['status'])
        self.assertEqual([], got['reports'][1]['signatures'])

    def test_amendment_and_corporate_abbreviation_keep_limits(self):
        args = arguments()
        raw = args['raw_bytes'].replace(b'Example Company</ix:nonNumeric>',
                                       b'Example Co</ix:nonNumeric>')
        self.assertEqual('BOUND_REPORT_CANDIDATE', inspect_visible_auditor_report(**binding(raw))['status'])
        raw = raw.replace(b'>10-K</ix:nonNumeric>', b'>10-K/A</ix:nonNumeric>')
        got = inspect_visible_auditor_report(**binding(raw))
        self.assertEqual('UNRESOLVED', got['status'])
        self.assertIn('TEXT_AMENDMENT_SOURCE_SET_REQUIRED', got['reasons'])

    def test_unproved_legal_name_alias_is_retained_as_unresolved(self):
        raw = arguments()['raw_bytes'].replace(b'Example Company</ix:nonNumeric>',
            b'EXAMPLE COMPANY /MD/</ix:nonNumeric>')
        got = inspect_visible_auditor_report(**binding(raw))
        self.assertEqual('UNRESOLVED', got['status'])
        self.assertEqual('/s/ Example Audit LLP', got['reports'][0]['signatures'][0]['text'])
        self.assertIn('VISIBLE_AUDITOR_AUDITEE_NOT_ESTABLISHED', got['reports'][0]['reasons'])

    def test_explicit_cover_name_binds_report_without_native_name_rewrite(self):
        args = arguments(CHARTER_COVER + REPORT)
        args = binding(args['raw_bytes'].replace(b'Example Company</ix:nonNumeric>',
                                                b'EXAMPLE COMPANY /MD/</ix:nonNumeric>'))
        self.assertEqual('UNRESOLVED', inspect_visible_auditor_report(**args)['status'])
        got = inspect_visible_auditor_report(**args, registrant_binding='COVER_CHARTER_NAME')
        self.assertEqual('BOUND_REPORT_CANDIDATE', got['status'])
        self.assertEqual('EXAMPLE COMPANY /MD/', got['registrant_name'])
        self.assertEqual('Example Company', got['report_registrant_name'])
        self.assertEqual('2', got['version'])
        pair = got['cover_charter_name']['candidates'][0]
        for key in ['name_locator', 'label_locator', 'form_locator', 'commission_locator']:
            b = pair[key]
            self.assertEqual(sha256_bytes(content=args['raw_bytes'][
                b['raw_start_byte']:b['raw_end_byte']]), b['raw_span_sha256'])
        self.assertEqual(got, verify_visible_auditor_report(inspection=got, **args,
                         registrant_binding='COVER_CHARTER_NAME'))
        self.assertFalse(got['metric_result_credit'])

    def test_cover_outside_cover_hidden_or_duplicated_never_binds(self):
        variants = [
            REPORT + CHARTER_COVER,
            CHARTER_COVER.replace('Exact name of registrant', 'Previous auditor') + REPORT,
            CHARTER_COVER.replace('<p>Example Company</p>',
                                  '<p style="display:none">Example Company</p>') + REPORT,
            CHARTER_COVER + '<p>Other Company</p><p>(Exact name of registrant as specified in its charter)</p>' + REPORT,
            CHARTER_COVER.replace('FORM 10-K', 'FORM 10-Q') + REPORT,
        ]
        for body in variants:
            with self.subTest(body=body[:75]):
                got = inspect_visible_auditor_report(**arguments(body),
                    registrant_binding='COVER_CHARTER_NAME')
                self.assertEqual('UNRESOLVED', got['status'])

    def test_cover_mismatch_and_unknown_option_rejected(self):
        got = inspect_visible_auditor_report(**arguments(CHARTER_COVER.replace(
            '<p>Example Company</p>', '<p>Another Company</p>') + REPORT),
            registrant_binding='COVER_CHARTER_NAME')
        self.assertEqual('UNRESOLVED', got['status'])
        self.assertIn('VISIBLE_AUDITOR_AUDITEE_NOT_ESTABLISHED', got['reports'][0]['reasons'])
        with self.assertRaisesRegex(ValueError, 'REGISTRANT_BINDING_INVALID'):
            inspect_visible_auditor_report(**arguments(), registrant_binding='strip-jurisdiction')

    def test_cover_option_cannot_hide_amendment_or_period_conflict(self):
        args = arguments(CHARTER_COVER + REPORT)
        raw = args['raw_bytes'].replace(b'>10-K</ix:nonNumeric>', b'>10-K/A</ix:nonNumeric>')
        raw = raw.replace(b'FORM 10-K<', b'FORM 10-K/A<')
        got = inspect_visible_auditor_report(**binding(raw), registrant_binding='COVER_CHARTER_NAME')
        self.assertEqual('BOUND_REPORT_CANDIDATE', got['reports'][0]['status'])
        self.assertEqual('UNRESOLVED', got['status'])
        self.assertIn('TEXT_AMENDMENT_SOURCE_SET_REQUIRED', got['reasons'])
        body = (CHARTER_COVER + REPORT).replace('as of December 31, 2025', 'as of December 31, 2024')
        got = inspect_visible_auditor_report(**arguments(body), registrant_binding='COVER_CHARTER_NAME')
        self.assertEqual('UNRESOLVED', got['status'])


if __name__ == '__main__':
    unittest.main()
