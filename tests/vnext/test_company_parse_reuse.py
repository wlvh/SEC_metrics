"""Scoped immutable parse reuse; quantity/identity checks remain downstream."""
import unittest
from unittest.mock import patch

from tests.vnext.test_text_coverage import annual, BODY
from vnext import deterministic_router as router


class CompanyParseReuseTest(unittest.TestCase):
    def test_one_operation_parses_same_bytes_once_with_same_immutable_content(self):
        raw=annual(BODY)
        expected=router.parse_accession_xbrl_source(raw_bytes=raw)
        with patch.object(router,'_parse_xbrl_parts',wraps=router._parse_xbrl_parts) as parser:
            with router.shared_xbrl_parses():
                first=router.parse_accession_xbrl_source(raw_bytes=raw)
                second=router.parse_accession_xbrl_source(raw_bytes=raw)
            self.assertEqual(parser.call_count,1)
            self.assertIs(first,second)
            self.assertEqual(first.parsed_source_id,expected.parsed_source_id)
            with self.assertRaises(TypeError):first.contexts['annual']['period_end']='2024-12-31'
            router.parse_accession_xbrl_source(raw_bytes=raw)
            self.assertEqual(parser.call_count,2)

    def test_byte_changes_are_not_cache_hits_or_identity_equivalence(self):
        raw=annual(BODY)
        with router.shared_xbrl_parses():
            first=router.parse_accession_xbrl_source(raw_bytes=raw)
            for changed in (raw.replace(b'2025-12-31',b'2024-12-31'),
                            raw.replace(b'12345',b'67890'),raw+b' '):
                second=router.parse_accession_xbrl_source(raw_bytes=changed)
                self.assertNotEqual(first.parsed_source_id,second.parsed_source_id)

    def test_nested_operations_and_failures_restore_previous_scope(self):
        raw=annual(BODY)
        with patch.object(router,'_parse_xbrl_parts',wraps=router._parse_xbrl_parts) as parser:
            with router.shared_xbrl_parses():
                outer=router.parse_accession_xbrl_source(raw_bytes=raw)
                with self.assertRaises(ValueError):
                    with router.shared_xbrl_parses():
                        inner=router.parse_accession_xbrl_source(raw_bytes=raw)
                        self.assertIsNot(inner,outer)
                        raise ValueError('interrupted company')
                self.assertIs(outer,router.parse_accession_xbrl_source(raw_bytes=raw))
            self.assertEqual(parser.call_count,2)
            router.parse_accession_xbrl_source(raw_bytes=raw)
            self.assertEqual(parser.call_count,3)

    def test_cache_is_bounded_without_omitting_later_sources(self):
        with router.shared_xbrl_parses():
            for number in range(18):
                raw=annual(BODY+str(number))
                parsed=router.parse_accession_xbrl_source(raw_bytes=raw)
                self.assertEqual(parsed.source_size,len(raw))
            self.assertEqual(len(router._BATCH_XBRL_PARSES.get()),16)

    def test_reused_parse_does_not_bypass_consumer_company_or_period_checks(self):
        from vnext.normal_annual_input import annual_period, NormalAnnualInputError
        extra=''.join('<ix:nonNumeric name="dei:'+name+'" contextRef="annual">'+value+'</ix:nonNumeric>'
            for name,value in [('DocumentFiscalYearFocus','2025'),('DocumentFiscalPeriodFocus','FY'),('AmendmentFlag','false')])
        raw=annual(BODY).replace(b'</ix:hidden>',extra.encode()+b'</ix:hidden>')
        filing={'form':'10-K','reportDate':'2025-12-31'}
        with router.shared_xbrl_parses():
            self.assertEqual(annual_period(raw=raw,cik='12345',filing=filing)['fiscal_year'],2025)
            with self.assertRaises(NormalAnnualInputError):
                annual_period(raw=raw,cik='67890',filing=filing)
            with self.assertRaises(NormalAnnualInputError):
                annual_period(raw=raw,cik='12345',filing={**filing,'reportDate':'2024-12-31'})


if __name__=='__main__':unittest.main()
