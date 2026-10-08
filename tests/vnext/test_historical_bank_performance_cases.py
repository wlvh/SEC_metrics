"""Source-role controls, with actual calculations covered by saved-source integration."""
import json
from unittest import TestCase
from vnext.normal_source_authority import ROOT
from vnext.historical_bank_performance_cases import METRICS
from vnext.paired_measure_v1 import paired_measure_problem, PAIRED_MEASURE_REASON

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


class BankPairedMeasureTest(TestCase):
    """Constructed claims exercise the shared guard, not a financial conclusion."""
    @classmethod
    def setUpClass(cls):
        cls.route=json.loads((ROOT/'catalog/deterministic_metrics.json').read_text())['metrics']['A07']

    def claim(self, concept, accession, *, value='40', unit='USD',
              start='2023-01-01', end='2023-12-31'):
        return {'locator': {'concept': concept, 'period_start': start, 'period_end': end},
                'attributes': {'accession': accession}, 'unit': unit, 'value': value}

    def check(self, bridge):
        current=self.claim('NetIncomeLoss','current',value='50',start='2024-01-01',end='2024-12-31')
        prior=self.claim('ProfitLoss','prior')
        return paired_measure_problem(route=self.route, claims=[current,prior],
            current_claims=[current,*bridge],accessions={'current':'current','prior':'prior'})

    def test_aliases_without_a_target_filing_bridge_are_withheld(self):
        problem,bridged=self.check([])
        self.assertEqual(PAIRED_MEASURE_REASON,problem['reason_code'])
        self.assertEqual('ProfitLoss',problem['prior']['concept'])
        self.assertEqual([],bridged)

    def test_bridge_requires_the_original_prior_value_under_the_current_concept(self):
        problem,bridged=self.check([self.claim('NetIncomeLoss','current')])
        self.assertIsNone(problem)
        self.assertEqual(1,len(bridged))
        problem,_=self.check([self.claim('NetIncomeLoss','current',value='41')])
        self.assertEqual(PAIRED_MEASURE_REASON,problem['reason_code'])

    def test_wrong_unit_window_or_filing_does_not_bridge_the_pair(self):
        for fields in [{'unit':'ratio'}, {'start':'2023-10-01'}, {'end':'2024-12-31'},
                       {'accession':'other'}]:
            with self.subTest(fields=fields):
                accession=fields.get('accession','current')
                bridge=self.claim('NetIncomeLoss',accession,**{k:v for k,v in fields.items() if k!='accession'})
                problem,_=self.check([bridge])
                self.assertEqual(PAIRED_MEASURE_REASON,problem['reason_code'])

    def test_conflicting_target_filing_comparatives_cannot_choose_one_value(self):
        problem,bridged=self.check([self.claim('NetIncomeLoss','current'),
                                   self.claim('NetIncomeLoss','current',value='41')])
        self.assertEqual(PAIRED_MEASURE_REASON,problem['reason_code'])
        self.assertEqual([],bridged)
