"""Verify the SIC × Metrics map and the Metrics definition table.

Purpose:
    Prove the reference generator is deterministic, self-contained, and that
    its output matches independent expectations about representative metrics
    (B03 reuse/fallback/guards, lodging KPIs, event and text methods, version
    selection), and that malformed inputs are rejected instead of silently
    accepted.  Every negative case runs against a temporary copy that holds
    only the declared inputs, so no repository or Git state is touched.

Call relationships:
    ``tools/generate_metrics_reference.py`` is imported directly.  The CI
    workflow ``.github/workflows/metrics-reference.yml`` runs this module and
    the generator's ``--check`` mode.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "tools" / "generate_metrics_reference.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_metrics_reference", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


generator = _load_generator()
ReferenceError = generator.ReferenceError


def _read_json(relative: str):
    return json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))


def _declared_inputs():
    return sorted(_read_json("catalog/reference/source_selection.json")["inputs"])


def _copy_declared_inputs(target: Path) -> None:
    """Copy only the declared inputs and the reference directory into ``target``."""
    relatives = list(_declared_inputs()) + [
        "catalog/reference/source_selection.json",
        "catalog/reference/metric_metadata.json",
        "catalog/reference/sic_metric_rules.json",
    ]
    for relative in relatives:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, destination)
    generated = REPO_ROOT / "catalog" / "reference" / "generated"
    for path in sorted(generated.iterdir()):
        destination = target / "catalog" / "reference" / "generated" / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)


class _TempCopy:
    """Context manager that yields a clean temporary copy of the declared inputs."""

    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory(prefix="metrics_reference_")
        root = Path(self._directory.name)
        _copy_declared_inputs(root)
        return root

    def __exit__(self, *_exc) -> None:
        self._directory.cleanup()


def _edit_json(root: Path, relative: str, mutate) -> None:
    path = root / relative
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class GeneratedTablesTest(unittest.TestCase):
    """Committed generated tables equal generator output and stay self-contained."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.built = generator.build_reference(REPO_ROOT, verify_digests=True)
        cls.sic_map = _read_json("catalog/reference/generated/sic_metric_map.json")
        cls.definitions = _read_json("catalog/reference/generated/metric_definitions.json")
        cls.by_metric = {record["metric_id"]: record for record in cls.definitions["metrics"]}

    def test_check_mode_matches_committed_files(self) -> None:
        self.assertEqual([], generator.check_reference(REPO_ROOT))

    def test_clean_copy_with_only_declared_inputs_reproduces_bytes(self) -> None:
        with _TempCopy() as root:
            self.assertFalse((root / ".git").exists())
            self.assertFalse((root / "outputs").exists())
            rebuilt = generator.build_reference(root, verify_digests=True)["files"]
            for relative, payload in self.built["files"].items():
                self.assertEqual(payload, rebuilt[relative], relative)
                self.assertEqual(payload, (REPO_ROOT / relative).read_bytes(), relative)
            self.assertEqual([], generator.check_reference(root))

    def test_output_is_deterministic_and_free_of_local_paths(self) -> None:
        again = generator.build_reference(REPO_ROOT, verify_digests=True)["files"]
        self.assertEqual(self.built["files"], again)
        for relative, payload in again.items():
            text = payload.decode("utf-8")
            self.assertNotIn(str(REPO_ROOT), text, relative)
            self.assertNotIn("/Users/", text, relative)
            self.assertNotIn("/home/", text, relative)
            self.assertTrue(text.endswith("\n"), relative)
            self.assertNotIn("\r\n", text, relative)

    def test_exact_39_ids_and_complete_unique_grid(self) -> None:
        expected_ids = list(generator.EXPECTED_METRIC_IDS)
        self.assertEqual(39, len(expected_ids))
        self.assertEqual(expected_ids, [record["metric_id"] for record in self.definitions["metrics"]])
        ranges = [(item["sic_start"], item["sic_end"]) for item in self.sic_map["sic_ranges"]]
        self.assertEqual(10, len(ranges))
        self.assertEqual(len(ranges) * 39, self.sic_map["row_count"])
        keys = [(row["sic_start"], row["sic_end"], row["metric_id"]) for row in self.sic_map["rows"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(sorted(set(keys)), sorted((s, e, m) for s, e in ranges for m in expected_ids))
        for row in self.sic_map["rows"]:
            self.assertRegex(row["sic_start"], r"^\d{4}$")
            self.assertRegex(row["sic_end"], r"^\d{4}$")
            self.assertLessEqual(row["sic_start"], row["sic_end"])
            self.assertIn(row["business_applicability"], generator.APPLICABILITY_VALUES)
            self.assertIn(row["structural_applicability"], generator.STRUCTURAL_VALUES)
            if row["business_applicability"] in ("APPLICABLE", "CONDITIONAL"):
                self.assertIn(row["business_priority"], generator.PRIORITY_VALUES)
            else:
                self.assertIsNone(row["business_priority"])
            if row["business_applicability"] != "APPLICABLE":
                self.assertTrue(row["condition_zh"], row)
            if row["structural_applicability"] == "STRUCTURAL_NOT_APPLICABLE":
                self.assertEqual("NOT_APPLICABLE", row["business_applicability"], row)
        self.assertEqual("PENDING_CONFIRMATION", self.sic_map["unmatched_sic_policy"]["applicability"])
        self.assertEqual("default_non_fi", self.sic_map["unmatched_sic_policy"]["legacy_pipeline_default_profile"])
        for record in self.definitions["metrics"]:
            for field in ("name_en", "name_zh", "description_zh", "description_en", "definition_text_excerpt"):
                self.assertTrue(record[field], (record["metric_id"], field))
            self.assertTrue(record["statuses"]["expected"], record["metric_id"])
            self.assertTrue(record["data_sources"], record["metric_id"])
            self.assertIn(record["definition_source"]["kind"], generator.DEFINITION_SOURCE_KINDS)

    def test_applicable_sic_ranges_are_derived_from_the_map(self) -> None:
        for record in self.definitions["metrics"]:
            expected = [
                {
                    "sic_start": row["sic_start"],
                    "sic_end": row["sic_end"],
                    "profile": row["profile"],
                    "applicability": row["business_applicability"],
                    "priority": row["business_priority"],
                    "rule_clause_id": row["rule_clause_id"],
                }
                for row in self.sic_map["rows"]
                if row["metric_id"] == record["metric_id"] and row["business_applicability"] != "NOT_APPLICABLE"
            ]
            self.assertEqual(expected, record["applicable_sic_ranges"], record["metric_id"])

    def test_b03_reuses_b01_with_ordered_fallback_and_guards(self) -> None:
        record = self.by_metric["B03"]
        formula = record["formula"]
        self.assertEqual("((operating_income + depreciation_and_amortization) / revenue)", formula["expression"])
        self.assertEqual(["B01"], formula["dependencies"])
        inputs = {entry["role"]: entry for entry in formula["inputs"]}
        self.assertEqual("reuse_metric_observation", inputs["revenue"]["kind"])
        self.assertEqual("B01", inputs["revenue"]["reuses_metric"])
        branches = [(b["role"], b["branch_ordinal"], b["quality"], b.get("approved_concepts") or b.get("expression")) for b in formula["fallback_branches"]]
        self.assertEqual(
            [
                ("operating_income", 1, "EXACT", ["us-gaap:OperatingIncomeLoss"]),
                ("operating_income", 2, "APPROX", "(pretax - nonoperating)"),
                ("depreciation_and_amortization", 1, "EXACT", [
                    "us-gaap:DepreciationDepletionAndAmortization",
                    "us-gaap:DepreciationAmortizationAndAccretionNet",
                    "us-gaap:DepreciationAndAmortization",
                ]),
                ("depreciation_and_amortization", 2, "EXACT", "(depreciation + amortization)"),
            ],
            branches,
        )
        reconstructed = formula["fallback_branches"][1]
        self.assertEqual(["same_accession", "same_period", "same_entity", "compatible_units"], reconstructed["guards"])
        self.assertEqual("(revenue - costs_and_expenses)", reconstructed["cross_check"]["expected"])
        self.assertEqual("0.01", reconstructed["cross_check"]["relative_tolerance"])
        self.assertEqual(
            ["same_accession", "same_period", "same_entity", "compatible_units", {"annual_duration": [300, 400]}, "denominator_nonzero"],
            formula["top_level_guards"],
        )
        self.assertEqual("ratio", record["unit"]["canonical_unit"])
        self.assertEqual("current_annual", record["period_and_scope"]["period_role"])
        self.assertEqual("ACTIVE_VNEXT_RELEASE_R3", record["implementation_status"]["vnext"]["vnext_release_state"])
        self.assertEqual("LEGACY_PRODUCER_RETIRED_FAIL_CLOSED", record["implementation_status"]["legacy_pipeline"]["producer_state"])
        b01 = self.by_metric["B01"]
        self.assertEqual("preserve_reported", b01["unit"]["unit_policy"])
        self.assertEqual(
            ["us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "us-gaap:Revenues", "us-gaap:SalesRevenueNet", "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax"],
            b01["data_sources"][0]["concepts"],
        )

    def test_lodging_kpis_apply_only_to_the_lodging_range(self) -> None:
        for metric_id, unit in (("B10", ("ratio", "percent")), ("B11", ("USD", "USD"))):
            record = self.by_metric[metric_id]
            self.assertEqual(unit, (record["unit"]["canonical_unit"], record["unit"]["reported_unit"]))
            self.assertEqual(
                {"property_population": "comparable", "operating_scope": "systemwide", "geography": "worldwide"},
                record["period_and_scope"]["entity_or_business_scope"],
            )
            self.assertEqual("current_fiscal_year", record["period_and_scope"]["period_role"])
            rows = [row for row in self.sic_map["rows"] if row["metric_id"] == metric_id]
            applicable = [(row["sic_start"], row["sic_end"], row["business_priority"]) for row in rows if row["business_applicability"] == "APPLICABLE"]
            self.assertEqual([("7010", "7019", "CORE")], applicable)
            for row in rows:
                if row["profile"] != "lodging":
                    self.assertEqual(("NOT_APPLICABLE", "STRUCTURAL_NOT_APPLICABLE"), (row["business_applicability"], row["structural_applicability"]))
            self.assertEqual(["AI_TABLE_READ"], record["method"]["reference_implementation"]["method_types"])
            self.assertEqual("table", record["method"]["registry_target_route"]["ai_fallback_representation"])
            self.assertEqual(["table_claim"], [source["role"] for source in record["data_sources"]])
        self.assertEqual("(adr * occupancy)", generator._render_expression({"op": "multiply", "args": ["adr", "occupancy"]}))

    def test_financial_metrics_only_for_commercial_banks(self) -> None:
        for row in self.sic_map["rows"]:
            metric_id = row["metric_id"]
            if metric_id.startswith("A"):
                expected = "APPLICABLE" if row["profile"] == "financial_institution" else "NOT_APPLICABLE"
                self.assertEqual(expected, row["business_applicability"], row)
            if metric_id in {"B01", "B02", "B03", "B04", "B05", "B07", "B08", "B09"} and row["profile"] == "financial_institution":
                self.assertEqual("NOT_APPLICABLE", row["business_applicability"], row)
            if metric_id[0] in "CDE":
                self.assertEqual("APPLICABLE", row["business_applicability"], row)
        b13 = {row["profile"]: row["business_applicability"] for row in self.sic_map["rows"] if row["metric_id"] == "B13"}
        self.assertEqual("CONDITIONAL", b13["manufacturing"])
        self.assertEqual("NOT_APPLICABLE", b13["financial_institution"])
        self.assertEqual("PENDING_CONFIRMATION", b13["pharma"])

    def test_event_and_text_methods_do_not_invent_tags_or_formulas(self) -> None:
        e01 = self.by_metric["E01"]
        self.assertEqual(["EVENT_ITEM_RULE"], e01["method"]["reference_implementation"]["method_types"])
        self.assertIsNone(e01["method"]["registry_target_route"]["ai_fallback_representation"])
        self.assertIsNone(e01["formula"])
        self.assertEqual("event_count", e01["unit"]["canonical_unit"])
        roles = {source["role"]: source for source in e01["data_sources"]}
        self.assertEqual(["1.01", "2.01"], roles["direct_item_codes"]["item_codes"])
        self.assertEqual(["8.01"], roles["keyword_item_rule"]["item_codes"])
        self.assertEqual(["merger", "acquisition", "combine", "transaction"], roles["keyword_item_rule"]["keywords"])
        self.assertEqual("NOT_AVAILABLE_SEC", roles["zero_hit_projection"]["status"])
        self.assertEqual("fiscal_year_window_8k", e01["period_and_scope"]["period_role"])
        for metric_id in ("C02", "D01", "D02", "D03", "D04"):
            record = self.by_metric[metric_id]
            self.assertIsNone(record["formula"], metric_id)
            self.assertIsNone(record["unit"]["canonical_unit"], metric_id)
            self.assertEqual("MAIN_TEXT_DEFINITION", record["definition_source"]["kind"])
            concept_sources = [source for source in record["data_sources"] if source.get("concepts")]
            self.assertEqual([], concept_sources, metric_id)
        d03 = self.by_metric["D03"]
        self.assertEqual(["investigation|subpoena|inquiry|regulatory|SEC|DOJ|FTC|FDA"], d03["data_sources"][0]["patterns"])
        self.assertEqual(["TEXT_QUAL", "NOT_AVAILABLE_SEC"], d03["statuses"]["expected"])
        self.assertEqual([], d03["definition_source"]["development_references"])
        d04 = self.by_metric["D04"]
        self.assertEqual(["going concern|substantial doubt"], d04["data_sources"][0]["patterns"])
        c04 = self.by_metric["C04"]
        self.assertEqual("flag_0_or_1", c04["unit"]["canonical_unit"])
        self.assertEqual(["dei:AuditorName"], c04["data_sources"][0]["concepts"])
        self.assertEqual(["4.01"], c04["data_sources"][1]["item_codes"])
        c03 = self.by_metric["C03"]
        self.assertEqual("USD", c03["unit"]["canonical_unit"])
        self.assertEqual(["ecd:PeoTotalCompAmt"], c03["data_sources"][0]["concepts"])
        legacy_pipeline = (REPO_ROOT / "scripts" / "sec_pipeline.py").read_text(encoding="utf-8")
        for record in self.definitions["metrics"]:
            for citation in record["implementation_status"]["legacy_pipeline"]["citations"]:
                if citation["path"] == "scripts/sec_pipeline.py":
                    for literal in citation["literals"]:
                        self.assertIn(literal, legacy_pipeline, (record["metric_id"], literal))

    def test_version_selection_follows_explicit_bindings(self) -> None:
        active = _read_json("config/release_plans/issue_15_lodging_r3.json")["cumulative_metric_ids"]
        self.assertEqual(24, len(active))
        r5 = _read_json("config/r5_b06_structured_v1.json")
        for record in self.definitions["metrics"]:
            metric_id = record["metric_id"]
            source = record["definition_source"]
            state = record["implementation_status"]["vnext"]["vnext_release_state"]
            if metric_id in active:
                self.assertEqual("active_release_r3", source["binding_authority"], metric_id)
                self.assertEqual("ACTIVE_VNEXT_RELEASE_R3", state, metric_id)
            elif metric_id in {"A03", "A04", "A09", "A11", "A12", "A13"}:
                self.assertTrue(source["primary"]["path"].startswith("catalog/r4_v2/"), metric_id)
                self.assertEqual("R4_OFFLINE_PLAN_NOT_ACTIVE", state, metric_id)
                self.assertEqual(["issue15_table_contract_historical"], [variant["role"] for variant in source["variants"]])
            elif metric_id == "B06":
                self.assertEqual(r5["primary_spec"], source["primary"]["path"])
                self.assertFalse(r5["production_authorized"])
                self.assertEqual("R5_STRUCTURED_DRAFT_NOT_AUTHORIZED", state)
                self.assertEqual("current_instant", record["period_and_scope"]["period_role"])
                self.assertEqual("(debt / equity)", record["formula"]["expression"])
                self.assertIn("denominator_positive", record["formula"]["top_level_guards"])
            elif metric_id == "B13":
                self.assertEqual("issue15_table_contracts", source["binding_authority"])
                self.assertEqual("NOT_IN_VNEXT_RELEASE_PLAN", state)
            else:
                self.assertEqual("MAIN_TEXT_DEFINITION", source["kind"], metric_id)
                self.assertEqual("NOT_IN_VNEXT_RELEASE_PLAN", state, metric_id)
            for reference in source["development_references"]:
                self.assertEqual("8346c326f04be5a863dc8bf2f010087a6f2025a3", reference["commit"])
                self.assertFalse(reference["verified_by_generator"])
                self.assertRegex(reference["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual("International net revenue", self.by_metric["A13"]["name_en"])
        self.assertEqual("Geographic exposure", self.by_metric["A13"]["definition_source"]["variants"][0]["name"])
        self.assertTrue(self.definitions["not_a_production_pointer"])

    def test_deterministic_formula_templates_match_the_evaluator(self) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from scripts.vnext.zero_ai_r2 import _formula_value
        finally:
            sys.path.pop(0)
        samples = [Decimal("7"), Decimal("3"), Decimal("5")]
        for (formula_id, arity), template in generator.DETERMINISTIC_FORMULA_TEMPLATES.items():
            names = ["v{}".format(index) for index in range(arity)]
            expression = template.format(*names)
            namespace = {name: value for name, value in zip(names, samples)}
            expected = eval(expression, {"__builtins__": {}}, namespace)  # noqa: S307 - fixed test expression
            actual = _formula_value(formula_id=formula_id, values=samples[:arity])
            self.assertEqual(Decimal(str(expected)).normalize(), actual.normalize(), (formula_id, arity))
        self.assertEqual("net_income / ((assets_current + assets_prior) / 2)", self.by_metric["A05"]["formula"]["expression"])
        self.assertEqual("(revenue_current - revenue_prior) / revenue_prior", self.by_metric["B02"]["formula"]["expression"])
        self.assertEqual("REQUIRE_CONTINUOUS", self.by_metric["B02"]["period_and_scope"]["continuity_policy"])
        registry = _read_json("config/source_strategy_registry.json")
        for entry in registry["metrics"].values():
            if entry["structured_route_id"] is not None:
                self.assertIn(entry["structured_route_id"], generator.STRUCTURED_ROUTE_DESCRIPTIONS)

    def test_csv_views_are_derived_and_complete(self) -> None:
        with io.StringIO(self.built["files"]["catalog/reference/generated/sic_metric_map.csv"].decode("utf-8")) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(390, len(rows))
        self.assertEqual(generator.MAP_CSV_COLUMNS, list(rows[0]))
        with io.StringIO(self.built["files"]["catalog/reference/generated/metric_definitions.csv"].decode("utf-8")) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(39, len(rows))
        self.assertEqual(generator.DEFINITIONS_CSV_COLUMNS, list(rows[0]))

    def test_reference_directory_is_not_scanned_by_runtime_code(self) -> None:
        offenders = []
        for directory in ("scripts", "tools"):
            for path in sorted((REPO_ROOT / directory).rglob("*.py")):
                if path == GENERATOR_PATH:
                    continue
                text = path.read_text(encoding="utf-8")
                if "catalog/reference" in text or re.search(r'"catalog"\s*\)?\s*\.rglob', text):
                    offenders.append(path.relative_to(REPO_ROOT).as_posix())
        self.assertEqual([], offenders)


    def test_d04_method_and_route_are_not_inferred_from_route_ids(self) -> None:
        d04 = self.by_metric["D04"]
        method = d04["method"]
        self.assertEqual(["LEGACY_TEXT_KEYWORD_RULE"], method["reference_implementation"]["method_types"])
        target = method["registry_target_route"]
        self.assertEqual("structured_first_ai_fallback", target["source_mode"])
        self.assertEqual("auditor_fact_v1", target["structured_route_id"])
        self.assertEqual("NOT_BOUND_ON_MAIN", target["structured_concept_binding_on_main"])
        self.assertEqual("text", target["ai_fallback_representation"])
        self.assertEqual(
            "config/source_strategy_fallback_representation.json#fallback_representation_by_metric.D04",
            target["ai_fallback_representation_basis"],
        )
        authority = _read_json("config/source_strategy_fallback_representation.json")
        self.assertEqual({"A09": "table", "A13": "table", "B06": "table", "D04": "text"}, authority["fallback_representation_by_metric"])
        serialized = json.dumps(d04, ensure_ascii=False)
        self.assertNotIn("AuditorName", serialized)
        self.assertNotIn("AI_TABLE_READ", serialized)
        for source in d04["data_sources"]:
            self.assertEqual([], source.get("concepts", []), source)
        route_source = [source for source in d04["data_sources"] if source["role"] == "registry_structured_route"][0]
        self.assertEqual("NOT_BOUND_ON_MAIN", route_source["concept_binding_on_main"])
        c04 = self.by_metric["C04"]
        self.assertEqual(["LEGACY_XBRL_FACT_RULE", "LEGACY_8K_ITEM_RULE"], c04["method"]["reference_implementation"]["method_types"])
        self.assertEqual("LEGACY_CODE_CITATION", c04["method"]["registry_target_route"]["structured_concept_binding_on_main"])
        self.assertEqual(["dei:AuditorName"], c04["data_sources"][0]["concepts"])
        for record in self.definitions["metrics"]:
            target = record["method"]["registry_target_route"]
            description = target["structured_route_description"] or ""
            self.assertNotIn("dei:", description, record["metric_id"])
            self.assertNotIn("DEF 14A", description, record["metric_id"])
            for metric_id, representation in authority["fallback_representation_by_metric"].items():
                if record["metric_id"] == metric_id:
                    self.assertEqual(representation, target["ai_fallback_representation"])
            if "AI_TABLE_READ_FALLBACK" in record["method"]["reference_implementation"]["method_types"]:
                self.assertEqual("table", target["ai_fallback_representation"], record["metric_id"])
        contracts = _read_json("catalog/table_task_contracts.json")
        table_metric_ids = {metric_id for contract in contracts["contracts"] for metric_id in contract["metric_ids"]}
        for record in self.definitions["metrics"]:
            types = record["method"]["reference_implementation"]["method_types"]
            if any(kind.startswith("AI_TABLE_READ") for kind in types):
                self.assertIn(record["metric_id"], table_metric_ids, record["metric_id"])

    def test_bank_b06_follows_the_selected_r5_scope_not_the_legacy_grouping(self) -> None:
        policy = _read_json("config/r5_b06_structured_v1.json")
        scope = policy["debt_scope_definition"]
        self.assertTrue(scope["bank_scope"])
        self.assertIn("customer_deposits", scope["excluded"])
        self.assertFalse(policy["production_authorized"])
        evidence = _read_json("docs/evidence/r5_b06_scope/debt_scope_relationships.json")
        bank_entries = [entry for entry in evidence["relationships"] if entry.get("scope_class") == "bank_funding"]
        self.assertEqual(1, len(bank_entries))
        self.assertFalse(bank_entries[0]["complete"])
        self.assertIn("BANK_FINANCE_LEASE_COMPLETENESS_NOT_ESTABLISHED", bank_entries[0]["unresolved"])
        rows = [row for row in self.sic_map["rows"] if row["metric_id"] == "B06" and row["profile"] == "financial_institution"]
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(("CONDITIONAL", "SUPPLEMENTARY", "B06-fi"), (row["business_applicability"], row["business_priority"], row["rule_clause_id"]))
        self.assertIn("config/r5_b06_structured_v1.json#debt_scope_definition.bank_scope", row["basis"])
        self.assertIn("可比性限制", row["condition_zh"])
        self.assertIn("BANK_FINANCE_LEASE_COMPLETENESS_NOT_ESTABLISHED", row["condition_zh"])
        b06 = self.by_metric["B06"]
        self.assertIn(
            {"sic_start": "6020", "sic_end": "6029", "profile": "financial_institution", "applicability": "CONDITIONAL", "priority": "SUPPLEMENTARY", "rule_clause_id": "B06-fi"},
            b06["applicable_sic_ranges"],
        )
        self.assertEqual([], b06["industries_by_applicability"]["NOT_APPLICABLE"])
        for row in self.sic_map["rows"]:
            if row["business_applicability"] != "NOT_APPLICABLE":
                continue
            for basis in row["basis"]:
                self.assertTrue(basis.startswith(generator.DEFINITION_LEVEL_BASIS_PREFIXES), (row["metric_id"], row["profile"], basis))
                for marker in generator.IMPLEMENTATION_STATE_MARKERS:
                    self.assertNotIn(marker, basis, (row["metric_id"], row["profile"], basis))
        d04 = self.by_metric["D04"]
        self.assertIn("有界的短语未命中", d04["description_zh"])
        self.assertIn("bounded phrase miss", d04["description_en"])

    def test_primary_provenance_matches_declared_and_parsed_sources(self) -> None:
        selection = _read_json("catalog/reference/source_selection.json")
        for record in self.definitions["metrics"]:
            primary = record["definition_source"]["primary"]
            payload = (REPO_ROOT / primary["path"]).read_bytes()
            self.assertEqual(generator.sha256_bytes(payload), primary["sha256"], record["metric_id"])
            role = selection["inputs"][primary["path"]]["role"]
            self.assertIn(role, generator.PRIMARY_ROLES_BY_KIND[record["definition_source"]["kind"]], record["metric_id"])
            if record["definition_source"]["kind"] == "MAIN_DETERMINISTIC_CATALOG":
                self.assertIn(record["metric_id"], json.loads(payload)["metrics"])
            if record["definition_source"]["kind"] == "MAIN_EVENT_ROUTE":
                self.assertIn(record["metric_id"], json.loads(payload)["routes"])
            if record["definition_source"]["kind"] == "MAIN_TEXT_DEFINITION":
                self.assertIn("### {} ".format(record["metric_id"]), payload.decode("utf-8"))
            excerpt_source = record["definition_text_excerpt_source"]
            self.assertEqual(generator.sha256_bytes((REPO_ROOT / excerpt_source["path"]).read_bytes()), excerpt_source["sha256"])


def self_built_files():
    """Return the committed generated bytes keyed by relative path."""
    return {
        relative: (REPO_ROOT / relative).read_bytes()
        for relative in (
            "catalog/reference/generated/metric_definitions.csv",
            "catalog/reference/generated/metric_definitions.json",
            "catalog/reference/generated/sic_metric_map.csv",
            "catalog/reference/generated/sic_metric_map.json",
        )
    }


class NegativeCasesTest(unittest.TestCase):
    """Malformed inputs, drift and tampering fail loudly."""

    def _assert_error(self, mutate, message: str, relative: str = "catalog/reference/sic_metric_rules.json") -> None:
        with _TempCopy() as root:
            _edit_json(root, relative, mutate)
            with self.assertRaisesRegex(ReferenceError, message):
                generator.build_reference(root, verify_digests=True)

    def test_source_drift_is_rejected(self) -> None:
        with _TempCopy() as root:
            path = root / "catalog" / "metrics" / "B01_revenue.md"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ReferenceError, "(?s)SOURCE_DRIFT.*B01_revenue"):
                generator.build_reference(root, verify_digests=True)

    def _calculator_variant(self, transform):
        """Run build_reference on a temp copy whose calculator.py is transformed."""
        with _TempCopy() as root:
            path = root / "scripts" / "vnext" / "calculator.py"
            original = path.read_text(encoding="utf-8")
            edited = transform(original)
            self.assertNotEqual(original, edited)
            path.write_text(edited, encoding="utf-8")
            return generator.build_reference(root, verify_digests=True)

    def test_code_digest_scope_ignores_unrelated_additions(self) -> None:
        built = self._calculator_variant(lambda text: text + "\n\ndef _unrelated_helper_added_by_test():\n    return None\n")
        self.assertEqual(self_built_files(), built["files"])

    def test_code_digest_scope_detects_plain_body_change(self) -> None:
        with self.assertRaisesRegex(ReferenceError, "(?s)SOURCE_DRIFT.*calculator.py.*scope cited_symbols"):
            self._calculator_variant(lambda text: text.replace(
                "    return set(applicability[\"all\"]).issubset(trait_set) and not (",
                "    return set(applicability[\"all\"]).issubset(trait_set) and not (  # edited",
            ))

    def test_code_digest_scope_detects_added_decorator(self) -> None:
        def transform(text: str) -> str:
            return text.replace(
                "def metric_is_applicable(",
                "def _wrap_added_by_test(function):\n    return function\n\n\n@_wrap_added_by_test\ndef metric_is_applicable(",
                1,
            )
        with self.assertRaisesRegex(ReferenceError, "(?s)SOURCE_DRIFT.*calculator.py.*scope cited_symbols"):
            self._calculator_variant(transform)

    def test_code_digest_scope_rejects_duplicate_definition(self) -> None:
        duplicate = "\n\ndef metric_is_applicable(*, applicability, traits):\n    return True\n"
        with self.assertRaisesRegex(ReferenceError, "metric_is_applicable is bound 2 times at top level"):
            self._calculator_variant(lambda text: text + duplicate)

    def test_code_digest_scope_rejects_direct_rebinding(self) -> None:
        rebinding = "\n\ndef _other_added_by_test(*, applicability, traits):\n    return False\n\n\nmetric_is_applicable = _other_added_by_test\n"
        with self.assertRaisesRegex(ReferenceError, "metric_is_applicable is bound 2 times at top level"):
            self._calculator_variant(lambda text: text + rebinding)

    def test_code_digest_scope_survives_column_zero_comment_inside_body(self) -> None:
        def transform(text: str) -> str:
            marker = "    trait_set = set(traits)\n"
            self.assertIn(marker, text)
            return text.replace(marker, "# column-zero comment added by test\n    trait_set = set(list(traits))\n", 1)
        with self.assertRaisesRegex(ReferenceError, "(?s)SOURCE_DRIFT.*calculator.py.*scope cited_symbols"):
            self._calculator_variant(transform)

    def test_symbol_block_includes_decorators_and_uses_parser_end_lines(self) -> None:
        source = (
            "import functools\n\n"
            "@functools.lru_cache(maxsize=None)\n"
            "def target(value):\n"
            "    \"\"\"doc\"\"\"\n"
            "# column-zero comment inside the body\n"
            "    return value + 1\n\n\n"
            "def other():\n    return target\n"
        )
        block = generator._symbol_block(source, "target", "test")
        self.assertTrue(block.startswith("@functools.lru_cache"))
        self.assertIn("return value + 1", block)
        self.assertNotIn("def other", block)
        with self.assertRaisesRegex(ReferenceError, "bound 2 times"):
            generator._symbol_block(source + "\ntarget = other\n", "target", "test")
        with self.assertRaisesRegex(ReferenceError, "not defined at top level"):
            generator._symbol_block("if True:\n    def target():\n        return 1\n", "target", "test")
        with self.assertRaisesRegex(ReferenceError, "not parseable Python"):
            generator._symbol_block("def broken(:\n", "target", "test")

    def test_code_target_without_cited_symbol_scope_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["inputs"]["scripts/vnext/calculator.py"].pop("digest_scope"),
            "digest_scope cited_symbols",
            relative="catalog/reference/source_selection.json",
        )

    def test_missing_digest_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["inputs"]["catalog/event_routes.json"].__setitem__("sha256", None),
            "no recorded digest",
            relative="catalog/reference/source_selection.json",
        )

    def test_tampered_generated_file_fails_check(self) -> None:
        with _TempCopy() as root:
            path = root / "catalog" / "reference" / "generated" / "metric_definitions.json"
            path.write_bytes(path.read_bytes().replace(b"EBITDA margin", b"EBITDA margin (edited)", 1))
            problems = generator.check_reference(root)
            self.assertEqual(["catalog/reference/generated/metric_definitions.json: committed bytes differ from generator output"], problems)

    def test_missing_metric_rule_is_rejected(self) -> None:
        self._assert_error(lambda payload: payload["metric_rules"].pop("D03"), "exactly the 39 metric IDs")

    def test_unknown_metric_rule_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["metric_rules"].__setitem__("Z99", payload["metric_rules"]["D03"]),
            "exactly the 39 metric IDs",
        )

    def test_duplicate_clause_id_is_rejected(self) -> None:
        def mutate(payload):
            clauses = payload["metric_rules"]["A01"]["clauses"]
            clauses[1]["clause_id"] = clauses[0]["clause_id"]
        self._assert_error(mutate, "duplicate clause_id")

    def test_default_clause_must_be_last(self) -> None:
        def mutate(payload):
            payload["metric_rules"]["A01"]["clauses"].reverse()
        self._assert_error(mutate, "DEFAULT clause must be last")

    def test_business_applicable_cannot_override_structural_inapplicability(self) -> None:
        def mutate(payload):
            default = payload["metric_rules"]["A01"]["clauses"][-1]
            default["applicability"] = "APPLICABLE"
            default["priority"] = "CORE"
        self._assert_error(mutate, "structurally inapplicable")

    def test_incomplete_evidence_cannot_be_encoded_as_not_applicable(self) -> None:
        def mutate(payload):
            clause = [c for c in payload["metric_rules"]["B06"]["clauses"] if c["clause_id"] == "B06-fi"][0]
            clause["applicability"] = "NOT_APPLICABLE"
            clause["priority"] = None
        self._assert_error(mutate, "NOT_APPLICABLE clause B06-fi needs a definition-level basis")

    def test_not_applicable_basis_may_not_cite_authorization_state(self) -> None:
        def mutate(payload):
            clause = payload["metric_rules"]["B08"]["clauses"][-1]
            clause["basis"] = ["catalog/deterministic_metrics.json#metrics.B08.applicability (production_authorized=false)"]
        self._assert_error(mutate, "cites an implementation/authorization state")
        self._assert_error(
            lambda payload: payload["metric_rules"]["B08"]["clauses"][-1].__setitem__("basis", ["config/r5_b06_structured_v1.json#production_authorized"]),
            "needs a definition-level basis",
        )

    def test_unknown_trait_reference_is_rejected(self) -> None:
        def mutate(payload):
            payload["metric_rules"]["B10"]["clauses"][0]["when"] = {"traits_all": ["hospitality"]}
        self._assert_error(mutate, "unknown traits_all")

    def test_conditional_without_condition_is_rejected(self) -> None:
        def mutate(payload):
            clause = payload["metric_rules"]["B13"]["clauses"][0]
            clause["condition_zh"] = None
        self._assert_error(mutate, "need condition_zh")

    def test_range_label_drift_is_rejected(self) -> None:
        self._assert_error(lambda payload: payload["sic_range_labels"].pop("7010-7019"), "sic_range_labels must match")

    def test_overlapping_sic_ranges_are_rejected(self) -> None:
        def mutate(payload):
            payload["profile_rules"].append({"sic_start": 7015, "sic_end": 7030, "profile": "lodging"})
        with _TempCopy() as root:
            _edit_json(root, "config/metric_applicability.yaml", mutate)
            with self.assertRaisesRegex(ReferenceError, "SOURCE_DRIFT"):
                generator.build_reference(root, verify_digests=True)
            generator.refresh_source_digests(root)
            with self.assertRaisesRegex(ReferenceError, "SIC ranges overlap"):
                generator.build_reference(root, verify_digests=True)

    def test_deterministic_primary_pointing_at_event_routes_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["A05"]["primary"].__setitem__("path", "catalog/event_routes.json"),
            "input role event_routes which is not allowed for MAIN_DETERMINISTIC_CATALOG",
            relative="catalog/reference/source_selection.json",
        )

    def test_declared_role_cannot_disguise_wrong_content(self) -> None:
        with _TempCopy() as root:
            disguised = root / "catalog" / "deterministic_metrics_copy.json"
            disguised.write_bytes((root / "catalog" / "event_routes.json").read_bytes())

            def mutate(payload):
                payload["inputs"]["catalog/deterministic_metrics_copy.json"] = {"sha256": None, "role": "deterministic_catalog"}
                payload["metrics"]["A05"]["primary"]["path"] = "catalog/deterministic_metrics_copy.json"
            _edit_json(root, "catalog/reference/source_selection.json", mutate)
            generator.refresh_source_digests(root)
            with self.assertRaisesRegex(ReferenceError, "is not a DETERMINISTIC_METRIC_CATALOG"):
                generator.build_reference(root, verify_digests=True)

    def test_event_primary_with_wrong_record_type_is_rejected(self) -> None:
        with _TempCopy() as root:
            disguised = root / "catalog" / "event_routes_copy.json"
            disguised.write_bytes((root / "catalog" / "deterministic_metrics.json").read_bytes())

            def mutate(payload):
                payload["inputs"]["catalog/event_routes_copy.json"] = {"sha256": None, "role": "event_routes"}
                payload["metrics"]["E01"]["primary"]["path"] = "catalog/event_routes_copy.json"
            _edit_json(root, "catalog/reference/source_selection.json", mutate)
            generator.refresh_source_digests(root)
            with self.assertRaisesRegex(ReferenceError, "is not a DETERMINISTIC_EVENT_ROUTE_CATALOG"):
                generator.build_reference(root, verify_digests=True)

    def test_text_primary_must_be_the_single_text_definition_input(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["C02"]["primary"].__setitem__("path", "catalog/reference/README.md" if False else "config/company_registry.csv"),
            "input role baseline_sample_companies which is not allowed for MAIN_TEXT_DEFINITION",
            relative="catalog/reference/source_selection.json",
        )
        with _TempCopy() as root:
            other = root / "docs_text_copy.md"
            other.write_text("# no sections here\n", encoding="utf-8")

            def mutate(payload):
                payload["inputs"]["docs_text_copy.md"] = {"sha256": None, "role": "text_definition"}
            _edit_json(root, "catalog/reference/source_selection.json", mutate)
            generator.refresh_source_digests(root)
            with self.assertRaisesRegex(ReferenceError, "Exactly one declared input must carry role text_definition"):
                generator.build_reference(root, verify_digests=True)

    def test_historical_spec_role_cannot_be_a_primary(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["B06"]["primary"].__setitem__("path", "catalog/r5/history/B06_structured_v1.md"),
            "role metric_spec_historical which is not allowed for MAIN_STRUCTURED_SPEC",
            relative="catalog/reference/source_selection.json",
        )

    def test_variant_path_with_non_spec_role_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["B06"]["variants"][0].__setitem__("path", "config/r5_b06_structured_v1.json"),
            "has role r5_policy which is not a spec role",
            relative="catalog/reference/source_selection.json",
        )

    def test_fallback_representation_authority_must_bind_the_registry(self) -> None:
        with _TempCopy() as root:
            _edit_json(root, "config/source_strategy_fallback_representation.json", lambda payload: payload.__setitem__("source_strategy_registry_sha256", "0" * 64))
            generator.refresh_source_digests(root)
            with self.assertRaisesRegex(ReferenceError, "bound to a different source_strategy_registry"):
                generator.build_reference(root, verify_digests=True)
        with _TempCopy() as root:
            _edit_json(root, "config/source_strategy_fallback_representation.json", lambda payload: payload["fallback_representation_by_metric"].__setitem__("D04", "table"))
            generator.refresh_source_digests(root)
            built = generator.build_reference(root, verify_digests=True)
            d04 = [record for record in built["metric_definitions"]["metrics"] if record["metric_id"] == "D04"][0]
            self.assertEqual("table", d04["method"]["registry_target_route"]["ai_fallback_representation"])

    def test_unselected_metric_version_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"].pop("B06"),
            "exactly the 39 metric IDs",
            relative="catalog/reference/source_selection.json",
        )

    def test_primary_spec_with_wrong_metric_id_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["B01"]["primary"].__setitem__("path", "catalog/metrics/B03_ebitda_margin.md"),
            "declares metric_id B03",
            relative="catalog/reference/source_selection.json",
        )

    def test_b06_primary_must_follow_r5_policy(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["B06"]["primary"].__setitem__("path", "catalog/metrics/B06_debt_to_equity.md"),
            "primary_spec",
            relative="catalog/reference/source_selection.json",
        )

    def test_missing_citation_literal_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["D04"]["legacy_method"]["citations"][0]["literals"].append("substantial doubt about liquidity"),
            "literal .* not found",
            relative="catalog/reference/metric_metadata.json",
        )

    def test_unknown_symbol_citation_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["D01"]["legacy_method"]["citations"][0].__setitem__("symbol", "stage_extract_risk_text_v2"),
            "is not defined at top level",
            relative="catalog/reference/metric_metadata.json",
        )

    def test_unknown_expected_status_is_rejected(self) -> None:
        self._assert_error(
            lambda payload: payload["metrics"]["B01"]["expected_statuses"].append("MAYBE_OK"),
            "not in the status vocabulary",
            relative="catalog/reference/metric_metadata.json",
        )

    def test_check_mode_writes_nothing(self) -> None:
        with _TempCopy() as root:
            before = {path: path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}
            self.assertEqual([], generator.check_reference(root))
            after = {path: path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
