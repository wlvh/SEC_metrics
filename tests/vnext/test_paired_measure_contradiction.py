"""Bounded prior-period comparison contradictions, no alternate fact selection."""
from copy import deepcopy
import unittest
from vnext.paired_measure_v1 import paired_measure_problem,PAIRED_MEASURE_REASON


class PairedReportedComparisonTest(unittest.TestCase):
    def setUp(self):
        self.route={'branches':[{'components':[{'accession_role':role,
            'approved_concepts':['Revenue','Contracts']} for role in ('current','prior')]}]}
        self.current=self.claim('Revenue','current','2021','80')
        self.prior=self.claim('Revenue','prior','2020','40')

    def claim(self,concept,accession,year,value,unit='USD'):
        return {'locator':{'concept':concept,'period_start':year+'-01-01',
            'period_end':year+'-12-31'},'attributes':{'accession':accession},'unit':unit,'value':value}

    def check(self,comparisons):
        return paired_measure_problem(route=self.route,claims=[self.current,self.prior],
            current_claims=[self.current,*comparisons],accessions={'current':'current','prior':'prior'})

    def test_same_label_prior_comparison_difference_is_not_accepted(self):
        before=deepcopy(self.prior)
        problem,bridged=self.check([self.claim('Revenue','current','2020','35')])
        self.assertIsNotNone(problem)
        self.assertEqual(problem['reason_code'],PAIRED_MEASURE_REASON)
        self.assertEqual(problem['prior']['value'],'40')
        self.assertEqual(problem['target_filing_reports_the_prior_year_under_the_current_concept'],['35'])
        self.assertEqual(bridged,[]);self.assertEqual(self.prior,before)

    def test_same_label_matching_or_no_comparison_keeps_existing_behavior(self):
        for comparisons in ([],[self.claim('Revenue','current','2020','40.00')]):
            with self.subTest(comparisons=comparisons):self.assertIsNone(self.check(comparisons)[0])

    def test_conflicting_comparisons_cannot_choose_the_matching_one(self):
        self.assertIsNotNone(self.check([self.claim('Revenue','current','2020','40'),
            self.claim('Revenue','current','2020','35')])[0])

    def test_other_period_unit_or_accession_is_not_a_prior_comparison(self):
        for comparison in (self.claim('Revenue','current','2019','35'),
                self.claim('Revenue','current','2020','35',unit='EUR'),
                self.claim('Revenue','unrelated','2020','35')):
            with self.subTest(comparison=comparison):self.assertIsNone(self.check([comparison])[0])

    def test_supported_label_change_requires_the_original_prior_value(self):
        self.prior['locator']['concept']='Contracts'
        self.assertIsNone(self.check([self.claim('Revenue','current','2020','40')])[0])
        self.assertIsNotNone(self.check([self.claim('Revenue','current','2020','35')])[0])


class DefaultRevenueScopeDefectTest(unittest.TestCase):
    def test_default_register_holds_exact_subtotal_result_only(self):
        from vnext.company_current_records import _registry,_defects
        registry=_registry()
        bad={'company_id':'pfizer','metric_id':'B01','period_end':'2023-12-31',
            'result_id':'sha256:a6e31052ee3e389e46442777fa69c0d06c6ec43e847dd65c412c0e05509aa8f7'}
        self.assertIn('ISSUE47_PFIZER_2023_REVENUE_COMPONENT_IS_NOT_TOTAL',_defects(bad,registry))
        for change in ({'period_end':'2025-12-31'},{'result_id':'different-result'},
                       {'company_id':'another-company'},{'metric_id':'B02'}):
            with self.subTest(change=change):self.assertNotIn(
                'ISSUE47_PFIZER_2023_REVENUE_COMPONENT_IS_NOT_TOTAL',_defects({**bad,**change},registry))


if __name__=='__main__':unittest.main()
