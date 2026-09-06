"""Pending/recorded governance boundaries; all GitHub/provider calls are mocked."""

import copy
import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from vnext import r4_live_authority as authority
from vnext.canonical import atomic_write_bytes, canonical_json_bytes, content_hash, sha256_bytes, strict_json_file
from vnext.r4_fixture_authority import load_r4_fixture_authority
from vnext.r4_live_plan import _risk_features, _schedule, _scope_identity
from vnext.requirements import load_requirement_snapshot


ROOT = Path(__file__).resolve().parents[2]
STATE = {"head": "1" * 40, "tree": "2" * 40}
WHEN = "2026-09-04T00:00:00Z"
OWNER_URL = "https://github.com/wlvh/SEC_metrics/pull/123#issuecomment-456"
ORIGINAL_CONTEXT_CHECK = authority.R4ExecutionPlanContext._check


def rebind(record, key):
    record[key] = content_hash(value={k: v for k, v in record.items() if k != key})
    return record


def private_shape_context():
    """Use a private unit context to isolate shape, not native eligibility.

    The separate integration class invokes the real repository factory. These
    records use the complete current corpus but replace source checks with the
    test's explicit private boundary; they are never provider-capable objects.
    """
    fixtures = load_r4_fixture_authority(repo_root=ROOT)
    index = strict_json_file(path=ROOT / "docs/r4_offline/qualified_cases/index.json")
    sample_entry = next(row for row in index["cases"] if row["artifact_kind"] == "SCOPED_EXTRACTION")
    sample_scope = strict_json_file(path=ROOT / sample_entry["directory"] / "source_scope.json")
    baseline = strict_json_file(path=ROOT / "requirements/issue_28_v2/baseline_manifest.json")
    # Identity-only unit fixture: current source execution validation deliberately
    # belongs to the real integration factory, not these private shape tests.
    requirement = {"artifact_requirement_generation": sample_scope["artifact_requirement_generation"],
        "requirement_id": sample_scope["requirement_id"],
        "requirement_closure_hash": sample_scope["requirement_closure_hash"],
        "hashes": sample_scope["requirement_hashes"], "baseline": baseline,
        "execution_authority": baseline["execution_authority"]}
    subjects = strict_json_file(path=ROOT / "config/r4_fixture_company_authority_v1.json")
    subjects_by_source = {entry["source_id"]: entry for entry in subjects["entries"]}
    eligible, requests = [], {}
    for row in index["cases"]:
        if row["artifact_kind"] != "SCOPED_EXTRACTION":
            continue
        scope = strict_json_file(path=ROOT / row["directory"] / "source_scope.json")
        plan = strict_json_file(path=ROOT / row["directory"] / "scoped_plan.json")
        recipe = fixtures["recipes"][row["fixture_id"]]
        identity = _scope_identity(scope, plan)
        subject = subjects_by_source[row["source_id"]]
        proof = scope["source_bound_proof"]
        disclosed = None if proof is None else proof["disclosed_period"]
        period = subject["default_fiscal_period"] if disclosed is None else disclosed
        target = {"fiscal_year": int(subject["default_fiscal_period"]["period_label"][2:]),
                  "period_start": period["period_start"], "period_end": period["period_end"]}
        subject_identity = {"fixture_company_authority_id": subjects["authority_id"],
            **{key: subject[key] for key in ("source_id", "company_id", "cik", "profile_id", "company_traits", "profile_authority", "source_binding")},
            "financial_nature_span_binding": None if subject["financial_nature_span"] is None else {
                key: subject["financial_nature_span"][key] for key in ("byte_start", "byte_end", "span_sha256")}}
        eligible.append({**{key: row[key] for key in ("fixture_id", "fixture_class", "metric_id", "source_id", "task_contract_id")},
            "scope_certificate_identity": identity, "risk_features": _risk_features(recipe, scope),
            "fixture_subject_identity": subject_identity, "target_period": target,
            "target_period_identity": {"period_label": scope["task_period"],
                "resolution": "NATIVE_DEFAULT_FISCAL_PERIOD" if disclosed is None else "SOURCE_BOUND_DISCLOSED_PERIOD",
                "source_bound_proof_id": None if disclosed is None else proof["source_bound_proof_id"]}})
        request = {**identity, "reader_payload_sha256": row["files"]["scoped_request.json"]["sha256"],
            "provider_request_body_sha256": sha256_bytes(content=(row["fixture_id"] + ":envelope").encode()),
            "live_scoped_reader_request_id": content_hash(value={"fixture_id": row["fixture_id"], "unit_capture": True}),
            "file_bindings": {}, "source_metadata": {"company_id": subject["company_id"], "cik": subject["cik"]},
            "fixture_company_authority_id": subjects["authority_id"], "target_period": target,
            "target_period_identity": eligible[-1]["target_period_identity"],
            "disclosed_period": None if disclosed is None else {key: disclosed[key] for key in (
                "period_label", "period_start", "period_end", "averaging_period", "must_not_claim_annual_average")}}
        requests[row["fixture_id"]] = SimpleNamespace(identity=request)
    entries, selection = _schedule(eligible)
    schedule = {**{key: requirement[key] for key in authority.IDENTITY_FIELDS if key != "requirement_hashes"},
        "requirement_hashes": requirement["hashes"], "schedule_input_id": content_hash(value={"entries": entries}),
        "fixture_matrix_id": fixtures["matrix_id"], "corpus_binding": {"path": "docs/r4_offline/qualified_cases/index.json", "index_id": index["index_id"]},
        "entries": entries, "zero_call_fixtures": sorted([
            {"fixture_id": row["fixture_id"], "metric_id": row["metric_id"],
             "fixture_class": row["fixture_class"], "artifact_kind": row["artifact_kind"],
             "planned_provider_calls": 0,
             "reason": "STRUCTURED_PRIMARY_RESOLVED" if row["artifact_kind"] == "STRUCTURED_PRIMARY"
             else row["fixture_class"]}
            for row in index["cases"] if row["artifact_kind"] != "SCOPED_EXTRACTION"],
            key=lambda row: row["fixture_id"]),
        "call_bounds": {"target_minimum": 12, "target_maximum": 18, "hard_maximum": 24},
        "counts": {"planned_provider_calls": 12, "base_provider_calls": 9, "stability_provider_calls": 3},
        "stability_selection": selection}
    session = SimpleNamespace(_requirement=requirement, _check=lambda: None, _root=ROOT.resolve())
    return authority.R4ExecutionPlanContext(factory=authority._PLAN_FACTORY, root=ROOT.resolve(),
        session=session, schedule=schedule, requests=requests,
        pointer={"publication_id": "unit:R3", "previous_publication_id": "unit:R2"},
        state=STATE, historical_files={}, historical_proof={"chain": [], "root_mirror_count": 14,
            "verified_files_hash": content_hash(value={})})


