"""B0 session counters, immutable byte reuse, terminal stop and disk replay."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.r4_b0_fixture_support import REPO_ROOT, SOURCE_PATH
from vnext.canonical import canonical_json_bytes, sha256_bytes
from vnext.offline_execution_session import FileBinding, OfflineExecutionSession
from vnext.offline_execution_session import OfflineSessionError
from vnext.offline_execution_session import OfflineOperationObserver
from vnext.r4_materialization import materialize_full_source, OfflineMaterializationError, PINNED_IMAGE_ID
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
        self.assertEqual("FAILED", session.state)

    def test_deep_observer_counts_native_work_without_replacing_verifiers(self):
        session = self._session()
        with OfflineOperationObserver() as observed:
            session.prepare()
            session.prepare()
            for index in range(6):
                session.run_child(child_id=str(index), operation=lambda _: {"status": "PASS"})
        self.assertEqual(1, observed.counts["source_materializations"])
        self.assertEqual(1, observed.counts["derived_asset_builds"])
        self.assertEqual(1, observed.counts["requirement_builds"])
        self.assertEqual(1, observed.counts["parent_authority_builds"])
        self.assertGreater(observed.counts["canonicalizations"], session.counts["canonicalizations"])
        self.assertGreater(observed.counts["semantic_hashes"], 0)
        self.assertEqual(0, observed.counts["native_prior_run_loads"])
        self.assertEqual(0, observed.counts["portable_prior_run_loads"])
        for key in ("provider_calls", "paid_model_calls", "sec_calls"):
            self.assertEqual(0, observed.counts[key])

    def test_crash_and_unknown_status_are_terminal_and_never_retried(self):
        for status in ("UNKNOWN", "PENDING", "FAILED", "CRASHED", "REUSED_SUCCESS", None):
            with self.subTest(status=status):
                session = self._session()
                session.prepare()
                with self.assertRaises(OfflineSessionError):
                    session.run_child(child_id="first", operation=lambda _: {"status": status})
                self.assertEqual("FAILED", session.state)
                with self.assertRaises(OfflineSessionError):
                    session.run_child(child_id="second", operation=lambda _: {"status": "PASS"})
                self.assertEqual(0, session.counts["final_independent_disk_replays"])

    def test_child_exception_never_allows_later_execution_or_replay(self):
        session = self._session()
        session.prepare()

        def crash(_):
            raise RuntimeError("synthetic local crash")

        with self.assertRaisesRegex(RuntimeError, "synthetic local crash"):
            session.run_child(child_id="crash", operation=crash)
        self.assertEqual("FAILED", session.state)
        with self.assertRaises(OfflineSessionError):
            session.final_disk_replay(replay=lambda *_: {"status": "PASSED"})

    def test_disk_hash_pin_rejects_same_size_mutation_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = root / "source.bin"
            p.write_bytes(b"original")
            session = OfflineExecutionSession(
                repo_root=root, source=FileBinding("source.bin", sha256_bytes(content=b"original"), 8),
                requirement_id="issue_28_v1", requirement_closure_hash="sha256:" + "0" * 64,
            )
            self.assertEqual(b"original", session._read_exact(session.source))
            p.write_bytes(b"mutated!")
            with self.assertRaises(OfflineSessionError):
                session._read_exact(session.source)
            p.unlink()
            other = root / "other.bin"
            other.write_bytes(b"original")
            p.symlink_to(other)
            with self.assertRaises(OfflineSessionError):
                session._read_exact(session.source)
            self.assertEqual("FAILED", session.state)

    def test_guarded_materializer_does_not_pull_when_local_image_is_absent(self):
        data = (REPO_ROOT / SOURCE_PATH).read_bytes()
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="no local image")
        with patch("vnext.r4_materialization.subprocess.run", return_value=failed) as run:
            with self.assertRaisesRegex(OfflineMaterializationError, "no pull"):
                materialize_full_source(
                    repo_root=REPO_ROOT, source_path=SOURCE_PATH,
                    source_sha256=sha256_bytes(content=data), source_size=len(data),
                )
        self.assertEqual(1, run.call_count)
        self.assertEqual(["docker", "image", "inspect"], run.call_args.args[0][:3])

    def test_snapshot_entry_addition_is_terminal_even_if_later_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.bin").write_bytes(b"original")
            authority = root / "requirements"
            authority.mkdir()
            session = OfflineExecutionSession(
                repo_root=root, source=FileBinding("source.bin", sha256_bytes(content=b"original"), 8),
                requirement_id="issue_28_v1", requirement_closure_hash="sha256:" + "0" * 64,
            )
            session.state = "OPEN"
            session._authority_directory_pins[authority] = set()
            session._check_pins()
            extra = authority / "detached.json"
            extra.write_bytes(b"{}")
            with self.assertRaisesRegex(OfflineSessionError, "entry set changed"):
                session._check_pins()
            extra.unlink()
            with self.assertRaises(OfflineSessionError):
                session.run_child(child_id="after-restore", operation=lambda _: {"status": "PASS"})

    def test_unrecognized_materialization_mode_cannot_override_resource_caps(self):
        session = self._session()
        with self.assertRaises(OfflineSessionError):
            OfflineExecutionSession(
                repo_root=REPO_ROOT, source=session.source,
                requirement_id=session.requirement_id,
                requirement_closure_hash=session.requirement_closure_hash,
                materialization_mode="NO_LIMITS",
            )

    def test_worker_output_cannot_self_declare_pass_without_guard_and_binding(self):
        data = (REPO_ROOT / SOURCE_PATH).read_bytes()
        asset = build_table_grid(
            html_bytes=data, parent_raw_asset_ids=["sha256:" + sha256_bytes(content=data)],
            storage_uri="offline://test",
        )
        inspected = subprocess.CompletedProcess([], 0, stdout=PINNED_IMAGE_ID + "\n", stderr="")
        forged = subprocess.CompletedProcess([], 0, stdout=canonical_json_bytes(value=asset),
                                            stderr=b'{"status":"PASSED_OFFLINE_ONLY"}')
        with patch("vnext.r4_materialization.subprocess.run", side_effect=[inspected, forged]) as run:
            with self.assertRaisesRegex(OfflineMaterializationError, "identity/guard"):
                materialize_full_source(
                    repo_root=REPO_ROOT, source_path=SOURCE_PATH,
                    source_sha256=sha256_bytes(content=data), source_size=len(data),
                )
        command = run.call_args_list[1].args[0]
        self.assertIn("--pull=never", command)
        self.assertIn("--read-only", command)
        self.assertEqual("none", command[command.index("--network") + 1])
        self.assertEqual("536870912", command[command.index("--memory") + 1])
        self.assertEqual("536870912", command[command.index("--memory-swap") + 1])
        self.assertEqual("32", command[command.index("--pids-limit") + 1])
