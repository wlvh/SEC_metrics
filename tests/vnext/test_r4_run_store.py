"""R4 successor Run identities, fixture subjects and native review authority.

The shape tests do not claim execution credit.  The integration tests below
copy actual immutable source/authority inputs before performing rebound
mutations; the source checkout is never edited.
"""

from __future__ import annotations

import copy
import csv
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.canonical import atomic_write_bytes, atomic_write_json, canonical_json_bytes, content_hash
from vnext.canonical import sha256_bytes, sha256_file, strict_json_file
from vnext.records import EXPLICIT_ARTIFACT_GENERATION, R4_EXECUTION_ARTIFACT_KINDS
from vnext.records import R4_SCOPED_ATTEMPT_TYPE, R4_SCOPED_PROTOCOL, R4_SCOPED_RUN_TYPE
from vnext.records import SOURCE_BOUND_CANDIDATE_FIELDS, SOURCE_BOUND_CANDIDATE_TYPE
from vnext.records import RecordError, validate_record
from vnext.requirements import load_requirement_snapshot
from vnext.review import inherited_optional_review_policy, system_review_allowed
from vnext.r4_run_store import COMPANY_AUTHORITY_PATH, R4RunStoreError
from vnext.r4_run_store import _artifact_closure, _successor_attempt
from vnext.r4_run_store import load_r4_fixture_company_authority
from vnext.r4_run_store import resolve_r4_run_target_period


def rebind_native_r4_run_envelope(run_dir: Path) -> None:
    """Re-sign only a copied untrusted Run envelope to reach semantic gates."""
    from vnext.run_store import _read_jsonl, _run_content_and_audit_hashes
    from vnext.run_store import _run_validation_artifacts, _run_validation_view_id
    manifest = strict_json_file(path=run_dir / "manifest.json")
    records = _read_jsonl(path=run_dir / "records.jsonl")
    decisions = _read_jsonl(path=run_dir / "review_decisions.jsonl")
    validation = strict_json_file(path=run_dir / "validation.json")
    validation_body = {
        "status": validation["status"],
        "view_id": _run_validation_view_id(manifest=manifest),
        "checks": validation["checks"],
        "artifact_hashes": _run_validation_artifacts(run_dir=run_dir),
    }
    validation = {
        **validation_body, "record_type": "VALIDATION_RECEIPT",
        "validation_receipt_id": content_hash(value=validation_body),
    }
    atomic_write_json(path=run_dir / "validation.json", value=validation)
    content, audit = _run_content_and_audit_hashes(
        manifest=manifest, records=records, decisions=decisions,
        validation=validation,
    )
    manifest.update(
        records_file_hash=sha256_file(path=run_dir / "records.jsonl"),
        review_decisions_file_hash=sha256_file(path=run_dir / "review_decisions.jsonl"),
        validation_file_hash=sha256_file(path=run_dir / "validation.json"),
        content_manifest_hash=content, audit_manifest_hash=audit,
    )
    atomic_write_json(path=run_dir / "manifest.json", value=manifest)


def rewrite_native_r4_execution_artifact(run_dir: Path, kind: str, mutate) -> None:
    """Mutate a complete copied artifact and rebind every outer Run pointer."""
    import json
    manifest = strict_json_file(path=run_dir / "manifest.json")
    bound = manifest["r4_execution_binding"]
    old_path = run_dir / bound["artifact_files"][kind]["path"]
    value = strict_json_file(path=old_path)
    mutate(value)
    id_field = {
        "request_record": "executed_scoped_request_id",
        "authorization_binding": "authorization_id",
        "terminal_bundle": "terminal_bundle_id",
        "execution_receipt": "execution_receipt_id",
    }.get(kind)
    if id_field is not None:
        value[id_field] = content_hash(value={k: v for k, v in value.items() if k != id_field})
    data = canonical_json_bytes(value=value)
    digest = sha256_bytes(content=data)
    relative = "r4_execution/{}_{}.json".format(kind, digest)
    bound["artifact_files"][kind] = {"path": relative, "sha256": digest, "size": len(data)}
    bound["identity_hashes"][kind + "_hash"] = "sha256:" + digest
    atomic_write_bytes(path=run_dir / relative, content=data)
    if old_path != run_dir / relative:
        old_path.unlink()
    records = [json.loads(line) for line in (run_dir / "records.jsonl").read_text().splitlines()]
    for record in records:
        if record["record_type"] == R4_SCOPED_ATTEMPT_TYPE:
            record["r4_binding"] = copy.deepcopy(bound["identity_hashes"])
    atomic_write_bytes(path=run_dir / "records.jsonl", content=b"".join(
        canonical_json_bytes(value=record) for record in records
    ))
    atomic_write_json(path=run_dir / "manifest.json", value=manifest)
    rebind_native_r4_run_envelope(run_dir)