def coherent_receipt(plan, requirement):
    text = canonical_json_bytes(value=authority.expected_r4_owner_approval(
        plan=plan, exact_head=STATE["head"], exact_tree=STATE["tree"])).decode()
    return rebind({"record_type": "R4_EXACT_HEAD_LIVE_AUTHORIZATION", "schema_version": 1,
        **{key: plan[key] for key in authority.IDENTITY_FIELDS}, "exact_head": STATE["head"], "exact_tree": STATE["tree"],
        "pending_plan_id": plan["pending_plan_id"], "authorized_entry_ids": [entry["entry_id"] for entry in plan["entries"]],
        "owner": "github:" + requirement["baseline"]["repository"]["identity"].split("/")[0],
        "approved_at_utc": WHEN, "source_url": OWNER_URL, "approval_text": text,
        "approval_text_sha256": sha256_bytes(content=text.encode()), "authorization_scope": "R4_LIVE_QUALIFICATION_ONLY",
        "provider_calls_authorized": True, "paid_model_calls_authorized": True, "sec_calls_authorized": False,
        "automatic_retry_count": 0, "response_reuse_authorized": False}, "receipt_id")


class R4LiveAuthorityShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check_patch = mock.patch.object(authority.R4ExecutionPlanContext, "_check", return_value=None)
        cls.check_patch.start()
        cls.context = private_shape_context()
        cls.recorded = authority.build_r4_recorded_test_plan(context=cls.context)
        cls.pending = authority._build_plan(cls.context, mode="LIVE", state=STATE)

    @classmethod
    def tearDownClass(cls):
        cls.check_patch.stop()

    def test_complete_recorded_plan_is_not_live_authority(self):
        plan = authority.validate_r4_execution_plan(plan=self.recorded, context=self.context,
            expected_plan_id=self.recorded["pending_plan_id"], mode="RECORDED_TEST")
        self.assertEqual(set(plan), authority.PENDING_FIELDS)
        self.assertEqual(plan["record_type"], "R4_RECORDED_TEST_PLAN")
        self.assertEqual(len(plan["entries"]), 12)
        self.assertEqual(len({entry["entry_id"] for entry in plan["entries"]}), 12)
        self.assertEqual(len(plan["zero_call_fixtures"]), 7)
        self.assertFalse(plan["provider_paid_sec_authorized"])
        self.assertEqual(plan["owner_authorization"], "NOT_ISSUED")

    def test_full_plan_relabel_count_request_and_membership_mutations_fail(self):
        changes = []
        for field, value in (("record_type", "R4_PENDING_LIVE_PLAN"), ("execution_mode", "LIVE"),
                             ("provider_paid_sec_authorized", True), ("qualification_credit", "CURRENT")):
            changed = copy.deepcopy(self.recorded)
            changed[field] = value
            changes.append(changed)
        changed = copy.deepcopy(self.recorded)
        changed["counts"]["planned_provider_calls"] = 25
        changes.append(changed)
        changed = copy.deepcopy(self.recorded)
        changed["entries"].pop()
        changes.append(changed)
        changed = copy.deepcopy(self.recorded)
        changed["entries"][0]["fixture_id"] = "r4_zero_negative_expected"
        changes.append(changed)
        changed = copy.deepcopy(self.recorded)
        changed["entries"][0]["request_identity"]["provider_request_body_sha256"] = "f" * 64
        changes.append(changed)
        for changed in changes:
            rebind(changed, "pending_plan_id")
            with self.subTest(plan_id=changed["pending_plan_id"]), self.assertRaises(authority.R4AuthorizationError):
                authority.validate_r4_execution_plan(plan=changed, context=self.context,
                    expected_plan_id=changed["pending_plan_id"], mode="RECORDED_TEST")

    def test_raw_nonempty_owner_strings_and_fully_coherent_receipt_maps_cannot_issue(self):
        receipt = coherent_receipt(self.pending, self.context._session._requirement)
        # Portable replay can validate the content; that does not create a cap.
        authority.validate_r4_live_authorization_receipt(receipt=receipt, plan=self.pending,
            requirement=self.context._session._requirement, exact_head=STATE["head"], exact_tree=STATE["tree"])
        for supplied in ("arbitrary-nonempty-owner", receipt, {"owner": "github:wlvh"}):
            with self.subTest(supplied_type=type(supplied).__name__), self.assertRaises(authority.R4AuthorizationError):
                authority.authorize_r4_live_entry(context=self.context, plan=self.pending,
                    entry_id=self.pending["entries"][0]["entry_id"], owner_receipt=supplied)
        with self.assertRaises(authority.R4AuthorizationError):
            authority.authorization_fields("non-empty-owner")
        with self.assertRaises(authority.R4AuthorizationError):
            authority.VerifiedR4OwnerComment(factory=object(), root=ROOT.resolve(), receipt=receipt, capture={})

    def test_recorded_capability_never_reaches_socket_and_request_drift_fails(self):
        plan = self.recorded
        authorization = authority.authorize_r4_recorded_test_entry(context=self.context, plan=plan,
            entry_id=plan["entries"][0]["entry_id"], authorized_at_utc=WHEN)
        binding = authority.authorization_binding(authorization)
        self.assertEqual(binding["execution_mode"], "RECORDED_TEST")
        with mock.patch("vnext.ai_adapter._DEEPSEEK_OPENER.open", side_effect=AssertionError("NO_SOCKET")) as opener:
            with self.assertRaises(authority.R4AuthorizationError):
                authority.authorization_fields(authorization, for_socket=True)
        opener.assert_not_called()
        changed = dict(binding["request_identity"], provider_request_body_sha256="f" * 64)
        with self.assertRaises(authority.R4AuthorizationError):
            authority.authorization_fields(authorization, request_binding=changed)
        portable = canonical_json_bytes(value=binding).decode()
        self.assertNotIn(str(ROOT), portable)
        self.assertNotIn(str(ROOT.resolve()), portable)
        self.assertFalse(Path(binding["invocation_namespace"]).is_absolute())

    def test_receipt_owner_head_tree_plan_scope_and_body_provenance_fail_rebound(self):
        original = coherent_receipt(self.pending, self.context._session._requirement)
        for field, value in (("owner", "github:intruder"), ("exact_head", "3" * 40),
                             ("exact_tree", "4" * 40), ("pending_plan_id", "sha256:" + "f" * 64),
                             ("source_url", "https://github.com/other/repo/pull/123#issuecomment-456"),
                             ("sec_calls_authorized", True), ("automatic_retry_count", 1),
                             ("response_reuse_authorized", True)):
            receipt = copy.deepcopy(original)
            receipt[field] = value
            rebind(receipt, "receipt_id")
            with self.subTest(field=field), self.assertRaises(authority.R4AuthorizationError):
                authority.validate_r4_live_authorization_receipt(receipt=receipt, plan=self.pending,
                    requirement=self.context._session._requirement, exact_head=STATE["head"], exact_tree=STATE["tree"])
        receipt = copy.deepcopy(original)
        body = json.loads(receipt["approval_text"])
        body["maximum_provider_calls"] = 25
        receipt["approval_text"] = canonical_json_bytes(value=body).decode()
        receipt["approval_text_sha256"] = sha256_bytes(content=receipt["approval_text"].encode())
        rebind(receipt, "receipt_id")
        with self.assertRaises(authority.R4AuthorizationError):
            authority.validate_r4_live_authorization_receipt(receipt=receipt, plan=self.pending,
                requirement=self.context._session._requirement, exact_head=STATE["head"], exact_tree=STATE["tree"])

    def github_values(self):
        text = canonical_json_bytes(value=authority.expected_r4_owner_approval(
            plan=self.pending, exact_head=STATE["head"], exact_tree=STATE["tree"])).decode()
        return ({"id": 456, "html_url": OWNER_URL, "user": {"login": "wlvh"},
            "body": text, "created_at": WHEN, "updated_at": WHEN,
            "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/123"},
            {"number": 123, "html_url": "https://github.com/wlvh/SEC_metrics/pull/123",
             "state": "open", "merged": False,
             "head": {"sha": STATE["head"], "repo": {"full_name": "wlvh/SEC_metrics"}},
             "base": {"ref": "main", "repo": {"full_name": "wlvh/SEC_metrics"}}})

    def capture(self, comment, pull):
        paths = []
        def response(argv, **kwargs):
            self.assertEqual(argv[:4], ["gh", "api", "--hostname", "github.com"])
            paths.append(argv[4])
            value = comment if argv[4].endswith("/issues/comments/456") else pull
            return subprocess.CompletedProcess(argv, 0, json.dumps(value), "")
        with mock.patch.object(authority, "_validate_live_implementation", return_value=STATE), \
                mock.patch.object(authority, "_git_state", return_value=STATE), \
                mock.patch.object(authority.subprocess, "run", side_effect=response):
            captured = authority.verify_r4_live_owner_comment(context=self.context,
                plan=self.pending, source_url=OWNER_URL)
        self.assertEqual(paths, ["repos/wlvh/SEC_metrics/issues/comments/456", "repos/wlvh/SEC_metrics/pulls/123"])
        return captured

    def test_real_preflight_boundary_is_mocked_once_then_socket_check_never_queries_github(self):
        captured = self.capture(*self.github_values())
        self.assertIs(type(captured), authority.VerifiedR4OwnerComment)
        copy_receipt = captured.receipt
        copy_receipt["owner"] = "github:intruder"
        self.assertEqual(captured.receipt["owner"], "github:wlvh")
        with mock.patch.object(authority, "_validate_live_implementation", return_value=STATE), \
                mock.patch.object(authority, "_git_state", return_value=STATE), \
                mock.patch.object(authority.subprocess, "run", side_effect=AssertionError("NO_GITHUB_AT_SOCKET")), \
                mock.patch("vnext.r4_live_qualification.validate_r4_execution_prefix", return_value=None):
            authorization = authority.authorize_r4_live_entry(context=self.context, plan=self.pending,
                entry_id=self.pending["entries"][0]["entry_id"], owner_receipt=captured)
            fields = authority.authorization_fields(authorization, for_socket=True)
        self.assertEqual(fields["execution_mode"], "LIVE")
        self.assertEqual(fields["owner_receipt_id"], captured.receipt["receipt_id"])
        # The check above does not open a socket or execute the plan.

    def test_preflight_rejects_wrong_owner_edited_body_foreign_comment_and_pr_head(self):
        mutations = []
        for field, value in (("html_url", OWNER_URL.replace("/123#", "/999#")),
                             ("user", {"login": "intruder"}),
                             ("updated_at", "2026-09-04T00:00:01Z"),
                             ("body", '{"decision":"APPROVE_REQUIREMENT_TRANSITION"}')):
            comment, pull = self.github_values()
            comment[field] = value
            mutations.append((comment, pull))
        comment, pull = self.github_values()
        pull["head"]["sha"] = "f" * 40
        mutations.append((comment, pull))
        comment, pull = self.github_values()
        pull["head"]["repo"]["full_name"] = "other/repository"
        mutations.append((comment, pull))
        comment, pull = self.github_values()
        pull["state"] = "closed"
        mutations.append((comment, pull))
        for comment, pull in mutations:
            with self.subTest(comment=comment["html_url"], head=pull["head"]["sha"]), self.assertRaises(authority.R4AuthorizationError):
                self.capture(comment, pull)

    def test_portable_binding_is_replay_data_and_cannot_recreate_live_capability(self):
        authorization = authority.authorize_r4_recorded_test_entry(context=self.context,
            plan=self.recorded, entry_id=self.recorded["entries"][0]["entry_id"], authorized_at_utc=WHEN)
        binding = authority.authorization_binding(authorization)
        self.assertEqual(authority.validate_portable_authorization_binding(binding=binding, context=self.context), binding)
        with self.assertRaises(authority.R4AuthorizationError):
            authority.authorization_fields(binding)
        changed = copy.deepcopy(binding)
        changed["execution_mode"] = "LIVE"
        rebind(changed, "authorization_id")
        with self.assertRaises(authority.R4AuthorizationError):
            authority.validate_portable_authorization_binding(binding=changed, context=self.context)

    def test_context_rechecks_historical_bytes_even_when_pointer_is_unchanged(self):
        original = self.context._historical_files
        try:
            self.context._historical_files = canonical_json_bytes(value={
                "outputs/active_publication.json": {"sha256": "f" * 64,
                    "size": (ROOT / "outputs/active_publication.json").stat().st_size}})
            with mock.patch.object(authority, "_pointer", return_value=self.context._pointer), self.assertRaises(ValueError):
                ORIGINAL_CONTEXT_CHECK(self.context)
        finally:
            self.context._historical_files = original
        with mock.patch.object(authority, "_pointer", return_value={"publication_id": "wrong:R2"}), \
                self.assertRaises(authority.R4AuthorizationError):
            ORIGINAL_CONTEXT_CHECK(self.context)

    def test_pending_factory_rejects_context_from_another_repository(self):
        original = self.context._root
        try:
            self.context._root = ROOT.parent
            with mock.patch.object(authority, "_git_state", return_value=STATE), self.assertRaises(authority.R4AuthorizationError):
                authority.build_r4_pending_live_plan(repo_root=ROOT, context=self.context)
        finally:
            self.context._root = original


