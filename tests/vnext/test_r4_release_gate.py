"""Release eligibility and private mutation gates; never 15-Run evidence.

Aggregate dictionaries and small pin fixtures test early shape/authority
branches only. Actual merge/ancestry checks use disposable local Git objects;
the full native qualification and publication rehearsal remain separate.
"""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tools import vnext_r4_release as cli
from vnext.canonical import atomic_write_json, content_hash, sha256_bytes
from vnext import r4_release as release
from vnext import r4_publication as publication
from vnext.r4_live_authority import RUNTIME_ROOT


WHEN = "2026-09-04T00:00:00Z"


def seal(value, field):
    value[field] = content_hash(value={key: item for key, item in value.items() if key != field})


def aggregate_shape():
    """Gate-only recorded shape; it contains no Runs, usage or owner proof."""
    plan = {"record_type": "R4_RECORDED_TEST_PLAN", "execution_mode": "RECORDED_TEST",
            "entries": [{"entry_id": content_hash(value={"test_entry": index})} for index in range(12)],
            "response_reuse_authorized": False}
    summary = {"execution_mode": "RECORDED_TEST", "status": "PASSED_RECORDED_ONLY",
        "qualification_credit": "NONE_RECORDED_TEST", "publication_credit": "NONE",
        "terminal_ids": [content_hash(value={"test_terminal": index}) for index in range(12)],
        "structured_terminal_ids": [content_hash(value={"test_structured": index}) for index in range(3)],
        "counters": {"real_model_provider_egress_count": 0, "paid_model_provider_call_count": 0,
                     "mock_transport_invocation_count": 12}, "sec_calls": 0, "response_reuse_authorized": False}
    replay = {"execution_mode": "RECORDED_TEST", "status": "PASSED",
        "qualification_credit": "NONE_RECORDED_TEST", "publication_credit": "NONE",
        "replayed_run_count": 15, "scoped_run_count": 12, "structured_run_count": 3,
        "verified_fixture_count": 16, "provider_paid_sec_calls": [0, 0, 0]}
    rebind_aggregate(plan, summary, replay)
    return plan, summary, replay


def rebind_aggregate(plan, summary, replay):
    seal(plan, "pending_plan_id")
    summary["pending_plan_id"] = plan["pending_plan_id"]
    seal(summary, "summary_id")
    replay.update(pending_plan_id=plan["pending_plan_id"], summary_id=summary["summary_id"])
    seal(replay, "replay_id")


def switch_shape(root, *, credit=publication.REHEARSAL_CREDIT, recorded=True):
    """An empty namespace exercises guards, not bundle/qualification validity."""
    plan_id = content_hash(value={"test_only": "switch namespace"})
    (root / RUNTIME_ROOT / plan_id[7:]).mkdir(parents=True)
    manifest = {"publication_id": "publication_" + "a" * 64,
                "previous_publication_id": "publication_" + "b" * 64,
                "publication_credit": credit}
    pin = publication._VerifiedBundle(factory=publication._FACTORY, manifest=manifest,
        context_document={"pending_plan": {"pending_plan_id": plan_id}}, receipt={"authority_files": {}})
    authority = publication._SwitchAuthority(factory=publication._FACTORY, root=root,
                                             pin=pin, owner_receipt=None, recorded=recorded)
    return manifest, pin, authority