def assert_native_r4_run_tamper_matrix(
    testcase: unittest.TestCase, *, repo_root: Path, run_dir: Path,
    acceptance_context: object,
) -> list:
    """Consume the root integration's real Run; never generate a second cycle.

    Each negative copies the entire native persisted Run, mutates a security
    identity and rebinds the Run's outer file/view/content/audit envelope.  The
    same native disk loader must still reject it against repository authority.
    """
    from vnext.r4_run_store import replay_r4_scoped_run
    mutations = (
        ("request source SHA", "request_record", lambda value: value.update(source_sha256="0" * 64)),
        ("request task identity", "request_record", lambda value: value.update(task_contract_id="r4_forbidden_future_task_v2")),
        ("request Spec identity", "request_record", lambda value: value.update(task_spec_semantic_hash="sha256:" + "1" * 64)),
        ("request full asset identity", "request_record", lambda value: value.update(full_derived_asset_id="sha256:" + "2" * 64)),
        ("request source proof", "request_record", lambda value: value.update(source_bound_proof_id="sha256:" + "3" * 64)),
        ("request window order", "request_record", lambda value: value["window_binding"]["ordered_table_orders"].__setitem__(0, value["window_binding"]["ordered_table_orders"][0] + 1)),
        ("authorization closure", "authorization_binding", lambda value: value.update(requirement_closure_hash="sha256:" + "4" * 64)),
        ("authorization quarter period", "request_record", lambda value: value["target_period"].update(period_start="2025-02-01")),
        ("terminal marker transport", "terminal_bundle", lambda value: value["egress_markers"][0].update(transport_kind="REAL_MODEL_PROVIDER")),
        ("terminal usage", "execution_receipt", lambda value: value["attempts"][0]["usage"].update(input_tokens=value["attempts"][0]["usage"]["input_tokens"] + 1)),
    )
    verified = []
    for label, kind, mutate in mutations:
        with tempfile.TemporaryDirectory(prefix="r4-native-run-tamper-") as directory:
            copied = Path(directory) / "run"
            shutil.copytree(run_dir, copied)
            original = (copied / "manifest.json").read_bytes()
            rewrite_native_r4_execution_artifact(copied, kind, mutate)
            if (copied / "manifest.json").read_bytes() == original:
                raise AssertionError("Tamper mutation changed no bytes: " + label)
            with testcase.subTest(mutation=label), testcase.assertRaises((ValueError, RuntimeError)):
                replay_r4_scoped_run(
                    repo_root=repo_root, run_dir=copied,
                    acceptance_context=acceptance_context,
                )
            verified.append(label)
    with tempfile.TemporaryDirectory(prefix="r4-native-locator-tamper-") as directory:
        import json
        copied = Path(directory) / "run"
        shutil.copytree(run_dir, copied)
        records = [json.loads(line) for line in (copied / "records.jsonl").read_text().splitlines()]
        candidate = next(record for record in records if record["record_type"] in {
            "OBSERVATION_CANDIDATE", SOURCE_BOUND_CANDIDATE_TYPE,
        })
        locator = next(iter(candidate["selected"].values()))["locator"]
        locator["row_index"] += 1
        locator["origin_row_index"] += 1
        body = {key: candidate[key] for key in (
            "disclosure_group", "source_reference_ids", "derived_asset_ids", "selected",
            "competing_candidates", "unresolved_competing_claims",
        )}
        if candidate["record_type"] == SOURCE_BOUND_CANDIDATE_TYPE:
            candidate["native_candidate_hash"] = content_hash(value=body)
            body.update({key: candidate[key] for key in SOURCE_BOUND_CANDIDATE_FIELDS})
        candidate["candidate_hash"] = content_hash(value=body)
        atomic_write_bytes(path=copied / "records.jsonl", content=b"".join(
            canonical_json_bytes(value=record) for record in records
        ))
        rebind_native_r4_run_envelope(copied)
        with testcase.subTest(mutation="native Candidate locator"), testcase.assertRaises((ValueError, RuntimeError)):
            replay_r4_scoped_run(repo_root=repo_root, run_dir=copied,
                                 acceptance_context=acceptance_context)
        verified.append("native Candidate locator")
    with tempfile.TemporaryDirectory(prefix="r4-native-time-tamper-") as directory:
        import json
        from datetime import timedelta
        from vnext.canonical import parse_utc_timestamp
        copied = Path(directory) / "run"
        shutil.copytree(run_dir, copied)
        records = [json.loads(line) for line in (copied / "records.jsonl").read_text().splitlines()]
        attempt = next(record for record in records if record["record_type"] == R4_SCOPED_ATTEMPT_TYPE)
        attempt["started_at_utc"] = (parse_utc_timestamp(value=attempt["started_at_utc"])
            - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        atomic_write_bytes(path=copied / "records.jsonl", content=b"".join(
            canonical_json_bytes(value=record) for record in records
        ))
        rebind_native_r4_run_envelope(copied)
        with testcase.subTest(mutation="original marker timestamp"), testcase.assertRaises((ValueError, RuntimeError)):
            replay_r4_scoped_run(repo_root=repo_root, run_dir=copied,
                                 acceptance_context=acceptance_context)
        verified.append("original marker timestamp")
    return verified


def _rebind_company_authority(root: Path, value: dict) -> None:
    value["authority_id"] = content_hash(
        value={key: item for key, item in value.items() if key != "authority_id"}
    )
    atomic_write_json(path=root / COMPANY_AUTHORITY_PATH, value=value)


def copy_fixture_company_inputs(root: Path) -> None:
    """Copy exact native subject inputs, not a mocked source or inferred trait."""
    for relative in ("config", "catalog", "docs/evidence",
                     "tests/fixtures/vnext/r4_offline/inputs"):
        shutil.copytree(REPO_ROOT / relative, root / relative)
    paths = {
        "docs/r4_offline/fixture_acquisition_receipt.json",
        "evidence/requests_log.csv", "evidence/requests_log_manifest.json",
    }
    authority = strict_json_file(path=REPO_ROOT / COMPANY_AUTHORITY_PATH)
    matrix = strict_json_file(path=REPO_ROOT / "config/r4_fixture_matrix_v1.json")
    selected = {entry["source_id"] for entry in authority["entries"]}
    sources = [source for source in matrix["sources"] if source["source_id"] in selected]
    source_hashes = {source["source_sha256"] for source in sources}
    paths.update(source["source_repo_relative_path"] for source in sources)
    for source in sources:
        structured = source["structured_source_authority"]
        if structured is not None:
            paths.add(structured["accession_xbrl"]["path"])
    with (REPO_ROOT / "evidence/requests_log.csv").open(
        mode="r", encoding="utf-8", newline="",
    ) as file_obj:
        for row in csv.DictReader(file_obj):
            if row["content_sha256"] in source_hashes:
                paths.add(row["repo_relative_path"])
                paths.add(row["headers_repo_relative_path"])
    for relative in sorted(paths):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, destination)


