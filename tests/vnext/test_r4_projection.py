"""R4 presentation/compatibility bounds and real zero-source native Runs.

The narrow Run tests do not issue a release capability or simulate a completed
qualification. The integrator separately exercises the full private context.
"""

from copy import deepcopy
import csv
import io
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_issue28_v2 import clone_authority
from vnext.canonical import atomic_write_json, content_hash, strict_json_file
from vnext.requirements import load_requirement_snapshot
from vnext.r4_projection import POLICY_PATH, R4ProjectionError, build_r4_projection
from vnext.r4_projection import _load_presentation, _validate_grid, _production_runs
from vnext.r4_projection import _structural_run, _compatibility
from vnext.specs import compile_spec_file
from vnext.traits import repository_company_traits


def specs_at(root):
    return {path.name.split("_", 1)[0]: compile_spec_file(path=path, dependency_specs={})
            for path in sorted((root / "catalog/r4_v2").glob("*.md"))}


def registry_at(root):
    with (root / "config/company_registry.csv").open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def presentation_copy(directory):
    root = Path(directory) / "repo"
    (root / "config").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / POLICY_PATH, root / POLICY_PATH)
    shutil.copytree(REPO_ROOT / "catalog/r4_v2", root / "catalog/r4_v2")
    return root


class R4ProjectionBoundaryTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("socket.socket", side_effect=AssertionError("NO_NETWORK"))
        self.socket = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.socket.assert_not_called)

    def test_public_projection_rejects_caller_mapping_before_any_write(self):
        for value in ({}, {"verified": True}, SimpleNamespace(mode="LIVE", root=REPO_ROOT)):
            with self.subTest(value=type(value).__name__), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "must-not-exist"
                with self.assertRaisesRegex(ValueError, "Caller mapping|release capability"):
                    build_r4_projection(value, destination)
                self.assertFalse(destination.exists())

    def test_presentation_retains_original_spec_bytes_and_native_numeric_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = presentation_copy(directory)
            specs = specs_at(root)
            before = deepcopy(specs)
            policy = _load_presentation(root=root, specs=specs, metric_ids=sorted(specs))
            self.assertEqual(before, specs)
            self.assertTrue(all(spec["compiled"]["legacy_projection"] == {} for spec in specs.values()))
            self.assertEqual(4, sum(row["compatibility_class"] == "STRICT_HISTORICAL_ANCHOR"
                                    for row in policy["metrics"].values()))
            self.assertEqual(2, sum(row["compatibility_class"] == "APPROVED_NATIVE_BACKFILL"
                                    for row in policy["metrics"].values()))

    def test_rebound_presentation_semantic_relaxations_and_wrong_spec_fail(self):
        changes = (
            lambda p: p["metrics"]["A03"]["projection"].update(value_multiplier="100"),
            lambda p: p["metrics"]["A03"]["projection"].update(unit="USD"),
            lambda p: p["metrics"]["A11"]["projection"].update(evidence_unit_policy="projected_result"),
            lambda p: p["metrics"]["A13"].update(spec_semantic_hash="sha256:" + "0" * 64),
            lambda p: p["metrics"]["A12"].update(spec_path="catalog/r4_v2/A03_liquidity_coverage_ratio.md"),
            lambda p: p["metric_ids"].append("B06"),
            lambda p: p.update(legacy_metadata_fallback_allowed=True),
            lambda p: p["compatibility_field_categories"].update(value="IGNORE"),
        )
        for index, change in enumerate(changes):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                root = presentation_copy(directory)
                specs = specs_at(root)
                policy = strict_json_file(path=root / POLICY_PATH)
                change(policy)
                atomic_write_json(path=root / POLICY_PATH, value=policy)
                with self.assertRaises(R4ProjectionError):
                    _load_presentation(root=root, specs=specs, metric_ids=sorted(specs))

    def test_complete_grid_rejects_missing_duplicate_extra_and_false_applicability(self):
        specs = specs_at(REPO_ROOT)
        registry = registry_at(REPO_ROOT)
        expected = []
        for company in registry:
            applicable = "financial" in repository_company_traits(repo_root=REPO_ROOT,
                                                                  company_id=company["company_id"])
            for metric in sorted(specs):
                expected.append({"company_id": company["company_id"], "metric_id": metric,
                    "applicability": "APPLICABLE" if applicable else "N_A_STRUCTURAL"})
        context = SimpleNamespace(root=REPO_ROOT, registry=registry, specs=specs, expected_keys=expected)
        policy = _load_presentation(root=REPO_ROOT, specs=specs, metric_ids=sorted(specs))
        _, _, grid = _validate_grid(context=context, policy=policy)
        self.assertEqual(6, list(grid.values()).count("APPLICABLE"))
        self.assertEqual(54, list(grid.values()).count("N_A_STRUCTURAL"))
        for mutation in ("missing", "duplicate", "extra", "applicability"):
            candidate = deepcopy(expected)
            if mutation == "missing":
                candidate.pop()
            elif mutation == "duplicate":
                candidate.append(deepcopy(candidate[0]))
            elif mutation == "extra":
                candidate[0]["metric_id"] = "B06"
            else:
                candidate[0]["applicability"] = "APPLICABLE"
            with self.subTest(mutation=mutation), self.assertRaises(R4ProjectionError):
                _validate_grid(context=SimpleNamespace(root=REPO_ROOT, registry=registry,
                    specs=specs, expected_keys=candidate), policy=policy)

    def test_alternate_or_stability_selection_is_rejected_before_loading_run(self):
        specs = specs_at(REPO_ROOT)
        policy = _load_presentation(root=REPO_ROOT, specs=specs, metric_ids=sorted(specs))
        requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_28_v2")
        expected = {("jpmorgan_chase", metric): "APPLICABLE" for metric in specs}
        for fixture_id in ("r4_a03_alternate", "r4_a03_production_stability"):
            entries = [{"company_id": "jpmorgan_chase", "metric_id": metric,
                        "fixture_id": fixture_id if metric == "A03" else "r4_" + metric.lower() + "_production"}
                       for metric in sorted(specs)]
            context = SimpleNamespace(root=REPO_ROOT, requirement=requirement, production_runs=entries)
            with self.subTest(fixture_id=fixture_id), self.assertRaisesRegex(R4ProjectionError, "alternate or stability"):
                _production_runs(context=context, policy=policy, expected=expected)

    def test_native_structural_runs_freeze_and_replay_all_six_original_specs(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = clone_authority(directory)
            root = snapshot.parent.parent
            shutil.copy2(REPO_ROOT / POLICY_PATH, root / POLICY_PATH)
            specs = specs_at(root)
            policy = _load_presentation(root=root, specs=specs, metric_ids=sorted(specs))
            requirement = load_requirement_snapshot(snapshot_dir=snapshot)
            context = SimpleNamespace(root=root, specs=specs, requirement=requirement,
                target_period={"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"},
                release_context_id=content_hash(value={"test_only": "structural native primitive"}))
            traits = repository_company_traits(repo_root=root, company_id="marriott_international")
            for metric_id in sorted(specs):
                with self.subTest(metric_id=metric_id):
                    run_dir, (manifest, records), binding = _structural_run(context=context,
                        workspace=root / "test-projection", company_id="marriott_international",
                        metric_id=metric_id, traits=traits, policy=policy)
                    self.assertEqual("SUCCESSOR_RUN", manifest["record_type"])
                    self.assertEqual("FROZEN", manifest["status"])
                    self.assertEqual([], manifest["source_references"])
                    self.assertEqual([], manifest["task_contract_bindings"])
                    self.assertEqual(["METRIC_RESULT", "EXECUTION_TRACE"], [r["record_type"] for r in records])
                    self.assertEqual("N_A_STRUCTURAL", records[0]["applicability"])
                    self.assertIsNone(records[0]["value"])
                    self.assertEqual([], records[1]["input_observation_ids"])
                    self.assertEqual(specs[metric_id]["spec_closure_hash"], records[0]["spec_closure_hash"])
                    self.assertEqual("NATIVE_STRUCTURAL", binding["kind"])
                    self.assertTrue((run_dir / "validation.json").is_file())
                    context._read_only = True
                    before = {path.relative_to(run_dir).as_posix(): path.read_bytes()
                              for path in run_dir.rglob("*") if path.is_file()}
                    replay_dir, _, replay_binding = _structural_run(context=context,
                        workspace=root / "test-projection", company_id="marriott_international",
                        metric_id=metric_id, traits=traits, policy=policy)
                    self.assertEqual(run_dir, replay_dir)
                    self.assertEqual(binding, replay_binding)
                    self.assertEqual(before, {path.relative_to(run_dir).as_posix(): path.read_bytes()
                                             for path in run_dir.rglob("*") if path.is_file()})
                    context._read_only = False

    def test_read_only_projection_cannot_create_missing_structural_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = presentation_copy(directory)
            specs = specs_at(root)
            policy = _load_presentation(root=root, specs=specs, metric_ids=sorted(specs))
            requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_28_v2")
            context = SimpleNamespace(root=root, specs=specs, requirement=requirement, _read_only=True,
                target_period={"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"},
                release_context_id=content_hash(value={"test_only": "read-only structural primitive"}))
            workspace = root / "must-not-exist"
            with self.assertRaisesRegex(R4ProjectionError, "Read-only.*missing structural"):
                _structural_run(context=context, workspace=workspace, company_id="marriott_international",
                    metric_id="A03", traits=["lodging", "non_financial"], policy=policy)
            self.assertFalse(workspace.exists())


class R4CompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.specs = specs_at(REPO_ROOT)
        self.policy = _load_presentation(root=REPO_ROOT, specs=self.specs, metric_ids=sorted(self.specs))
        all_rows = list(csv.DictReader(io.StringIO((REPO_ROOT / "outputs/metrics_matrix.csv").read_text())))
        all_evidence = list(csv.DictReader(io.StringIO((REPO_ROOT / "outputs/metric_evidence.csv").read_text())))
        self.old = [row for row in all_rows if row["metric_id"] in self.specs]
        self.retained = [next(row for row in all_rows if row["metric_id"] not in self.specs)]
        self.evidence = [next(row for row in all_evidence if row["metric_id"] not in self.specs)]
        self.evidence += [row for row in all_evidence if row["metric_id"] in self.specs]
        self.rows = deepcopy(self.old)
        backfill = {"A09": ("0.0066", "ratio"), "A13": ("42758000000", "USD")}
        for row in self.rows:
            if row["metric_id"] in backfill:
                row["value"], row["unit"] = backfill[row["metric_id"]]
            row["metric_name"] = self.specs[row["metric_id"]]["compiled"]["name"]
            row["fiscal_year"] = "2025"
            row["status"] = "MDA_OK"
        self.indexes = {"results": {("jpmorgan_chase", row["metric_id"]): {
            "company_id": "jpmorgan_chase", "applicability": "APPLICABLE", "value": row["value"], "unit": row["unit"]}
            for row in self.rows}}
        self.projected_evidence = deepcopy(self.evidence)
        template = next(row for row in self.evidence if row["metric_id"] == "A03")
        for metric_id, (value, unit) in backfill.items():
            self.projected_evidence.append({**template, "metric_id": metric_id,
                "unit": unit, "value_raw": value, "value_normalized": value})
        company = next(row for row in registry_at(REPO_ROOT) if row["company_id"] == "jpmorgan_chase")
        self.registry = {company["company_id"]: company}

    def compare(self, *, rows=None, retained=None, evidence=None, old=None):
        return _compatibility(policy=self.policy, predecessor_rows=self.retained + (old or self.old),
            predecessor_evidence=self.evidence, rendered_rows=rows or self.rows,
            projected_rows=(retained or self.retained) + (rows or self.rows),
            projected_evidence=evidence or self.projected_evidence, indexes=self.indexes, registry=self.registry)

    def test_four_strict_anchors_and_two_native_backfills_are_distinct(self):
        receipt = self.compare()
        self.assertEqual("PASS", receipt["status"])
        self.assertEqual(4, receipt["strict_historical_anchor_count"])
        self.assertEqual(2, receipt["approved_native_backfill_count"])
        self.assertEqual("NONE", receipt["historical_legacy_anchor_credit_for_backfill"])
        self.assertEqual(6, len(receipt["evidence_replacements"]))

    def test_anchor_identity_period_value_unit_and_native_backfill_tampering_fail(self):
        for metric, field, value in (("A03", "value", "1.12"), ("A04", "unit", "USD"),
                                     ("A11", "period_start", "2024-01-01"), ("A12", "cik", "1"),
                                     ("A09", "value", "0.2"), ("A13", "unit", "shares")):
            rows = deepcopy(self.rows)
            next(row for row in rows if row["metric_id"] == metric)[field] = value
            with self.subTest(metric=metric, field=field), self.assertRaises(R4ProjectionError):
                self.compare(rows=rows)
        old = deepcopy(self.old)
        next(row for row in old if row["metric_id"] == "A09")["status"] = "MDA_OK"
        with self.assertRaisesRegex(R4ProjectionError, "approved missing-value predecessor"):
            self.compare(old=old)

    def test_retained_metric_and_evidence_bytes_cannot_change(self):
        retained = deepcopy(self.retained)
        retained[0]["notes"] += " changed"
        with self.assertRaisesRegex(R4ProjectionError, "retained"):
            self.compare(retained=retained)
        evidence = deepcopy(self.projected_evidence)
        evidence[0]["evidence_quote"] += " changed"
        with self.assertRaisesRegex(R4ProjectionError, "retained"):
            self.compare(evidence=evidence)
        evidence = deepcopy(self.projected_evidence)
        next(row for row in evidence if row["metric_id"] == "A03")["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(R4ProjectionError, "anchor evidence"):
            self.compare(evidence=evidence)


if __name__ == "__main__":
    unittest.main()
