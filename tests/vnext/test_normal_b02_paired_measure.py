"""Normal B02 keeps revenue growth on one reported quantity."""
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.annual_update import saved_source
from vnext.paired_measure_v1 import (
    PAIRED_MEASURE_REASON, paired_measure_problem)
from vnext.zero_ai_r2 import _load_deterministic_catalog
from sec_urls import companyfacts_url


CIK = 78003
FILINGS = {'FY2021': '0000078003-22-000027',
           'FY2022': '0000078003-23-000024',
           'FY2023': '0000078003-24-000039',
           'FY2024': '0000078003-25-000054'}
CONTRACT = 'RevenueFromContractWithCustomerExcludingAssessedTax'
TOTAL = 'Revenues'


def _claims():
    raw = saved_source(repo_root=ROOT,
                       url=companyfacts_url(cik=CIK))['raw']
    facts = json.loads(raw)['facts']['us-gaap']
    result = []
    for concept in (CONTRACT, TOTAL, 'SalesRevenueNet',
                    'RevenueFromContractWithCustomerIncludingAssessedTax'):
        for fact in facts.get(concept, {}).get('units', {}).get('USD', []):
            if 'start' in fact:
                result.append({'locator': {'concept': concept,
                    'period_start': fact['start'], 'period_end': fact['end']},
                    'attributes': {'accession': fact['accn']},
                    'unit': 'USD', 'value': str(fact['val'])})
    return result


def _one(rows, accession, concept, end):
    matches = [row for row in rows
               if row['attributes']['accession'] == accession
               and row['locator']['concept'] == concept
               and row['locator']['period_end'] == end]
    if len(matches) != 1:
        raise AssertionError((accession, concept, end, len(matches)))
    return matches[0]


class NormalB02PairedMeasureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _claims()
        cls.route = _load_deterministic_catalog(
            repo_root=ROOT)['metrics']['B02']

    def check(self, current, prior, current_accession,
              current_rows=None):
        return paired_measure_problem(route=self.route,
            claims=[current, prior],
            current_claims=self.rows if current_rows is None else current_rows,
            accessions={'current': current_accession,
                        'prior': prior['attributes']['accession']})

    def test_pfizer_2023_and_2024_mixed_revenue_scopes_are_withheld(self):
        cases = ((FILINGS['FY2023'], CONTRACT, '2023-12-31',
                  FILINGS['FY2022'], TOTAL, '2022-12-31', '91793000000'),
                 (FILINGS['FY2024'], TOTAL, '2024-12-31',
                  FILINGS['FY2023'], CONTRACT, '2023-12-31', '59553000000'))
        for current_acc, current_concept, current_end, prior_acc, prior_concept, prior_end, reported in cases:
            with self.subTest(target=current_end):
                problem, bridged = self.check(
                    _one(self.rows,current_acc,current_concept,current_end),
                    _one(self.rows,prior_acc,prior_concept,prior_end),
                    current_acc)
                self.assertEqual(PAIRED_MEASURE_REASON,problem['reason_code'])
                self.assertEqual([reported],problem[
                    'target_filing_reports_the_prior_year_under_the_current_concept'])
                self.assertEqual([],bridged)

    def test_pfizer_2022_legitimate_label_change_is_bridged_by_its_own_filing(self):
        current = _one(self.rows,FILINGS['FY2022'],TOTAL,'2022-12-31')
        prior = _one(self.rows,FILINGS['FY2021'],CONTRACT,'2021-12-31')
        problem, bridged = self.check(current,prior,FILINGS['FY2022'])
        self.assertIsNone(problem)
        self.assertEqual('81288000000',bridged[0][
            'target_filing_reports_the_prior_year_under_the_current_concept'][0])
        # A matching value in the prior filing alone is not a bridge.
        problem, _ = self.check(current,prior,FILINGS['FY2022'],
            current_rows=[row for row in self.rows
                          if row['attributes']['accession'] != FILINGS['FY2022']])
        self.assertEqual(PAIRED_MEASURE_REASON,problem['reason_code'])

    def test_same_concept_needs_no_cross_label_bridge(self):
        current = _one(self.rows,FILINGS['FY2024'],TOTAL,'2024-12-31')
        prior = _one(self.rows,FILINGS['FY2023'],TOTAL,'2023-12-31')
        self.assertEqual((None,[]),self.check(current,prior,FILINGS['FY2024']))


if __name__ == '__main__':
    unittest.main()
