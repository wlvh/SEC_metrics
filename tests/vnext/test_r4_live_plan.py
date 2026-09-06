"""R4 dry schedule identity/risk tests; no plan is a live authorization."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext.canonical import atomic_write_bytes, canonical_json_bytes, content_hash, strict_json_file
from vnext.r4_fixture_authority import load_r4_fixture_authority
from vnext.r4_live_plan import DRAFT_TYPE, R4DraftPlanContext, R4DraftPlanError
from vnext.r4_live_plan import _risk_features, _schedule
from vnext.r4_live_plan import build_r4_draft_plan, prepare_r4_draft_plan_context
from vnext.r4_live_plan import derive_r4_repository_schedule
from vnext.r4_live_plan import _derive_r4_repository_schedule_from_requirement
from vnext.r4_live_plan import validate_r4_draft_plan, load_r4_draft_plan
from vnext.requirements import load_requirement_snapshot


ROOT = Path(__file__).resolve().parents[2]


def real_eligible_shapes():
    """Read full committed corpus certificates; do not synthesize risk flags."""
    authority = load_r4_fixture_authority(repo_root=ROOT)
    index = strict_json_file(path=ROOT / "docs/r4_offline/qualified_cases/index.json")
    values = []
    for entry in index["cases"]:
        if entry["artifact_kind"] != "SCOPED_EXTRACTION":
            continue
        scope = strict_json_file(path=ROOT / entry["directory"] / "source_scope.json")
        recipe = authority["recipes"][entry["fixture_id"]]
        values.append({**{key: entry[key] for key in ("fixture_id", "fixture_class", "metric_id", "source_id")},
                       "risk_features": _risk_features(recipe, scope)})
    return values


class R4DraftPlanRiskTest(unittest.TestCase):
    def test_actual_certificate_risks_choose_exact_three_distinct_fresh_repeats(self):
        entries, selection = _schedule(real_eligible_shapes())
        self.assertEqual(len(entries), 12)
        self.assertEqual([entry["ordinal"] for entry in entries], list(range(1, 13)))
        self.assertEqual([entry["fixture_id"] for entry in entries[9:]],
                         ["r4_a03_alternate", "r4_a09_production", "r4_a12_alternate"])
        self.assertEqual([entry["repeats_base_ordinal"] for entry in entries[9:]], [2, 5, 9])
        self.assertEqual([entry["fixture_execution_ordinal"] for entry in entries], [1] * 9 + [2] * 3)
        self.assertTrue(all(entry["fresh_response_required"] and not entry["response_reuse_authorized"] for entry in entries))
        self.assertEqual(len({entry["draft_entry_id"] for entry in entries}), 12)
        self.assertEqual([row["new_risk_features"][0]["kind"] for row in selection],
                         ["ALTERNATE_DISCLOSED_PERIOD", "NO_INDEPENDENT_LEGACY_ANCHOR", "MIXED_TABLE_NARRATIVE_SCOPE"])

    def test_selection_is_order_independent_and_does_not_branch_on_issuer_identity(self):
        inputs = real_eligible_shapes()
        expected, expected_selection = _schedule(inputs)
        observed, observed_selection = _schedule(list(reversed(inputs)))
        self.assertEqual(observed, expected)
        self.assertEqual(observed_selection, expected_selection)
        renamed = [{**row, "source_id": "synthetic-source-" + str(index)} for index, row in enumerate(inputs)]
        changed, _ = _schedule(renamed)
        self.assertEqual([e["fixture_id"] for e in changed], [e["fixture_id"] for e in expected])

    def test_distinct_numeric_scales_remain_explicit_even_when_not_stability_selected(self):
        inputs = real_eligible_shapes()
        signatures = {(f["mechanism"], f["factor"], f["canonical_unit"])
                      for row in inputs for f in row["risk_features"] if f["kind"] == "NUMERIC_NORMALIZATION"}
        self.assertEqual(signatures, {("SAME_ROW_PERCENT_MARKER", "0.01", "ratio"),
                                     ("SAME_TABLE_HEADER_SCALE", "1000000", "USD"),
                                     ("SAME_TABLE_HEADER_SCALE", "1000000000", "USD")})

    def test_offline_plan_cannot_be_relabelled_into_draft_schema(self):
        offline = strict_json_file(path=ROOT / "docs/r4_offline/qualified_cases/r4_a03_production/scoped_plan.json")
        offline["record_type"] = DRAFT_TYPE
        offline["draft_plan_id"] = content_hash(value={k: v for k, v in offline.items() if k != "draft_plan_id"})
        with self.assertRaises(R4DraftPlanError):
            validate_r4_draft_plan(plan=offline, repo_root=ROOT, expected_plan_id=offline["draft_plan_id"])

    def test_caller_cannot_supply_a_fake_verified_context_or_path_requirement(self):
        with self.assertRaises(R4DraftPlanError):
            build_r4_draft_plan(repo_root=ROOT, context={"validated": True})
        with self.assertRaises(R4DraftPlanError):
            R4DraftPlanContext(factory=object(), root=ROOT, requirement_id="issue_28_v2",
                               body_bytes=b"{}", files={}, directories={})
        with self.assertRaises(R4DraftPlanError):
            prepare_r4_draft_plan_context(repo_root=ROOT, requirement_id="../issue_28_v2")


class R4DraftPlanFullCorpusIntegrationTest(unittest.TestCase):
    """Native corpus replay happens once; every validation rechecks exact inputs.

    Run after the integrator regenerates the corpus for the final Requirement
    closure. An in-progress execution-authority drift is a failure, not a skip.
    """

    @classmethod
    def setUpClass(cls):
        cls.context = prepare_r4_draft_plan_context(repo_root=ROOT)
        cls.plan = build_r4_draft_plan(repo_root=ROOT, context=cls.context)

    def validate(self, plan):
        return validate_r4_draft_plan(plan=plan, repo_root=ROOT,
            expected_plan_id=plan["draft_plan_id"], context=self.context)

    def rebind(self, plan):
        plan["draft_plan_id"] = content_hash(value={k: v for k, v in plan.items() if k != "draft_plan_id"})
        return plan

    def test_complete_draft_is_twelve_calls_and_zero_live_authority(self):
        self.assertEqual(self.validate(self.plan), self.plan)
        self.assertEqual(self.plan["counts"], {"base_provider_calls": 9, "stability_provider_calls": 3,
            "planned_provider_calls": 12, "structured_positive_zero_calls": 3, "zero_class_fixtures": 4,
            "actual_provider_calls": 0, "actual_paid_calls": 0, "actual_sec_calls": 0})
        self.assertEqual(self.plan["call_bounds"], {"target_minimum": 12, "target_maximum": 18, "hard_maximum": 24})
        self.assertIsNone(self.plan["exact_head"])
        self.assertEqual(self.plan["owner_authorization"], "NOT_ISSUED")
        self.assertFalse(self.plan["provider_paid_sec_authorized"])
        self.assertEqual(self.plan["native_validation"]["verified_case_count"], 16)
        self.assertEqual({row["reason"] for row in self.plan["zero_call_fixtures"]},
            {"STRUCTURED_PRIMARY_RESOLVED", "NEGATIVE_EXPECTED", "NOT_APPLICABLE", "QUALITATIVE_ONLY", "AMBIGUOUS_EXCLUDED"})

    def test_repository_shape_api_defers_native_replay_and_cannot_be_a_draft(self):
        with patch("vnext.r4_live_plan._native_corpus_replay", side_effect=AssertionError("shape read must not replay")):
            inputs = derive_r4_repository_schedule(repo_root=ROOT)
        self.assertEqual(inputs["entries"], self.plan["entries"])
        self.assertEqual(inputs["record_type"], "R4_REPOSITORY_CALL_SCHEDULE_INPUTS")
        self.assertEqual(inputs["native_validation"]["verified_case_count"], 0)
        self.assertEqual(inputs["native_validation"]["tier"], "NOT_RUN_BY_SHAPE_INSPECTION")
        with self.assertRaises(R4DraftPlanError):
            validate_r4_draft_plan(plan=inputs, repo_root=ROOT,
                expected_plan_id=inputs["schedule_input_id"], context=self.context)

    def test_subject_traits_and_quarter_period_are_source_bound_not_issuer_inferred(self):
        for entry in self.plan["entries"]:
            self.assertEqual(entry["fixture_subject_identity"]["source_id"], entry["source_id"])
            self.assertEqual(entry["fixture_subject_identity"]["company_traits"], ["financial"])
            self.assertEqual(set(entry["target_period"]), {"fiscal_year", "period_start", "period_end"})
            self.assertEqual(entry["target_period_identity"]["period_label"],
                             entry["scope_certificate_identity"]["task_period"])
        quarter = next(entry for entry in self.plan["entries"] if entry["fixture_id"] == "r4_a03_alternate")
        self.assertEqual(quarter["target_period"], {"fiscal_year": 2025,
            "period_start": "2025-10-01", "period_end": "2025-12-31"})
        self.assertEqual(quarter["target_period_identity"]["period_label"], "2025Q4")
        self.assertEqual(quarter["target_period_identity"]["resolution"], "SOURCE_BOUND_DISCLOSED_PERIOD")
        plan = copy.deepcopy(self.plan)
        plan["entries"][1]["target_period"]["period_start"] = "2025-01-01"
        with self.assertRaises(R4DraftPlanError):
            self.validate(self.rebind(plan))

    def test_trusted_bridge_reuses_verified_requirement_and_exact_subject_bytes(self):
        requirement = load_requirement_snapshot(snapshot_dir=ROOT / "requirements/issue_28_v2")
        source = strict_json_file(path=ROOT / "config/r4_fixture_company_authority_v1.json")
        subject = {"authority_id": source["authority_id"],
            "entries": {entry["source_id"]: entry for entry in source["entries"]},
            "target_period_resolution": source["target_period_resolution"],
            "qualification_credit": "NONE_INDIVIDUAL_RUN"}
        with patch("vnext.r4_live_plan.load_requirement_snapshot", side_effect=AssertionError("NO_PARENT_REBUILD")), \
                patch("vnext.r4_run_store.load_r4_fixture_company_authority", side_effect=AssertionError("NO_DEI_REPARSE")):
            inputs = _derive_r4_repository_schedule_from_requirement(repo_root=ROOT,
                requirement=requirement, company_authority=subject)
            self.assertEqual(inputs["entries"], self.plan["entries"])
            changed = copy.deepcopy(subject)
            next(iter(changed["entries"].values()))["company_traits"] = ["non_financial"]
            with self.assertRaises(R4DraftPlanError):
                _derive_r4_repository_schedule_from_requirement(repo_root=ROOT,
                    requirement=requirement, company_authority=changed)

    def test_rebound_count_membership_order_and_risk_mutations_fail(self):
        changed = []
        for field, value in (("planned_provider_calls", 11), ("planned_provider_calls", 25),
                             ("actual_provider_calls", 1), ("stability_provider_calls", 0)):
            plan = copy.deepcopy(self.plan)
            plan["counts"][field] = value
            changed.append(plan)
        plan = copy.deepcopy(self.plan)
        plan["call_bounds"]["hard_maximum"] = 25
        changed.append(plan)
        plan = copy.deepcopy(self.plan)
        plan["entries"].pop()
        changed.append(plan)
        plan = copy.deepcopy(self.plan)
        plan["entries"][0], plan["entries"][1] = plan["entries"][1], plan["entries"][0]
        changed.append(plan)
        for forbidden in ("r4_a13_production", "r4_zero_negative_expected"):
            plan = copy.deepcopy(self.plan)
            plan["entries"][9]["fixture_id"] = forbidden
            changed.append(plan)
        plan = copy.deepcopy(self.plan)
        plan["entries"][11] = copy.deepcopy(plan["entries"][5])
        plan["entries"][11].update(ordinal=12, phase="STABILITY", fixture_execution_ordinal=2,
                                  repeats_base_ordinal=6)
        changed.append(plan)
        plan = copy.deepcopy(self.plan)
        plan["entries"][9]["response_reuse_authorized"] = True
        changed.append(plan)
        plan = copy.deepcopy(self.plan)
        plan["stability_selection"][0]["new_risk_features"] = []
        changed.append(plan)
        for plan in changed:
            with self.subTest(draft_plan_id=self.rebind(plan)["draft_plan_id"]), self.assertRaises(R4DraftPlanError):
                self.validate(plan)

    def test_draft_cannot_become_pending_live_or_exact_head_authorization(self):
        for key, value in (("record_type", "R4_PENDING_LIVE_QUALIFICATION_PLAN"),
                           ("planning_mode", "PENDING_LIVE"), ("exact_head", "a" * 40),
                           ("provider_paid_sec_authorized", True), ("owner_authorization", "APPROVED"),
                           ("qualification_credit", "CURRENT")):
            plan = copy.deepcopy(self.plan)
            plan[key] = value
            with self.subTest(key=key), self.assertRaises(R4DraftPlanError):
                self.validate(self.rebind(plan))

    def test_context_returns_copies_and_rejects_input_pin_tampering(self):
        plan = build_r4_draft_plan(repo_root=ROOT, context=self.context)
        plan["entries"][0]["fixture_id"] = "changed-only-in-caller"
        self.assertEqual(build_r4_draft_plan(repo_root=ROOT, context=self.context), self.plan)
        path = next(iter(self.context._files))
        original = self.context._files[path]
        try:
            self.context._files[path] = {**original, "sha256": "f" * 64}
            with self.assertRaises(ValueError):
                build_r4_draft_plan(repo_root=ROOT, context=self.context)
        finally:
            self.context._files[path] = original

    def test_draft_loader_rejects_path_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.json"
            atomic_write_bytes(path=path, content=canonical_json_bytes(value=self.plan))
            with self.assertRaises(ValueError):
                load_r4_draft_plan(repo_root=ROOT, path=path,
                    expected_plan_id=self.plan["draft_plan_id"], context=self.context)


if __name__ == "__main__":
    unittest.main()
