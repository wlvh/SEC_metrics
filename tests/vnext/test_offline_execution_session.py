"""B0 session counters, immutable byte reuse, terminal stop and disk replay."""

import json
import unittest

from tests.vnext.r4_b0_fixture_support import REPO_ROOT, SOURCE_PATH
from vnext.canonical import sha256_bytes
from vnext.offline_execution_session import FileBinding, OfflineExecutionSession
from vnext.offline_execution_session import OfflineSessionError
from vnext.requirements import load_requirement_snapshot
from vnext.table_grid import build_table_grid


class OfflineExecutionSessionTest(unittest.TestCase):
    def _session(self):
        data = (REPO_ROOT / SOURCE_PATH).read_bytes()
        return OfflineExecutionSession(
            repo_root=REPO_ROOT,
            source=FileBinding(SOURCE_PATH, sha256_bytes(content=data), len(data)),
            requirement_id="issue_28_v1",
            requirement_closure_hash="sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac",
        )

    def test_prepare_once_six_children_and_one_independent_disk_replay(self):
        session = self._session()
        inputs = session.prepare()
        self.assertIs(inputs, session.prepare())
        for i in range(6):
            session.run_child(child_id="child:" + str(i), operation=lambda current: {
                "status": "PASSED", "same_immutable_object": current is inputs,
                "source_size": len(current.source_bytes),
            })
        cached_id = json.loads(inputs.derived_asset_bytes)["derived_asset_id"]

        def replay(root, binding, requirement_id, closure):
            data = (root / binding.path).read_bytes()
            self.assertEqual(binding.sha256, sha256_bytes(content=data))
            fresh = build_table_grid(html_bytes=data, parent_raw_asset_ids=["sha256:" + binding.sha256],
                                     storage_uri="offline://independent-final-disk")
            self.assertEqual(cached_id, fresh["derived_asset_id"])
            authority = load_requirement_snapshot(snapshot_dir=root / "requirements" / requirement_id)
            self.assertEqual(closure, authority["requirement_closure_hash"])
            return {"status": "PASSED", "derived_asset_id": fresh["derived_asset_id"]}

        session.final_disk_replay(replay=replay)
        report = session.report()
        self.assertEqual("FINALIZED", report["state"])
        for key in ("source_materializations", "derived_asset_builds", "parent_authority_builds", "final_independent_disk_replays"):
            self.assertEqual(1, report["operation_counts"][key])
        for key in ("full_prior_run_replays_per_child", "full_derived_asset_rebuilds_per_child", "provider_calls", "paid_model_calls", "sec_calls"):
            self.assertEqual(0, report["operation_counts"][key])
        with self.assertRaises(OfflineSessionError):
            session.final_disk_replay(replay=replay)

    def test_unknown_is_terminal_and_cannot_be_retried(self):
        session = self._session()
        session.prepare()
        with self.assertRaises(OfflineSessionError):
            session.run_child(child_id="unknown", operation=lambda _: {"status": "UNKNOWN"})
        with self.assertRaises(OfflineSessionError):
            session.run_child(child_id="later", operation=lambda _: {"status": "PASSED"})
        self.assertEqual("FAILED", session.report()["state"])

    def test_exact_file_hash_and_size_are_required(self):
        session = self._session()
        session.source = FileBinding(SOURCE_PATH, "0" * 64, session.source.size)
        with self.assertRaises(OfflineSessionError):
            session.prepare()