class R4RunSchemaTest(unittest.TestCase):
    """Full native records exercise schema dispatch, not a helper dictionary."""

    @classmethod
    def setUpClass(cls):
        cls.requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/issue_28_v1",
        )
        native = None
        for path in sorted((REPO_ROOT / "artifacts/vnext/qualification/cycles").rglob("records.jsonl")):
            import json
            records = [json.loads(line) for line in path.read_text().splitlines()]
            matches = [record for record in records
                       if record["record_type"] == "AI_EXTRACTION_ATTEMPT"
                       and record.get("task_contract_id")]
            if matches:
                native = copy.deepcopy(matches[0])
                cls.native_manifest = strict_json_file(path=path.parent / "manifest.json")
                break
        if native is None:
            raise AssertionError("Main's historical native attempt fixture is absent")
        native.pop("qualification_authorization", None)
        hashes, files = _artifact_closure(values={
            kind: {"record_type": "SCHEMA_TEST_ONLY", "kind": kind}
            for kind in R4_EXECUTION_ARTIFACT_KINDS
        })
        cls.identities = {"protocol": R4_SCOPED_PROTOCOL, **hashes}
        cls.files = files
        cls.attempt = _successor_attempt(
            native=native, requirement=cls.requirement,
            identity_hashes=cls.identities,
        )
        cls.manifest = {
            **copy.deepcopy(cls.native_manifest),
            "record_type": R4_SCOPED_RUN_TYPE,
            "artifact_requirement_generation": EXPLICIT_ARTIFACT_GENERATION,
            "requirement_id": cls.requirement["requirement_id"],
            "requirement_closure_hash": cls.requirement["requirement_closure_hash"],
            "requirement_hashes": cls.requirement["hashes"],
            "r4_execution_binding": {
                "protocol": R4_SCOPED_PROTOCOL,
                "identity_hashes": cls.identities,
                "artifact_files": cls.files,
                "qualification_credit": "NONE_INDIVIDUAL_RUN",
            },
        }
        cls.manifest.pop("qualification_authorization", None)

    def test_full_native_artifact_subtypes_require_the_complete_identity(self):
        self.assertEqual(validate_record(record=self.attempt)["record_type"], R4_SCOPED_ATTEMPT_TYPE)
        self.assertEqual(validate_record(record=self.manifest)["record_type"], R4_SCOPED_RUN_TYPE)
        fields = ("artifact_requirement_generation", "requirement_id",
                  "requirement_closure_hash", "requirement_hashes")
        for original in (self.attempt, self.manifest):
            for removed in ((fields[0],), (fields[1], fields[2]), fields):
                changed = copy.deepcopy(original)
                for field in removed:
                    changed.pop(field)
                with self.subTest(kind=original["record_type"], removed=removed), self.assertRaises(RecordError):
                    validate_record(record=changed)

    def test_six_execution_artifacts_and_no_legacy_qualification_are_required(self):
        for original, binding_key in ((self.attempt, "r4_binding"), (self.manifest, "r4_execution_binding")):
            changed = copy.deepcopy(original)
            identity = changed[binding_key] if binding_key == "r4_binding" else changed[binding_key]["identity_hashes"]
            identity.pop("terminal_bundle_hash")
            with self.assertRaises(RecordError):
                validate_record(record=changed)
            changed = copy.deepcopy(original)
            changed["qualification_authorization"] = {"legacy": "cannot be inherited"}
            with self.assertRaises(RecordError):
                validate_record(record=changed)

    def test_forged_requirement_hashes_and_artifact_file_path_are_rejected(self):
        changed = copy.deepcopy(self.attempt)
        changed["requirement_hashes"] = {"bogus": "nonempty"}
        with self.assertRaises(RecordError):
            validate_record(record=changed)
        changed = copy.deepcopy(self.manifest)
        changed["r4_execution_binding"]["artifact_files"]["terminal_bundle"]["path"] = "../terminal.json"
        with self.assertRaises(RecordError):
            validate_record(record=changed)


