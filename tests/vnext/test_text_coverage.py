"""Source-range acceptance and false-absence counterexamples for R6."""

import copy
import unittest

from tests.vnext.common import REPO_ROOT  # Establish the shared scripts path.
from vnext.canonical import content_hash, sha256_bytes
from vnext.sources import source_reference_record
from vnext.text_coverage import TextCoverageError, build_text_document
from vnext.text_coverage import inspect_text_scope, verify_text_document


def annual(body, *, form="10-K", cik="12345", period="2025-12-31"):
    return ('''<!doctype html><html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
 xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:dei="http://xbrl.sec.gov/dei/2025">
<head><title>SEC title is outside the checked range</title></head><body>
<ix:header><ix:hidden>
<xbrli:context id="annual"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">''' + cik + '''</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<ix:nonNumeric name="dei:EntityCentralIndexKey" contextRef="annual">''' + cik + '''</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="annual">''' + period + '''</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentType" contextRef="annual">''' + form + '''</ix:nonNumeric>
</ix:hidden></ix:header>''' + body + "</body></html>").encode()


BODY = '''<h2>Item 1. Business</h2><p>Our activities are described here.</p>
<h2>Item 1A. Risk Factors</h2><p>A supply constraint could affect production.</p>
<h2>Item 1B. Unresolved Staff Comments</h2><p>None.</p>
<h2>Item 3. Legal Proceedings</h2><p>We received a subpoena from an authority.</p>
<h2>Item 4. Mine Safety Disclosures</h2><p>Not applicable.</p>
<h2>Item 8. Financial Statements and Supplementary Data</h2>
<p>The claim and related loss contingency are described in the following note.</p>
<h2>Item 9. Changes in and Disagreements with Accountants</h2><p>None.</p>'''


def binding(raw):
    blob = {"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
            "byte_length": len(raw), "media_type": "text/html", "storage_uri": "fixture/source.htm"}
    ref = source_reference_record(raw_blob=blob, company_id="sample_entity",
        source_url="https://www.sec.gov/Archives/edgar/data/12345/000001234526000001/source.htm",
        accession="0000012345-26-000001", document_name="source.htm", source_role="target_primary",
        request_attempt_id="test-only-source-attempt")
    return {"raw_bytes": raw, "raw_blob": blob, "source_reference": ref,
            "expected_company_id": "sample_entity", "expected_cik": "12345",
            "expected_period_end": "2025-12-31"}


