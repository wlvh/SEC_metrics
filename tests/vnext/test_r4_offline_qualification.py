"""Audit regressions only: rejected references must never become qualification."""

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.vnext.r4_b0_fixture_support import b0_fixture
from vnext.batch_workflow import request_attempt_binding
from vnext.canonical import content_hash, strict_json_file
from vnext.deterministic_router import adapt_accession_xbrl, source_set_manifest
from vnext.r4_source_audit import R4SourceAuditError, _native_probe
from vnext.r4_source_audit import audit_scope_alias_coverage
from vnext.r4_source_audit import inventory_immutable_sources, source_authority
from vnext.sources import raw_blob_record, source_reference_record
from vnext.r4_fixture_authority import load_r4_fixture_authority
from vnext.r4_offline_qualification import INDEX_PATH, R4OfflineQualificationError
from vnext.r4_offline_qualification import replay_case_artifacts, _scoped_summary
from vnext.r4_offline_qualification import _structured_context, prepare_source_bundle_from_context
from vnext.r4_offline_qualification import prepare_source_bundle, _validate_recipe_scope_binding
from vnext.r4_offline_qualification import _structured_fiscal_period
from vnext.r4_task_contracts import inspect_r4_task_catalog
from vnext.deterministic_router import DeterministicRouterError, parse_accession_xbrl_source
from vnext.requirements import load_requirement_snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
RECIPE_PATH = REPO_ROOT / "tests/fixtures/vnext/r4_offline/jpm_fy2025_probe.json"