class R4ImplementationAncestryTest(unittest.TestCase):
    def test_real_ancestor_tree_and_no_production_python_delta_are_required(self):
        plan = {"implementation_head": STATE["head"], "implementation_tree": STATE["tree"]}
        execution = {"head": "3" * 40, "tree": "4" * 40}
        scenarios = [(0, STATE["tree"], 0, "", True),
                     (128, "", 0, "", False),
                     (0, "f" * 40, 0, "", False),
                     (0, STATE["tree"], 1, "", False),
                     (0, STATE["tree"], 0, "scripts/vnext/reader.py\n", False)]
        for tree_rc, tree, ancestor_rc, changed, okay in scenarios:
            def response(argv, **kwargs):
                if argv[1] == "rev-parse":
                    return subprocess.CompletedProcess(argv, tree_rc, tree, "")
                if argv[1] == "merge-base":
                    return subprocess.CompletedProcess(argv, ancestor_rc, "", "")
                return subprocess.CompletedProcess(argv, 0, changed, "")
            with self.subTest(tree_rc=tree_rc, ancestor_rc=ancestor_rc, changed=changed), \
                    mock.patch.object(authority, "_git_state", return_value=execution), \
                    mock.patch.object(authority.subprocess, "run", side_effect=response):
                if okay:
                    self.assertEqual(authority._validate_live_implementation(repo_root=ROOT, plan=plan), execution)
                else:
                    with self.assertRaises(authority.R4AuthorizationError):
                        authority._validate_live_implementation(repo_root=ROOT, plan=plan)


