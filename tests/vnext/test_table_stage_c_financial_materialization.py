"""Verify the guarded Stage-C JPM materialization terminal evidence."""

from __future__ import annotations

import json
import unittest

from tests.vnext.common import REPO_ROOT
from tools.benchmark_jpm_full_materialization import CURRENT_POINTER
from tools.benchmark_jpm_full_materialization import RESOURCE_LIMITS_RELATIVE
from tools.benchmark_jpm_full_materialization import RSS_CEILING_BYTES
from tools.benchmark_jpm_full_materialization import SOURCE_RELATIVE
from tools.benchmark_jpm_full_materialization import SOURCE_SHA256
from tools.benchmark_jpm_full_materialization import STAGE_B_CENSUS_RECEIPT_ID
from tools.benchmark_jpm_full_materialization import TEST_ONLY_MAX_TOTAL_CELLS
from tools.benchmark_jpm_full_materialization import _production_source_hashes
from tools.benchmark_jpm_full_materialization import _root_state
from tools.benchmark_jpm_full_materialization import _stage_b_census
from vnext.canonical import content_hash, sha256_file, strict_json_file


EXPECTED_BENCHMARK_RECEIPT_ID = (
    "sha256:7129778529da4e8b402ad693433531f36c52cd99f4c1b71e20735bb33196b3c3"
)
EXPECTED_RUN_RECEIPT_ID = (
    "sha256:769a848b5099596c9ea04210b8cc7e69facdd010d6739f16d1edbcb90baf32be"
)
PRODUCTION_RESOURCE_LIMITS_SHA256 = (
    "b9b337e31168c73371a9f27fe2a5349e8a5308b1aaee117fbab6f86bee8e3f04"
)
ACTIVE_R3_PUBLICATION_ID = (
    "publication_4f2542a2e74de50e2e005d787a7edd57cbf587697593e4f3b74a59a81a684cc8"
)
EXACT_R2_PUBLICATION_ID = (
    "publication_fe01e227848d6a4212318b4942742d06b0a2861df55e0b268df2062a441c438f"
)
R3_RECEIPT_INDEX_ID = (
    "sha256:fcaca01e14859d9479173616cdad96a41541a472590af41175accb9d7b5a19ac"
)
R3_ROOT_CHANGE_SET = {
    "outputs/active_publication.json",
    "outputs/metrics_matrix.csv",
    "outputs/metric_evidence.csv",
    "REPORT_十公司财务指标.md",
}
R3_ROOT_TO_BUNDLE = {
    "outputs/metrics_matrix.csv": "metrics_matrix.csv",
    "outputs/metric_evidence.csv": "metric_evidence.csv",
    "REPORT_十公司财务指标.md": "REPORT_十公司财务指标.md",
}


