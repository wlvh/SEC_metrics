"""Verify the guarded Stage-C JPM materialization terminal evidence."""

from __future__ import annotations

import json
import unittest

from tests.vnext.common import REPO_ROOT
from tools.benchmark_jpm_full_materialization import CURRENT_POINTER
from tools.benchmark_jpm_full_materialization import DOCKER_LINUX_IMAGE
from tools.benchmark_jpm_full_materialization import DOCKER_WORKDIR
from tools.benchmark_jpm_full_materialization import RESOURCE_LIMITS_RELATIVE
from tools.benchmark_jpm_full_materialization import RSS_CEILING_BYTES
from tools.benchmark_jpm_full_materialization import SOURCE_SHA256
from tools.benchmark_jpm_full_materialization import STAGE_B_CENSUS_RECEIPT_ID
from tools.benchmark_jpm_full_materialization import TEST_ONLY_MAX_TOTAL_CELLS
from tools.benchmark_jpm_full_materialization import _docker_argv
from tools.benchmark_jpm_full_materialization import validate_current_receipts
from vnext.canonical import sha256_file, strict_json_file


EXPECTED_BENCHMARK_RECEIPT_ID = (
    "sha256:7129778529da4e8b402ad693433531f36c52cd99f4c1b71e20735bb33196b3c3"
)
EXPECTED_RUN_RECEIPT_ID = (
    "sha256:769a848b5099596c9ea04210b8cc7e69facdd010d6739f16d1edbcb90baf32be"
)
PRODUCTION_RESOURCE_LIMITS_SHA256 = (
    "b9b337e31168c73371a9f27fe2a5349e8a5308b1aaee117fbab6f86bee8e3f04"
)


class DockerLinuxGuardContractTest(unittest.TestCase):
    """Keep the Linux benchmark command fixed before materialization."""

    def test_docker_argv_has_hard_memory_wall_parent_and_no_network(self) -> None:
        """Bind the immutable image, read-only source, cgroup, and netns flags."""
        argv = list(_docker_argv(
            executable="docker", container_name="guard-contract-test",
        ))
        self.assertIn("--network=none", argv)
        self.assertIn("--memory={}".format(RSS_CEILING_BYTES), argv)
        self.assertIn("--memory-swap={}".format(RSS_CEILING_BYTES), argv)
        self.assertIn("--pids-limit=64", argv)
        self.assertIn("--cap-drop=ALL", argv)
        self.assertIn("--security-opt=no-new-privileges", argv)
        self.assertIn("--read-only", argv)
        self.assertIn(DOCKER_LINUX_IMAGE, argv)
        self.assertIn("--workdir={}".format(DOCKER_WORKDIR), argv)
        mounts = [value for value in argv if value.startswith("--mount=")]
        self.assertEqual(1, len(mounts))
        self.assertTrue(mounts[0].endswith(",readonly"))
        self.assertEqual("--child", argv[-1])


class TableStageCFinancialMaterializationTest(unittest.TestCase):
    """Keep the fallback honest when macOS lacks a reliable RSS hard limit."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load and content-verify the committed semantic/run pointer chain."""
        cls.summary = validate_current_receipts(repo_root=REPO_ROOT)
        cls.pointer = strict_json_file(path=REPO_ROOT / CURRENT_POINTER)
        cls.semantic = strict_json_file(
            path=REPO_ROOT / cls.pointer["benchmark_receipt_path"],
        )
        cls.run_receipt = strict_json_file(
            path=REPO_ROOT / cls.pointer["run_receipt_path"],
        )

    def test_current_receipt_is_census_bound_and_resource_safe(self) -> None:
        """Bind exact JPM/census bytes while refusing an unguarded allocation."""
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

    def test_production_root_and_egress_remain_unchanged(self) -> None:
        """Prove fallback evidence changed no production policy or business bytes."""
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
        self.assertEqual(
            self.semantic["root_business_artifacts_before"],
            self.semantic["root_business_artifacts_after"],
        )
        self.assertTrue(self.semantic["root_business_artifacts_byte_equal"])
        network = self.semantic["no_network_proof"]
        self.assertEqual(0, network["real_model_provider_egress_count"])
        self.assertEqual(0, network["paid_model_provider_call_count"])
        self.assertEqual(0, network["real_SEC_egress_count"])

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