class R4ExecutionPrefixTest(unittest.TestCase):
    """Temporary on-disk prefix mutations; native Run replay is tested separately."""

    def setUp(self):
        from vnext import r4_live_qualification
        self.module = r4_live_qualification
        self.original_structured_terminals = self.module._structured_terminals
        self.structured_patch = mock.patch.object(self.module, "_structured_terminals", return_value=[])
        self.structured_patch.start()
        self.addCleanup(self.structured_patch.stop)
        self.temporary = tempfile.TemporaryDirectory()
        with mock.patch.object(authority.R4ExecutionPlanContext, "_check", return_value=None):
            self.context = private_shape_context()
            self.plan = authority.build_r4_recorded_test_plan(context=self.context)
        self.context._root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def root_for(self, entry):
        return self.module._entry_root(self.context, self.plan, entry["entry_id"])

    def terminal(self, entry, *, status="PASSED", execution_status="SUCCEEDED"):
        root = self.root_for(entry)
        (root / "run").mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path=root / "run/shape.json", content=b'{"unit":"prefix-only"}\n')
        body = {"record_type": "R4_QUALIFICATION_ENTRY_TERMINAL", "schema_version": 1,
            "pending_plan_id": self.plan["pending_plan_id"], "entry_id": entry["entry_id"],
            "ordinal": entry["ordinal"], "fixture_id": entry["fixture_id"], "execution_mode": self.plan["execution_mode"],
            "status": status, "run_id": content_hash(value={"entry": entry["entry_id"]}),
            "run_path": (root / "run").relative_to(self.context._root).as_posix(),
            "run_status": "FROZEN" if status == "PASSED" else "OPEN",
            "execution_receipt_id": content_hash(value={"execution": entry["entry_id"]}),
            "execution_status": execution_status,
            "counters": {"real_model_provider_egress_count": 0, "paid_model_provider_call_count": 0,
                         "mock_transport_invocation_count": 1},
            "qualification_credit": "NONE_INDIVIDUAL_RUN", "publication_credit": "NONE",
            "response_reuse_authorized": False, "files": self.module._tree_files(root)}
        terminal = {**body, "terminal_id": content_hash(value=body)}
        atomic_write_bytes(path=root / "qualification_terminal.json", content=canonical_json_bytes(value=terminal))
        self.context._terminal_pins[entry["entry_id"]] = terminal
        return terminal

    def validate(self, ordinal, *, for_socket=False):
        entry = self.plan["entries"][ordinal - 1]
        return self.module.validate_r4_execution_prefix(context=self.context, plan=self.plan,
            entry_id=entry["entry_id"], for_socket=for_socket)

    def structured_terminal(self, fixture, *, run_status="FROZEN", calls=None):
        """Seal a unit-only terminal to test the prefix, not native Run replay."""
        root = (self.context._root / authority.RUNTIME_ROOT
            / self.plan["pending_plan_id"].split(":")[1] / "structured" / fixture["fixture_id"])
        (root / "run").mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path=root / "run/shape.json", content=b'{"unit":"structured-prefix-only"}\n')
        body = {"record_type": "R4_STRUCTURED_QUALIFICATION_TERMINAL", "schema_version": 1,
            "pending_plan_id": self.plan["pending_plan_id"], "fixture_id": fixture["fixture_id"],
            "run_id": content_hash(value={"structured_fixture": fixture["fixture_id"]}),
            "run_status": run_status, "execution_mode": self.plan["execution_mode"],
            "provider_paid_sec_calls": [0, 0, 0] if calls is None else calls,
            "qualification_credit": "NONE_INDIVIDUAL_RUN", "publication_credit": "NONE",
            "files": self.module._tree_files(root)}
        terminal = {**body, "terminal_id": content_hash(value=body)}
        atomic_write_bytes(path=root / "qualification_terminal.json", content=canonical_json_bytes(value=terminal))
        self.context._terminal_pins["structured:" + fixture["fixture_id"]] = terminal
        return terminal

    def test_missing_or_failed_structured_terminal_blocks_first_scoped_entry(self):
        fixtures = [entry for entry in self.plan["zero_call_fixtures"]
                    if entry["artifact_kind"] == "STRUCTURED_PRIMARY"]
        self.assertEqual(len(fixtures), 3)
        # Unlike the scoped-prefix units, invoke the real structured gate here.
        # Native creation/replay remains the separate full-corpus integration.
        with mock.patch.object(self.module, "_structured_terminals",
                               side_effect=self.original_structured_terminals):
            with self.assertRaisesRegex(self.module.R4QualificationError, "absent or unsafe"):
                self.validate(1)
            for fixture in fixtures:
                self.structured_terminal(fixture)
            self.assertEqual(self.validate(1), {"prior_terminal_count": 0, "entry_ordinal": 1})
            for run_status, calls in (("OPEN", [0, 0, 0]), ("FROZEN", [1, 0, 0])):
                self.structured_terminal(fixtures[0], run_status=run_status, calls=calls)
                with self.subTest(run_status=run_status, calls=calls), self.assertRaisesRegex(
                        self.module.R4QualificationError, "structured native terminal binding/bytes differ"):
                    self.validate(1)
                self.structured_terminal(fixtures[0])

    def test_missing_prior_terminal_and_unknown_or_evidence_failure_block_later_entries(self):
        with self.assertRaises(self.module.R4QualificationError):
            self.validate(2)
        first = self.plan["entries"][0]
        for terminal_status in ("UNKNOWN_REMOTE_OUTCOME", "FAILED_EVIDENCE", "FAILED_RETRYABLE_FINAL"):
            self.terminal(first, status="FAILED", execution_status=terminal_status)
            with self.subTest(terminal_status=terminal_status), self.assertRaises(self.module.R4QualificationError):
                self.validate(2)

    def test_good_prior_is_pinned_and_added_or_mutated_terminal_bytes_fail(self):
        first = self.plan["entries"][0]
        self.terminal(first)
        self.assertEqual(self.validate(2), {"prior_terminal_count": 1, "entry_ordinal": 2})
        atomic_write_bytes(path=self.root_for(first) / "run/unlisted.json", content=b"{}")
        with self.assertRaises(self.module.R4QualificationError):
            self.validate(2)

    def test_nested_terminal_basename_is_not_exempt_from_the_exact_file_set(self):
        first = self.plan["entries"][0]
        self.terminal(first)
        atomic_write_bytes(path=self.root_for(first) / "run/qualification_terminal.json", content=b"{}")
        with self.assertRaises(self.module.R4QualificationError):
            self.validate(2)

    def test_later_or_foreign_namespace_cannot_exist_before_current_entry(self):
        later = self.root_for(self.plan["entries"][1])
        later.mkdir(parents=True)
        atomic_write_bytes(path=later / "marker.json", content=b"{}")
        with self.assertRaises(self.module.R4QualificationError):
            self.validate(1)
        foreign = later.parent / "not-in-plan"
        foreign.mkdir()
        with self.assertRaises(self.module.R4QualificationError):
            self.validate(1)

    def test_socket_needs_one_current_marker_and_no_terminal_or_execution(self):
        root = self.root_for(self.plan["entries"][0])
        with self.assertRaises(self.module.R4QualificationError):
            self.validate(1, for_socket=True)
        marker = root / "invocation_control/egress/one.json"
        marker.parent.mkdir(parents=True)
        atomic_write_bytes(path=marker, content=b"{}")
        self.assertEqual(self.validate(1, for_socket=True)["entry_ordinal"], 1)
        atomic_write_bytes(path=marker.parent / "two.json", content=b"{}")
        with self.assertRaises(self.module.R4QualificationError):
            self.validate(1, for_socket=True)
        execution = root / "invocation_control/executions/terminal.json"
        execution.parent.mkdir(parents=True)
        atomic_write_bytes(path=execution, content=b"{}")
        with self.assertRaises(self.module.R4QualificationError):
            self.validate(1, for_socket=True)


