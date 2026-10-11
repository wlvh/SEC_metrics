"""Small selected-source contracts; amounts are labelled constructed controls."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from vnext.selected_income_calculation import calculate_selected_income
from vnext.normal_run_specs import installed_ordinary_spec_documents


class SelectedIncomeCalculationContractTest(TestCase):
    def invoke(self, **options):
        spec = installed_ordinary_spec_documents()['B03']['compiled_spec']
        return calculate_selected_income(repo_root=Path('/constructed'),
            prepared={}, inventory={}, primary_source={}, facts_source={},
            metric_id='B03', spec=spec, dependency_specs={}, target={}, period={},
            traits={}, **options)

    def test_invalid_policy_refuses_before_reading_any_amount(self):
        with patch('vnext.selected_income_calculation.companyfacts_structured_facts') as parse:
            with self.assertRaisesRegex(ValueError,'SINGLE_REVENUE_OPTION_INVALID'):
                self.invoke(allow_single_revenue_line=True)
            with self.assertRaisesRegex(ValueError,'REVENUE_SCOPE_CONTRACT_INVALID'):
                self.invoke(revenue_scope_contract='unreviewed')
        parse.assert_not_called()

    def test_latest_filing_selection_is_not_owned_by_selected_calculation(self):
        # Explicitly selected wrappers own discovery. The common function
        # cannot silently choose latest if the caller omitted selected identity.
        with patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',
                   side_effect=AssertionError('Selected calculation must not discover')):
            with self.assertRaises(KeyError):
                self.invoke()