class R4InheritedReviewPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requirement = load_requirement_snapshot(
            snapshot_dir=REPO_ROOT / "requirements/issue_28_v2",
        )

    def test_legacy_and_each_successor_retain_the_exact_seven_d06_obligations(self):
        requirement = self.requirement
        while requirement is not None:
            self.assertTrue(system_review_allowed(requirement=requirement))
            self.assertEqual(len(inherited_optional_review_policy(requirement=requirement)), 7)
            requirement = requirement.get("parent_snapshot")

    def test_parent_presence_alone_or_partial_forged_carry_forward_is_insufficient(self):
        changes = []
        changed = copy.deepcopy(self.requirement)
        del changed["effective_decisions"]["S-INHERITED-SEMANTICS"]
        changes.append(changed)
        changed = copy.deepcopy(self.requirement)
        changed["effective_decisions"]["S-INHERITED-SEMANTICS"]["status"] = "REJECTED"
        changes.append(changed)
        for operation in ("remove", "duplicate", "hash"):
            changed = copy.deepcopy(self.requirement)
            rows = changed["effective_decisions"]["S-INHERITED-SEMANTICS"]["choice"]["obligations"]
            row = next(row for row in rows if row["decision_id"] == "D-06")
            if operation == "remove":
                rows.remove(row)
            elif operation == "duplicate":
                rows.append(copy.deepcopy(row))
            else:
                row["source_value_hash"] = "sha256:" + "0" * 64
            changes.append(changed)
        changed = copy.deepcopy(self.requirement)
        changed.pop("parent_snapshot")
        changes.append(changed)
        for changed in changes:
            with self.subTest(choice=changed["effective_decisions"].get("S-INHERITED-SEMANTICS")):
                self.assertFalse(system_review_allowed(requirement=changed))


class R4FixtureCompanyAuthorityIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="r4-company-authority-")
        cls.root = Path(cls.temporary.name) / "repo"
        copy_fixture_company_inputs(cls.root)
        cls.original = strict_json_file(path=cls.root / COMPANY_AUTHORITY_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def tearDown(self):
        atomic_write_json(path=self.root / COMPANY_AUTHORITY_PATH, value=self.original)

    def test_real_native_source_registry_and_owner_proofs_bind_all_three_subjects(self):
        result = load_r4_fixture_company_authority(repo_root=self.root)
        self.assertEqual(set(result["entries"]), {
            "jpmorgan_fy2025_10k", "bank_of_america_fy2025_10k", "citigroup_fy2025_10k",
        })
        self.assertEqual(result["authority_id"], self.original["authority_id"])
        for entry in result["entries"].values():
            self.assertEqual(entry["company_traits"], ["financial"])
            self.assertEqual(entry["default_fiscal_period"]["authority"], "NATIVE_SOURCE_BOUND_DEI_FISCAL_CONTEXT")

    def test_rebound_traits_cik_period_and_exact_span_mutations_fail(self):
        mutations = (
            lambda row: row.update(company_traits=["non_financial"]),
            lambda row: row.update(cik="1"),
            lambda row: row["default_fiscal_period"].update(period_start="2025-02-01"),
            lambda row: row["source_binding"].update(sha256="0" * 64),
            lambda row: row["financial_nature_span"].update(byte_start=row["financial_nature_span"]["byte_start"] + 1),
        )
        for mutate in mutations:
            changed = copy.deepcopy(self.original)
            mutate(changed["entries"][1])
            _rebind_company_authority(self.root, changed)
            with self.assertRaises((R4RunStoreError, ValueError)):
                load_r4_fixture_company_authority(repo_root=self.root)

    def test_owner_source_pointer_cannot_be_rebound_to_unrelated_policy_content(self):
        changed = copy.deepcopy(self.original)
        changed["owner_source_designation"]["json_pointer"] = "/a12_scope_policy"
        _rebind_company_authority(self.root, changed)
        with self.assertRaises(R4RunStoreError):
            load_r4_fixture_company_authority(repo_root=self.root)

    def test_source_byte_change_and_symlink_fail_before_subject_credit(self):
        source = self.root / self.original["entries"][1]["source_binding"]["path"]
        original = source.read_bytes()
        try:
            atomic_write_bytes(path=source, content=original + b" ")
            with self.assertRaises(R4RunStoreError):
                load_r4_fixture_company_authority(repo_root=self.root)
        finally:
            atomic_write_bytes(path=source, content=original)
        authority = self.root / COMPANY_AUTHORITY_PATH
        held = authority.with_name("held-company-authority.json")
        authority.rename(held)
        try:
            authority.symlink_to(held.name)
            with self.assertRaises(ValueError):
                load_r4_fixture_company_authority(repo_root=self.root)
        finally:
            authority.unlink()
            held.rename(authority)

    def test_quarter_period_keeps_native_run_shape_and_never_claims_annual_average(self):
        subject = copy.deepcopy(self.original["entries"][2])
        request = {
            "task_period": "2025Q4", "source_bound_proof_id": "sha256:" + "a" * 64,
            "disclosed_period": {
                "period_label": "2025Q4", "period_start": "2025-10-01", "period_end": "2025-12-31",
                "averaging_period": "AS_DISCLOSED_QUARTER_AVERAGE",
                "must_not_claim_annual_average": True,
            },
        }
        self.assertEqual(resolve_r4_run_target_period(request_record=request, fixture_company=subject), {
            "fiscal_year": 2025, "period_start": "2025-10-01", "period_end": "2025-12-31",
        })
        request["disclosed_period"]["must_not_claim_annual_average"] = False
        with self.assertRaises(R4RunStoreError):
            resolve_r4_run_target_period(request_record=request, fixture_company=subject)


if __name__ == "__main__":
    unittest.main()
