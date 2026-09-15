"""R6 source navigation and false-risk/false-absence counterexamples."""

import copy
import json
import unittest

from tests.vnext.test_text_coverage import annual, binding
from vnext.text_coverage import build_text_document
from vnext.text_business_candidates import board_composition_candidates, governance_source_document
from vnext.text_business_candidates import legal_risk_candidates, going_concern_candidates
from vnext.text_business_candidates import prepare_business_candidates, replay_business_candidates
from vnext.text_business_candidates import TextBusinessCandidateError


BODY = '''<h2>Item 1A. Risk Factors</h2><p>If a regulator conducts an investigation, our expenses could increase.</p>
<h2>Item 1B. Unresolved Staff Comments</h2><p>None.</p>
<h2>Item 3. Legal Proceedings</h2><p>Refer to Note 2 for our legal proceedings and pending litigation.</p>
<h2>Item 4. Mine Safety Disclosures</h2><p>Not applicable.</p>
<h2>Item 8. Financial Statements and Supplementary Data</h2><p>The financial statements follow the numbered form items.</p>
<h2>Item 9. Changes in and Disagreements with Accountants</h2><p>None.</p>
<h2>Report of Independent Registered Public Accounting Firm</h2>
<p>We have audited the consolidated financial statements of the Company.</p>
<p>In our opinion, the financial statements present fairly in all material respects.</p>
<h2>Consolidated Balance Sheets</h2><p>The financial statements appear here.</p>
<h2>Note 1. Accounting Policies</h2><p>Accounting policies are described here.</p>
<h2>Note 2. Contingencies</h2><p>We are defendants in litigation concerning a product contract.</p>
<h3>1. Procedural matters</h3><p>The court has not resolved the matter described in the preceding paragraph.</p>
<h2>Note 3. Income Taxes</h2><p>Taxes are reported in this section.</p>'''


def document(body=BODY):
    return build_text_document(**binding(annual(body)))


def source_arguments(raw, form="10-K"):
    args = binding(raw)
    return dict(raw_bytes=raw, raw_blob=args["raw_blob"], source_reference=args["source_reference"],
                company_id="sample_entity", cik="12345", filing={"form": form, "accessionNumber": "0000012345-26-000001",
                "primaryDocument": "source.htm", "filingDate": "2026-03-27", "reportDate": "2025-12-31"})


