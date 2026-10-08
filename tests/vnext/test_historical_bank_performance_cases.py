"""Source-role controls, with actual calculations covered by saved-source integration."""
import json
from unittest import TestCase
from vnext.normal_source_authority import ROOT
from vnext.historical_bank_performance_cases import METRICS

class BankSourceRoleTest(TestCase):
    def test_only_the_average_and_trend_metrics_need_a_prior(self):
        catalog=json.loads((ROOT/'catalog/deterministic_metrics.json').read_text())['metrics']
        prior={m:any(c['accession_role']=='prior' for b in catalog[m]['branches'] for c in b['components']) for m in METRICS}
        self.assertEqual({'A05':True,'A06':True,'A07':True,'A08':False,'A10':False},prior)
    def test_average_balance_does_not_become_quarter_or_annual_flow_average(self):
        routes=json.loads((ROOT/'catalog/deterministic_metrics.json').read_text())['metrics']
        for m in ['A05','A06']:
            branch=routes[m]['branches'][0]
            self.assertEqual('average_denominator_ratio',branch['formula_id'])
            self.assertEqual(['current_annual','current_instant','prior_instant'],[c['period_role'] for c in branch['components']])
        self.assertEqual('current_instant',routes['A10']['result_period_role'])