class TextCoverageTest(unittest.TestCase):
    def test_identity_local_names_cannot_impersonate_dei_namespace(self):
        raw = annual(BODY).replace(b"http://xbrl.sec.gov/dei/2025",
                                   b"https://example.test/dei-lookalike")
        with self.assertRaisesRegex(TextCoverageError, "DOCUMENT_ENTITY_MISMATCH_OR_MISSING"):
            build_text_document(**binding(raw))

    def test_found_and_complete_are_separate_with_exact_source_span(self):
        args = binding(annual(BODY))
        document = build_text_document(**args)
        scan = inspect_text_scope(document=document, required_sections=["ITEM_3", "ITEM_8"], terms=["subpoena"])
        self.assertEqual("COMPLETE_LOCAL_SECTION_SCAN", scan["coverage_status"])
        self.assertEqual("FOUND", scan["finding_status"])
        finding = scan["findings"][0]
        exact = args["raw_bytes"][finding["raw_start_byte"]:finding["raw_end_byte"]]
        self.assertEqual(b"We received a subpoena from an authority.", exact)
        self.assertEqual(sha256_bytes(content=exact), finding["raw_span_sha256"])
        self.assertFalse(scan["semantic_disclosure_verified"])
        self.assertFalse(scan["publication_credit"])

    def test_contents_link_and_page_rows_do_not_compete_with_body(self):
        toc = '<table><tr><td><a href="#risk">Item 1A. Risk Factors</a></td><td>4</td></tr><tr><td><a href="#staff">Item 1B. Unresolved Staff Comments</a></td><td>8</td></tr></table>'
        document = build_text_document(**binding(annual(toc + BODY)))
        self.assertEqual("LOCATED", document["sections"]["ITEM_1A"]["status"])
        scan = inspect_text_scope(document=document, required_sections=["ITEM_1A"], terms=["subpoena"])
        self.assertEqual("NOT_FOUND_IN_CHECKED_RANGES", scan["finding_status"])
        self.assertFalse(scan["not_disclosed_confirmed"])

    def test_contents_only_and_wrong_section_never_confirm_absence(self):
        toc = '<div>Item 1A.</div><div>Risk Factors</div><div>4</div><div>Item 1B.</div><div>Unresolved Staff Comments</div><div>8</div>'
        doc = build_text_document(**binding(annual(toc)))
        scan = inspect_text_scope(document=doc, required_sections=["ITEM_1A"], terms=["investigation"])
        self.assertEqual("INCOMPLETE", scan["coverage_status"])
        self.assertEqual("ITEM_1A_MISSING", scan["coverage_reasons"][0])
        self.assertFalse(scan["not_disclosed_confirmed"])

    def test_repeated_page_heading_keeps_later_content(self):
        body = BODY.replace("<h2>Item 4.", '<h2>Item 3. Legal Proceedings (Continued)</h2><p>A second investigation is ongoing.</p><h2>Item 4.')
        scan = inspect_text_scope(document=build_text_document(**binding(annual(body))), required_sections=["ITEM_3"], terms=["investigation", "subpoena"])
        self.assertEqual("COMPLETE_LOCAL_SECTION_SCAN", scan["coverage_status"])
        self.assertEqual(2, len(scan["findings"]))

    def test_fragment_truncation_and_unclosed_sections_are_incomplete(self):
        full = annual(BODY)
        for raw in (full.replace(b"</body></html>", b""), full.replace(b"<html ", b"<section ").replace(b"</html>", b"</section>"), annual(BODY[:BODY.index("<h2>Item 4.")])):
            with self.subTest(raw=raw[-80:]):
                doc = build_text_document(**binding(raw))
                scan = inspect_text_scope(document=doc, required_sections=["ITEM_3"], terms=["subpoena"])
                self.assertEqual("INCOMPLETE", scan["coverage_status"])
                self.assertFalse(scan["not_disclosed_confirmed"])

    def test_a_found_span_does_not_close_a_missing_required_scope(self):
        body = BODY.replace("Item 8. Financial Statements", "Appendix Financial Statements")
        scan = inspect_text_scope(document=build_text_document(**binding(annual(body))), required_sections=["ITEM_3", "ITEM_8"], terms=["subpoena"])
        self.assertEqual("FOUND", scan["finding_status"])
        self.assertEqual("INCOMPLETE", scan["coverage_status"])
        self.assertIn("ITEM_8_MISSING", scan["coverage_reasons"])

    def test_amendment_even_with_headings_cannot_claim_full_filing_coverage(self):
        scan = inspect_text_scope(document=build_text_document(**binding(annual(BODY, form="10-K/A"))), required_sections=["ITEM_3"], terms=["subpoena"])
        self.assertEqual("FOUND", scan["finding_status"])
        self.assertEqual("INCOMPLETE", scan["coverage_status"])
        self.assertIn("TEXT_AMENDMENT_SOURCE_SET_REQUIRED", scan["coverage_reasons"])

    def test_subject_url_document_entity_and_period_are_bound(self):
        args = binding(annual(BODY))
        args["expected_company_id"] = "different_entity"
        with self.assertRaisesRegex(TextCoverageError, "COMPANY_MISMATCH"):
            build_text_document(**args)
        for raw in (annual(BODY, cik="54321"), annual(BODY, period="2024-12-31")):
            with self.assertRaises(TextCoverageError):
                build_text_document(**binding(raw))
        args = binding(annual(BODY))
        args["expected_cik"] = "54321"
        with self.assertRaises(ValueError):
            build_text_document(**args)

    def test_utf8_entities_inline_markup_and_visible_hyperlinks_round_trip(self):
        body = BODY.replace("We received a subpoena from an authority.", 'Café &amp; partners received a <b>subpoena</b>; <a href="https://www.sec.gov/">details</a> follow.')
        args = binding(b"\xef\xbb\xbf" + annual(body))
        scan = inspect_text_scope(document=build_text_document(**args), required_sections=["ITEM_3"], terms=["subpoena"])
        finding = scan["findings"][0]
        self.assertIn("Café & partners", finding["text"])
        exact = args["raw_bytes"][finding["raw_start_byte"]:finding["raw_end_byte"]].decode()
        self.assertIn("<b>subpoena</b>", exact)
        self.assertTrue(exact.startswith("Café &amp;"))

    def test_hidden_terms_and_partial_word_sec_are_not_evidence(self):
        body = BODY.replace("We received a subpoena from an authority.", '<span style="display:none">subpoena</span>We provide secure services. <script>investigation</script>')
        scan = inspect_text_scope(document=build_text_document(**binding(annual(body))), required_sections=["ITEM_3"], terms=["SEC", "subpoena", "investigation"])
        self.assertEqual("NOT_FOUND_IN_CHECKED_RANGES", scan["finding_status"])

    def test_rehashed_span_and_source_mutation_fail_independent_replay(self):
        args = binding(annual(BODY))
        doc = build_text_document(**args)
        changed = copy.deepcopy(doc)
        changed["blocks"][0]["raw_start_byte"] += 1
        changed["text_document_id"] = content_hash(value={k: v for k, v in changed.items() if k != "text_document_id"})
        with self.assertRaisesRegex(TextCoverageError, "REPLAY_MISMATCH"):
            verify_text_document(document=changed, **args)
        args["raw_bytes"] = args["raw_bytes"].replace(b"subpoena", b"no issue")
        with self.assertRaisesRegex(TextCoverageError, "BYTES_CHANGED"):
            build_text_document(**args)

    def test_two_unclosed_body_candidates_are_ambiguous(self):
        doubled = BODY + BODY
        doc = build_text_document(**binding(annual(doubled)))
        scan = inspect_text_scope(document=doc, required_sections=["ITEM_3"], terms=["subpoena"])
        self.assertEqual("INCOMPLETE", scan["coverage_status"])
        self.assertIn("ITEM_3_AMBIGUOUS", scan["coverage_reasons"])


if __name__ == "__main__":
    unittest.main()