class R4ReleaseAggregateGateTest(unittest.TestCase):
    def test_gate_shape_control_has_no_live_or_publication_credit(self):
        plan, summary, replay = aggregate_shape()
        self.assertIsNone(release._credit(plan, summary, replay, "RECORDED_REHEARSAL"))
        self.assertEqual("NONE", summary["publication_credit"])
        self.assertEqual("NONE_RECORDED_TEST", replay["qualification_credit"])
        with self.assertRaisesRegex(release.R4ReleaseError, "Recorded execution"):
            release._credit(plan, summary, replay, "LIVE")

    def test_fully_rebound_partial_aggregate_and_credit_relaxations_fail(self):
        mutations = (
            lambda p, s, r: p["entries"].pop(),
            lambda p, s, r: p["entries"].__setitem__(1, deepcopy(p["entries"][0])),
            lambda p, s, r: s["terminal_ids"].pop(),
            lambda p, s, r: s["terminal_ids"].__setitem__(1, s["terminal_ids"][0]),
            lambda p, s, r: s["structured_terminal_ids"].pop(),
            lambda p, s, r: s["structured_terminal_ids"].__setitem__(1, s["structured_terminal_ids"][0]),
            lambda p, s, r: r.update(replayed_run_count=14),
            lambda p, s, r: r.update(scoped_run_count=11),
            lambda p, s, r: r.update(structured_run_count=2),
            lambda p, s, r: r.update(verified_fixture_count=15),
            lambda p, s, r: s.update(status="FAILED"),
            lambda p, s, r: s.update(qualification_credit="PENDING_INDEPENDENT_REPLAY"),
            lambda p, s, r: r.update(status="NOT_RUN"),
            lambda p, s, r: r.update(qualification_credit="EXACT_PLAN_LIVE_QUALIFICATION_ONLY"),
            lambda p, s, r: p.update(response_reuse_authorized=True),
            lambda p, s, r: s.update(response_reuse_authorized=True),
            lambda p, s, r: s.update(publication_credit="LIVE"),
            lambda p, s, r: r.update(publication_credit="LIVE"),
            lambda p, s, r: s.update(sec_calls=1),
            lambda p, s, r: s["counters"].update(mock_transport_invocation_count=11),
            lambda p, s, r: s["counters"].update(real_model_provider_egress_count=1),
            lambda p, s, r: s["counters"].update(paid_model_provider_call_count=1),
            lambda p, s, r: r.update(provider_paid_sec_calls=[1, 0, 0]),
        )
        for index, mutate in enumerate(mutations):
            plan, summary, replay = aggregate_shape()
            mutate(plan, summary, replay)
            rebind_aggregate(plan, summary, replay)
            with self.subTest(index=index), self.assertRaises(release.R4ReleaseError):
                release._credit(plan, summary, replay, "RECORDED_REHEARSAL")

    def test_missing_fields_and_rebound_foreign_plan_summary_edges_fail(self):
        for index, field in ((0, "entries"), (1, "terminal_ids"), (2, "qualification_credit")):
            objects = aggregate_shape()
            del objects[index][field]
            rebind_aggregate(*objects)
            with self.subTest(missing=field), self.assertRaises((release.R4ReleaseError, KeyError)):
                release._credit(*objects, "RECORDED_REHEARSAL")
        for target, field in ((1, "pending_plan_id"), (2, "pending_plan_id"), (2, "summary_id")):
            plan, summary, replay = aggregate_shape()
            objects = (plan, summary, replay)
            objects[target][field] = content_hash(value={"foreign": field})
            seal(summary, "summary_id")
            if target == 1:
                replay["summary_id"] = summary["summary_id"]
            seal(replay, "replay_id")
            with self.subTest(target=target, field=field), self.assertRaises(release.R4ReleaseError):
                release._credit(plan, summary, replay, "RECORDED_REHEARSAL")


class R4RepositoryReleasePathTest(unittest.TestCase):
    def test_r3_plan_is_in_verified_portable_authority_not_the_r2_wrapper(self):
        from vnext import publication as native
        from vnext.canonical import strict_json_file
        pointer = strict_json_file(path=REPO_ROOT / 'outputs/active_publication.json')
        directory = REPO_ROOT / 'outputs/publications' / pointer['publication_id']
        manifest = strict_json_file(path=directory / 'publication_manifest.json')
        # This is a manifest-bound path smoke, not a full R3 closure replay.
        view = native.PublicationView(publication_id=pointer['publication_id'], bundle_dir=directory, manifest=manifest)
        plan = release._verified_r3_plan(view)
        self.assertEqual(plan['release_plan_id'], 'issue_15_lodging_r3')
        self.assertEqual(len(plan['cumulative_vnext_result_keys']), 240)
        self.assertFalse((directory / 'internal/issue15_release_plan.json').exists())

    def test_active_terminal_cannot_report_an_unrelated_publication_as_requested(self):
        wrong = SimpleNamespace(publication_id='publication_' + 'b' * 64)
        with mock.patch.object(publication.pub.PublicationView, 'open', return_value=wrong):
            with self.assertRaisesRegex(release.R4ReleaseError, 'requested publication'):
                publication.active_terminal(publication_root=REPO_ROOT,
                    expected_publication_id='publication_' + 'a' * 64)


