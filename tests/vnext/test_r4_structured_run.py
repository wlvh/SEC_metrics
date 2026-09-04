"""Explicit structured-primary Run contracts and shared native tamper probes."""

import copy
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_r4_run_store import rebind_native_r4_run_envelope
from vnext.canonical import atomic_write_bytes, atomic_write_json, canonical_json_bytes
from vnext.canonical import content_hash, sha256_bytes, strict_json_file
from vnext.records import EXPLICIT_ARTIFACT_GENERATION, R4_STRUCTURED_ARTIFACT_KINDS
from vnext.records import R4_STRUCTURED_PROTOCOL, R4_STRUCTURED_RUN_TYPE
from vnext.records import RecordError, validate_record
from vnext.requirements import load_requirement_snapshot
from vnext.r4_structured_run import R4StructuredRunContext, R4StructuredRunError
from vnext.r4_structured_run import prepare_r4_structured_run_context


def assert_native_r4_structured_run_tamper_matrix(
    testcase: unittest.TestCase, *, repo_root: Path, run_dir: Path,
    structured_context: object,
) -> list:
    """Use the integrator's real zero-provider Run, never fabricate AI evidence."""
    from vnext.r4_structured_run import replay_r4_structured_run
    mutations = (
        ("structured value", "structured_route", lambda value: value.update(value="999999")),
        ("selected native claim", "structured_route", lambda value: value["selected_claims"][0].update(value="999999")),
        ("native claim dispositions", "structured_route", lambda value: value["claim_dispositions"].pop()),
        ("native fiscal duration", "structured_route", lambda value: value["target_fiscal_period"].update(period_start="2025-02-01")),
        ("native source set", "structured_route", lambda value: value["source_set_manifest"].update(source_set_manifest_id="sha256:" + "0" * 64)),
        ("provider-zero plan", "plan", lambda value: value["zero_call_fixtures"][0].update(planned_provider_calls=1)),
    )
    verified = []
    for label, kind, mutate in mutations:
        with tempfile.TemporaryDirectory(prefix="r4-structured-run-tamper-") as directory:
            copied = Path(directory) / "run"
            shutil.copytree(run_dir, copied)
            manifest = strict_json_file(path=copied / "manifest.json")
            binding = manifest["r4_structured_binding"]
            original_path = copied / binding["artifact_files"][kind]["path"]
            value = strict_json_file(path=original_path)
            mutate(value)
            identity_key = "structured_route_receipt_id" if kind == "structured_route" else "pending_plan_id"
            value[identity_key] = content_hash(value={key: item for key, item in value.items() if key != identity_key})
            data = canonical_json_bytes(value=value)
            digest = sha256_bytes(content=data)
            relative = "r4_structured/{}_{}.json".format(kind, digest)
            binding["artifact_hashes"][kind + "_hash"] = "sha256:" + digest
            binding["artifact_files"][kind] = {"path": relative, "sha256": digest, "size": len(data)}
            atomic_write_bytes(path=copied / relative, content=data)
            if original_path != copied / relative:
                original_path.unlink()
            atomic_write_json(path=copied / "manifest.json", value=manifest)
            rebind_native_r4_run_envelope(copied)
            with testcase.subTest(mutation=label), testcase.assertRaises((ValueError, RuntimeError)):
                replay_r4_structured_run(repo_root=repo_root, run_dir=copied,
                                         structured_context=structured_context)
            verified.append(label)
    return verified


class R4StructuredRunSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_28_v1")
        path = next(iter(sorted((REPO_ROOT / "artifacts/vnext/qualification/cycles").rglob("manifest.json"))))
        base = strict_json_file(path=path)
        base.pop("qualification_authorization", None)
        files, hashes = {}, {}
        for kind in R4_STRUCTURED_ARTIFACT_KINDS:
            data = canonical_json_bytes(value={"record_type": "SCHEMA_ONLY", "kind": kind})
            digest = sha256_bytes(content=data)
            files[kind] = {"path": "r4_structured/{}_{}.json".format(kind, digest),
                           "sha256": digest, "size": len(data)}
            hashes[kind + "_hash"] = "sha256:" + digest
        cls.manifest = {**base, "record_type": R4_STRUCTURED_RUN_TYPE,
            "artifact_requirement_generation": EXPLICIT_ARTIFACT_GENERATION,
            "requirement_id": requirement["requirement_id"],
            "requirement_closure_hash": requirement["requirement_closure_hash"],
            "requirement_hashes": requirement["hashes"],
            "r4_structured_binding": {"protocol": R4_STRUCTURED_PROTOCOL,
                "fixture_id": "schema_structured_fixture", "source_id": "schema_structured_source",
                "artifact_hashes": hashes, "artifact_files": files,
                "fixture_company_authority_id": "sha256:" + "a" * 64,
                "execution_mode": "RECORDED_TEST", "qualification_credit": "NONE_INDIVIDUAL_RUN",
                "publication_credit": "NONE", "provider_paid_sec_calls": [0, 0, 0]}}

    def test_full_record_has_explicit_generation_and_no_provider_artifact(self):
        record = validate_record(record=self.manifest)
        self.assertEqual(record["record_type"], R4_STRUCTURED_RUN_TYPE)
        self.assertNotIn("r4_execution_binding", record)
        self.assertNotIn("qualification_authorization", record)
        for field in ("artifact_requirement_generation", "requirement_id", "requirement_closure_hash",
                      "requirement_hashes", "r4_structured_binding", "task_contract_bindings"):
            changed = copy.deepcopy(record)
            changed.pop(field)
            with self.subTest(field=field), self.assertRaises(RecordError):
                validate_record(record=changed)

    def test_call_credit_or_mixed_protocol_cannot_be_rebound_into_structured_run(self):
        for field, value in (("provider_paid_sec_calls", [1, 0, 0]),
                             ("qualification_credit", "CURRENT"),
                             ("publication_credit", "PUBLISHABLE"),
                             ("protocol", "R4_SCOPED_TRANSPORT_V1")):
            changed = copy.deepcopy(self.manifest)
            changed["r4_structured_binding"][field] = value
            with self.subTest(field=field), self.assertRaises(RecordError):
                validate_record(record=changed)
        changed = copy.deepcopy(self.manifest)
        changed["qualification_authorization"] = {}
        with self.assertRaises(RecordError):
            validate_record(record=changed)

    def test_context_cannot_be_a_caller_authored_verified_dictionary(self):
        with self.assertRaises(R4StructuredRunError):
            R4StructuredRunContext(factory=object(), execution=object(), plan={}, fixture_id="forged")
        with self.assertRaises(R4StructuredRunError):
            prepare_r4_structured_run_context(repo_root=REPO_ROOT, fixture_id="forged",
                                              plan={}, execution_context={"verified": True})


if __name__ == "__main__":
    unittest.main()