class R4LiveAuthorityRealCorpusIntegrationTest(unittest.TestCase):
    """Run after final Requirement/corpus repin; all work remains read-only."""

    @classmethod
    def setUpClass(cls):
        cls.context = authority.prepare_r4_execution_context(repo_root=ROOT)
        cls.plan = authority.build_r4_recorded_test_plan(context=cls.context)

    def test_actual_nine_captures_produce_twelve_recorded_entries(self):
        self.assertEqual(len(self.context._requests), 9)
        self.assertEqual(len(self.plan["entries"]), 12)
        self.assertEqual(self.plan["active_predecessor"]["immutable_read_back"]["root_mirror_count"], 14)
        self.assertEqual(len(self.plan["active_predecessor"]["immutable_read_back"]["chain"]), 3)
        self.assertEqual(authority.validate_r4_execution_plan(plan=self.plan, context=self.context,
            expected_plan_id=self.plan["pending_plan_id"], mode="RECORDED_TEST"), self.plan)

    def test_real_context_recorded_authorization_has_zero_socket_capability(self):
        authorization = authority.authorize_r4_recorded_test_entry(context=self.context, plan=self.plan,
            entry_id=self.plan["entries"][0]["entry_id"], authorized_at_utc=WHEN)
        with mock.patch("vnext.ai_adapter._DEEPSEEK_OPENER.open", side_effect=AssertionError("NO_SOCKET")) as opener:
            with self.assertRaises(authority.R4AuthorizationError):
                authority.authorization_fields(authorization, for_socket=True)
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
