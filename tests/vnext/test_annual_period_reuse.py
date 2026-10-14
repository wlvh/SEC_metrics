"""Small real DEI parsing controls; no saved company install or result oracle."""
import unittest
from unittest.mock import patch
from vnext import normal_annual_input as annual, governance_signals


def document():
    values={'DocumentType':'10-K','DocumentPeriodEndDate':'2025-12-31',
            'DocumentFiscalYearFocus':'2025','DocumentFiscalPeriodFocus':'FY',
            'AmendmentFlag':'false','EntityCentralIndexKey':'123'}
    facts=''.join('<ix:nonNumeric name="dei:'+name+'" contextRef="current">'+value+'</ix:nonNumeric>'
                  for name,value in values.items())
    return ('<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" '
            'xmlns:xbrli="http://www.xbrl.org/2003/instance" '
            'xmlns:dei="http://xbrl.sec.gov/dei/2025"><body>'
            '<xbrli:context id="current"><xbrli:entity>'
            '<xbrli:identifier scheme="http://www.sec.gov/CIK">123</xbrli:identifier>'
            '</xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate>'
            '<xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
            +facts+'</body></html>').encode()


class AnnualPeriodReuseTest(unittest.TestCase):
    def setUp(self):
        self.raw=document();self.filing={'form':'10-K','reportDate':'2025-12-31',
            'accessionNumber':'selected','primaryDocument':'annual.htm','filingDate':'2026-02-01'}
    def period(self, **changes):
        return annual.annual_period(**{'raw':self.raw,'cik':123,'filing':self.filing,**changes})
    def test_same_operation_reads_one_period_without_mutable_result_alias(self):
        with patch.object(governance_signals,'_FactAttributes',wraps=governance_signals._FactAttributes) as scan:
            with annual.shared_annual_periods():
                first=self.period();first['fiscal_year']=1900
                second=self.period()
        self.assertEqual(2025,second['fiscal_year'])
        self.assertEqual(1,scan.call_count)
    def test_independent_operations_and_exception_exit_reparse(self):
        with patch.object(governance_signals,'_FactAttributes',wraps=governance_signals._FactAttributes) as scan:
            with annual.shared_annual_periods():self.period()
            with self.assertRaisesRegex(RuntimeError,'stop'):
                with annual.shared_annual_periods():self.period();raise RuntimeError('stop')
            with annual.shared_annual_periods():self.period()
        self.assertEqual(3,scan.call_count)
    def test_changed_entity_date_form_or_namespace_cannot_consume_old_period(self):
        changed=[{'cik':999},{'filing':{**self.filing,'reportDate':'2025-09-30'}},
                 {'filing':{**self.filing,'form':'10-K/A'}},
                 {'raw':self.raw.replace(b'http://xbrl.sec.gov/dei/2025',b'https://example.invalid/dei/2025')}]
        with annual.shared_annual_periods():
            self.period()
            for changes in changed:
                with self.subTest(changes=changes),self.assertRaises(annual.NormalAnnualInputError):self.period(**changes)
    def test_other_filing_or_parser_option_runs_its_own_check(self):
        with patch.object(governance_signals,'_FactAttributes',wraps=governance_signals._FactAttributes) as scan:
            with annual.shared_annual_periods():
                self.period();self.period(filing={**self.filing,'accessionNumber':'different'})
                self.period(dei_release='YEAR_QUARTER_OR_DATE')
        self.assertEqual(3,scan.call_count)
    def test_changed_actual_annual_bytes_yield_the_changed_period(self):
        with annual.shared_annual_periods():
            self.period()
            changed=self.raw.replace(b'2025',b'2024')
            value=self.period(raw=changed,filing={**self.filing,'reportDate':'2024-12-31'})
        self.assertEqual({'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'},value)
    def test_invalid_period_is_not_cached_as_success(self):
        bad=self.raw.replace(b'>FY<',b'>Q3<')
        with patch.object(governance_signals,'_FactAttributes',wraps=governance_signals._FactAttributes) as scan:
            with annual.shared_annual_periods():
                for _ in range(2):
                    with self.assertRaises(annual.NormalAnnualInputError):self.period(raw=bad)
                self.period()
        self.assertEqual(3,scan.call_count)
