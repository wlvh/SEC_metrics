"""Focused aggregate-summary, path-safety and completed-Run recovery probes.

Unit probes isolate orchestration from already-verified native terminals.
The recovery helper consumes the integrator's real fifteen-Run temporary
workspace, so no second qualification fixture or model execution is created.
"""

import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from vnext.canonical import atomic_write_bytes, atomic_write_json, canonical_json_bytes
from vnext.canonical import content_hash, strict_json_file
from vnext import r4_live_qualification as qualification


def _summary_fixture():
    """Full summary shape; native source/Run verification is patched separately."""
    plan_id = content_hash(value={"unit": "plan"})
    entries = [{"entry_id": content_hash(value={"ordinal": ordinal}), "ordinal": ordinal,
                "fixture_id": "fixture_" + str(ordinal)} for ordinal in range(1, 13)]
    zero = [{"fixture_id": "structured_" + str(index), "artifact_kind": "STRUCTURED_PRIMARY",
             "planned_provider_calls": 0, "reason": "STRUCTURED_PRIMARY_RESOLVED"} for index in range(3)]
    zero += [{"fixture_id": "zero_" + str(index), "artifact_kind": "ZERO_CALL_CLASSIFICATION",
              "planned_provider_calls": 0, "reason": kind} for index, kind in enumerate(
        ("NEGATIVE_EXPECTED", "NOT_APPLICABLE", "QUALITATIVE_ONLY", "AMBIGUOUS_EXCLUDED"))]
    plan = {"pending_plan_id": plan_id, "execution_mode": "RECORDED_TEST", "entries": entries,
        "requirement_id": "issue_28_v2", "requirement_closure_hash": "sha256:" + "a" * 64,
        "zero_call_fixtures": zero, "stability_selection": []}
    structured = [{"terminal_id": content_hash(value={"structured": index}),
                   "run_id": "run:structured:" + str(index), "run_status": "FROZEN"}
                  for index in range(3)]
    terminals = [{"terminal_id": content_hash(value={"entry": entry["entry_id"]}),
        "entry_id": entry["entry_id"], "ordinal": entry["ordinal"], "fixture_id": entry["fixture_id"],
        "pending_plan_id": plan_id, "execution_mode": "RECORDED_TEST", "status": "PASSED",
        "run_status": "FROZEN", "execution_status": "SUCCEEDED",
        "execution_receipt_id": content_hash(value={"execution": entry["entry_id"]}),
        "counters": {"real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0, "mock_transport_invocation_count": 1}}
        for entry in entries]
    body = {"record_type": "R4_QUALIFICATION_EXECUTION_SUMMARY", "schema_version": 1,
        "pending_plan_id": plan_id, "requirement_id": plan["requirement_id"],
        "requirement_closure_hash": plan["requirement_closure_hash"], "execution_mode": "RECORDED_TEST",
        "status": "PASSED_RECORDED_ONLY", "terminal_ids": [row["terminal_id"] for row in terminals],
        "counters": {"real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0, "mock_transport_invocation_count": 12},
        "sec_calls": 0, "structured_terminal_ids": [row["terminal_id"] for row in structured],
        "zero_call_fixtures": zero, "stability_selection": [], "response_reuse_authorized": False,
        "publication_credit": "NONE", "qualification_credit": "NONE_RECORDED_TEST",
        "active_publication_id": "sha256:" + "b" * 64}
    summary = {**body, "summary_id": content_hash(value=body)}
    context = SimpleNamespace(_root=Path("/unused/unit/repository"), _terminal_pins={},
        _session=SimpleNamespace(validate_full_corpus=lambda: list(range(16))),
        _pointer={"publication_id": body["active_publication_id"]}, _check=lambda: None)
    return context, plan, structured, terminals, summary


class R4AggregateSummaryTest(unittest.TestCase):
    def _replay(self, summary):
        context, plan, structured, terminals, _original = _summary_fixture()
        by_entry = {row["entry_id"]: row for row in terminals}
        with mock.patch.object(qualification, "validate_r4_execution_plan", return_value=plan), \
                mock.patch.object(qualification, "_structured_terminals", return_value=structured), \
                mock.patch.object(qualification, "_validated_terminal",
                    side_effect=lambda **kwargs: by_entry[kwargs["entry"]["entry_id"]]), \
                mock.patch.object(qualification, "_read_json", return_value=summary):
            return qualification.replay_r4_qualification(repo_root=context._root, plan=plan, context=context)

    def test_complete_derived_summary_control_passes(self):
        summary = _summary_fixture()[-1]
        self.assertEqual(self._replay(summary)["qualification_credit"], "NONE_RECORDED_TEST")

    def test_rebound_summary_observability_and_credit_fields_are_not_ignored(self):
        mutations = (
            lambda row: row["counters"].update(real_model_provider_egress_count=1),
            lambda row: row.update(status="PASSED_PENDING_INDEPENDENT_REPLAY"),
            lambda row: row.update(qualification_credit="EXACT_PLAN_LIVE_QUALIFICATION_ONLY"),
            lambda row: row.update(publication_credit="PUBLISHABLE"),
            lambda row: row.update(sec_calls=1),
            lambda row: row.update(response_reuse_authorized=True),
            lambda row: row["zero_call_fixtures"].pop(),
            lambda row: row.update(stability_selection=[{"unapproved": True}]),
            lambda row: row.update(active_publication_id="sha256:" + "0" * 64),
            lambda row: row.update(unrecognized_credit_field=True),
        )
        for index, mutate in enumerate(mutations):
            summary = copy.deepcopy(_summary_fixture()[-1])
            mutate(summary)
            summary["summary_id"] = content_hash(value={key: value for key, value in summary.items() if key != "summary_id"})
            with self.subTest(mutation=index), self.assertRaises(qualification.R4QualificationError):
                self._replay(summary)


class R4StructuredNamespaceTest(unittest.TestCase):
    def test_structured_writer_rejects_a_symlink_in_every_runtime_ancestor(self):
        for aliased in ("artifacts", "r4_scoped"):
            with self.subTest(ancestor=aliased), tempfile.TemporaryDirectory(prefix="r4-ancestor-probe-") as directory:
                root = Path(directory) / "repo"
                external = Path(directory) / "outside"
                root.mkdir()
                external.mkdir()
                if aliased == "artifacts":
                    (root / "artifacts").symlink_to(external, target_is_directory=True)
                else:
                    (root / "artifacts/vnext/qualification").mkdir(parents=True)
                    (root / "artifacts/vnext/qualification/r4_scoped").symlink_to(external, target_is_directory=True)
                plan = {"pending_plan_id": "sha256:" + "a" * 64, "execution_mode": "RECORDED_TEST",
                    "zero_call_fixtures": [{"fixture_id": "structured_fixture", "artifact_kind": "STRUCTURED_PRIMARY"}]}
                parent = root / qualification.RUNTIME_ROOT / ("a" * 64) / "structured"
                parent.mkdir(parents=True)
                context = SimpleNamespace(_root=root, _terminal_pins={})
                with mock.patch("vnext.r4_structured_run.create_and_freeze_r4_structured_run",
                    side_effect=AssertionError("structured writer reached aliased path")) as writer:
                    with self.assertRaises(qualification.R4QualificationError):
                        qualification._structured_terminals(context=context, plan=plan, create=True)
                writer.assert_not_called()


def assert_completed_r4_run_recovery(
    testcase: unittest.TestCase, *, repo_root: Path, context, plan, recorded_transports, clock,
) -> list:
    """Simulate the last scoped child crash after Run persistence, with no new send."""
    entry = plan["entries"][-1]
    parent = repo_root / qualification.RUNTIME_ROOT / plan["pending_plan_id"][7:]
    root = parent / "entries" / entry["entry_id"][7:]
    return _assert_completed_run_recovery(testcase, repo_root=repo_root, root=root,
        context=context, plan=plan, recorded_transports=recorded_transports, clock=clock)


def assert_completed_r4_structured_run_recovery(
    testcase: unittest.TestCase, *, repo_root: Path, context, plan, recorded_transports, clock,
) -> list:
    """Resume the same last structured Run before sealing its zero-call terminal."""
    fixtures = [fixture for fixture in plan["zero_call_fixtures"]
                if fixture["artifact_kind"] == "STRUCTURED_PRIMARY"]
    testcase.assertEqual(len(fixtures), 3)
    parent = repo_root / qualification.RUNTIME_ROOT / plan["pending_plan_id"][7:]
    root = parent / "structured" / fixtures[-1]["fixture_id"]
    return _assert_completed_run_recovery(testcase, repo_root=repo_root, root=root,
        context=context, plan=plan, recorded_transports=recorded_transports, clock=clock)


def _assert_completed_run_recovery(
    testcase: unittest.TestCase, *, repo_root: Path, root: Path, context, plan, recorded_transports, clock,
) -> list:
    """Exercise both durable Run states using the shared immutable source context.

    The caller must supply the real isolated integration workspace after its
    complete execution.  All changed temporary bytes are restored in ``finally``.
    """
    from vnext import ai_adapter
    if repo_root.resolve() == REPO_ROOT.resolve():
        raise AssertionError("Recovery probe may only mutate the isolated integration copy")
    parent = repo_root / qualification.RUNTIME_ROOT / plan["pending_plan_id"][7:]
    terminal_path, manifest_path = root / "qualification_terminal.json", root / "run/manifest.json"
    summary_path = parent / "execution_summary.json"
    saved = {path: path.read_bytes() for path in (terminal_path, manifest_path, summary_path)}
    pins = dict(context._terminal_pins)
    verified = []
    for state in ("FROZEN", "OPEN"):
        try:
            terminal_path.unlink()
            if state == "OPEN":
                manifest = strict_json_file(path=manifest_path)
                manifest["status"] = "OPEN"
                atomic_write_json(path=manifest_path, value=manifest)
            with mock.patch.object(ai_adapter, "_open_provider_request",
                    side_effect=AssertionError("recovery opened provider")) as opener, \
                    mock.patch.object(ai_adapter._ScopedInvocationControllerTransport, "send",
                    side_effect=AssertionError("recovery sent another mock/provider request")) as sender:
                recovered = qualification.execute_r4_qualification(repo_root=repo_root, plan=plan,
                    recorded_transports=recorded_transports, context=context, clock=clock)
            opener.assert_not_called()
            sender.assert_not_called()
            testcase.assertEqual(recovered["status"], "PASSED_RECORDED_ONLY")
            testcase.assertEqual(terminal_path.read_bytes(), saved[terminal_path])
            testcase.assertEqual(manifest_path.read_bytes(), saved[manifest_path])
            testcase.assertEqual(summary_path.read_bytes(), saved[summary_path])
            verified.append(state + "_BEFORE_QUALIFICATION_TERMINAL")
        finally:
            for path, data in saved.items():
                atomic_write_bytes(path=path, content=data)
            context._terminal_pins.clear()
            context._terminal_pins.update(pins)
    return verified


if __name__ == "__main__":
    unittest.main()