class R4PrivateReleaseGateTest(unittest.TestCase):
    def test_stage_and_switch_factories_reject_caller_maps_and_tokens(self):
        for claimed in ({}, {"mode": "LIVE", "approved": True}, SimpleNamespace(_factory=object())):
            with self.subTest(claimed=type(claimed).__name__):
                with self.assertRaises(release.R4ReleaseError):
                    release.validate_r4_release_context(claimed)
                with self.assertRaises(release.R4ReleaseError):
                    publication.stage_r4_release(context=claimed)
                with self.assertRaises(release.R4ReleaseError):
                    publication.switch_r4_release(authority=claimed, operation="publish", committed_at_utc=WHEN)
        with self.assertRaises(release.R4ReleaseError):
            publication._VerifiedBundle(factory=object(), manifest={}, context_document={}, receipt={})
        with self.assertRaises(release.R4ReleaseError):
            publication._SwitchAuthority(factory=object(), root=REPO_ROOT, pin=None,
                                         owner_receipt={"approved": True}, recorded=False)

    def test_recorded_factory_rejects_actual_root_descendant_ancestor_and_git_copy(self):
        plan, _, replay = aggregate_shape()
        for root in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT.parent):
            with self.subTest(root=root), self.assertRaisesRegex(release.R4ReleaseError, "implementation root"):
                release._prepare_recorded_release_context(repo_root=root, plan=plan, replay=replay)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / ".git").mkdir()
            with self.assertRaisesRegex(release.R4ReleaseError, "non-Git"):
                release._prepare_recorded_release_context(repo_root=root, plan=plan, replay=replay)

    def test_switch_recovery_and_mirror_repair_need_private_scope(self):
        pointer = REPO_ROOT / "outputs/active_publication.json"
        with self.assertRaisesRegex(release.R4ReleaseError, "private release authorization"):
            publication.guard_switch(pointer_path=pointer, manifest={}, expected_active_id=None, switch_mode="COMMIT")
        with self.assertRaisesRegex(release.R4ReleaseError, "private release authorization"):
            publication.guard_recovery(pointer_path=pointer, intent={})
        with self.assertRaisesRegex(release.R4ReleaseError, "private release authorization"):
            publication.guard_mirror_repair(publication_root=REPO_ROOT)

    def test_guard_scope_enforces_root_exact_edge_and_immutable_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, _, authority = switch_shape(root)
            with publication._switch_scope(authority):
                # Gate-only control: full guard_switch also validates the
                # active bundle/mirrors, owned by the separate rehearsal.
                publication._guard_edge(pointer_path=root / "outputs/active_publication.json", manifest=manifest,
                    expected_active_id=manifest["previous_publication_id"], switch_mode="COMMIT")
                publication.guard_mirror_repair(publication_root=root)
                with self.assertRaisesRegex(release.R4ReleaseError, "root substitution"):
                    publication.guard_switch(pointer_path=root / "foreign/active_publication.json", manifest=manifest,
                        expected_active_id=manifest["previous_publication_id"], switch_mode="COMMIT")
                with self.assertRaisesRegex(release.R4ReleaseError, "mirror repair root"):
                    publication.guard_mirror_repair(publication_root=REPO_ROOT)
                for changed, prior, mode in ((manifest, None, "COMMIT"), (manifest, manifest["publication_id"], "ROLLBACK"),
                                            ({**manifest, "publication_id": "publication_" + "c" * 64},
                                             manifest["previous_publication_id"], "COMMIT")):
                    with self.subTest(mode=mode, prior=prior), self.assertRaisesRegex(release.R4ReleaseError, "exact R4/R3 edge"):
                        publication.guard_switch(pointer_path=root / "outputs/active_publication.json", manifest=changed,
                                                  expected_active_id=prior, switch_mode=mode)
                with self.assertRaisesRegex(release.R4ReleaseError, "manifest drift"):
                    publication.guard_switch(pointer_path=root / "outputs/active_publication.json",
                        manifest={**manifest, "unreviewed": True},
                        expected_active_id=manifest["previous_publication_id"], switch_mode="COMMIT")
            with self.assertRaises(release.R4ReleaseError):
                publication.guard_mirror_repair(publication_root=root)
            self.assertFalse((root / "outputs").exists())

    def test_rehearsal_credit_cannot_be_promoted_and_live_capability_rejects_foreign_root(self):
        for recorded, credit, message in ((True, "LIVE", "Recorded rehearsal"),
                                         (False, "LIVE", "foreign-root"),
                                         (False, publication.REHEARSAL_CREDIT, "recorded or foreign-root")):
            with self.subTest(recorded=recorded, credit=credit), tempfile.TemporaryDirectory() as directory:
                _, _, authority = switch_shape(Path(directory).resolve(), recorded=recorded, credit=credit)
                with self.assertRaisesRegex(release.R4ReleaseError, message):
                    publication._check_switch_authority(authority)

    def test_release_cli_has_no_recorded_flag_or_root_override(self):
        plan_id = content_hash(value={"test": "plan"})
        argv = ["stage", "--plan-id", plan_id, "--replay-id", plan_id, "--implementation-merge", "a" * 40]
        for option in ("--recorded", "--rehearsal", "--recorded-transport", "--repo-root", "--workspace-dir"):
            with self.subTest(option=option), redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                with mock.patch.object(cli, "prepare_r4_release_context") as factory:
                    with self.assertRaises(SystemExit) as raised:
                        cli.main(argv + [option])
                    self.assertEqual(2, raised.exception.code)
                    factory.assert_not_called()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli.main(["publish", "--publication-id", "publication_" + "a" * 64])
        self.assertEqual(2, raised.exception.code)

    def test_validate_missing_publication_returns_structured_blocked_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output, errors = io.StringIO(), io.StringIO()
            with mock.patch.object(cli, "REPO_ROOT", root), redirect_stderr(errors), redirect_stdout(output):
                rc = cli.main(["validate", "--publication-id", "publication_" + "f" * 64])
            self.assertEqual(1, rc)
            self.assertEqual("", output.getvalue())
            self.assertEqual("BLOCKED", json.loads(errors.getvalue())["status"])
            self.assertNotIn("Traceback", errors.getvalue())
            self.assertEqual([], list(root.iterdir()))


