"""Real corpus -> recorded live-shaped execution -> independent portable replay.

This integration tier is intentionally outside the thirty-second fast runner.
No source fixtures, responses or qualification cycles are imported from PR22.
The recorded wire is synthesized from the current offline test certificate and
has no actual model-accuracy, live-usage or publication credit.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from vnext import ai_adapter
from vnext.canonical import canonical_json_bytes, strict_json_file
from vnext.r4_live_authority import build_r4_recorded_test_plan, prepare_r4_execution_context
from vnext.r4_live_qualification import execute_r4_qualification
from vnext.live_scoped_reader import build_scoped_invocation_acceptance_context
from tests.vnext.test_r4_run_store import assert_native_r4_run_tamper_matrix
from tests.vnext.test_r4_structured_run import assert_native_r4_structured_run_tamper_matrix
from tests.vnext.test_r4_qualification_recovery import assert_completed_r4_run_recovery


def copy_r4_release_workspace(destination: Path):
    """Copy current exact bytes; neither borrow Git metadata nor use symlinks."""
    shutil.copytree(REPO_ROOT, destination, symlinks=True, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", ".DS_Store",
        "r4_scoped", ".secrets", "provider_cache"))
    lock = destination / "outputs/active_publication.json.lock"
    if not lock.exists():
        lock.touch()


def recorded_r4_transports(*, context, plan):
    transports = {}
    for entry in plan["entries"]:
        request = context._requests[entry["fixture_id"]]
        offline = strict_json_file(path=context._root / "docs/r4_offline/qualified_cases"
                                   / entry["fixture_id"] / "scoped_attempt.json")
        wire = {"id": "recorded-r4-entry-" + str(entry["ordinal"]), "model": "deepseek-v4-flash",
            "choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": offline["response_text"]}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100,
                      "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1000}}
        transports[entry["entry_id"]] = ai_adapter.build_recorded_scoped_transport(
            raw_response_bytes=canonical_json_bytes(value=wire),
            expected_provider_request_body_sha256=request.identity["provider_request_body_sha256"])
    return transports


class R4RecordedQualificationIntegrationTest(unittest.TestCase):
    """Build one complete execution, shared by all negatives and portable read-back."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="r4-recorded-live-seam-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name).resolve() / "release"
        copy_r4_release_workspace(cls.root)
        print("R4_LIVE_SHAPED: copied isolated release workspace", flush=True)
        cls.context = prepare_r4_execution_context(repo_root=cls.root)
        cls.plan = build_r4_recorded_test_plan(context=cls.context)
        cls.transports = recorded_r4_transports(context=cls.context, plan=cls.plan)
        print("R4_LIVE_SHAPED: verified immutable requests and exact12 plan", flush=True)
        with mock.patch.object(ai_adapter, "_open_provider_request", side_effect=AssertionError("forbidden provider socket")) as opener:
            cls.result = execute_r4_qualification(repo_root=cls.root, plan=cls.plan,
                recorded_transports=cls.transports, context=cls.context,
                clock=lambda: datetime(2026, 9, 4, 1, 0, tzinfo=timezone.utc))
            cls.provider_socket_count = opener.call_count
        print("R4_LIVE_SHAPED: completed twelve native recorded executions", flush=True)

    def test_full_live_shaped_native_execution_has_zero_sockets_and_no_reuse(self):
        self.assertEqual(self.provider_socket_count, 0)
        self.assertEqual(self.result["status"], "PASSED_RECORDED_ONLY")
        self.assertEqual(self.result["counters"], {"real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0, "mock_transport_invocation_count": 12})
        self.assertEqual(self.result["sec_calls"], 0)
        self.assertEqual(len(set(self.result["terminal_ids"])), 12)
        self.assertEqual(len(set(self.result["structured_terminal_ids"])), 3)
        self.assertEqual(len(self.plan["entries"]), 12)
        self.assertEqual(len(self.plan["zero_call_fixtures"]), 7)
        self.assertFalse(self.result["response_reuse_authorized"])
        self.assertEqual(self.result["qualification_credit"], "NONE_RECORDED_TEST")
        self.assertEqual(self.result["publication_credit"], "NONE")

    def test_native_run_full_artifact_rebound_tamper_matrix(self):
        entry = self.plan["entries"][0]
        request = self.context._requests[entry["fixture_id"]]
        acceptance = build_scoped_invocation_acceptance_context(request=request, execution_context=self.context)
        root = self.root / "artifacts/vnext/qualification/r4_scoped" / self.plan["pending_plan_id"][7:]
        run_dir = root / "entries" / entry["entry_id"][7:] / "run"
        negatives = assert_native_r4_run_tamper_matrix(self, repo_root=self.root,
            run_dir=run_dir, acceptance_context=acceptance)
        self.assertEqual(len(negatives), 12)

    def test_same_execution_run_crash_gap_resumes_without_transport_or_new_credit(self):
        recovered = assert_completed_r4_run_recovery(self, repo_root=self.root,
            context=self.context, plan=self.plan, recorded_transports=self.transports,
            clock=lambda: datetime(2026, 9, 4, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(recovered, ["FROZEN", "OPEN"])

    def test_structured_primary_runs_use_native_claims_and_reject_rebound_mutations(self):
        from vnext.r4_structured_run import prepare_r4_structured_run_context
        fixture = next(entry for entry in self.plan["zero_call_fixtures"] if entry["artifact_kind"] == "STRUCTURED_PRIMARY")
        context = prepare_r4_structured_run_context(repo_root=self.root, fixture_id=fixture["fixture_id"],
                                                   plan=self.plan, execution_context=self.context)
        run = self.root / "artifacts/vnext/qualification/r4_scoped" / self.plan["pending_plan_id"][7:] / "structured" / fixture["fixture_id"] / "run"
        negatives = assert_native_r4_structured_run_tamper_matrix(self, repo_root=self.root,
            run_dir=run, structured_context=context)
        self.assertEqual(len(negatives), 6)

    def test_portable_fresh_process_replays_without_source_checkout(self):
        portable = Path(self.temp.name).resolve() / "portable"
        shutil.copytree(self.root, portable, symlinks=True)
        plan_path = portable / "recorded_test_plan.json"
        plan_path.write_bytes(canonical_json_bytes(value=self.plan))
        code = (
            "import json,pathlib,socket,sys; from unittest.mock import patch; "
            "root=pathlib.Path.cwd(); sys.path.insert(0,str(root/'scripts')); "
            "from vnext.r4_live_qualification import replay_r4_qualification; "
            "from vnext import ai_adapter; "
            "plan=json.loads((root/'recorded_test_plan.json').read_text()); "
            "guard=patch.object(ai_adapter,'_open_provider_request',side_effect=AssertionError('forbidden socket')); "
            "opener=guard.start(); result=replay_r4_qualification(repo_root=root,plan=plan); "
            "assert opener.call_count==0; assert pathlib.Path(ai_adapter.__file__).is_relative_to(root); "
            "print(json.dumps(result,sort_keys=True)); guard.stop()"
        )
        # The mutable source checkout may evolve later. Only this isolated
        # fixture copy is mutated; the portable child must use its own pinned
        # engine/canonical bytes, never import from the original checkout.
        future_paths = [self.root / "scripts/vnext/canonical.py",
                        self.root / "scripts/vnext/requirement_profile_v3.py"]
        saved = {path: path.read_bytes() for path in future_paths}
        try:
            for path in future_paths:
                path.write_bytes(b"raise RuntimeError('future checkout must not be imported by portable replay')\n")
            result = subprocess.run([sys.executable, "-B", "-c", code], cwd=portable,
                text=True, capture_output=True, check=False, timeout=1800)
        finally:
            for path, data in saved.items():
                path.write_bytes(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        replay = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(replay["status"], "PASSED")
        self.assertEqual(replay["replayed_run_count"], 15)
        self.assertEqual(replay["verified_fixture_count"], 16)
        self.assertEqual(replay["provider_paid_sec_calls"], [0, 0, 0])
        self.assertEqual(replay["qualification_credit"], "NONE_RECORDED_TEST")


if __name__ == "__main__":
    unittest.main()
