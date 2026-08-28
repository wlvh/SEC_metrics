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
    "sha256:00144ea89bec568904a24ec52be33f75897a5a2d132525a727f770dd1b993508"
)
EXPECTED_RUN_RECEIPT_ID = (
    "sha256:f3b954403c9e9dde84d46a5013755ebb329c868551189b46b634506a6a33855a"
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
    """Verify the completed Linux hard-guard materialization evidence."""

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
        """Bind exact JPM/census bytes and the completed full materialization."""
        self.assertEqual(
            EXPECTED_BENCHMARK_RECEIPT_ID,
            self.summary["benchmark_receipt_id"],
        )
        self.assertEqual(
            EXPECTED_RUN_RECEIPT_ID, self.summary["run_receipt_id"],
        )
        self.assertEqual(
            "COMPLETED", self.summary["status"],
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
            "LINUX_CGROUP_V2_AND_NETWORK_NONE_PASS",
            self.semantic["safety_ceilings"]["guard_status"],
        )
        self.assertEqual(
            RSS_CEILING_BYTES,
            self.semantic["safety_ceilings"][
                "hard_address_space_and_peak_rss_ceiling_bytes"
            ],
        )
        self.assertTrue(
            self.semantic["no_network_proof"]["benchmark_child_started"]
        )
        self.assertEqual(
            "DOCKER_NETWORK_NONE",
            self.semantic["no_network_proof"]["policy"],
        )
        self.assertEqual(
            0, self.semantic["no_network_proof"]["ipv4_route_count"],
        )
        self.assertEqual(
            0,
            self.semantic["no_network_proof"][
                "ipv6_non_loopback_route_count"
            ],
        )
        materialization = self.semantic["materialization"]
        self.assertTrue(materialization["completed"])
        self.assertEqual(124761, materialization["final_expanded_cells"])
        self.assertEqual(679, materialization["table_count"])
        self.assertEqual(22174348, self.summary["canonical_json_bytes"])
        self.assertEqual(
            "sha256:694e176416c50b28974e8fa9844bd0d8e6ee772bd3915b2819aa708bab288110",
            self.summary["derived_asset_id"],
        )
        self.assertEqual(282877952, self.summary["peak_rss_bytes"])
        self.assertEqual(
            288043008, self.summary["cgroup_memory_peak_bytes"],
        )
        self.assertEqual("5.10483", self.summary["wall_time_seconds"])

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
