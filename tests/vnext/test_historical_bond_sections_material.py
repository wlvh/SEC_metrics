"""Reuse the complete latest filing and its original financing counterexamples."""
from tests.vnext import test_b06_bond_leases as ordinary
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_bond_sections import inspect_bond_debt_scope


class HistoricalBondSectionMaterialTest(ordinary.BondDebtScopeTest):
    def inspect(self, args):
        with original_sources_only():
            return inspect_bond_debt_scope(**args)

    def test_unique_labels_preserve_the_entire_original_scope_proof(self):
        self.assertEqual(self.actual, self.inspect(self.args))
