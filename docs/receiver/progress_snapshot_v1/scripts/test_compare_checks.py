"""Boundary cases for build_snapshot.compare_checks (run: python3 -m unittest test_compare_checks)."""
import hashlib
import unittest

from build_snapshot import compare_checks


def rec(value, verdict='MATCH', filings=(), unit=None, period_start=None, entities=(), digest=None, defects=()):
    return {'basis': 'CONTENT_READ', 'verdict': verdict, 'value': value, 'filings': list(filings), 'source': 't',
            'unit': unit, 'period_start': period_start, 'entities': list(entities), 'digest': digest,
            'defects': list(defects)}


class CompareChecksTest(unittest.TestCase):
    def test_conflicting_readings_never_confirm(self):
        # two unexplained readings 99 and 100; the current 100 matches only one of them
        self.assertEqual('CONFLICTING_CHECKS', compare_checks('100', [rec('99'), rec('100')], set()))

    def test_value_and_filing_must_come_from_the_same_record(self):
        # A: filing A reads 99; B: filing B reads 100; current uses filing A with value 100
        records = [rec('99', filings=['0000000001-25-000001']), rec('100', filings=['0000000001-25-000002'])]
        self.assertEqual('CONFLICTING_CHECKS',
                         compare_checks('100', records, set(), cur_filings={'0000000001-25-000001'}))
        # without the conflicting record the value match from another filing is still not a confirmation
        self.assertEqual('SAME_VALUE_DIFFERENT_FILING',
                         compare_checks('100', [records[1]], set(), cur_filings={'0000000001-25-000001'}))
        self.assertEqual('SAME_VALUE',
                         compare_checks('100', [records[1]], set(), cur_filings={'0000000001-25-000002'}))

    def test_unit_period_and_entity_belong_to_the_same_record(self):
        r = rec('100', unit='USD', period_start='2025-01-01', entities=['813828'])
        self.assertEqual('SAME_VALUE_DIFFERENT_UNIT', compare_checks('100', [r], set(), cur_unit='ratio'))
        self.assertEqual('SAME_VALUE_DIFFERENT_PERIOD', compare_checks('100', [r], set(), cur_period_start='2025-08-08'))
        self.assertEqual('SAME_VALUE_DIFFERENT_ENTITY', compare_checks('100', [r], set(), cur_cik='2041610'))
        self.assertEqual('SAME_VALUE', compare_checks('100', [r], set(), cur_unit='usd', cur_period_start='2025-01-01',
                                                       cur_cik='0000813828'))

    def test_a_reading_that_found_the_old_result_wrong_confirms_the_corrected_value(self):
        # old result published 90; the original reading was 100 and the verdict said they differ
        self.assertEqual('SAME_VALUE_AS_CORRECTING_READING', compare_checks('100', [rec('100', verdict='DIFFERS')], set()))
        self.assertEqual('DIFFERENT_VALUE', compare_checks('90', [rec('100', verdict='DIFFERS')], set()))

    def test_a_reading_equal_to_a_registered_wrong_value_is_not_evidence(self):
        # the earlier reading took the same revenue subtotal that was later registered as wrong
        self.assertEqual('NO_USABLE_CHECK_READING_IS_REGISTERED_ERROR', compare_checks('100', [rec('90')], {'90'}))
        self.assertEqual('SAME_VALUE', compare_checks('100', [rec('90'), rec('100', verdict='DIFFERS')], {'90'})[:10])
        self.assertEqual('DIFFERENT_VALUE_CURRENT_IS_REGISTERED_ERROR', compare_checks('90', [rec('100')], {'90'}))

    def test_a_registered_defect_without_its_wrong_value_explains_but_does_not_prove(self):
        self.assertEqual('DIFFERENT_VALUE_CELL_HAS_REGISTERED_DEFECT',
                         compare_checks('17478', [rec('16108')], set(), cell_has_defect=True))
        self.assertEqual('DIFFERENT_VALUE', compare_checks('17478', [rec('16108')], set()))

    def test_records_without_a_reading_are_ignored(self):
        self.assertEqual('NO_USABLE_CHECK', compare_checks('100', [rec('', verdict='NOT_READ'),
                                                                   rec('100', verdict='DIRECT_CANDIDATES_DISAGREE')], set()))
        self.assertEqual('NO_USABLE_CHECK', compare_checks('100', [rec('100', verdict='ACCEPTED', defects=['D1'])], set()))
        self.assertEqual('', compare_checks('100', [], set()))

    def test_declared_percent_and_ratio_presentations_compare_equal(self):
        self.assertEqual('SAME_VALUE', compare_checks('51.3', [rec('0.513', unit='ratio')], set(), cur_unit='percent'))
        self.assertEqual('DIFFERENT_VALUE', compare_checks('51.3', [rec('0.531', unit='ratio')], set(), cur_unit='percent'))
        self.assertEqual('SAME_VALUE_DIFFERENT_UNIT', compare_checks('51.3', [rec('51.3', unit='USD')], set(), cur_unit='percent'))

    def test_same_reading_at_different_precision_is_not_a_conflict(self):
        self.assertEqual('SAME_VALUE', compare_checks('0.04631', [rec('0.0463'), rec('0.04631')], set()))

    def test_text_is_compared_by_digest_of_matching_records(self):
        text = 'Risk factors heading'
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        self.assertEqual('SAME_VALUE', compare_checks(text, [rec(None, digest=digest)], set()))
        self.assertEqual('CONFLICTING_CHECKS', compare_checks(text, [rec(None, digest=digest), rec(None, digest='0' * 64)], set()))


if __name__ == '__main__':
    unittest.main()
