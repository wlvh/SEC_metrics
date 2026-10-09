"""A03 window consistency only; constructed records are not financial credit."""
from copy import deepcopy
from pathlib import Path
import unittest
from vnext.canonical import content_hash
from vnext.ordinary_projection import _reported_average_period
from vnext.specs import compile_spec_file

ROOT=Path(__file__).resolve().parents[2]


class ReportedAveragePeriodTest(unittest.TestCase):
    def setUp(self):
        filing={'fiscal_year':2021,'period_start':'2021-01-01','period_end':'2021-12-31'}
        actual={'fiscal_year':2021,'period_start':'2021-10-01','period_end':'2021-12-31'}
        self.annual={'company_id':'jpmorgan_chase','entity':'19617',
            'filing':{'accessionNumber':'0000019617-22-000272'},'table_input':{'target_period':filing}}
        fact={'status':'SINGLE_SOURCE_SEMANTIC_FACT','value':'1.11','source_sha256':'1'*64,
              'target_filing_period':filing,'measurement_period':actual,'unresolved':[]}
        ref={'source_reference_id':'constructed-source','company_id':'jpmorgan_chase',
             'raw_asset_id':'sha256:'+'1'*64,'accession':'0000019617-22-000272'}
        self.result={'metric_id':'A03','company_id':'jpmorgan_chase','value':'1.11','unit':'ratio',
                     'trace_id':'constructed-trace',**actual}
        binding={'source_fact_hash':content_hash(value=fact),'source_reference_id':ref['source_reference_id'],
            'raw_asset_id':ref['raw_asset_id'],'accession':ref['accession'],'entity':'19617',
            'measurement_time_basis':'SOURCE_DISCLOSED_AVERAGE','filing_period':filing,
            'actual_measurement_period':actual}
        observation={'record_type':'VERIFIED_OBSERVATION','observation_id':'constructed-observation',
            'metric_id':'A03','company_id':'jpmorgan_chase','semantic_role':'lcr_disclosed_average',
            'value':'1.11','unit':'ratio','source_binding':binding,**actual}
        trace={'record_type':'EXECUTION_TRACE','trace_id':'constructed-trace',
               'input_observation_ids':['constructed-observation']}
        self.records=[trace,observation]
        spec=compile_spec_file(path=ROOT/'catalog/r4_normal/A03_liquidity_coverage_ratio.md',dependency_specs={})
        self.case={'compiled_specs':{'A03':spec},'target_period':actual,'selection':{'source_fact':fact},'references':[ref]}

    def check(self):
        return _reported_average_period(case=self.case,result=self.result,annual=self.annual,records=self.records)

    def test_quarter_stays_quarter_with_annual_filing_group(self):
        before=deepcopy((self.case,self.result,self.annual,self.records))
        self.assertTrue(self.check())
        self.assertEqual(before,(self.case,self.result,self.annual,self.records))
        self.assertEqual(self.result['period_start'],'2021-10-01')

    def test_year_label_cannot_annualize_the_measurement(self):
        self.result['period_start']='2021-01-01'
        with self.assertRaisesRegex(ValueError,'AVERAGE_PERIOD_PROOF_CHANGED'):self.check()

    def test_reference_period_entity_value_and_uncertainty_do_not_disappear(self):
        for field,value in [('entity','1'),('entity',None),('accession','wrong'),
                            ('measurement_time_basis','ANNUAL_LABEL_ONLY')]:
            with self.subTest(field=field,value=value):
                before=deepcopy(self.records);self.records[1]['source_binding'][field]=value
                with self.assertRaisesRegex(ValueError,'AVERAGE_PERIOD_PROOF_CHANGED'):self.check()
                self.records=before
        self.case['selection']['source_fact']['unresolved']=['unresolved original relation']
        with self.assertRaisesRegex(ValueError,'AVERAGE_PERIOD_PROOF_CHANGED'):self.check()

    def test_another_metric_cannot_borrow_the_quarter_exception(self):
        self.result['metric_id']='B01'
        self.assertFalse(self.check())


if __name__=='__main__':unittest.main()
