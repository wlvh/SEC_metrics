"""Small history scope controls; balance-date values use saved-source integration."""
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
from vnext import historical_liquidity_cases as cases

class HistoricalLiquidityScopeTest(TestCase):
    def test_other_family_does_not_select_sources(self):
        with patch.object(cases,'resolve_period_selection') as select:
            with self.assertRaisesRegex(ValueError,'FAMILY_NOT_RECEIVED'):
                cases.prepare_historical_liquidity_year_case(repo_root=Path('/constructed'),company_id='constructed',metric_id='B03',fiscal_year=2024)
            select.assert_not_called()

    def test_unknown_or_cross_entity_subject_is_rejected_before_calculation(self):
        policies=[{'mode':'SUCCESSOR_PREDECESSOR'},
                  {'mode':'SUCCESSOR_REGISTRANT_ONLY','selected_cik':'2','cross_entity_combination_authorized':False},
                  {'mode':'SUCCESSOR_REGISTRANT_ONLY','selected_cik':'1','cross_entity_combination_authorized':True}]
        for policy in policies:
            with self.subTest(policy=policy),patch.object(cases,'resolve_period_selection',return_value={}),patch.object(cases,'prepare_historical_annual_input',return_value={'entity':'1','subject_policy':policy}),patch.object(cases,'_deterministic_metric_graph') as calc:
                with self.assertRaisesRegex(ValueError,'SUBJECT_SCOPE_NOT_RECEIVED'):
                    cases.prepare_historical_liquidity_year_case(repo_root=Path('/constructed'),company_id='constructed',metric_id='B08',fiscal_year=2024)
                calc.assert_not_called()
