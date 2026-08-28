"""Verify the decision-neutral JPM interval-based grid census."""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash, strict_json_file


EXPECTED_RECEIPT_ID = (
    "sha256:ea3d796f256a43ac5a6079de753d7d5456fc6d7485bb794ef4c9e27276ca6f2c"
)


class TableStageBFinancialGridCensusTest(unittest.TestCase):
    """Keep the complete JPM count reproducible and option-neutral."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the immutable pre-policy census consumed by the Decision."""
        digest = EXPECTED_RECEIPT_ID.split(":", maxsplit=1)[1]
        cls.first = strict_json_file(path=REPO_ROOT / Path(
            "artifacts/vnext/table_stage_b_investigation/"
            "financial_grid_census/{}.json".format(digest)
        ))

    def test_committed_receipt_identity_is_deterministic(self) -> None:
        """Recompute the immutable pre-policy census content identity."""
        self.assertEqual(EXPECTED_RECEIPT_ID, self.first["receipt_id"])
        body = {
            key: value for key, value in self.first.items()
            if key != "receipt_id"
        }
        self.assertEqual(EXPECTED_RECEIPT_ID, content_hash(value=body))

    def test_exact_grid_counts_and_production_gate_trigger(self) -> None:
        """Close source, origin, span, blank, and rectangle accounting."""
        census = self.first["census"]
        self.assertEqual(12927325, self.first["source"]["exact_html_bytes"])
        self.assertEqual(679, census["exact_table_count"])
        self.assertEqual(60348, census["exact_source_cell_count"])
        self.assertEqual(124761, census[
            "exact_total_rectangular_expanded_cell_count"
        ])
        self.assertEqual(60348, census["origin_cell_count"])
        self.assertEqual(
            62748,
            census["rowspan_colspan_duplicate_coordinate_count"],
        )
        self.assertEqual(1665, census["synthetic_blank_count"])
        self.assertEqual("0.01334552", census["synthetic_blank_ratio"])
        self.assertEqual("0.50294563", census["span_duplicate_ratio"])
        self.assertEqual(0, census["nested_table_count"])
        self.assertEqual(1, census["maximum_nesting_depth"])
        self.assertEqual(
            census["exact_total_rectangular_expanded_cell_count"],
            census["origin_cell_count"]
            + census["rowspan_colspan_duplicate_coordinate_count"]
            + census["synthetic_blank_count"],
        )
        trigger = self.first["production_gate_trigger"]
        self.assertEqual(587, trigger["order"])
        self.assertEqual("table_000588", trigger["table_id_candidate"])
        self.assertEqual(99975, trigger[
            "previous_cumulative_rectangular_cells"
        ])
        self.assertEqual(100050, trigger[
            "attempted_cumulative_rectangular_cells"
        ])

    def test_per_table_census_and_size_estimate_are_complete(self) -> None:
        """Persist all tables, top 50, and one-row-at-a-time size evidence."""
        self.assertEqual(679, len(self.first["tables"]))
        self.assertEqual(50, len(self.first["top_50_largest_tables"]))
        self.assertEqual(
            list(range(679)),
            [row["order"] for row in self.first["tables"]],
        )
        census = self.first["census"]
        self.assertEqual(
            22173876,
            census["expanded_table_set_canonical_json_bytes_estimate"],
        )
        self.assertEqual(
            22174365,
            census["full_derived_asset_canonical_json_bytes_estimate"],
        )
        self.assertFalse(census["complete_expanded_object_materialized"])
        memory = census["estimated_python_dict_list_memory_interval"]
        self.assertEqual(56947869, memory["estimated_lower_bytes"])
        self.assertEqual(152764317, memory["estimated_upper_bytes"])

    def test_options_remain_unselected_and_benchmark_is_safely_not_run(
        self,
    ) -> None:
        """Record A/B/C facts without implementing or recommending one."""
        self.assertIsNone(self.first["selected_option"])
        options = {
            row["option_id"]: row
            for row in self.first["decision_neutral_option_matrix"]
        }
        self.assertEqual({"OPTION-A", "OPTION-B", "OPTION-C"}, set(options))
        self.assertTrue(all(
            not row["implementation_selected"] for row in options.values()
        ))
        self.assertEqual(
            124761,
            options["OPTION-A"]["minimum_safe_value_for_this_exact_source"],
        )
        self.assertFalse(
            options["OPTION-B"]["application_cache_required"]
        )
        self.assertFalse(
            options["OPTION-C"]["solves_jpm_final_production_processing"]
        )
        benchmark = self.first["full_materialization_benchmark"]
        self.assertEqual("NOT_RUN_RESOURCE_SAFETY", benchmark["outcome"])
        self.assertEqual("NOT_RUN", benchmark["peak_rss_bytes"])
        self.assertEqual("NOT_RUN", benchmark["wall_time_seconds"])

    def test_no_production_mutation_or_egress(self) -> None:
        """Keep resource limits, parser, root bytes, and network untouched."""
        self.assertEqual(
            100000,
            self.first["authority"]["production_max_total_cells"],
        )
        self.assertFalse(
            self.first["authority"]["production_limits_changed"]
        )
        self.assertFalse(
            self.first["authority"]["production_parser_semantics_changed"]
        )
        self.assertTrue(self.first["root_business_artifacts_byte_equal"])
        self.assertEqual({
            "real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0,
            "real_sec_egress_count": 0,
        }, self.first["egress_counts"])
        self.assertTrue(all(
            value is False
            for value in self.first["forbidden_actions_performed"].values()
        ))


if __name__ == "__main__":
    unittest.main()