class TextBusinessCandidateTest(unittest.TestCase):
    def test_current_and_prospective_board_text_do_not_become_an_asof_count(self):
        raw = annual('<p>Our Board currently has eleven directors serving the Company.</p>'
                     '<p>Upon election, our Board will consist of twelve directors.</p>'
                     '<p>The Board determined that all directors except the CEO are independent.</p>'
                     '<p>Our Audit Committee consists of three directors and meets quarterly.</p>', form="DEF 14A")
        args = source_arguments(raw, "DEF 14A")
        proposal = board_composition_candidates(document=governance_source_document(**args))
        self.assertEqual(4, len(proposal["candidates"]))
        self.assertFalse(proposal["numeric_board_counts_asserted"])
        self.assertFalse(proposal["board_measurement_date_assigned"])
        self.assertIn("PROSPECTIVE_OR_ELECTION_CONTEXT_PRESENT", proposal["candidates"][1]["labels"])

    def test_committee_pay_decision_is_not_board_composition(self):
        raw = annual('<p>The Compensation Committee approved a bonus of $4 million to the executive.</p>', form="DEF 14A")
        p = board_composition_candidates(document=governance_source_document(**source_arguments(raw, "DEF 14A")))
        self.assertEqual([], p["candidates"])
        self.assertFalse(p["not_disclosed_confirmed"])

    def test_forward_note_after_form_items_is_located_without_stopping_at_numbered_bullet(self):
        p = legal_risk_candidates(document=document())
        ref = p["note_references"][0]
        self.assertEqual("LOCATED_NOTE_RANGE", ref["status"])
        note = ref["range_candidates"][0]
        self.assertEqual("Note 3. Income Taxes", document()["blocks"][note["end_block_exclusive"]]["text"])
        self.assertTrue(any("court has not resolved" in x["text"] for x in p["D02"]["candidates"]))

    def test_reference_to_subsection_expands_explicitly_to_the_parent_note(self):
        d = document(BODY.replace("Refer to Note 2", "Refer to Note 2A"))
        p = legal_risk_candidates(document=d)
        self.assertEqual("WIDER_PARENT_NOTE", p["note_references"][0]["range_candidates"][0]["scope_relation"])

    def test_missing_note_is_unresolved_navigation_not_undisclosed(self):
        p = legal_risk_candidates(document=document(BODY.replace("Refer to Note 2", "Refer to Note 8")))
        self.assertEqual("INCOMPLETE", p["coverage_status"])
        self.assertIn("UNRESOLVED_NOTE_8", p["coverage_reasons"])
        self.assertFalse(p["not_disclosed_confirmed"])

    def test_hypothetical_and_negated_regulatory_language_needs_interpretation(self):
        body = BODY.replace("If a regulator conducts an investigation, our expenses could increase.",
                            "We have not received a subpoena from the SEC. We could face future investigations.")
        p = legal_risk_candidates(document=document(body))["D03"]
        self.assertTrue(p["semantic_review_required"])
        self.assertFalse(p["actual_investigation_asserted"])
        self.assertIn("NEGATION_OR_RESOLUTION_LANGUAGE_PRESENT", p["candidates"][0]["labels"])
        self.assertIn("HYPOTHETICAL_OR_GENERAL_LANGUAGE_PRESENT", p["candidates"][0]["labels"])

    def test_sec_header_and_table_of_contents_do_not_create_an_investigation(self):
        body = BODY.replace("If a regulator conducts an investigation, our expenses could increase.", "Economic conditions affect our business.")
        d = document('<p>SECURITIES AND EXCHANGE COMMISSION</p><p><a href="#risk">SEC investigation</a></p>' + body)
        p = legal_risk_candidates(document=d)["D03"]
        self.assertFalse(any("SECURITIES AND EXCHANGE" in c["text"] or c["text"] == "SEC investigation" for c in p["candidates"]))

    def test_clean_opinion_and_no_phrase_never_prove_absence_of_doubt(self):
        p = going_concern_candidates(document=document())
        self.assertEqual("NO_MATCHED_SOURCE_LANGUAGE", p["finding_status"])
        self.assertTrue(p["auditor_report_ranges"])
        self.assertTrue(p["semantic_review_required"])
        self.assertFalse(p["not_disclosed_confirmed"])
        self.assertFalse(p["clean_opinion_used_as_absence"])

    def test_report_continuation_sentence_is_not_a_financial_statement_heading(self):
        body = BODY.replace('<h2>Consolidated Balance Sheets</h2>',
                            '<p>consolidated financial statements, taken as a whole, and we are not providing a separate opinion.</p>'
                            '<p>Our additional audit procedures and signature follow here.</p>'
                            '<h2>Consolidated Balance Sheets</h2>')
        d = document(body)
        report = going_concern_candidates(document=d)["auditor_report_ranges"][0]
        self.assertEqual("Consolidated Balance Sheets", report["closing_heading"]["text"])
        self.assertTrue(any("signature follow" in b["text"] for b in d["blocks"][report["start_block"]:report["end_block_exclusive"]]))

    def test_parenthesized_note_heading_is_navigable_without_claiming_semantic_completeness(self):
        body = BODY.replace("<h2>Note 2. Contingencies</h2>", "<h2>2) Contingencies</h2>").replace("<h2>Note 3. Income Taxes</h2>", "<h2>3) Income Taxes</h2>")
        p = legal_risk_candidates(document=document(body))
        self.assertEqual("LOCATED_NOTE_RANGE", p["note_references"][0]["status"])
        self.assertFalse(p["semantic_scope_completeness_asserted"])

    def test_goodwill_going_concern_phrase_is_not_a_doubt_conclusion(self):
        body = BODY.replace("Accounting policies are described here.", "Goodwill includes the going-concern element of the acquired business.")
        p = going_concern_candidates(document=document(body))
        self.assertEqual("SOURCE_LANGUAGE_FOUND", p["finding_status"])
        self.assertFalse(p["going_concern_doubt_asserted"])
        self.assertTrue(p["semantic_review_required"])

    def test_raw_offsets_and_json_replay_are_mechanical_not_self_reported_success(self):
        args = source_arguments(annual(BODY))
        bundle = prepare_business_candidates(**args)
        self.assertEqual(bundle, replay_business_candidates(bundle=json.loads(json.dumps(bundle)), **args))
        excerpt = next(c for c in bundle["proposals"]["legal_regulatory"]["D02"]["candidates"] if "defendants" in c["text"])
        self.assertIn(b"defendants", args["raw_bytes"][excerpt["raw_start_byte"]:excerpt["raw_end_byte"]])
        changed = copy.deepcopy(bundle);changed["proposals"]["D04"]["not_disclosed_confirmed"] = True
        with self.assertRaisesRegex(TextBusinessCandidateError, "REPLAY_CHANGED"):
            replay_business_candidates(bundle=changed, **args)

    def test_cross_entity_and_fragment_cannot_grant_coverage(self):
        args = source_arguments(annual(BODY));args["cik"] = "54321"
        with self.assertRaises(ValueError): prepare_business_candidates(**args)
        p = going_concern_candidates(document=build_text_document(**binding(annual(BODY).replace(b"</body></html>", b""))))
        self.assertEqual("INCOMPLETE", p["coverage_status"])
        self.assertFalse(p["not_disclosed_confirmed"])


if __name__ == "__main__":
    unittest.main()