class R4OfflineAuditTest(unittest.TestCase):
    def test_source_context_adapter_rejects_caller_dictionary(self):
        with self.assertRaises(R4OfflineQualificationError):
            prepare_source_bundle_from_context(repo_root=REPO_ROOT,
                source_id="jpmorgan_fy2025_10k", evidence_context={},
                task_contract_id="r4_liquidity_coverage_ratio_table_v2")

    def test_native_structured_inputs_do_not_depend_on_old_diagnostic_document(self):
        authority = load_r4_fixture_authority(repo_root=REPO_ROOT)
        source = next(s for s in authority["sources"].values() if s["structured_source_authority"] is not None)
        bundle = {**source_authority(repo_root=REPO_ROOT, declaration=source),
            "declaration": source, "source_id": source["source_id"], "structured_context": None}
        def read(*, path):
            if path.name == "source_audit_evidence.json":
                raise AssertionError("Historical diagnostic document is not runtime authority")
            return strict_json_file(path=path)
        with patch("vnext.r4_offline_qualification.strict_json_file", side_effect=read):
            context = _structured_context(repo_root=REPO_ROOT, bundle=bundle)
        self.assertEqual(context["source_set_manifest"]["source_set_manifest_id"],
                         source["structured_source_authority"]["source_set_manifest_id"])
        self.assertEqual(len(context["file_bindings"]), 3)
        fiscal = _structured_fiscal_period(context=context,
            recipe=authority["recipes"]["r4_a13_production"], source_bundle=bundle)
        self.assertEqual(fiscal["period_label"], "FY2025")
        self.assertEqual(fiscal["period_start"], "2025-01-01")
        self.assertEqual(fiscal["period_end"], "2025-12-31")
        wrong = dict(bundle, source_id="another_source")
        with self.assertRaises(R4OfflineQualificationError):
            _structured_context(repo_root=REPO_ROOT, bundle=wrong)

    def test_inventory_binds_existing_ledger_and_immutable_source(self):
        recipe = strict_json_file(path=RECIPE_PATH)
        inventory = inventory_immutable_sources(
            repo_root=REPO_ROOT, issuer_ciks=[recipe["source"]["cik"]])
        body = {k: v for k, v in inventory.items() if k != "inventory_id"}
        self.assertEqual(inventory["inventory_id"], content_hash(value=body))
        self.assertEqual(inventory["provider_paid_sec_calls"], [0, 0, 0])
        self.assertIn(recipe["source"]["source_sha256"], [
            row["source_sha256"] for row in inventory["issuer_inventory"][0]["immutable_sources"]])

    def test_source_path_sha_size_and_attempt_identity_are_not_optional(self):
        declaration = strict_json_file(path=RECIPE_PATH)["source"]
        source = source_authority(repo_root=REPO_ROOT, declaration=declaration)
        self.assertEqual(source["raw_blob"]["raw_asset_id"],
                         "sha256:" + declaration["source_sha256"])
        self.assertTrue(source["source_reference"]["request_attempt_id"].startswith("request:attempt:"))
        for field, value in (("source_sha256", "f" * 64),
                             ("source_size", declaration["source_size"] + 1),
                             ("accession", "0000000000-26-000001"),
                             ("source_repo_relative_path", "outputs/metrics_matrix.csv")):
            with self.subTest(field=field):
                changed = dict(declaration, **{field: value})
                with self.assertRaises(R4SourceAuditError):
                    source_authority(repo_root=REPO_ROOT, declaration=changed)

    def test_native_review_required_remains_non_auto_eligible(self):
        fixture = b0_fixture()
        authority = fixture["authority"]
        recipe = {
            "target": {"table_order": 1, "row_index": 1, "column_index": 1},
            "claimed_period": "FY2025", "scope_labels": [],
            "header_coordinates": [],
        }
        original_asset = copy.deepcopy(authority["full_derived_asset"])
        result = _native_probe(
            asset=authority["full_derived_asset"],
            source={"source_reference": authority["source_reference"]},
            task=authority["task_contract"], recipe=recipe, unit="percent")
        self.assertEqual(result["candidate"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["evidence"]["status"], "PASS")
        self.assertFalse(result["evidence"]["system_approval_eligible"])
        self.assertEqual(authority["full_derived_asset"], original_asset)

    def test_jpm_native_a12_has_no_complete_same_table_scope(self):
        recipe = strict_json_file(path=RECIPE_PATH)
        task_id = next(p["task_contract_id"] for p in recipe["probes"]
                       if p["metric_id"] == "A12")
        coverage = audit_scope_alias_coverage(
            repo_root=REPO_ROOT, declaration=recipe["source"], task_contract_id=task_id)
        self.assertEqual(coverage["table_count"], 679)
        self.assertEqual(coverage["complete_scope_tables"], [])
        self.assertTrue(coverage["any_alias_tables"])
        self.assertTrue(all("holding_period" not in row["scope_aliases"]
                            for row in coverage["any_alias_tables"]))
        self.assertEqual(coverage["qualification_credit"], "NONE_OFFLINE_AUDIT")

    def test_structured_ambiguity_replays_through_native_accession_adapter(self):
        """Verify actual claim sets without choosing a new economic meaning."""
        recipe = strict_json_file(path=RECIPE_PATH)
        evidence = strict_json_file(path=REPO_ROOT / "docs/r4_offline/source_audit_evidence.json")
        expected = evidence["structured_route_probe"]
        declaration = dict(recipe["source"])
        declaration.update({
            "document_name": "jpm-20251231_htm.xml",
            "source_url": recipe["source"]["source_url"].replace(".htm", "_htm.xml"),
            "source_repo_relative_path": "evidence/request_attempts/{}/{}/{}".format(
                expected["source_sha256"][:2], expected["source_sha256"], "jpm-20251231_htm.xml"),
            "source_sha256": expected["source_sha256"],
            "source_size": expected["source_size"], "media_type": "application/xml",
        })
        source = source_authority(repo_root=REPO_ROOT, declaration=declaration)
        inventory_name = "CIK{}.json".format(declaration["cik"].zfill(10))
        inventory_url = "https://data.sec.gov/submissions/" + inventory_name
        inventory_path = "evidence/request_attempts/{}/{}/{}".format(
            expected["submissions_sha256"][:2], expected["submissions_sha256"], inventory_name)
        raw = raw_blob_record(repo_root=REPO_ROOT, repo_relative_path=inventory_path,
                              media_type="application/json")
        binding = request_attempt_binding(
            repo_root=REPO_ROOT, source_url=inventory_url,
            content_sha256=expected["submissions_sha256"],
            accession="SUBMISSIONS-2025", document_name=inventory_name)
        self.assertEqual(binding["request_attempt_id"], expected["submissions_attempt_id"])
        reference = source_reference_record(
            raw_blob=raw, company_id=declaration["company_id"],
            source_url=inventory_url, accession="SUBMISSIONS-2025",
            document_name=inventory_name, source_role="sec_submissions_inventory",
            request_attempt_id=binding["request_attempt_id"])
        manifest = source_set_manifest(
            company_id=declaration["company_id"], source_role="target_primary",
            form_types=["10-K"], fiscal_or_date_window=expected["filing_date_window"],
            discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1",
            inventory_source_reference=reference,
            inventory_bytes=(REPO_ROOT / inventory_path).read_bytes(),
            ordered_source_references=[source["source_reference"]],
            cutoff_timestamp_or_pinned_submissions_attempt=reference["request_attempt_id"])
        self.assertEqual(manifest["source_set_manifest_id"], expected["source_set_manifest_id"])
        for outcome in expected["outcomes"]:
            with self.subTest(metric_id=outcome["metric_id"]):
                claims = adapt_accession_xbrl(
                    raw_bytes=source["source_bytes"], source_reference=source["source_reference"],
                    source_set_manifest=manifest, fact_names=outcome["fact_names"])
                self.assertEqual(len(claims), outcome["adapted_claims_count"])
                self.assertEqual(content_hash(value=claims), outcome["adapted_claims_hash"])
                axes = outcome.get("geographic_dimension_axes", [])
                current = [claim for claim in claims
                           if claim["attributes"]["context"]["period_end"] == "2025-12-31"
                           and (not axes or set(axes).intersection(
                               claim["attributes"]["context"]["dimensions"]))]
                self.assertEqual(len(current), outcome["current_period_candidates_count"])
                self.assertEqual(content_hash(value=current), outcome["current_period_candidates_hash"])
                self.assertGreater(len(current), 1)
                self.assertEqual(outcome["candidate_resolution"], "NOT_SELECTED_BY_AUDIT")
                self.assertEqual(outcome["no_anchor_closure"], "NOT_COMPLETE")


class R4CompleteOfflineArtifactTest(unittest.TestCase):
    """Integration assertions over all complete real-source artifacts, not stubs."""

    @classmethod
    def setUpClass(cls):
        cls.authority = load_r4_fixture_authority(repo_root=REPO_ROOT)
        cls.index = strict_json_file(path=REPO_ROOT / INDEX_PATH)
        cls.requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_28_v2")

    def test_all_pairs_remain_offline_and_structured_success_does_not_get_ai_plan(self):
        self.assertEqual(len(self.index["cases"]), 16)
        self.assertEqual(self.index["requirement_closure_hash"], self.requirement["requirement_closure_hash"])
        self.assertEqual(self.index["provider_paid_sec_calls"], [0, 0, 0])
        eligible = []
        for entry in self.index["cases"]:
            summary = entry["summary"]
            self.assertEqual(summary["qualification_credit"], "NONE_OFFLINE_SYNTHETIC")
            if summary["provider_call_eligible"]:
                eligible.append(entry["fixture_id"])
                self.assertEqual(entry["artifact_kind"], "SCOPED_EXTRACTION")
            if entry["artifact_kind"] == "STRUCTURED_PRIMARY":
                self.assertEqual(set(entry["files"]), {"structured_route.json", "source_audit.json"})
                self.assertFalse(summary["provider_call_eligible"])
                route = entry["structured_route"]
                self.assertEqual(route["outcome"], "STRUCTURED_PRIMARY_RESOLVED")
                self.assertEqual(len(route["claim_dispositions"]), route["all_claims_count"])
                self.assertFalse(any(d["unresolved"] for d in route["claim_dispositions"]))
                self.assertFalse(route["regional_sum_used"])
        self.assertEqual(len(eligible), 9)

    def test_native_scoped_evidence_and_quarter_period_are_not_promoted_or_relabelled(self):
        for entry in self.index["cases"]:
            if entry["artifact_kind"] != "SCOPED_EXTRACTION":
                continue
            directory = REPO_ROOT / entry["directory"]
            scope = strict_json_file(path=directory / "source_scope.json")
            attempt = strict_json_file(path=directory / "scoped_attempt.json")
            recipe = self.authority["recipes"][entry["fixture_id"]]
            self.assertEqual(attempt["evidence"]["status"], "PASS")
            self.assertTrue(attempt["evidence"]["system_approval_eligible"])
            self.assertEqual([attempt[k] for k in ("provider_call_count", "paid_model_call_count", "sec_call_count")], [0, 0, 0])
            self.assertEqual(_scoped_summary(recipe=recipe, scope=scope, attempt=attempt), entry["summary"])
            self.assertEqual(scope["task_period"], recipe["period"])
            self.assertEqual(len(scope["table_audit"]), self.authority["sources"][recipe["source_id"]]["table_count"])
            self.assertTrue(all(not d["unresolved"] for d in scope["out_of_window_candidates"]))
            self.assertTrue(1 <= len(scope["windows"]) <= 2)
        quarter = next(c for c in self.index["cases"] if c["fixture_id"] == "r4_a03_alternate")
        self.assertEqual(quarter["summary"]["period"], "2025Q4")
        self.assertEqual(quarter["summary"]["value"], "1.15")

    def test_forged_index_claims_fail_even_with_recomputed_content_id(self):
        fixture = self.authority["fixtures"][0]
        mutations = []
        for key, value in (("status", "LIVE"), ("requirement_id", "issue_28_v1"),
                           ("provider_paid_sec_calls", [1, 0, 0]),
                           ("qualification_credit", "CURRENT"), ("live_authorization", "APPROVED")):
            changed = copy.deepcopy(self.index)
            changed[key] = value
            mutations.append(changed)
        changed = copy.deepcopy(self.index)
        changed["cases"].append(copy.deepcopy(changed["cases"][0]))
        mutations.append(changed)
        changed = copy.deepcopy(self.index)
        changed["metric_ids"].append("B13")
        mutations.append(changed)
        for changed in mutations:
            changed["index_id"] = content_hash(value={k: v for k, v in changed.items() if k != "index_id"})
            with self.subTest(index_id=changed["index_id"]), patch(
                    "vnext.r4_offline_qualification.strict_json_file", return_value=changed):
                with self.assertRaises(R4OfflineQualificationError):
                    replay_case_artifacts(repo_root=REPO_ROOT, requirement=self.requirement,
                        fixture=fixture, source_bundle={"source_id": fixture["source_id"]})

    def test_negative_and_ambiguity_native_evidence_never_receive_auto_credit(self):
        entries = {c["fixture_class"]: c for c in self.index["cases"] if c["artifact_kind"] == "ZERO_CALL_CLASSIFICATION"}
        self.assertEqual(set(entries), {"NEGATIVE_EXPECTED", "NOT_APPLICABLE", "QUALITATIVE_ONLY", "AMBIGUOUS_EXCLUDED"})
        for fixture_class in ("NEGATIVE_EXPECTED", "AMBIGUOUS_EXCLUDED"):
            entry = entries[fixture_class]
            result = strict_json_file(path=REPO_ROOT / entry["directory"] / "zero_call_result.json")
            self.assertFalse(result["native_evidence"]["system_approval_eligible"])
            self.assertFalse(result["provider_call_eligible"])
        self.assertEqual(entries["AMBIGUOUS_EXCLUDED"]["summary"]["synthetic_candidate"]["status"], "REVIEW_REQUIRED")


class R4FullArtifactRecipeBindingTest(unittest.TestCase):
    """Real JPM source/Scope/attempt mutations at the recipe authority boundary."""

    @classmethod
    def setUpClass(cls):
        cls.authority = load_r4_fixture_authority(repo_root=REPO_ROOT)
        recipe = cls.authority["recipes"]["r4_a04_production"]
        cls.bundle = prepare_source_bundle(repo_root=REPO_ROOT, source_id=recipe["source_id"])
        cls.bundle["repo_root"] = str(REPO_ROOT)
        cls.tasks = {t["task_contract_id"]: t for t in inspect_r4_task_catalog(repo_root=REPO_ROOT)["contracts"]}

    def records(self, fixture_id):
        directory = REPO_ROOT / "docs/r4_offline/qualified_cases" / fixture_id
        return (strict_json_file(path=directory / "source_scope.json"),
                strict_json_file(path=directory / "scoped_attempt.json"),
                self.authority["recipes"][fixture_id])

    def check(self, scope, attempt, recipe):
        _validate_recipe_scope_binding(scope=scope, attempt=attempt, recipe=recipe,
            authority=self.authority, source_bundle=self.bundle,
            task=self.tasks[recipe["task_contract_id"]])

    def test_real_complete_artifact_matches_recipe_and_rebound_scope_mutations_fail(self):
        scope, attempt, recipe = self.records("r4_a04_production")
        self.check(scope, attempt, recipe)
        mutations = []
        changed = copy.deepcopy(scope)
        changed["windows"][0]["end_order"] += 1
        mutations.append(changed)
        changed = copy.deepcopy(scope)
        changed["reference"]["value"] = "0.026"
        mutations.append(changed)
        changed = copy.deepcopy(scope)
        changed["navigation_paths"][1]["evidence"] = "Unrelated but nonempty text"
        mutations.append(changed)
        changed = copy.deepcopy(scope)
        changed["out_of_window_candidates"].pop()
        mutations.append(changed)
        changed = copy.deepcopy(scope)
        changed["table_audit"][0]["grid_sha256"] = "sha256:" + "f" * 64
        mutations.append(changed)
        for changed in mutations:
            changed["source_scope_manifest_id"] = content_hash(value={k: v for k, v in changed.items() if k != "source_scope_manifest_id"})
            with self.subTest(scope_id=changed["source_scope_manifest_id"]):
                with self.assertRaises(R4OfflineQualificationError):
                    self.check(changed, attempt, recipe)

    def test_rebound_response_and_composite_proof_cannot_choose_different_recipe(self):
        scope, attempt, recipe = self.records("r4_a12_production")
        self.check(scope, attempt, recipe)
        changed = copy.deepcopy(scope)
        changed["source_bound_proof"]["composite_scope"]["recipe"]["table_association_span"]["start_byte"] += 1
        with self.assertRaises(R4OfflineQualificationError):
            self.check(changed, attempt, recipe)
        changed = copy.deepcopy(attempt)
        changed["response_text"] = changed["response_text"].replace('"40"', '"41"')
        self.assertNotEqual(changed["response_text"], attempt["response_text"])
        with self.assertRaises(R4OfflineQualificationError):
            self.check(scope, changed, recipe)


class R4NativeFiscalPeriodTest(unittest.TestCase):
    """Native XBRL bytes supply the complete fiscal duration, not code literals."""

    def context(self, *, omit=None, duplicate=False, document_end="2051-02-28",
                period_focus="FY", context_end="2051-02-28"):
        fields = {"EntityCentralIndexKey": "1", "DocumentType": "10-K",
                  "DocumentFiscalYearFocus": "2050", "DocumentFiscalPeriodFocus": period_focus,
                  "DocumentPeriodEndDate": document_end}
        if omit is not None:
            fields.pop(omit)
        tags = ''.join('<dei:{0} contextRef="fiscal">{1}</dei:{0}>'.format(k, v) for k, v in fields.items())
        if duplicate:
            tags += '<dei:DocumentFiscalYearFocus contextRef="fiscal">2049</dei:DocumentFiscalYearFocus>'
        raw = ('<xbrl><xbrli:context id="fiscal"><xbrli:entity><xbrli:identifier scheme="CIK">1</xbrli:identifier></xbrli:entity>'
               '<xbrli:period><xbrli:startDate>2050-03-01</xbrli:startDate><xbrli:endDate>' + context_end +
               '</xbrli:endDate></xbrli:period></xbrli:context>' + tags + '</xbrl>').encode()
        parsed = parse_accession_xbrl_source(raw_bytes=raw)
        return {"parsed": parsed, "raw_bytes": raw,
                "source_reference": {"raw_asset_id": "sha256:" + parsed.source_sha256}}

    def test_noncalendar_fiscal_duration_is_taken_from_native_source(self):
        for end in ("2051-02-28", "February 28, 2051"):
            result = _structured_fiscal_period(context=self.context(document_end=end),
                recipe={"period": "FY2050"}, source_bundle={"declaration": {"cik": "1"}})
            self.assertEqual((result["period_start"], result["period_end"]), ("2050-03-01", "2051-02-28"))
            self.assertEqual(result["period_label"], "FY2050")

    def test_native_metadata_omission_conflict_and_period_relabel_fail(self):
        contexts = [self.context(omit="DocumentFiscalYearFocus"), self.context(duplicate=True),
                    self.context(document_end="2050-02-28"), self.context(period_focus="Q4")]
        for context in contexts:
            with self.subTest(parsed_source_id=context["parsed"].parsed_source_id):
                with self.assertRaises(R4OfflineQualificationError):
                    _structured_fiscal_period(context=context, recipe={"period": "FY2050"},
                                             source_bundle={"declaration": {"cik": "1"}})
        for period, cik in (("FY2049", "1"), ("2050Q4", "1"), ("FY2050", "2")):
            with self.subTest(period=period, cik=cik), self.assertRaises(R4OfflineQualificationError):
                _structured_fiscal_period(context=self.context(), recipe={"period": period},
                                         source_bundle={"declaration": {"cik": cik}})
        with self.assertRaises(DeterministicRouterError):
            self.context(context_end="")


if __name__ == "__main__":
    unittest.main()
