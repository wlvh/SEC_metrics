import copy
import hashlib
import re
import unittest

from sec_urls import accession_document_url
from vnext.ordinary_depreciation_sources import inspect_depreciation_sources


class DepreciationSourcesTest(unittest.TestCase):
    def packet(self):
        raw = b'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
        xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
        xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:dei="http://xbrl.sec.gov/dei/2021q4"
        xmlns:us-gaap="http://fasb.org/us-gaap/2021-01-31" xmlns:own="http://example.com/2021">
        <xbrli:context id="base"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">123</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:startDate>2021-01-01</xbrli:startDate><xbrli:endDate>2021-12-31</xbrli:endDate></xbrli:period></xbrli:context>
        <xbrli:context id="part"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">123</xbrli:identifier>
        <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:IncomeStatementLocationAxis">own:ReimbursedExpensesMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
        <xbrli:period><xbrli:startDate>2021-01-01</xbrli:startDate><xbrli:endDate>2021-12-31</xbrli:endDate></xbrli:period></xbrli:context>
        <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
        <ix:nonNumeric name="dei:DocumentType" contextRef="base">10-K</ix:nonNumeric>
        <ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="base">December 31, 2021</ix:nonNumeric>
        <ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="base">2021</ix:nonNumeric>
        <ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="base">FY</ix:nonNumeric>
        <ix:nonNumeric name="dei:AmendmentFlag" contextRef="base">false</ix:nonNumeric>
        <ix:nonNumeric name="dei:EntityCentralIndexKey" contextRef="base">123</ix:nonNumeric>
        <p>Our depreciation was <ix:nonFraction name="us-gaap:Depreciation" contextRef="base" unitRef="usd" decimals="0">138</ix:nonFraction>
        (of which <ix:nonFraction name="us-gaap:Depreciation" contextRef="part" unitRef="usd" decimals="0">49</ix:nonFraction> was reimbursed).</p></html>'''
        def source(doc):
            return {'raw_bytes': raw, 'source_reference': {'raw_asset_id': 'sha256:' + hashlib.sha256(raw).hexdigest(),
                'company_id': 'sample', 'accession': '0000000123-22-000001',
                'document_name': doc, 'source_url': accession_document_url(cik=123,
                    accession='0000000123-22-000001', document_name=doc), 'source_reference_id': doc}}
        return {'primary': source('sample.htm'), 'xml': source('sample.xml'), 'company_id': 'sample',
            'entity': '123', 'filing': {'form': '10-K', 'reportDate': '2021-12-31',
                'accessionNumber': '0000000123-22-000001', 'primaryDocument': 'sample.htm'},
            'period': {'fiscal_year': 2021, 'period_start': '2021-01-01', 'period_end': '2021-12-31'},
            'namespace_policy': {'concept_namespaces': ['http://fasb.org/us-gaap/2021-01-31'],
                'dei_namespaces': ['http://xbrl.sec.gov/dei/2021q4']}}

    def replace_raw(self, packet, kind, before, after):
        s = packet[kind]; s['raw_bytes'] = s['raw_bytes'].replace(before, after)
        s['source_reference']['raw_asset_id'] = 'sha256:' + hashlib.sha256(s['raw_bytes']).hexdigest()

    def test_dimensioned_reports_preserved_without_full_role_or_additive_credit(self):
        p = self.packet(); before = copy.deepcopy(p); result = inspect_depreciation_sources(**p)
        self.assertEqual(p, before)
        self.assertEqual({'138', '49'}, {c['value'] for c in result['candidates']})
        self.assertEqual(1, len(result['scope_relations']))
        self.assertFalse(result['scope_relations'][0]['additive_relationship_established'])
        self.assertFalse(result['definition_complete']); self.assertFalse(result['metric_result_created'])
        self.assertTrue(all(c['visible_blocks'] for c in result['candidates']))

    def test_xml_conflict_is_named_and_not_selected(self):
        p = self.packet(); self.replace_raw(p, 'xml', b'>49</ix:', b'>50</ix:')
        r = inspect_depreciation_sources(**p)
        self.assertEqual(['138'], [c['value'] for c in r['candidates']])
        self.assertEqual('PRIMARY_XML_AMOUNT_CONFLICT', r['issues'][0]['reason'])

    def test_xml_element_names_and_inline_names_share_canonical_concept(self):
        p = self.packet()
        text = p['xml']['raw_bytes'].decode()
        text = re.sub(r'<ix:(nonNumeric|nonFraction) name="([^"]+)"([^>]*)>(.*?)</ix:\1>',
                      lambda m: '<' + m[2] + m[3] + '>' + m[4] + '</' + m[2] + '>', text)
        p['xml']['raw_bytes'] = text.encode()
        p['xml']['source_reference']['raw_asset_id'] = 'sha256:' + hashlib.sha256(text.encode()).hexdigest()
        result = inspect_depreciation_sources(**p)
        self.assertEqual({'138', '49'}, {c['value'] for c in result['candidates']})
        self.assertEqual([], result['issues'])

    def test_missing_xml_candidate_is_not_replaced_by_primary(self):
        p = self.packet(); self.replace_raw(p, 'xml', b'name="us-gaap:Depreciation" contextRef="part"',
                                           b'name="own:Unrelated" contextRef="part"')
        r = inspect_depreciation_sources(**p)
        self.assertEqual(['138'], [c['value'] for c in r['candidates']])
        self.assertEqual('PRIMARY_XML_CANDIDATE_MISSING', r['issues'][0]['reason'])

    def test_changed_body_url_and_accession_are_rejected(self):
        for field in ('body', 'source_url', 'accession', 'company_id'):
            p = self.packet()
            if field == 'body': p['primary']['raw_bytes'] += b'changed'
            else: p['primary']['source_reference'][field] = 'wrong'
            with self.subTest(field=field), self.assertRaises(ValueError):
                inspect_depreciation_sources(**p)

    def test_period_and_entity_changes_are_rejected(self):
        for field, value in [('entity', '456'), ('period', {'fiscal_year': 2021,
                'period_start': '2021-02-01', 'period_end': '2021-12-31'})]:
            p = self.packet(); p[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                inspect_depreciation_sources(**p)

    def test_namespace_policy_explicit_and_official(self):
        for change in ({}, {'concept_namespaces': ['http://example.com/us-gaap/2021'],
                           'dei_namespaces': ['http://xbrl.sec.gov/dei/2021q4']}):
            p = self.packet(); p['namespace_policy'] = change
            with self.assertRaisesRegex(ValueError, 'NAMESPACE_POLICY_REQUIRED'):
                inspect_depreciation_sources(**p)

    def test_non_usd_and_wrong_concept_namespace_do_not_supply_candidates(self):
        for old, new, reason in [(b'iso4217:USD', b'iso4217:EUR', 'TYPED_SCOPE_OR_NON_USD'),
                (b'name="us-gaap:Depreciation"', b'name="own:Depreciation"', 'CONCEPT_NAMESPACE_NOT_SELECTED')]:
            p = self.packet()
            for kind in ('primary', 'xml'): self.replace_raw(p, kind, old, new)
            r = inspect_depreciation_sources(**p)
            self.assertEqual([], r['candidates']); self.assertTrue(any(x['reason'] == reason for x in r['issues']))


if __name__ == '__main__':
    unittest.main()