class TableStageCFinancialMaterializationTest(unittest.TestCase):
    """Keep the fallback honest when macOS lacks a reliable RSS hard limit."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load historical benchmark facts and the independent R3 read-back."""
        cls.pointer = strict_json_file(path=REPO_ROOT / CURRENT_POINTER)
        cls.semantic = strict_json_file(
            path=REPO_ROOT / cls.pointer["benchmark_receipt_path"],
        )
        cls.run_receipt = strict_json_file(
            path=REPO_ROOT / cls.pointer["run_receipt_path"],
        )
        cls.census = _stage_b_census(repo_root=REPO_ROOT)
        cls.current_root = _root_state(repo_root=REPO_ROOT)
        benchmark_root = cls.semantic["root_business_artifacts_after"]
        cls.current_root_drift = {
            relative
            for relative in set(benchmark_root) | set(cls.current_root)
            if benchmark_root.get(relative) != cls.current_root.get(relative)
        }
        cls.r3_index = strict_json_file(
            path=REPO_ROOT / "outputs" / "ratchet_release_receipts" / "r3"
            / "index.json"
        )
        cls.r3_read_back = strict_json_file(
            path=REPO_ROOT
            / cls.r3_index["receipts"]["immutable_read_back"]["path"]
        )
        cls.r3_active_terminal_path = (
            REPO_ROOT / cls.r3_index["receipts"]["active_terminal"]["path"]
        )
        cls.r3_active_terminal = strict_json_file(
            path=cls.r3_active_terminal_path
        )
        cls.active_pointer = strict_json_file(
            path=REPO_ROOT / "outputs" / "active_publication.json"
        )
        cls.summary = {
            "status": cls.semantic["status"],
            "benchmark_receipt_id": cls.semantic["benchmark_receipt_id"],
            "run_receipt_id": cls.run_receipt["run_receipt_id"],
            "peak_rss_bytes": cls.run_receipt["peak_rss_bytes"],
            "wall_time_seconds": cls.run_receipt["wall_time_seconds"],
            "canonical_json_bytes": cls.semantic["materialization"][
                "canonical_json_bytes"
            ],
            "derived_asset_id": cls.semantic["materialization"][
                "derived_asset_id"
            ],
        }

    def test_current_receipt_is_census_bound_and_resource_safe(self) -> None:
        """Bind historical JPM facts and exact, independently verified R3 drift."""
        pointer_body = {
            key: self.pointer[key] for key in self.pointer if key != "pointer_id"
        }
        semantic_body = {
            key: self.semantic[key]
            for key in self.semantic
            if key != "benchmark_receipt_id"
        }
        run_body = {
            key: self.run_receipt[key]
            for key in self.run_receipt
            if key != "run_receipt_id"
        }
        self.assertEqual(
            self.pointer["pointer_id"], content_hash(value=pointer_body)
        )
        self.assertEqual(
            self.semantic["benchmark_receipt_id"],
            content_hash(value=semantic_body),
        )
        self.assertEqual(
            self.run_receipt["run_receipt_id"], content_hash(value=run_body)
        )
        self.assertEqual(
            EXPECTED_BENCHMARK_RECEIPT_ID,
            self.summary["benchmark_receipt_id"],
        )
        self.assertEqual(
            EXPECTED_RUN_RECEIPT_ID, self.summary["run_receipt_id"],
        )
        self.assertEqual(
            "NOT_RUN_RSS_GUARD_UNAVAILABLE", self.summary["status"],
        )
        self.assertEqual(SOURCE_SHA256, self.semantic["source"]["sha256"])
        self.assertEqual(
            STAGE_B_CENSUS_RECEIPT_ID,
            self.semantic["stage_b_census_binding"]["receipt_id"],
        )
        self.assertEqual(
            STAGE_B_CENSUS_RECEIPT_ID, self.census["receipt_id"]
        )
        self.assertEqual(
            124761,
            self.semantic["stage_b_census_binding"][
                "exact_total_rectangular_expanded_cell_count"
            ],
        )
        self.assertEqual(
            TEST_ONLY_MAX_TOTAL_CELLS,
            self.semantic["test_only_override"]["value"],
        )
        self.assertEqual(
            "BENCHMARK_CHILD_PROCESS_ONLY",
            self.semantic["test_only_override"]["scope"],
        )
        self.assertEqual(
            "RSS_HARD_LIMIT_SETUP_FAILED",
            self.semantic["safety_ceilings"]["guard_status"],
        )
        self.assertEqual(
            RSS_CEILING_BYTES,
            self.semantic["safety_ceilings"][
                "hard_address_space_and_peak_rss_ceiling_bytes"
            ],
        )
        self.assertFalse(
            self.semantic["no_network_proof"]["benchmark_child_started"]
        )
        self.assertFalse(self.semantic["materialization"]["completed"])
        self.assertIsNone(self.summary["peak_rss_bytes"])
        self.assertIsNone(self.summary["wall_time_seconds"])
        self.assertIsNone(self.summary["canonical_json_bytes"])
        self.assertIsNone(self.summary["derived_asset_id"])
        self.assertEqual(
            SOURCE_RELATIVE.as_posix(),
            self.semantic["source"]["repo_relative_path"],
        )
        self.assertEqual(
            SOURCE_SHA256, sha256_file(path=REPO_ROOT / SOURCE_RELATIVE)
        )
        self.assertEqual(
            (REPO_ROOT / SOURCE_RELATIVE).stat().st_size,
            self.semantic["source"]["size"],
        )
        self.assertEqual(
            _production_source_hashes(repo_root=REPO_ROOT),
            self.semantic["production_source_code_hashes"],
        )
        self.assertEqual(
            self.semantic["root_business_artifacts_before"],
            self.semantic["root_business_artifacts_after"],
        )
        self.assertTrue(self.semantic["root_business_artifacts_byte_equal"])
        self.assertEqual(R3_ROOT_CHANGE_SET, self.current_root_drift)

    def test_production_root_and_egress_remain_unchanged(self) -> None:
        """Prove benchmark-time stability and bind current roots to active R3."""
        policy = self.semantic["production_resource_policy"]
        self.assertEqual(100000, policy["max_total_cells"])
        self.assertTrue(policy["unchanged"])
        self.assertEqual(
            PRODUCTION_RESOURCE_LIMITS_SHA256,
            sha256_file(path=REPO_ROOT / RESOURCE_LIMITS_RELATIVE),
        )
        self.assertEqual(
            PRODUCTION_RESOURCE_LIMITS_SHA256,
            policy["resource_limits_sha256_before"],
        )
        network = self.semantic["no_network_proof"]
        self.assertEqual(0, network["real_model_provider_egress_count"])
        self.assertEqual(0, network["paid_model_provider_call_count"])
        self.assertEqual(0, network["real_SEC_egress_count"])

        index_body = {
            key: self.r3_index[key]
            for key in self.r3_index
            if key != "receipt_index_id"
        }
        self.assertEqual("PASSED", self.r3_index["status"])
        self.assertEqual(R3_RECEIPT_INDEX_ID, self.r3_index["receipt_index_id"])
        self.assertEqual(
            self.r3_index["receipt_index_id"], content_hash(value=index_body)
        )
        for binding in self.r3_index["receipts"].values():
            path = REPO_ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256_file(path=path))
            self.assertEqual(binding["size"], path.stat().st_size)

        read_back_body = {
            key: self.r3_read_back[key]
            for key in self.r3_read_back
            if key != "read_back_proof_id"
        }
        self.assertEqual("PASSED", self.r3_read_back["status"])
        self.assertEqual(
            self.r3_read_back["read_back_proof_id"],
            content_hash(value=read_back_body),
        )
        self.assertEqual(
            ACTIVE_R3_PUBLICATION_ID,
            self.r3_read_back["active_publication_id"],
        )
        self.assertEqual(
            EXACT_R2_PUBLICATION_ID,
            self.r3_read_back["predecessor_publication_id"],
        )
        self.assertEqual(
            self.active_pointer,
            self.r3_active_terminal,
        )
        self.assertEqual(
            ACTIVE_R3_PUBLICATION_ID,
            self.r3_active_terminal["publication_id"],
        )
        self.assertEqual(
            EXACT_R2_PUBLICATION_ID,
            self.r3_active_terminal["previous_publication_id"],
        )
        active_bundle = (
            REPO_ROOT
            / "outputs"
            / "publications"
            / ACTIVE_R3_PUBLICATION_ID
        )
        for root_relative, bundle_relative in R3_ROOT_TO_BUNDLE.items():
            current_hash = sha256_file(path=REPO_ROOT / root_relative)
            self.assertEqual(
                self.r3_read_back["mirror_hashes"][bundle_relative],
                current_hash,
            )
            self.assertEqual(
                self.r3_read_back["artifact_hashes"][bundle_relative],
                current_hash,
            )
            self.assertEqual(
                current_hash,
                sha256_file(path=active_bundle / bundle_relative),
            )

    def test_semantic_preimage_excludes_process_and_temporary_noise(self) -> None:
        """Keep semantic identity free of PID, temp locators, and stderr lines."""
        text = json.dumps(self.semantic, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "process_id",
            "pid",
            "temporary_directory",
            "/var/folders/",
            "stderr_line",
        ):
            self.assertNotIn(forbidden, text.lower())
        self.assertNotIn("duration_seconds", self.semantic)
        self.assertNotIn("wall_time_seconds", self.semantic)
        self.assertNotIn("peak_rss_bytes", self.semantic)


if __name__ == "__main__":
    unittest.main()
