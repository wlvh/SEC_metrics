"""Verbatim Item 1A headings, including bold lead text inside a paragraph."""

import unittest

from tests.vnext.test_text_coverage import BODY, annual, binding
from tests.vnext.test_annual_input import independent_inputs
from vnext.canonical import sha256_bytes
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.risk_signals import risk_factor_headings
from vnext.sources import raw_blob_record, source_reference_record
from vnext.text_coverage import build_text_document, verify_text_document
from tests.vnext.common import REPO_ROOT


class RiskSignalsTest(unittest.TestCase):
    def test_bold_lead_is_separate_from_explanatory_paragraph(self):
        body = BODY.replace("<p>A supply constraint could affect production.</p>",
            '<p><b>Supply constraints <span>may affect production</span></b>'
            '. A later sentence explains an uncertain outcome.</p>')
        args = binding(annual(body))
        document = build_text_document(**args)
        result = risk_factor_headings(document=document)
        self.assertEqual("SOURCE_HEADINGS_READY", result["status"])
        self.assertEqual(["Supply constraints may affect production"],
                         [h["text"] for h in result["headings"]])
        locator = result["headings"][0]["locators"][0]
        raw = args["raw_bytes"][locator["raw_start_byte"]:locator["raw_end_byte"]]
        self.assertEqual(sha256_bytes(content=raw), locator["raw_span_sha256"])
        self.assertNotIn(b"later sentence", raw)
        self.assertFalse(result["risk_occurrence_asserted"])
        self.assertFalse(result["native_result_created"])

    def test_mid_sentence_emphasis_and_plain_paragraph_do_not_become_titles(self):
        body = BODY.replace("<p>A supply constraint could affect production.</p>",
            '<p>A later <strong>risk disclosure</strong> is only part of a sentence.</p>')
        result = risk_factor_headings(document=build_text_document(**binding(annual(body))))
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual([], result["headings"])
        self.assertIn("RISK_HEADING_STRUCTURE_NOT_IMPLEMENTED", result["reasons"])

    def test_inherited_bold_and_explicit_normal_weight_remain_distinct(self):
        body = BODY.replace("<p>A supply constraint could affect production.</p>",
            '<div style="font-weight:700"><span>Title &amp; evidence</span>'
            '<span style="font-weight:400"> Explanation in normal weight.</span></div>')
        args = binding(annual(body))
        document = build_text_document(**args)
        self.assertEqual(document, verify_text_document(document=document, **args))
        result = risk_factor_headings(document=document)
        self.assertEqual("Title & evidence", result["headings"][0]["text"])

    def test_amendment_and_missing_section_boundary_never_claim_complete(self):
        body = BODY.replace("<p>A supply constraint could affect production.</p>",
                            '<p><b>A material supply risk</b></p>')
        for raw in [annual(body, form="10-K/A"),
                    annual(body.split("<h2>Item 1B.")[0])]:
            result = risk_factor_headings(document=build_text_document(**binding(raw)))
            self.assertEqual("INCOMPLETE", result["status"])
            self.assertFalse(result["publication_credit"])

    def test_saved_heading_plus_paragraph_layouts_are_automatically_read(self):
        with independent_inputs():
            for company_id in ["marriott_international", "ford_motor_company"]:
                p = prepare_saved_annual_input(repo_root=REPO_ROOT, company_id=company_id)
                a = p["table_input"]
                blob = raw_blob_record(repo_root=REPO_ROOT,
                    repo_relative_path=a["source_repo_relative_path"], media_type="text/html")
                ref = source_reference_record(raw_blob=blob, company_id=company_id,
                    source_url=a["source_url"], accession=a["accession"],
                    document_name=a["document_name"], source_role="target_primary",
                    request_attempt_id=a["request_attempt_id"])
                args = {"raw_bytes": (REPO_ROOT / a["source_repo_relative_path"]).read_bytes(),
                        "raw_blob": blob, "source_reference": ref,
                        "expected_company_id": company_id, "expected_cik": p["entity"],
                        "expected_period_end": a["target_period"]["period_end"]}
                document = build_text_document(**args)
                result = risk_factor_headings(document=document)
                self.assertEqual("SOURCE_HEADINGS_READY", result["status"])
                self.assertGreater(len(result["headings"]), 10)
                self.assertTrue(any(b["leading_emphasis"] and not b["emphasized"]
                                    for b in document["blocks"]))
                for heading in result["headings"]:
                    for locator in heading["locators"]:
                        raw = args["raw_bytes"][locator["raw_start_byte"]:locator["raw_end_byte"]]
                        self.assertEqual(sha256_bytes(content=raw), locator["raw_span_sha256"])


if __name__ == "__main__":
    unittest.main()
