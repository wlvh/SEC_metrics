"""Complete source-bound successor artifacts and immutable session negatives."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import cell_locator
from tests.vnext.r4_b0_fixture_support import REPO_ROOT, b0_fixture
from vnext.canonical import canonical_json_bytes, content_hash
from vnext.composite_scope import CompositeScopeError, build_source_bound_proof
from vnext.composite_scope import index_source_structure, validate_source_bound_proof
from vnext.evidence import EvidenceError, check_evidence, check_evidence_in_offline_session
from vnext.evidence import prepare_offline_evidence_context
from vnext.reader import validate_reader_output, validate_source_bound_reader_output
from vnext.r4_task_contracts import resolve_r4_task_contract
from vnext.records import SOURCE_BOUND_CANDIDATE_TYPE, validate_record
from vnext.reader_input import build_reader_input_manifest, build_reader_payload
from vnext.requirements import load_requirement_snapshot
from vnext.scoped_reader import prepare_scoped_reader_request, validate_scoped_reader_response
from vnext.scoped_reader import replay_scoped_offline_attempt
from vnext.source_scope import build_source_scope_manifest, validate_source_scope_manifest
from vnext.sources import raw_blob_record, source_reference_record
from vnext.table_grid import build_table_grid


SYNTHETIC_SOURCE = b"""<html><body>
<h1>Market Risk Management</h1><h2>Value-at-risk</h2>
<p>Trading VaR uses a one-day holding period and a 95% confidence level.</p>
<p>Regulatory VaR uses 99% confidence and ten days.</p>
<p>The table below reports Trading VaR.</p>
<table><tr><td>(in millions)</td><td>2025</td></tr>
<tr><td>Total VaR</td><td>40</td></tr></table>
<h2>Backtesting</h2><h1>Credit Risk Management</h1>
</body></html>"""


class CompositeScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This is the actual versioned snapshot, not a helper policy dict.
        cls.requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_28_v2")

    def _fixture(self, directory, *, source_bytes=SYNTHETIC_SOURCE,
                 task_id="r4_value_at_risk_table_v2", target=(1, 1), unit=(0, 0),
                 composite=True, scope_labels=None):
        path = directory / "source.html"
        path.write_bytes(source_bytes)
        raw = raw_blob_record(repo_root=REPO_ROOT, repo_relative_path=path.relative_to(REPO_ROOT).as_posix(), media_type="text/html")
        source = source_reference_record(raw_blob=raw, company_id="synthetic_r4_issuer",
            source_url="https://www.sec.gov/Archives/edgar/data/123/000000012326000001/test.htm",
            accession="0000000123-26-000001", document_name="test.htm", source_role="target_primary",
            request_attempt_id="sha256:" + "e" * 64)
        asset = build_table_grid(html_bytes=source_bytes, parent_raw_asset_ids=[raw["raw_asset_id"]], storage_uri="offline://synthetic-full-grid")
        task = resolve_r4_task_contract(repo_root=REPO_ROOT, requirement=self.requirement, task_contract_id=task_id)
        locator = cell_locator(asset=asset, table_id="table_000001", row_index=target[0], column_index=target[1])
        unit_locator = cell_locator(asset=asset, table_id="table_000001", row_index=unit[0], column_index=unit[1])
        manifest = build_reader_input_manifest(derived_asset=asset, source_reference_ids=[source["source_reference_id"]])
        payload = build_reader_payload(manifest=manifest, derived_asset=asset, task_contract=task)
        recipe = None
        if composite:
            blocks = index_source_structure(source_bytes=source_bytes)["blocks"]
            def block(text):
                item = next(b for b in blocks if b["visible_text"] == text)
                return {k: item[k] for k in ("start_byte", "end_byte")}
            selected = block("Trading VaR uses a one-day holding period and a 95% confidence level.")
            recipe = {
                "section_heading": block("Market Risk Management"),
                "section_end_heading": block("Credit Risk Management"),
                "association_heading": block("Value-at-risk"),
                "association_end_heading": block("Backtesting"),
                "target_measure_name": "Trading VaR",
                "table_association_span": block("The table below reports Trading VaR."),
                "selected_scope_spans": [
                    {"dimension": "confidence_level", "raw_value": "95%", **selected},
                    {"dimension": "holding_period", "raw_value": "one-day", **selected}],
            }
        authority = {"requirement": self.requirement, "repo_root": REPO_ROOT, "source_bytes": source_bytes,
                     "raw_blob": raw, "source_reference": source, "full_derived_asset": asset, "task_contract": task}
        proof = build_source_bound_proof(target_locator=locator, numeric_locator=unit_locator,
                                         composite_scope_recipe=recipe, **authority)
        labels, claims = [], []
        for dimension, value, row, column in scope_labels or []:
            label_locator = cell_locator(asset=asset, table_id="table_000001", row_index=row, column_index=column)
            cell = asset["tables"][0]["rows"][row]["cells"][column]
            label_id = "scope:" + dimension
            labels.append({"id": label_id, "location_type": "label", "raw_text": cell["raw_text"],
                           "supports_dimensions": [dimension], "locator": label_locator})
            claims.append({"dimension": dimension, "raw_value": value, "evidence_locator_ids": [label_id]})
        response = {"disclosure_group": task["disclosure_group"],
            "table_locator": {"derived_asset_id": asset["derived_asset_id"], "table_id": "table_000001"},
            "candidates": [{"role": task["required_roles"][0], "claimed_period": "FY2025",
                "claimed_raw_value": asset["tables"][0]["rows"][target[0]]["cells"][target[1]]["text"],
                "claimed_reported_unit": proof["numeric_normalization"]["reported_unit"],
                "claimed_scope": claims, "locator": locator, "scope_evidence_locators": labels,
                "competing_candidates": []}], "unresolved_competing_claims": []}
        response_text = json.dumps(response)
        candidate = validate_source_bound_reader_output(response_text=response_text, attempt_id="attempt:composite:synthetic",
            source_bound_proof=proof, expected_proof_id=proof["source_bound_proof_id"], **authority)
        context = {"proof": proof, "expected_proof_id": proof["source_bound_proof_id"],
            "requirement": self.requirement, "repo_root": REPO_ROOT, "source_bytes": source_bytes,
            "raw_blob": raw, "task_contract": task}
        evidence_args = {"candidate": candidate, "derived_asset": asset, "reader_manifest": manifest,
            "reader_payload_body": payload["body"], "source_references": [source],
            "identity_constraints": task["identity_constraints"], "scope_contract": task["scope_contract"],
            "source_bound_context": context}
        evidence = check_evidence(**evidence_args)
        return {"authority": authority, "proof": proof, "candidate": candidate, "evidence": evidence,
                "evidence_args": evidence_args, "manifest": manifest, "payload": payload,
                "response": response, "response_text": response_text, "path": path}

    def test_full_a12_proof_uses_existing_evidence_and_preserves_source_bytes(self):
        with tempfile.TemporaryDirectory(prefix="r4-composite-", dir=REPO_ROOT) as tmp:
            f = self._fixture(Path(tmp))
            self.assertEqual(SYNTHETIC_SOURCE, f["path"].read_bytes())
            self.assertEqual(SOURCE_BOUND_CANDIDATE_TYPE, f["candidate"]["record_type"])
            self.assertEqual("PASS", f["evidence"]["status"])
            self.assertTrue(f["evidence"]["system_approval_eligible"])
            self.assertEqual(["40000000"], list(f["evidence"]["normalized_values"].values()))
            self.assertEqual({"confidence_level": "ninety_five_percent", "holding_period": "one_day"},
                             f["evidence"]["normalized_scope"])
            self.assertIn("DIFFERENT_DECLARED_MEASURE", [r["disposition"] for r in f["proof"]["composite_scope"]["competing_scope_span_census"]])
            self.assertEqual(f["proof"], validate_source_bound_proof(proof=f["proof"],
                expected_proof_id=f["proof"]["source_bound_proof_id"], **f["authority"]))

    def test_rebound_span_census_scale_and_requirement_tampers_fail(self):
        with tempfile.TemporaryDirectory(prefix="r4-composite-tamper-", dir=REPO_ROOT) as tmp:
            f = self._fixture(Path(tmp))
            mutations = [
                lambda p: p.__setitem__("source_sha256", "0" * 64),
                lambda p: p["source_reference"].__setitem__("accession", "0000000123-26-000002"),
                lambda p: p["numeric_normalization"].__setitem__("factor", "1000000000"),
                lambda p: p["numeric_normalization"].__setitem__("reported_unit", "USD million"),
                lambda p: p["composite_scope"]["selected_scope_spans"][0]["source_span"].__setitem__("exact_source_utf8", "fabricated"),
                lambda p: p["composite_scope"]["competing_scope_span_census"].pop(),
                lambda p: p["composite_scope"]["recipe"].__setitem__("target_measure_name", "Regulatory VaR"),
                lambda p: p["composite_scope"]["recipe"]["selected_scope_spans"][0].__setitem__("start_byte", 1),
                lambda p: p.__setitem__("requirement_hashes", {}),
                lambda p: p.__setitem__("artifact_requirement_generation", "LEGACY"),
            ]
            for mutation in mutations:
                altered = copy.deepcopy(f["proof"])
                mutation(altered)
                altered["source_bound_proof_id"] = content_hash(value={k: v for k, v in altered.items() if k != "source_bound_proof_id"})
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    validate_source_bound_proof(proof=altered, expected_proof_id=altered["source_bound_proof_id"], **f["authority"])

    def test_actual_same_measure_conflict_cannot_be_dispositioned_away(self):
        conflicting = SYNTHETIC_SOURCE.replace(b"Regulatory VaR uses 99%", b"Trading VaR uses 99%")
        with tempfile.TemporaryDirectory(prefix="r4-composite-conflict-", dir=REPO_ROOT) as tmp:
            with self.assertRaisesRegex(CompositeScopeError, "Conflicting"):
                self._fixture(Path(tmp), source_bytes=conflicting)

    def test_source_bound_candidate_requires_context_and_cannot_downgrade(self):
        with tempfile.TemporaryDirectory(prefix="r4-composite-subtype-", dir=REPO_ROOT) as tmp:
            f = self._fixture(Path(tmp))
            with self.assertRaises(EvidenceError):
                check_evidence(**{**f["evidence_args"], "source_bound_context": None})
            for fields in (["source_bound_proof_id"], ["requirement_id", "requirement_closure_hash", "requirement_hashes"]):
                altered = copy.deepcopy(f["candidate"])
                for field in fields:
                    altered.pop(field)
                with self.assertRaises(ValueError):
                    validate_record(record=altered)
            native = validate_reader_output(response_text=f["response_text"], attempt_id="attempt:legacy:synthetic",
                required_roles=f["authority"]["task_contract"]["required_roles"],
                scope_contract=f["authority"]["task_contract"]["scope_contract"],
                source_reference_ids=f["manifest"]["source_reference_ids"],
                derived_asset_ids=[f["authority"]["full_derived_asset"]["derived_asset_id"]])
            self.assertEqual("REVIEW_REQUIRED", native["status"])
            with self.assertRaisesRegex(EvidenceError, "Legacy Candidate"):
                check_evidence(**{**f["evidence_args"], "candidate": native})

    def test_a09_separate_marker_and_a11_header_scale_keep_reported_units(self):
        cases = [
            ("r4_nonperforming_loan_ratio_table_v2", b"<table><tr><td>Firmwide</td><td>0.66</td><td>%</td></tr></table>",
             (0, 1), (0, 2), [("loan_population", "Firmwide", 0, 0)], "ratio", "0.0066"),
            ("r4_assets_under_management_table_v2", b"<table><tr><td>(in billions)</td><td>2025</td></tr><tr><td>Total assets under management</td><td>4,791</td></tr></table>",
             (1, 1), (0, 0), [("asset_scope", "Total assets under management", 1, 0)], "USD", "4791000000000"),
        ]
        for task, source, target, unit, labels, reported, expected in cases:
            with self.subTest(task=task), tempfile.TemporaryDirectory(prefix="r4-numeric-", dir=REPO_ROOT) as tmp:
                f = self._fixture(Path(tmp), source_bytes=source, task_id=task, target=target,
                                  unit=unit, composite=False, scope_labels=labels)
                self.assertEqual([expected], list(f["evidence"]["normalized_values"].values()))
                self.assertEqual(reported, next(iter(f["candidate"]["selected"].values()))["claimed_reported_unit"])


class OfflineEvidenceContextTest(unittest.TestCase):
    def _context(self, f):
        a = f["authority"]
        return prepare_offline_evidence_context(repo_root=REPO_ROOT, requirement=a["requirement"],
            source_bytes=(REPO_ROOT / a["raw_blob"]["storage_uri"]).read_bytes(), raw_blob=a["raw_blob"],
            source_reference=a["source_reference"], derived_asset_bytes=canonical_json_bytes(value=a["full_derived_asset"]),
            reader_manifest=a["reader_manifest"], full_table_transport=a["evidence_authority_payload"]["untrusted_table_data"],
            task_contracts=[a["task_contract"]], task_generation="LEGACY_CATALOG")

    def test_context_owns_immutable_graph_and_native_evidence_bytes_match(self):
        f = b0_fixture()
        context = self._context(f)
        expected = f["scope"]["check_evidence_result"]
        f["authority"]["full_derived_asset"]["tables"].clear()
        f["authority"]["reader_manifest"]["tables"].clear()
        with self.assertRaises(TypeError):
            context._asset["tables"][1]["rows"][1]["cells"][1]["text"] = "999"
        actual = check_evidence_in_offline_session(context=context, candidate=f["audit"]["synthetic_candidate"],
            task_contract_id=f["authority"]["task_contract"]["task_contract_id"])
        self.assertEqual(expected, actual)

    def test_context_retains_native_locator_and_evidence_rejection(self):
        f = b0_fixture()
        context = self._context(f)
        changed = copy.deepcopy(f["response"])
        changed["candidates"][0]["claimed_raw_value"] = "112%"
        candidate = validate_reader_output(response_text=json.dumps(changed), attempt_id="attempt:wrong:value",
            required_roles=f["authority"]["task_contract"]["required_roles"],
            scope_contract=f["authority"]["task_contract"]["scope_contract"],
            source_reference_ids=f["authority"]["reader_manifest"]["source_reference_ids"],
            derived_asset_ids=[f["authority"]["full_derived_asset"]["derived_asset_id"]])
        evidence = check_evidence_in_offline_session(context=context, candidate=candidate,
            task_contract_id=f["authority"]["task_contract"]["task_contract_id"])
        self.assertEqual("REJECTED", evidence["status"])
        self.assertIn("AI_CLAIMED_VALUE_CELL_MISMATCH", evidence["reason_codes"])
