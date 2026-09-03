"""Complete source-bound successor artifacts and immutable session negatives."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.vnext.common import cell_locator
from tests.vnext.r4_b0_fixture_support import REPO_ROOT, b0_fixture
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes
from vnext.composite_scope import CompositeScopeError, build_source_bound_proof
from vnext.composite_scope import index_source_structure, validate_source_bound_proof
from vnext.evidence import EvidenceError, check_evidence, check_evidence_in_offline_session
from vnext.evidence import prepare_offline_evidence_context
from vnext.evidence import prepare_offline_evidence_context_from_asset_bytes
from vnext.reader import validate_reader_output, validate_source_bound_reader_output
from vnext.r4_task_contracts import resolve_r4_task_contract
from vnext.records import SOURCE_BOUND_CANDIDATE_TYPE, validate_record
from vnext.reader_input import build_reader_input_manifest, build_reader_payload
from vnext.requirements import load_requirement_snapshot
from vnext.scoped_reader import prepare_scoped_reader_request, validate_scoped_reader_response
from vnext.scoped_reader import replay_scoped_offline_attempt
from vnext.scoped_reader import prepare_offline_scoped_context, prepare_scoped_reader_request_in_session
from vnext.scoped_reader import validate_scoped_reader_response_in_session, replay_scoped_offline_attempt_in_session
from vnext.scoped_reader import replay_scoped_offline_artifact_set
from vnext.source_scope import build_source_scope_manifest, validate_source_scope_manifest
from vnext.sources import raw_blob_record, source_reference_record
from vnext.specs import compile_spec_file
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
                 composite=True, scope_labels=None, recipe_override=None,
                 period_recipe=None, source_identity=None):
        path = directory / "source.html"
        path.write_bytes(source_bytes)
        raw = raw_blob_record(repo_root=REPO_ROOT, repo_relative_path=path.relative_to(REPO_ROOT).as_posix(), media_type="text/html")
        identity = dict(company_id="synthetic_r4_issuer",
            source_url="https://www.sec.gov/Archives/edgar/data/123/000000012326000001/test.htm",
            accession="0000000123-26-000001", document_name="test.htm", source_role="target_primary",
            request_attempt_id="sha256:" + "e" * 64)
        identity.update(source_identity or {})
        source = source_reference_record(raw_blob=raw, **identity)
        asset = build_table_grid(html_bytes=source_bytes, parent_raw_asset_ids=[raw["raw_asset_id"]], storage_uri="offline://synthetic-full-grid")
        task = resolve_r4_task_contract(repo_root=REPO_ROOT, requirement=self.requirement, task_contract_id=task_id)
        locator = cell_locator(asset=asset, table_id="table_000001", row_index=target[0], column_index=target[1])
        unit_locator = None if unit is None else cell_locator(asset=asset, table_id="table_000001", row_index=unit[0], column_index=unit[1])
        manifest = build_reader_input_manifest(derived_asset=asset, source_reference_ids=[source["source_reference_id"]])
        payload = build_reader_payload(manifest=manifest, derived_asset=asset, task_contract=task)
        recipe = None
        if composite and recipe_override is None:
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
        if recipe_override is not None:
            recipe = recipe_override(source_bytes, asset)
        period = None if period_recipe is None else period_recipe(source_bytes, asset)
        authority = {"requirement": self.requirement, "repo_root": REPO_ROOT, "source_bytes": source_bytes,
                     "raw_blob": raw, "source_reference": source, "full_derived_asset": asset, "task_contract": task}
        proof = build_source_bound_proof(target_locator=locator, numeric_locator=unit_locator,
                                         composite_scope_recipe=recipe, disclosed_period_recipe=period, **authority)
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
            "candidates": [{"role": task["required_roles"][0], "claimed_period": "FY2025" if period is None else period["period_label"],
                "claimed_raw_value": asset["tables"][0]["rows"][target[0]]["cells"][target[1]]["text"],
                "claimed_reported_unit": compile_spec_file(path=REPO_ROOT / task["metric_spec_paths"][0],
                                                           dependency_specs={})["compiled"]["reported_unit"],
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

    def _block_locator(self, source_bytes, text):
        block = next(b for b in index_source_structure(source_bytes=source_bytes)["blocks"] if b["visible_text"] == text)
        return {k: block[k] for k in ("start_byte", "end_byte")}

    def _scope(self, f):
        authority = {**f["authority"], "reader_manifest": f["manifest"],
                     "evidence_authority_payload": f["payload"]["body"]}
        locator = f["proof"]["target_locator"]
        source_sha = f["proof"]["source_sha256"]
        audit = {"fixture_id": "source_bound_interface_fixture", "fixture_class": "POSITIVE_PRODUCTION",
            "windows": [{"start_order": 0, "end_order": 0}], "target_locator": locator,
            "reference": {"status": "SYNTHETIC_INTERFACE_REFERENCE",
                "value": next(iter(f["evidence"]["normalized_values"].values())), "unit": "USD",
                "period": "FY2025", "scope": f["evidence"]["normalized_scope"],
                "evidence": "Full-artifact source-bound interface test only; no qualification credit"},
            "synthetic_candidate": f["candidate"], "out_of_window_candidates": [],
            "table_audit": [{"table_id": table["table_id"], "grid_sha256": table["grid_sha256"],
                "disposition": "TARGET", "evidence": "Complete synthetic file census",
                "candidate_locator_ids": [content_hash(value=locator)],
                "candidate_dispositions": [{"locator": locator, "disposition": "TARGET",
                    "evidence": "Native selected synthetic cell", "unresolved": False}]} for table in f["authority"]["full_derived_asset"]["tables"]],
            "material_layout_proof": {"kind": "SYNTHETIC_INTERFACE_ONLY", "source_cik": "123", "source_sha256": source_sha,
                "comparison_source_cik": None, "comparison_source_sha256": None, "differences": [],
                "evidence": "Synthetic interface, not a production or alternate filing"},
            "navigation_paths": [{"path_id": name, "method": method, "source_sha256": source_sha,
                "anchor": "Exact synthetic source coordinates", "evidence": "Independent synthetic navigation seam",
                "target_locator": locator} for name, method in (("A", "SECTION_AND_ORIGINAL_TABLE"), ("B", "REVERSE_EXACT_CELL"))]}
        scope = build_source_scope_manifest(audit=audit, scope_schema_version=2,
                                            source_bound_proof=f["proof"], **authority)
        return scope, authority

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

    def test_explicit_regulatory_while_contrast_retains_both_source_clauses(self):
        source = SYNTHETIC_SOURCE.replace(b"Regulatory VaR uses 99% confidence and ten days.",
            b"The holding period for VaR used for regulatory capital calculations is 10 days, while for Trading VaR it is one day.")
        with tempfile.TemporaryDirectory(prefix="r4-source-contrast-", dir=REPO_ROOT) as tmp:
            f = self._fixture(Path(tmp), source_bytes=source)
            rows = f["proof"]["composite_scope"]["competing_scope_span_census"]
            exclusions = [item for row in rows for item in row["measure_dispositions"]
                          if item.get("kind") == "EXACT_SOURCE_WHILE_CONTRAST"]
            self.assertEqual(1, len(exclusions))
            self.assertIn("10 days", exclusions[0]["exact_excluded_clause"])
            self.assertIn("one day", exclusions[0]["exact_target_clause"])

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

    def test_v2_scope_request_attempt_disk_chain_and_session_match(self):
        with tempfile.TemporaryDirectory(prefix="r4-v2-full-chain-", dir=REPO_ROOT) as tmp:
            directory = Path(tmp)
            f = self._fixture(directory)
            scope, authority = self._scope(f)
            scope_id = scope["source_scope_manifest_id"]
            prepared = prepare_scoped_reader_request(source_scope_manifest=scope, expected_manifest_id=scope_id, **authority)
            request = json.loads(prepared.request_bytes)
            self.assertEqual(2, request["schema_version"])
            self.assertEqual(f["proof"]["source_bound_proof_id"], request["source_bound_proof_id"])
            self.assertEqual("FY2025", request["task_period"])
            self.assertEqual("FY2025", request["scoped_transport_contract"]["requested_period"])
            self.assertEqual("USD", request["scoped_transport_contract"]["reported_unit_contract"])
            self.assertEqual(["confidence_level", "holding_period"], request["scoped_transport_contract"]["locally_proven_scope_dimensions"])
            self.assertTrue(request["scoped_transport_contract"]["locally_proven_dimensions_may_be_omitted"])
            self.assertTrue(request["scoped_transport_contract"]["empty_scope_arrays_are_valid_for_locally_proven_dimensions"])
            self.assertNotIn(b"Trading VaR uses a one-day", prepared.request_bytes)
            self.assertNotIn("source_bound_proof", request)
            attempt = validate_scoped_reader_response(prepared_request=prepared, response_text=f["response_text"],
                attempt_id="attempt:v2:full-chain", source_scope_manifest=scope, expected_manifest_id=scope_id, **authority)
            bundle = directory / "bundle"
            bundle.mkdir()
            contents = {"source_scope.json": canonical_json_bytes(value=scope), "scoped_plan.json": prepared.plan_bytes,
                        "scoped_request.json": prepared.request_bytes, "scoped_attempt.json": canonical_json_bytes(value=attempt)}
            for name, data in contents.items():
                (bundle / name).write_bytes(data)
            bindings = {name: {"sha256": sha256_bytes(content=data), "size": len(data)} for name, data in contents.items()}
            replay = replay_scoped_offline_artifact_set(directory=bundle, repo_root=REPO_ROOT, file_bindings=bindings,
                expected_manifest_id=scope_id, expected_plan_id=prepared.plan_id, expected_request_id=prepared.request_id,
                expected_attempt_id=attempt["scoped_attempt_id"], **{k: v for k, v in authority.items() if k != "repo_root"})
            self.assertEqual(attempt, replay["attempt"])
            a = f["authority"]
            evidence_context = prepare_offline_evidence_context(repo_root=REPO_ROOT, requirement=a["requirement"],
                source_bytes=a["source_bytes"], raw_blob=a["raw_blob"], source_reference=a["source_reference"],
                derived_asset_bytes=canonical_json_bytes(value=a["full_derived_asset"]), reader_manifest=f["manifest"],
                full_table_transport=f["payload"]["body"]["untrusted_table_data"], task_contracts=[a["task_contract"]],
                task_generation="R4_V2")
            context = prepare_offline_scoped_context(evidence_context=evidence_context,
                scope_files={scope_id: {"path": str(bundle / "source_scope.json"), **bindings["source_scope.json"]}})
            self.assertEqual(prepared, prepare_scoped_reader_request_in_session(context=context, source_scope_manifest_id=scope_id))
            optimized = validate_scoped_reader_response_in_session(context=context, source_scope_manifest_id=scope_id,
                prepared_request=prepared, response_text=f["response_text"], attempt_id=attempt["attempt_id"])
            self.assertEqual(attempt, optimized)
            self.assertEqual(attempt, replay_scoped_offline_attempt_in_session(context=context, attempt=attempt))
            for field in ("source_bound_proof", "task_contract_generation", "task_period"):
                altered = copy.deepcopy(scope)
                altered.pop(field)
                altered["source_scope_manifest_id"] = content_hash(value={k: v for k, v in altered.items() if k != "source_scope_manifest_id"})
                with self.assertRaises(ValueError):
                    validate_source_scope_manifest(manifest=altered, expected_manifest_id=altered["source_scope_manifest_id"], **authority)

    def test_real_provider_schema_allows_certified_scope_omissions_without_extra_fields(self):
        from vnext.ai_adapter import READER_OUTPUT_JSON_SCHEMA
        properties = READER_OUTPUT_JSON_SCHEMA["properties"]["candidates"]["items"]["properties"]
        for field in ("claimed_scope", "scope_evidence_locators"):
            self.assertEqual("array", properties[field]["type"])
            self.assertNotIn("minItems", properties[field])
        for task_id in ("r4_liquidity_coverage_ratio_table_v2", "r4_value_at_risk_table_v2"):
            task = resolve_r4_task_contract(repo_root=REPO_ROOT, requirement=self.requirement, task_contract_id=task_id)
            self.assertEqual("3", task["output_schema_version"])
            self.assertEqual("Return raw claims and exact locators from one selected table only.", task["system_prompt"])

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

    def test_mixed_table_confidence_and_narrative_holding_require_target_column(self):
        source = b"""<html><body><h1>Trading Risk Management</h1><h2>Value-at-risk</h2>
