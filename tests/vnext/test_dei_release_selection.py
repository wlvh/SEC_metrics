"""Explicit release parsing retains source/subject/annual-period boundaries."""
import unittest

from vnext.normal_annual_input import annual_period, NormalAnnualInputError


FILING = {"form": "10-K", "reportDate": "2021-12-31"}
PERIOD = {"fiscal_year": 2021, "period_start": "2021-01-01", "period_end": "2021-12-31"}
SUCCESSOR = "YEAR_QUARTER_OR_DATE"


def annual(namespace="http://xbrl.sec.gov/dei/2021q4", **changes):
    facts = {"DocumentType": "10-K", "DocumentPeriodEndDate": "2021-12-31",
             "DocumentFiscalYearFocus": "2021", "DocumentFiscalPeriodFocus": "FY",
             "AmendmentFlag": "false", "EntityCentralIndexKey": "19617"}
    facts.update(changes)
    raw = (f'<html xmlns:dei="{namespace}"><xbrli:context id="annual">'
           '<xbrli:entity><xbrli:identifier>19617</xbrli:identifier></xbrli:entity>'
           '<xbrli:period><xbrli:startDate>2021-01-01</xbrli:startDate>'
           '<xbrli:endDate>2021-12-31</xbrli:endDate></xbrli:period></xbrli:context>')
    raw += ''.join(f'<ix:nonNumeric name="dei:{name}" contextRef="annual">{value}</ix:nonNumeric>'
                   for name, value in facts.items())
    return (raw + '</html>').encode()


class DeiReleaseSelectionTest(unittest.TestCase):
    def evaluate(self, raw, **kwargs):
        return annual_period(raw=raw, cik="19617", filing=FILING, **kwargs)

    def test_original_default_and_explicit_year_have_identical_return(self):
        raw = annual("https://xbrl.sec.gov/dei/2021")
        self.assertEqual(PERIOD, self.evaluate(raw))
        self.assertEqual(self.evaluate(raw), self.evaluate(raw, dei_release=SUCCESSOR))

    def test_old_release_requires_explicit_successor(self):
        for suffix in ("2021q4", "2020-01-31", "2021q1"):
            for protocol in ("http", "https"):
                with self.subTest(suffix=suffix, protocol=protocol):
                    raw = annual(f"{protocol}://xbrl.sec.gov/dei/{suffix}")
                    with self.assertRaisesRegex(NormalAnnualInputError, "DEI_MISSING_OR_AMBIGUOUS"):
                        self.evaluate(raw)
                    self.assertEqual(PERIOD, self.evaluate(raw, dei_release=SUCCESSOR))

    def test_foreign_extension_invalid_quarter_and_extra_suffix_rejected(self):
        for uri in ("https://example.test/dei/2021q4", "https://xbrl.sec.gov/dei/2021q0",
                    "https://xbrl.sec.gov/dei/2021q5", "https://xbrl.sec.gov/dei/2021q4/",
                    "https://xbrl.sec.gov/dei/2021-custom"):
            with self.subTest(uri=uri), self.assertRaisesRegex(NormalAnnualInputError, "DEI_MISSING_OR_AMBIGUOUS"):
                self.evaluate(annual(uri), dei_release=SUCCESSOR)

    def test_no_arbitrary_regex_or_boolean_selection(self):
        for value in (None, True, {}, ".*", "YEAR_OR_DATE_RELEASE"):
            with self.subTest(value=value), self.assertRaisesRegex(NormalAnnualInputError, "DEI_RELEASE_SELECTION_INVALID"):
                self.evaluate(annual(), dei_release=value)

    def test_successor_does_not_relax_entity_or_annual_identity(self):
        for field, value in (("DocumentType", "10-Q"), ("DocumentFiscalPeriodFocus", "Q4"),
                             ("AmendmentFlag", "true"), ("EntityCentralIndexKey", "1"),
                             ("DocumentFiscalYearFocus", "2022")):
            with self.subTest(field=field), self.assertRaisesRegex(NormalAnnualInputError,
                    "ANNUAL_IDENTITY_CONFLICT|DEI_FISCAL_YEAR_CONFLICT"):
                self.evaluate(annual(**{field: value}), dei_release=SUCCESSOR)
        with self.assertRaisesRegex(NormalAnnualInputError, "DEI_SUBJECT_CONFLICT"):
            annual_period(raw=annual(), cik="1", filing=FILING, dei_release=SUCCESSOR)

    def test_conflicting_facts_and_short_context_remain_rejected(self):
        raw = annual().replace(b'</html>', b'<ix:nonNumeric name="dei:DocumentType" contextRef="annual">10-Q</ix:nonNumeric></html>')
        with self.assertRaisesRegex(NormalAnnualInputError, "DEI_MISSING_OR_AMBIGUOUS:DocumentType"):
            self.evaluate(raw, dei_release=SUCCESSOR)
        raw = annual().replace(b'2021-01-01', b'2021-10-01')
        with self.assertRaisesRegex(NormalAnnualInputError, "ANNUAL_DURATION_NOT_IMPLEMENTED"):
            self.evaluate(raw, dei_release=SUCCESSOR)


if __name__ == '__main__':
    unittest.main()
