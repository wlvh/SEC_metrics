"""D04 at a pinned period: the source, the registered assessment and its text result.

What is proven here is plumbing. The outputs these tests register are synthetic:
each finding restates a relation the frozen checker itself derives from the
source, and each required candidate the checker cannot relate is labelled
"another meaning". A registered synthetic output says nothing about any
filing's content; it is the fixture that lets a response travel from the
acceptance to a Result.

The Run layer - installation, a native Run under issue_47_v1, freeze, cold read,
public row - needs the registration patch and is measured in the runtime tree
(docs/evidence/issue47_history/semantic-route-wiring/).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import capacity_semantic_source as frozen_capacity
from vnext import capacity_text_results
from vnext import going_concern_source as frozen_going_concern
from vnext import historical_model_session as session_module
from vnext import historical_semantic_results as semantic
from vnext import historical_semantic_source as pinned
from vnext import r6_semantic_source as frozen_semantic
from vnext.capacity_semantic_review import _restore_units
from vnext.canonical import content_hash
from vnext.continuous_request_context import FORMAT_VERSION
from vnext.d04_native_assessment import source_statement_relations
from vnext.normal_period_selection import resolve_period_selection
from vnext.r6_semantic_review import _source_items
from vnext.regulatory_investigation_candidates import _self_aliases


def _selection(company_id, report_end):
    return resolve_period_selection(repo_root=ROOT, company_id=company_id, report_end=report_end)


def synthetic_output(request):
    """A response the frozen checker accepts: its own relations, nothing else.

    Every relation the checker proves is reported as that relation; every
    required candidate it cannot relate is reported as another meaning. This is
    the checker's expected answer, which is exactly what a plumbing fixture
    should be and exactly why it proves nothing about a filing.
    """
    units = _restore_units(request["units"], request["shared_source_dictionaries"])
    blocks = [b for u in units if u["kind"] == "VISIBLE_TEXT" for b in u["payload"]["blocks"]]
    binding = request["document_context"]["registrant_name_binding"]
    aliases = _self_aliases({"registrant_names": binding.get("accepted_source_names", []),
                             "blocks": blocks,
                             "text_document_id": request["document_context"]["document_id"],
                             "raw_asset_id": None, "source_reference_id": None})
    names = [a["text"] for a in aliases if a["text"].casefold() != "we"]
    required = {(r["unit_id"], r["kind"], r["source_index"])
                for r in request["required_candidate_assessments"]}
    rows = []
    for unit in units:
        kind, items = _source_items(unit)
        findings = []
        for index, item in items.items():
            text = item["raw_xml"] if kind == "NATIVE_SUPPLEMENT" else item["text"]
            proven = [r for r in source_statement_relations(
                text=text, names=names, period=request["target_period"],
                quoted=item.get("html_quotation_context", False)) if r["reason"] is None]
            for relation in proven:
                findings.append({"kind": relation["kind"],
                                 "subject": relation["subject"] or "TARGET_REGISTRANT",
                                 "timing": relation["timing"] or "CURRENT_REPORT",
                                 "evidence": [{"kind": kind, "source_index": index}],
                                 "reason": "synthetic fixture: the checker's own relation"})
            if not proven and (unit["unit_id"], kind, index) in required:
                findings.append({"kind": "VALUATION_OR_OTHER_MEANING",
                                 "subject": "TARGET_REGISTRANT", "timing": "CURRENT_REPORT",
                                 "evidence": [{"kind": kind, "source_index": index}],
                                 "reason": "synthetic fixture: an unrelated required candidate"})
        rows.append({"unit_id": unit["unit_id"], "reviewed": True, "findings": findings,
                     "unresolved": []})
    return json.dumps({"request_id": request["request_id"], "units": rows}).encode("utf-8")


class ThePinnedSourceIsTheFrozenBuildersOutputTest(unittest.TestCase):
    """The successor restates the frozen builders with one change: the input.

    So the frozen builders, with their two "latest" reads pointed at the same
    pinned inputs, must produce the same bytes - semantic_source_id included.
    Held on an earlier year (Marriott 2023), a predecessor year whose period
    carries a Part III 10-K/A (Paramount 2024, filed by CIK 813828), and B13 at
    a company inside the approved scope.
    """

    def _frozen(self, company_id, report_end, metric):
        selection = _selection(company_id, report_end)
        original, annual = pinned.pinned_inputs(repo_root=ROOT, company_id=company_id,
                                                period_selection=selection)
        with patch.object(frozen_going_concern, "prepare_saved_annual_input",
                          lambda **_: original), \
                patch.object(frozen_semantic, "prepare_saved_annual_input", lambda **_: annual):
            if metric == "D04":
                return selection, frozen_semantic.prepare_d04_semantic_source(
                    repo_root=ROOT, company_id=company_id, ordinary_registered=True)
            with patch.object(frozen_capacity, "policy", self._approved_policy()):
                return selection, frozen_capacity.prepare_capacity_semantic_source(
                    repo_root=ROOT, company_id=company_id, request_context_format=FORMAT_VERSION,
                    ordinary_registered=True)

    @staticmethod
    def _approved_policy():
        rules = json.loads((ROOT / frozen_capacity.POLICY_PATH).read_text(encoding="utf-8"))
        return lambda: (rules, {"applicable_company_ids": ["enphase_energy", "ford_motor_company"]})

    def test_an_earlier_year(self):
        with original_sources_only():
            selection, frozen = self._frozen("marriott_international", "2023-12-31", "D04")
            mine = pinned.prepare_historical_d04_semantic_source(
                repo_root=ROOT, company_id="marriott_international", period_selection=selection)
        self.assertEqual(frozen, mine)
        self.assertEqual("2023-12-31", mine["prepared_annual_input"]["table_input"]
                         ["target_period"]["period_end"])

    def test_a_predecessor_year_with_its_part_iii_amendment(self):
        with original_sources_only():
            selection, frozen = self._frozen("paramount_skydance_paramount_global",
                                             "2024-12-31", "D04")
            mine = pinned.prepare_historical_d04_semantic_source(
                repo_root=ROOT, company_id="paramount_skydance_paramount_global",
                period_selection=selection)
        self.assertEqual(frozen, mine)
        self.assertEqual(["10-K", "10-K/A"], [d["filing"]["form"] for d in mine["documents"]])
        # Read from the predecessor's own filings, not the successor's.
        self.assertEqual({"813828"}, {d["source_reference"]["source_url"].split("/data/")[1]
                                     .split("/")[0] for d in mine["documents"]})

    def test_b13_inside_the_approved_scope(self):
        with original_sources_only():
            selection, frozen = self._frozen("enphase_energy", "2025-12-31", "B13")
            mine = pinned.prepare_historical_capacity_semantic_source(
                repo_root=ROOT, company_id="enphase_energy", period_selection=selection,
                request_context_format=FORMAT_VERSION)
        self.assertEqual(frozen, mine)

    def test_b13_outside_the_scope_is_not_assembled(self):
        with self.assertRaisesRegex(ValueError, "B13_OUTSIDE_APPROVED_APPLICABILITY"):
            pinned.prepare_historical_capacity_semantic_source(
                repo_root=ROOT, company_id="marriott_international",
                period_selection=_selection("marriott_international", "2025-12-31"),
                request_context_format=FORMAT_VERSION)


class ARegisteredAssessmentTravelsToATextResultTest(unittest.TestCase):
    """Recorded registration, the loader, the case and the frozen text builders."""

    @classmethod
    def setUpClass(cls):
        cls.selection = _selection("marriott_international", "2023-12-31")
        with original_sources_only():
            cls.session = session_module.recorded_historical_model_session()
            planned = cls.session.plan(repo_root=ROOT, company_id="marriott_international",
                                       metric_id="D04", period_selection=cls.selection)
            cls.source, cls.requests = planned["source"], planned["requests"]
            cls.outputs = {r["request_id"]: synthetic_output(r) for r in cls.requests}
            cls.record = cls.session.register(
                repo_root=ROOT, company_id="marriott_international", metric_id="D04",
                period_selection=cls.selection, outputs=cls.outputs)

    @classmethod
    def tearDownClass(cls):
        cls.session.discard()

    def test_every_request_is_registered_and_the_branch_is_the_defined_scope(self):
        self.assertEqual(4, len(self.requests))
        self.assertEqual([r["request_id"] for r in self.requests],
                         self.record["assessment"]["required_request_ids"])
        self.assertEqual("DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW",
                         self.record["assessment"]["proposed_branch"])
        self.assertEqual("RECORDED_TEST_ONLY", self.record["mode"])
        self.assertIs(False, self.record["new_call_authority"])

    def test_a_batch_never_consumes_a_recorded_registration(self):
        """The default is LIVE, and there is no LIVE registration to find."""
        with original_sources_only():
            with self.assertRaisesRegex(ValueError, "HISTORICAL_SEMANTIC_ASSESSMENT_NOT_REGISTERED:LIVE"):
                semantic.load_historical_assessment(data_root=ROOT, source=self.source)
            loaded = semantic.load_historical_assessment(data_root=ROOT, source=self.source,
                                                         mode="RECORDED_TEST_ONLY")
        self.assertEqual(self.record, loaded)

    def test_the_case_builds_the_frozen_text_result(self):
        with original_sources_only():
            case = semantic.prepare_historical_semantic_case(
                repo_root=ROOT, company_id="marriott_international", metric_id="D04",
                period_selection=self.selection, assessment_mode="RECORDED_TEST_ONLY")
            arguments = {"compiled_spec": case["compiled_spec"], **case["text_arguments"]}
            candidate = capacity_text_results.create_deterministic_text_candidate(**arguments)
            evidence = capacity_text_results.build_text_evidence(candidate=candidate, **arguments)
        self.assertEqual({}, candidate["selected"])
        self.assertEqual("PASS", evidence["status"])
        self.assertEqual("RECORDED_TEST_ONLY", case["component"]["mode"])
        self.assertEqual("2023-12-31", case["target_period"]["period_end"])
        coverage = evidence["checks"][0]["coverage"]
        self.assertEqual([d["document_id"] for d in self.source["documents"]],
                         [c["document_id"] for c in coverage])

    def test_the_run_input_is_a_text_case_that_carries_its_registration(self):
        from vnext.historical_results import prepare_historical_run_input
        with original_sources_only():
            prepared = prepare_historical_run_input(
                repo_root=ROOT, company_id="marriott_international", metric_id="D04",
                period_selection=self.selection, assessment_mode="RECORDED_TEST_ONLY")
            # Without naming the mode it is LIVE, and there is none.
            with self.assertRaisesRegex(ValueError, "NOT_REGISTERED:LIVE"):
                prepare_historical_run_input(
                    repo_root=ROOT, company_id="marriott_international", metric_id="D04",
                    period_selection=self.selection)
            # A mode means nothing to a route without an assessment.
            with self.assertRaisesRegex(ValueError, "ASSESSMENT_MODE_WITHOUT_ASSESSMENT"):
                prepare_historical_run_input(
                    repo_root=ROOT, company_id="marriott_international", metric_id="D02",
                    period_selection=self.selection, assessment_mode="RECORDED_TEST_ONLY")
        self.assertEqual("TEXT", prepared["kind"])
        self.assertEqual(self.record, prepared["registered_assessment"])
        self.assertEqual({"D04": semantic.SPEC_PATHS["D04"]}, prepared["spec_paths"])
        self.assertEqual("RECORDED_TEST_ONLY", prepared["component"]["mode"])

    def test_the_text_api_is_the_ordinary_native_builders(self):
        from vnext.historical_text_results import text_api
        api, review_builder = text_api("D04")
        self.assertIs(capacity_text_results, api)
        self.assertIs(capacity_text_results.build_text_review_unit, review_builder)

    def test_an_installed_copy_is_the_creator_record_or_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = root / semantic.EXPORT_PATHS["D04"]
            export.parent.mkdir(parents=True)
            export.write_bytes(semantic.registered_export_bytes(self.record))
            self.assertEqual(self.record, semantic.load_historical_assessment(
                data_root=root, source=self.source))
            # Edited output, hash recomputed: not the creator's record.
            edited = json.loads(json.dumps(self.record))
            edited["native_requests"][0]["assistant_output"] += " "
            body = {k: v for k, v in edited.items() if k != "input_record_id"}
            edited["input_record_id"] = content_hash(value=body)
            export.write_bytes(semantic.registered_export_bytes(edited))
            with self.assertRaisesRegex(ValueError, "ACCEPTANCE_DOES_NOT_RE_DERIVE"):
                semantic.load_historical_assessment(data_root=root, source=self.source)
            # The same claim under LIVE is refused before anything is re-derived.
            live = {**{k: v for k, v in self.record.items() if k != "input_record_id"},
                    "mode": "LIVE"}
            live["input_record_id"] = content_hash(value=live)
            export.write_bytes(semantic.registered_export_bytes(live))
            with self.assertRaisesRegex(ValueError, "HISTORICAL_LIVE_ASSESSMENT_NOT_IN_CREATOR_JOURNAL"):
                semantic.load_historical_assessment(data_root=root, source=self.source)

    def test_another_issues_registration_is_refused(self):
        other = {**{k: v for k, v in self.record.items() if k != "input_record_id"},
                 "requirement_id": "issue_28_v14"}
        other["input_record_id"] = content_hash(value=other)
        with self.assertRaisesRegex(ValueError, "REGISTERED_FOR_ANOTHER_REQUIREMENT"):
            semantic.validate_registered_record(record=other, source=self.source,
                                                mode="RECORDED_TEST_ONLY")

    def test_an_incomplete_output_set_is_not_registered(self):
        partial = dict(list(self.outputs.items())[:-1])
        with original_sources_only():
            with self.assertRaisesRegex(ValueError, "OUTPUT_SET_DIFFERS_FROM_REQUEST_SET"):
                self.session.register(repo_root=ROOT, company_id="marriott_international",
                                      metric_id="D04", period_selection=self.selection,
                                      outputs=partial)

    def test_a_response_out_of_unit_order_is_refused_by_the_frozen_acceptance(self):
        request = self.requests[0]
        body = json.loads(self.outputs[request["request_id"]])
        body["units"] = list(reversed(body["units"]))
        with self.assertRaisesRegex(ValueError, "D04_RESPONSE_UNIT_CENSUS_ORDER_CHANGED"):
            semantic.accept_output(source=self.source, request=request,
                                   output=json.dumps(body).encode("utf-8"))


class TheLiveSessionRefusesByNameTest(unittest.TestCase):

    def test_without_an_allowance(self):
        self.assertFalse((ROOT / session_module.ALLOWANCE_PATH).exists())
        with self.assertRaisesRegex(ValueError, "ISSUE_47_MODEL_ALLOWANCE_NOT_GRANTED"):
            session_module.live_historical_model_session()

    def test_an_allowance_alone_does_not_open_a_provider_path(self):
        with tempfile.TemporaryDirectory() as directory:
            allowance = Path(directory) / session_module.ALLOWANCE_PATH
            allowance.parent.mkdir(parents=True)
            allowance.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ISSUE_47_MODEL_EGRESS_NOT_REGISTERED:"
                                        "scripts/vnext/invocation_control.py"):
                session_module.live_historical_model_session(repo_root=Path(directory))

    def test_the_controller_does_refuse_this_generation(self):
        """The egress reason is measured, not asserted: the controller says it.

        Asked with nothing but the generation's id, the controller's registry
        refuses before it reads anything else. (In this tree the Requirement
        itself does not load - the engine registry learns issue_47_v1 only in
        the registration patch - so the id is all there is to ask with.)
        """
        from vnext import invocation_control as control
        with self.assertRaisesRegex(control.InvocationControlError, "registered R4 revision"):
            control._prepare_successor_invocation_authority_from_requirement(
                repo_root=ROOT, requirement={"requirement_id": "issue_47_v1"})


if __name__ == "__main__":
    unittest.main()