<p>Trading VaR uses a one-day holding period.</p>
<p>The table below reports Trading VaR at 99% and 95% confidence.</p>
<table><tr><td>(in millions)</td><td>99%</td><td>95%</td></tr>
<tr><td>Total VaR</td><td>60</td><td>40</td></tr></table>
<h2>Backtesting</h2><h1>Credit Risk Management</h1></body></html>"""
        def recipe(content, asset):
            block = lambda text: self._block_locator(content, text)
            return {"section_heading": block("Trading Risk Management"),
                    "section_end_heading": block("Credit Risk Management"),
                    "association_heading": block("Value-at-risk"),
                    "association_end_heading": block("Backtesting"),
                    "target_measure_name": "Trading VaR",
                    "table_association_span": block("The table below reports Trading VaR at 99% and 95% confidence."),
                    "selected_scope_spans": [{"dimension": "holding_period", "raw_value": "one-day",
                                              **block("Trading VaR uses a one-day holding period.")}]}
        with tempfile.TemporaryDirectory(prefix="r4-composite-mixed-", dir=REPO_ROOT) as tmp:
            f = self._fixture(Path(tmp), source_bytes=source, target=(1, 2), unit=(0, 0),
                recipe_override=recipe, scope_labels=[("confidence_level", "95%", 0, 2)])
            self.assertEqual("PASS", f["evidence"]["status"])
            self.assertEqual(["confidence_level"], f["proof"]["composite_scope"]["table_disambiguation_dimensions"])
            wrong = copy.deepcopy(f["response"])
            wrong["candidates"][0]["scope_evidence_locators"][0]["locator"] = cell_locator(
                asset=f["authority"]["full_derived_asset"], table_id="table_000001", row_index=0, column_index=1)
            wrong["candidates"][0]["scope_evidence_locators"][0]["raw_text"] = "99%"
            wrong["candidates"][0]["claimed_scope"][0]["raw_value"] = "99%"
            with self.assertRaises(ValueError):
                validate_source_bound_reader_output(response_text=json.dumps(wrong), attempt_id="attempt:wrong:column",
                    source_bound_proof=f["proof"], expected_proof_id=f["proof"]["source_bound_proof_id"], **f["authority"])

    def test_a03_disclosed_quarter_is_source_bound_and_never_annual(self):
        source = """<html><body><h1>Liquidity Risk</h1><h2>Liquidity coverage ratio</h2>