class R4ReleaseOwnerPinGateTest(unittest.TestCase):
    """Retarget/immutability probes on gate-only private pin fixtures."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="r4-owner-pin-gate-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        _, original, _ = switch_shape(self.root)
        self.manifest = {**json.loads(original.manifest), "publication_credit": "LIVE",
            "requirement_id": "issue_28_v2", "requirement_closure_hash": content_hash(value={"test": "requirement"}),
            "r4_release_receipt_id": content_hash(value={"test": "release receipt"})}
        self.pin = publication._VerifiedBundle(factory=publication._FACTORY, manifest=self.manifest,
                                               context_document=original.context_document, receipt=original.receipt)
        self.body = publication.expected_release_owner_approval(manifest=self.manifest,
                                                               exact_head="a" * 40, exact_tree="b" * 40)
        text = json.dumps(self.body)
        self.receipt = {**self.body, "record_type": "R4_EXACT_HEAD_RELEASE_AUTHORIZATION", "schema_version": 1,
            "source_url": "https://github.com/test-owner/repository/pull/30#issuecomment-9",
            "owner": "github:test-owner", "approved_at_utc": WHEN, "approval_text": text,
            "approval_text_sha256": sha256_bytes(content=text.encode())}
        seal(self.receipt, "receipt_id")
        self.authority = self.authority_for(self.pin, self.receipt)

    def authority_for(self, pin, receipt):
        return publication._SwitchAuthority(factory=publication._FACTORY, root=self.root,
                                             pin=pin, owner_receipt=receipt, recorded=False)

    def test_fully_rebound_owner_receipt_or_pin_cannot_target_a_different_release(self):
        values = (("publication_id", "publication_" + "c" * 64),
                  ("r4_release_receipt_id", content_hash(value={"other": "release"})),
                  ("requirement_closure_hash", content_hash(value={"other": "requirement"})),
                  ("predecessor_publication_id", "publication_" + "d" * 64),
                  ("allowed_operations", ["publish", "provider-call"]),
                  ("provider_paid_sec_authorized", True))
        for field, value in values:
            receipt = deepcopy(self.receipt)
            receipt[field] = value
            body = deepcopy(self.body)
            body[field] = value
            receipt["approval_text"] = json.dumps(body)
            receipt["approval_text_sha256"] = sha256_bytes(content=receipt["approval_text"].encode())
            seal(receipt, "receipt_id")
            with self.subTest(field=field), mock.patch.object(publication, "REPOSITORY_ROOT", self.root), \
                    mock.patch.object(publication, "_git", side_effect=AssertionError("RETARGET_REACHED_GIT")):
                with self.assertRaisesRegex(release.R4ReleaseError, "cannot be retargeted"):
                    publication._check_switch_authority(self.authority_for(self.pin, receipt))
        changed = {**self.manifest, "publication_id": "publication_" + "e" * 64}
        pin = publication._VerifiedBundle(factory=publication._FACTORY, manifest=changed,
            context_document=self.pin.context_document, receipt=self.pin.receipt)
        with mock.patch.object(publication, "REPOSITORY_ROOT", self.root), \
                mock.patch.object(publication, "_git", side_effect=AssertionError("RETARGET_REACHED_GIT")):
            with self.assertRaisesRegex(release.R4ReleaseError, "cannot be retargeted"):
                publication._check_switch_authority(self.authority_for(pin, self.receipt))

    def test_authority_and_pin_are_frozen_and_nested_properties_return_copies(self):
        for value, field, changed in ((self.authority, "recorded", True),
                                      (self.authority, "root", REPO_ROOT),
                                      (self.pin, "manifest", b"{}")):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(value, field, changed)
        receipt = self.authority.owner_receipt
        receipt["provider_paid_sec_authorized"] = True
        self.assertIs(self.authority.owner_receipt["provider_paid_sec_authorized"], False)
        document = self.pin.context_document
        original_id = document["pending_plan"]["pending_plan_id"]
        document["pending_plan"]["pending_plan_id"] = content_hash(value={"forged": "plan"})
        self.assertEqual(original_id, self.pin.context_document["pending_plan"]["pending_plan_id"])
        receipt = self.pin.receipt
        receipt["authority_files"]["forged.txt"] = {"sha256": "0" * 64, "size": 0}
        self.assertEqual({}, self.pin.receipt["authority_files"])


class R4MergedImplementationGateTest(unittest.TestCase):
    """Real local Git graph proof with test-only activation receipt content."""

    def git(self, *args):
        result = subprocess.run(["git", "-c", "user.name=R4 Gate Test", "-c", "user.email=r4-gate@invalid.test",
            "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args], cwd=self.root,
            capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="r4-merge-gate-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.git("init", "-b", "main")
        self.engine = self.root / "scripts/engine.py"
        self.engine.parent.mkdir()
        self.engine.write_text("VERSION = 1\n", encoding="utf-8")
        self.contract = self.root / "requirements/issue_28_v2/CONTRACT.md"
        self.contract.parent.mkdir(parents=True)
        self.contract.write_text("# Test-only frozen requirement bytes\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "Test-only base")
        self.base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-b", "implementation")
        (self.root / "implementation.txt").write_text("test-only implementation head\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "Test-only candidate")
        self.head = self.git("rev-parse", "HEAD")
        self.git("checkout", "main")
        self.git("merge", "--no-ff", "implementation", "-m", "Test-only merge")
        self.merge = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.merge)
        self.requirement = {"requirement_id": "issue_28_v2",
            "requirement_closure_hash": content_hash(value={"test_only": "merge gate requirement"}),
            "execution_authority": {"files": {"scripts/engine.py": release._binding(self.engine)}},
            "baseline": {"repository": {"identity": "test-owner/repository"},
                         "issue": {"identifier_comment_url": "https://github.com/test-owner/repository/issues/28#issuecomment-1"},
                         "policy_evidence": [{"author": "github:test-owner"}]}}
        body = {"decision": "APPROVE_REQUIREMENT_TRANSITION", "exact_head": self.head,
            "requirement_id": "issue_28_v2", "requirement_closure_hash": self.requirement["requirement_closure_hash"],
            "scope": "TRANSITION_ONLY", "provider_paid_sec_authorized": False}
        text = json.dumps(body)
        self.activation = {"record_type": "REQUIREMENT_TRANSITION_ACTIVATION", "schema_version": 1,
            "requirement_id": "issue_28_v2", "requirement_closure_hash": self.requirement["requirement_closure_hash"],
            "exact_head": self.head, "authorization_scope": "TRANSITION_ONLY", "provider_paid_sec_authorized": False,
            "approval_kind": "EXACT_HEAD_TRANSITION_APPROVAL", "owner": "github:test-owner", "approved_at_utc": WHEN,
            "source_url": "https://github.com/test-owner/repository/pull/30#issuecomment-2", "approval_text": text,
            "approval_text_sha256": sha256_bytes(content=text.encode())}
        seal(self.activation, "receipt_id")
        self.owner = {"exact_head": self.merge, "exact_tree": self.git("rev-parse", "HEAD^{tree}")}

    def check(self, *, commit=None, activation=None, owner=None):
        return release._merged_implementation(self.root, self.requirement,
            activation or self.activation, commit or self.merge, owner or self.owner)

    def test_actual_two_parent_merge_and_unchanged_bytes_are_required(self):
        self.assertEqual({"commit": self.merge, "tree": self.owner["exact_tree"], "approved_head": self.head}, self.check())
        with self.assertRaisesRegex(release.R4ReleaseError, "exact approved transition merge"):
            self.check(commit=self.head)
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        with self.assertRaisesRegex(release.R4ReleaseError, "Git identity/ancestry"):
            self.check()

    def test_rebound_activation_closure_owner_and_approval_scope_fail(self):
        for field, value in (("requirement_closure_hash", content_hash(value={"foreign": "requirement"})),
                             ("owner", "github:intruder"), ("authorization_scope", "LIVE"),
                             ("provider_paid_sec_authorized", True)):
            activation = deepcopy(self.activation)
            activation[field] = value
            seal(activation, "receipt_id")
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(activation=activation)
        activation = deepcopy(self.activation)
        activation["exact_head"] = "f" * 40
        body = json.loads(activation["approval_text"])
        body["exact_head"] = activation["exact_head"]
        activation["approval_text"] = json.dumps(body)
        activation["approval_text_sha256"] = sha256_bytes(content=activation["approval_text"].encode())
        seal(activation, "receipt_id")
        with self.assertRaisesRegex(release.R4ReleaseError, "exact approved transition merge"):
            self.check(activation=activation)

    def test_owner_head_tree_and_actual_clean_worktree_are_checked(self):
        with self.assertRaisesRegex(release.R4ReleaseError, "Git identity/ancestry"):
            self.check(owner={"exact_head": self.base, "exact_tree": self.git("rev-parse", self.base + "^{tree}")})
        with self.assertRaisesRegex(release.R4ReleaseError, "actual commit"):
            self.check(owner={**self.owner, "exact_tree": "f" * 40})
        (self.root / "uncommitted.txt").write_text("uncommitted\n", encoding="utf-8")
        with self.assertRaisesRegex(release.R4ReleaseError, "clean exact committed"):
            self.check()

    def test_committed_production_python_and_requirement_drift_fail(self):
        for path, expected in ((self.engine, "PR-C cannot modify production Python"),
                               (self.contract, "Merged Requirement snapshot differs")):
            original = path.read_bytes()
            path.write_bytes(original + b"# drift\n")
            self.git("add", ".")
            self.git("commit", "-m", "Test-only post-merge drift")
            owner = {"exact_head": self.git("rev-parse", "HEAD"), "exact_tree": self.git("rev-parse", "HEAD^{tree}")}
            with self.subTest(path=path.name), self.assertRaisesRegex(release.R4ReleaseError, expected):
                self.check(owner=owner)
            path.write_bytes(original)
            self.git("add", ".")
            self.git("commit", "-m", "Restore test-only bytes")

    def test_rebound_execution_binding_cannot_claim_other_merged_bytes(self):
        self.requirement["execution_authority"]["files"]["scripts/engine.py"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(release.R4ReleaseError, "Merged implementation execution authority"):
            self.check()


if __name__ == "__main__":
    unittest.main()
