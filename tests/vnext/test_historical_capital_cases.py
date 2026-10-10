"""Small labelled XBRL controls; no registered company or acquisition credit."""
import copy,hashlib,json
from unittest import TestCase
from vnext.canonical import content_hash
from vnext.deterministic_router import source_set_manifest
from vnext.sources import source_reference_record
from vnext.normal_accession_results import NormalAccessionError
from vnext.normal_source_authority import ROOT
from vnext.historical_capital_cases import inspect_historical_capital_source

class HistoricalCapitalSourceTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads((ROOT/'config/normal_accession_metrics_v1.json').read_text())
        cls.route=json.loads((ROOT/'catalog/deterministic_metrics.json').read_text())['metrics']['A01']
    def inspect(self, *, cik='1', date='2021-12-31', member='ParentCompanyMember', method='BaselIIIStandardizedMember', unit='xbrli:pure', gaap='http://fasb.org/us-gaap/2021-01-31', srt='http://fasb.org/srt/2021-01-31', value='0.15', metric_id='A01', concept='TierOneRiskBasedCapitalToRiskWeightedAssets', dimensions=True):
        raw=f'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:us-gaap="{gaap}" xmlns:srt="{srt}" xmlns:jpm="http://example.invalid/bank/2021" xmlns:iso="http://www.xbrl.org/2003/iso4217"><body><xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{cik}</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="srt:ConsolidatedEntitiesAxis">srt:{member}</xbrldi:explicitMember><xbrldi:explicitMember dimension="us-gaap:RiskWeightedAssetsCalculationMethodologyAxis">jpm:{method}</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>{date}</xbrli:instant></xbrli:period></xbrli:context><xbrli:unit id="u"><xbrli:measure>{unit}</xbrli:measure></xbrli:unit><ix:nonFraction name="us-gaap:TierOneRiskBasedCapitalToRiskWeightedAssets" contextRef="c" unitRef="u" decimals="INF">{value}</ix:nonFraction></body></html>'''.encode()
        raw = raw.replace(b'TierOneRiskBasedCapitalToRiskWeightedAssets', concept.encode())
        if not dimensions:
            import re
            raw = re.sub(rb'<xbrli:segment>.*?</xbrli:segment>', b'', raw)
        inventory=json.dumps({'filings':{'recent':{'accessionNumber':['0000000001-22-000001'],'filingDate':['2022-02-01'],'form':['10-K']}}}).encode()
        def ref(data,doc,accession,role):
            blob={'record_type':'RAW_BLOB','raw_asset_id':'sha256:'+hashlib.sha256(data).hexdigest(),'byte_length':len(data),'media_type':'text/html','storage_uri':doc}
            return source_reference_record(raw_blob=blob,company_id='constructed',source_url='https://www.sec.gov/Archives/edgar/data/1/000000000122000001/'+doc,accession=accession,document_name=doc,source_role=role,request_attempt_id='CONSTRUCTED_NO_ACQUISITION')
        source=ref(raw,'test.htm','0000000001-22-000001','target_primary');inv=ref(inventory,'index.json','SUBMISSIONS-1','sec_submissions_inventory')
        manifest=source_set_manifest(company_id='constructed',source_role='target_accession_instance',form_types=['10-K'],fiscal_or_date_window={'period_start':'2022-02-01','period_end':'2022-02-01'},discovery_policy='CONSTRUCTED_TEST_ONLY',inventory_source_reference=inv,inventory_bytes=inventory,ordered_source_references=[source],cutoff_timestamp_or_pinned_submissions_attempt='CONSTRUCTED_NO_ACQUISITION')
        return inspect_historical_capital_source(raw_bytes=raw,source_reference=source,source_set_manifest=manifest,expected_cik='1',period_end='2021-12-31',route=self.route,metric_id=metric_id,policy=self.policy)
    def test_dated_parent_standardized_ratio_keeps_pure_unit(self):
        result,policy=self.inspect();self.assertEqual('SOURCE_SCOPE_PROVEN',result['status']);self.assertEqual([('0.15','ratio')],[(r['value'],r['unit']) for r in result['selected_claims']]);self.assertNotEqual(policy,self.policy)
    def test_subsidiary_advanced_other_entity_or_period_cannot_be_parent_ratio(self):
        for changes in [{'member':'SubsidiaryMember'},{'method':'BaselIIIAdvancedMember'},{'cik':'2'},{'date':'2020-12-31'}]:
            with self.subTest(changes=changes):
                r,_=self.inspect(**changes);self.assertEqual('UNRESOLVED',r['status']);self.assertEqual([],r['selected_claims'])
    def test_usd_and_unformatted_comma_are_not_pure_ratios(self):
        for changes in [{'unit':'iso:USD'},{'value':'0,15'}]:
            with self.subTest(changes=changes):
                r,_=self.inspect(**changes);self.assertEqual('UNRESOLVED',r['status']);self.assertTrue(r['conflicts'])
    def test_unknown_taxonomy_does_not_enter_the_dated_release_path(self):
        with self.assertRaises(NormalAccessionError):self.inspect(srt='http://example.invalid/srt/2021-01-31')
    def test_year_only_inspection_preserves_the_original_policy_object(self):
        r,policy=self.inspect(gaap='http://fasb.org/us-gaap/2025',srt='http://fasb.org/srt/2025');self.assertEqual('SOURCE_SCOPE_PROVEN',r['status']);self.assertIs(policy,self.policy)

    def test_rpo_total_is_an_instant_usd_fact_not_a_segment_or_arr(self):
        self.route = json.loads((ROOT/'catalog/deterministic_metrics.json').read_text())['metrics']['B12']
        options = {'metric_id': 'B12', 'concept': 'RevenueRemainingPerformanceObligation',
                   'dimensions': False, 'unit': 'iso:USD', 'value': '43700000000'}
        report, _ = self.inspect(**options)
        self.assertEqual('SOURCE_SCOPE_PROVEN', report['status'])
        self.assertEqual('USD', report['selected_claims'][0]['unit'])
        self.assertEqual('43700000000', report['selected_claims'][0]['value'])
        for change in ({'unit': 'xbrli:pure'}, {'date': '2021-12-30'},
                       {'dimensions': True}, {'concept': 'RevenueFromContractWithCustomerExcludingAssessedTax'}):
            with self.subTest(change=change):
                wrong, _ = self.inspect(**{**options, **change})
                self.assertEqual('UNRESOLVED', wrong['status'])