<p>Citigroup’s consolidated LCR for the fourth quarter of 2025 follows.</p>
<p>The table below presents Citi’s LCR calculation.</p>
<table><tr><td>Measure</td><td>Dec. 31, 2025</td></tr>
<tr><td>LCR</td><td>115</td></tr></table>
<p>Note: The amounts are presented on an average basis.</p>
<h2>Long-Term Liquidity</h2><h1>Deposits</h1></body></html>""".encode("utf-8")
        def recipe(content, asset):
            block = lambda text: self._block_locator(content, text)
            return {"section_heading": block("Liquidity Risk"), "section_end_heading": block("Deposits"),
                "association_heading": block("Liquidity coverage ratio"), "association_end_heading": block("Long-Term Liquidity"),
                "target_measure_name": "LCR", "table_association_span": block("The table below presents Citi’s LCR calculation."),
                "selected_scope_spans": [
                    {"dimension": "entity_scope", "raw_value": "Citigroup’s consolidated LCR",
                     **block("Citigroup’s consolidated LCR for the fourth quarter of 2025 follows.")},
                    {"dimension": "aggregation", "raw_value": "average",
                     **block("Note: The amounts are presented on an average basis.")}]}
        def period(content, asset):
            return {"source_id": "citigroup_fy2025_10k", "fixture_class": "POSITIVE_ALTERNATE_LAYOUT",
                "averaging_period": "AS_DISCLOSED_QUARTER_AVERAGE", "period_label": "2025-Q4",
                "period_start": "2025-10-01", "period_end": "2025-12-31",
                "period_header_locator": cell_locator(asset=asset, table_id="table_000001", row_index=0, column_index=1),
                "quarter_span": self._block_locator(content, "Citigroup’s consolidated LCR for the fourth quarter of 2025 follows."),
                "averaging_span": self._block_locator(content, "Note: The amounts are presented on an average basis.")}
        identity = {"company_id": "citigroup", "accession": "0000831001-26-000011", "document_name": "c-20251231.htm",
                    "source_url": "https://www.sec.gov/Archives/edgar/data/831001/000083100126000011/c-20251231.htm"}
        with tempfile.TemporaryDirectory(prefix="r4-composite-quarter-", dir=REPO_ROOT) as tmp:
            f = self._fixture(Path(tmp), source_bytes=source, task_id="r4_liquidity_coverage_ratio_table_v2",
                unit=None, recipe_override=recipe, period_recipe=period, source_identity=identity)
            self.assertEqual("PASS", f["evidence"]["status"])
            self.assertEqual("2025-Q4", next(iter(f["candidate"]["selected"].values()))["claimed_period"])
            self.assertEqual(["1.15"], list(f["evidence"]["normalized_values"].values()))
            altered = copy.deepcopy(f["response"])
            altered["candidates"][0]["claimed_period"] = "FY2025"
            with self.assertRaisesRegex(ValueError, "disclosed quarter"):
                validate_source_bound_reader_output(response_text=json.dumps(altered), attempt_id="attempt:annual:spoof",
                    source_bound_proof=f["proof"], expected_proof_id=f["proof"]["source_bound_proof_id"], **f["authority"])
            wrong_recipe = period(source, f["authority"]["full_derived_asset"])
            wrong_recipe["period_start"] = "2025-01-01"
            with self.assertRaisesRegex(ValueError, "quarter dates"):
                build_source_bound_proof(target_locator=f["proof"]["target_locator"],
                    composite_scope_recipe=recipe(source, f["authority"]["full_derived_asset"]),
                    disclosed_period_recipe=wrong_recipe, **f["authority"])
            with self.assertRaisesRegex(ValueError, "requires an explicit disclosed-period"):
                build_source_bound_proof(target_locator=f["proof"]["target_locator"],
                    composite_scope_recipe=recipe(source, f["authority"]["full_derived_asset"]), **f["authority"])


class OfflineEvidenceContextTest(unittest.TestCase):
    def _context(self, f):
        a = f["authority"]
        return prepare_offline_evidence_context(repo_root=REPO_ROOT, requirement=a["requirement"],
            source_bytes=(REPO_ROOT / a["raw_blob"]["storage_uri"]).read_bytes(), raw_blob=a["raw_blob"],
            source_reference=a["source_reference"], derived_asset_bytes=canonical_json_bytes(value=a["full_derived_asset"]),
            reader_manifest=a["reader_manifest"], full_table_transport=a["evidence_authority_payload"]["untrusted_table_data"],
            task_contracts=[a["task_contract"]], task_generation="LEGACY_CATALOG")

    def _byte_arguments(self, f):
        a = f["authority"]
        return {"repo_root": REPO_ROOT, "requirement": a["requirement"],
            "source_bytes": (REPO_ROOT / a["raw_blob"]["storage_uri"]).read_bytes(),
            "raw_blob": a["raw_blob"], "source_reference": a["source_reference"],
            "derived_asset_bytes": canonical_json_bytes(value=a["full_derived_asset"]),
            "task_contracts": [a["task_contract"]], "task_generation": "LEGACY_CATALOG"}

    def test_byte_owned_factory_preserves_full_inputs_with_one_actual_asset_decode(self):
        from vnext.offline_execution_session import OfflineOperationObserver
        f = b0_fixture()
        original = self._context(f)
        arguments = self._byte_arguments(f)
        with OfflineOperationObserver() as setup:
            context = prepare_offline_evidence_context_from_asset_bytes(**arguments)
        self.assertEqual(1, setup.counts["derived_asset_json_decodes"])
        self.assertEqual(0, setup.counts["derived_asset_builds"])
        self.assertEqual(original.identity, context.identity)
        self.assertEqual(original._asset, context._asset)
        self.assertEqual(original._manifest, context._manifest)
        self.assertEqual(original._transport, context._transport)
        f["authority"]["full_derived_asset"]["tables"].clear()
        f["authority"]["reader_manifest"]["tables"].clear()
        with self.assertRaises(TypeError):
            context._asset["tables"][1]["rows"][1]["cells"][1]["text"] = "999"
        with OfflineOperationObserver() as children:
            for _ in range(6):
                evidence = check_evidence_in_offline_session(context=context,
                    candidate=f["audit"]["synthetic_candidate"],
                    task_contract_id=f["authority"]["task_contract"]["task_contract_id"])
                self.assertEqual(f["scope"]["check_evidence_result"], evidence)
        for key in ("derived_asset_json_decodes", "derived_asset_builds", "source_materializations",
                    "provider_calls", "paid_model_calls", "sec_calls"):
            self.assertEqual(0, children.counts[key], key)

    def test_byte_owned_factory_rejects_source_asset_task_and_mutable_input_drift(self):
        f = b0_fixture()
        arguments = self._byte_arguments(f)
        wrong_parent = build_table_grid(html_bytes=arguments["source_bytes"],
            parent_raw_asset_ids=["sha256:" + "d" * 64], storage_uri="offline://wrong-source")
        changed_task = copy.deepcopy(arguments["task_contracts"][0])
        changed_task["required_roles"] = []
        changes = [
            {"source_bytes": arguments["source_bytes"] + b" "},
            {"source_bytes": bytearray(arguments["source_bytes"])},
            {"derived_asset_bytes": f["authority"]["full_derived_asset"]},
            {"derived_asset_bytes": bytearray(arguments["derived_asset_bytes"])},
            {"derived_asset_bytes": b"{}"},
            {"derived_asset_bytes": canonical_json_bytes(value=wrong_parent)},
            {"task_contracts": [changed_task]},
            {"task_contracts": arguments["task_contracts"] * 2},
            {"task_contracts": []},
            {"task_generation": "INFER_FROM_ID"},
        ]
        for index, changed in enumerate(changes):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                prepare_offline_evidence_context_from_asset_bytes(**{**arguments, **changed})

    def test_original_factory_still_rejects_manifest_or_full_transport_tamper(self):
        for target in ("manifest", "transport"):
            with self.subTest(target=target):
                f = b0_fixture()
                if target == "manifest":
                    f["authority"]["reader_manifest"]["tables"].pop()
                else:
                    f["authority"]["evidence_authority_payload"]["untrusted_table_data"]["tables"].pop()
                with self.assertRaises(ValueError):
                    self._context(f)

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

    def test_full_session_pipeline_is_byte_identical_and_detects_scope_file_drift(self):
        f = b0_fixture()
        evidence_context = self._context(f)
        with tempfile.TemporaryDirectory(prefix="r4-scoped-context-", dir=REPO_ROOT) as tmp:
            path = Path(tmp) / "scope.json"
            data = canonical_json_bytes(value=f["scope"])
            path.write_bytes(data)
            scope_id = f["scope"]["source_scope_manifest_id"]
            context = prepare_offline_scoped_context(evidence_context=evidence_context,
                scope_files={scope_id: {"path": str(path), "sha256": sha256_bytes(content=data), "size": len(data)}})
            optimized = prepare_scoped_reader_request_in_session(context=context, source_scope_manifest_id=scope_id)
            ordinary = prepare_scoped_reader_request(source_scope_manifest=f["scope"], expected_manifest_id=scope_id, **f["authority"])
            self.assertEqual(ordinary, optimized)
            kwargs = {"response_text": f["response_text"], "attempt_id": "attempt:session:byte-parity"}
            attempt = validate_scoped_reader_response_in_session(context=context, source_scope_manifest_id=scope_id,
                prepared_request=optimized, **kwargs)
            native = validate_scoped_reader_response(source_scope_manifest=f["scope"], expected_manifest_id=scope_id,
                prepared_request=ordinary, **f["authority"], **kwargs)
            self.assertEqual(native, attempt)
            self.assertEqual(attempt, replay_scoped_offline_attempt_in_session(context=context, attempt=attempt))
            path.write_bytes(data + b"\n")
            with self.assertRaises(ValueError):
                prepare_scoped_reader_request_in_session(context=context, source_scope_manifest_id=scope_id)
