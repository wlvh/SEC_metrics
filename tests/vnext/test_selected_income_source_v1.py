"""Small original-source checks, never a fabricated financial result."""
import copy,unittest
from unittest.mock import patch
from vnext.canonical import sha256_bytes
from vnext.selected_income_source_v1 import native_income_reports,visible_income_periods
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE


def fixture(*, gaap='http://fasb.org/us-gaap/2025', unit='USD', entity='123', short=False):
    context=lambda key,start: f'''<xbrli:context id="{key}"><xbrli:entity>
      <xbrli:identifier scheme="http://www.sec.gov/CIK">{entity}</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>'''
    raw=f'''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:dei="http://xbrl.sec.gov/dei/2025" xmlns:us-gaap="{gaap}"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
      {context('annual','2025-01-01')}{context('short','2025-08-08')}
      <xbrli:unit id="usd"><xbrli:measure>iso4217:{unit}</xbrli:measure></xbrli:unit>
      <dei:DocumentType contextRef="annual">10-K</dei:DocumentType>
      <dei:DocumentPeriodEndDate contextRef="annual">2025-12-31</dei:DocumentPeriodEndDate>
      <dei:DocumentFiscalYearFocus contextRef="annual">2025</dei:DocumentFiscalYearFocus>
      <dei:DocumentFiscalPeriodFocus contextRef="annual">FY</dei:DocumentFiscalPeriodFocus>
      <dei:AmendmentFlag contextRef="annual">false</dei:AmendmentFlag>
      <dei:EntityCentralIndexKey contextRef="annual">{entity}</dei:EntityCentralIndexKey>
      <us-gaap:Revenues contextRef="annual" unitRef="usd" decimals="0">12000000</us-gaap:Revenues>
      <us-gaap:Depreciation contextRef="annual" unitRef="usd" decimals="0">400000</us-gaap:Depreciation>
      {'<table><tr><td></td><td>Period From August 7 - December 31,</td></tr><tr><td></td><td>2025</td></tr><tr><td>Revenues</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="short" unitRef="usd" decimals="0">5000000</ix:nonFraction></td></tr></table>' if short else ''}
      </xbrli:xbrl>'''.encode()
    annual={'company_id':'test_company','entity':'123','filing':{'accessionNumber':'0000000123-26-000001','form':'10-K','reportDate':'2025-12-31'},
            'table_input':{'target_period':{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}}}
    source={'raw_bytes':raw,'source_reference':{'company_id':'test_company','accession':annual['filing']['accessionNumber'],'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}
    return source,annual


class SelectedIncomeSourceTest(unittest.TestCase):
    def test_selected_original_default_matches_retained_reader_without_current_preparation(self):
        from vnext.ordinary_income_input import native_income_reports as retained
        source,annual=fixture();concepts=['us-gaap:Revenues','us-gaap:Depreciation']
        expected=retained(source,annual,concepts)
        with patch('vnext.normal_candidates._prepare_b06',side_effect=AssertionError('No current filing selection')):
            actual=native_income_reports(source,annual,concepts)
        self.assertEqual(actual,expected)
        self.assertEqual([r['value'] for r in actual],['12000000','400000'])
        self.assertEqual(actual[0]['source_reference'],source['source_reference'])

    def test_source_byte_company_and_accession_binding_rejected(self):
        source,annual=fixture()
        for key,value in [('raw_asset_id','sha256:wrong'),('company_id','wrong_company'),('accession','wrong_accession')]:
            changed=copy.deepcopy(source);changed['source_reference'][key]=value
            with self.subTest(field=key),self.assertRaisesRegex(ValueError,'ORIGINAL_BINDING_CHANGED'):
                native_income_reports(changed,annual,['us-gaap:Revenues'])

    def test_wrong_annual_period_and_dei_subject_rejected(self):
        source,annual=fixture();changed=copy.deepcopy(annual);changed['table_input']['target_period']['period_start']='2025-02-01'
        with self.assertRaisesRegex(ValueError,'ORIGINAL_ANNUAL_IDENTITY_CHANGED'):
            native_income_reports(source,changed,['us-gaap:Revenues'])
        source,annual=fixture(entity='456')
        with self.assertRaisesRegex(ValueError,'DEI_SUBJECT_CONFLICT'):
            native_income_reports(source,annual,['us-gaap:Revenues'])

    def test_non_usd_and_fake_namespace_rejected(self):
        for args,reason in [({'unit':'EUR'},'NATIVE_USD_REQUIRED'),({'gaap':'https://example.org/us-gaap/2025'},'OFFICIAL_CONCEPT_REQUIRED')]:
            source,annual=fixture(**args)
            with self.subTest(args=args),self.assertRaisesRegex(ValueError,reason):
                native_income_reports(source,annual,['us-gaap:Revenues'])

    def test_release_date_requires_explicit_policy_and_old_default_unchanged(self):
        source,annual=fixture(gaap='http://fasb.org/us-gaap/2021-01-31')
        with self.assertRaisesRegex(ValueError,'OFFICIAL_CONCEPT_REQUIRED'):
            native_income_reports(source,annual,['us-gaap:Revenues'])
        rows=native_income_reports(source,annual,['us-gaap:Revenues'],namespace_policy=YEAR_OR_DATE_RELEASE)
        self.assertEqual(rows[0]['value'],'12000000')
        with self.assertRaisesRegex(ValueError,'XBRL_NAMESPACE_POLICY_UNSUPPORTED'):
            native_income_reports(source,annual,['us-gaap:Revenues'],namespace_policy='ANY_URI')

    def test_explicit_period_reader_inspects_exact_bytes_and_must_match_target(self):
        source,annual=fixture();seen=[]
        from vnext.normal_annual_input import annual_period
        def reader(**kwargs):seen.append(kwargs);return annual_period(**kwargs)
        self.assertEqual(native_income_reports(source,annual,['us-gaap:Revenues'],annual_period_reader=reader)[0]['value'],'12000000')
        self.assertIs(seen[0]['raw'],source['raw_bytes']);self.assertEqual(seen[0]['cik'],'123')
        def changed(**kwargs):return {**annual_period(**kwargs),'fiscal_year':2024}
        with self.assertRaisesRegex(ValueError,'ORIGINAL_ANNUAL_IDENTITY_CHANGED'):
            native_income_reports(source,annual,['us-gaap:Revenues'],annual_period_reader=changed)

    def test_short_visible_period_conflict_and_missing_header_remain_explicit(self):
        source,annual=fixture(short=True)
        rows=native_income_reports(source,annual,['us-gaap:Revenues'],check_visible_short_period=True)
        check=rows[-1]['visible_period_check']
        self.assertEqual(check['status'],'CONFLICT')
        self.assertEqual(check['visible_periods'],[['2025-08-07','2025-12-31']])
        self.assertTrue(check['headers'])
        changed=copy.deepcopy(source);changed['raw_bytes']=source['raw_bytes'].replace(b'Period From August 7 - December 31,',b'Unknown interval')
        changed['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=changed['raw_bytes'])
        row=native_income_reports(changed,annual,['us-gaap:Revenues'],check_visible_short_period=True)[-1]
        self.assertEqual(row['visible_period_check']['status'],'UNRESOLVED')
