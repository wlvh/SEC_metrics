"""A Part III amendment's explanatory note, read whole, as paragraphs and sentences.

The approved classifier refuses Paramount Global's FY2024 10-K/A because its
three-paragraph note is thirteen markup blocks and its purpose sentence
continues past "such Items". historical_amendment_note reads the note whole.
The real cases are the three saved amendments; the counterexamples are that
same filing with one phrase changed in its bytes, each built to be refused for
one reason, because a reader that accepts the real note is only half-tested
until it is seen refusing the notes it must not accept.
"""
import atexit
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from sec_urls import accession_document_url
from tests.vnext.common import REPO_ROOT as ROOT
from vnext.annual_amendment_scope import POLICY, AmendmentScopeError, inspect_annual_amendment_scope
from vnext.annual_update import saved_source
from vnext.historical_amendment_admission import AmendmentAdmissionError, amendment_admission
from vnext.historical_amendment_note import (PART_III_CLASS, AmendmentNoteError,
                                             read_part_iii_note)
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.sources import raw_blob_record, source_reference_record

PARAMOUNT = "paramount_skydance_paramount_global"
EVENTS = ("C01", "E01", "E02", "E03", "E04", "E05")


def _pair(company_id, report_end):
    selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                         report_end=report_end)
    prepared = prepare_historical_annual_input(repo_root=ROOT, company_id=company_id,
                                               period_selection=selection)

    def read(filing):
        url = accession_document_url(cik=int(prepared["entity"]),
                                     accession=filing["accessionNumber"],
                                     document_name=filing["primaryDocument"])
        saved = saved_source(repo_root=ROOT, url=url, accession=filing["accessionNumber"])
        proof = saved["proof"]
        blob = raw_blob_record(repo_root=ROOT,
                               repo_relative_path=proof["request_repo_relative_path"],
                               media_type="text/html")
        reference = source_reference_record(
            raw_blob=blob, company_id=company_id, source_url=url,
            accession=filing["accessionNumber"], document_name=filing["primaryDocument"],
            source_role="annual_source_identity", request_attempt_id=proof["request_attempt_id"])
        return {"raw": saved["raw"], "blob": blob, "reference": reference, "filing": filing}

    return prepared, read(prepared["filing"]), [read(a) for a in prepared["amendments"]]


class _Saved:
    cache = {}

    @classmethod
    def get(cls, company_id, report_end):
        key = (company_id, report_end)
        if key not in cls.cache:
            cls.cache[key] = _pair(company_id, report_end)
        return cls.cache[key]


def _changed(amendment, old, new, *, count=1):
    """The same amendment with one phrase replaced in its bytes, as a source of its own."""
    text = amendment["raw"].decode("utf-8")
    assert text.count(old) >= 1, old
    changed = text.replace(old, new, count).encode("utf-8")
    root = Path(tempfile.mkdtemp(prefix="issue47-note-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    (root / "amendment.htm").write_bytes(changed)
    blob = raw_blob_record(repo_root=root, repo_relative_path="amendment.htm",
                           media_type="text/html")
    reference = source_reference_record(
        raw_blob=blob, company_id=PARAMOUNT, source_url=amendment["reference"]["source_url"],
        accession=amendment["reference"]["accession"],
        document_name=amendment["reference"]["document_name"],
        source_role="annual_source_identity",
        request_attempt_id=amendment["reference"]["request_attempt_id"])
    return {"raw": changed, "blob": blob, "reference": reference,
            "filing": amendment["filing"]}


def _read(amendment, original, prepared):
    return read_part_iii_note(original=original, amendment=amendment, company_id=PARAMOUNT,
                              cik=prepared["entity"],
                              refusal="AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED")


class TheSavedAmendments(unittest.TestCase):

    def test_the_classifier_refuses_the_predecessor_note_on_its_markup(self):
        prepared, original, (amendment,) = _Saved.get(PARAMOUNT, "2024-12-31")
        with self.assertRaisesRegex(AmendmentScopeError, "AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED"):
            inspect_annual_amendment_scope(original=original, amendment=amendment,
                                           company_id=PARAMOUNT, cik=prepared["entity"])

    def test_read_whole_it_is_the_approved_class(self):
        prepared, original, (amendment,) = _Saved.get(PARAMOUNT, "2024-12-31")
        scope = _read(amendment, original, prepared)
        self.assertEqual(scope["classification"], PART_III_CLASS)
        self.assertEqual(scope["unchanged_input_classes"], ["FISCAL_EVENT_WINDOW"])
        self.assertTrue(scope["original_statement_admission_requires_further_review"])
        self.assertEqual((scope["note"]["block_count"], len(scope["note"]["paragraphs"])), (12, 3))
        self.assertEqual([row["kind"] for row in scope["note"]["sentences"]],
                         ["PURPOSE", "NO_CHANGE", "DEFINED_TERMS"])
        self.assertEqual(scope["note"]["purpose_continuation"],
                         ", rather than incorporate such information into Part III by reference"
                         " to a proxy statement.")
        self.assertEqual(scope["pointer"], {"period_end": "2024-12-31",
                                            "original_filing_date": "2025-02-26"})

    def test_where_the_classifier_does_classify_the_reading_agrees(self):
        prepared, original, (amendment,) = _Saved.get(PARAMOUNT, "2025-12-31")
        frozen = inspect_annual_amendment_scope(original=original, amendment=amendment,
                                                company_id=PARAMOUNT, cik=prepared["entity"])
        ours = _read(amendment, original, prepared)
        self.assertEqual((ours["classification"], ours["unchanged_input_classes"]),
                         (frozen["classification"], frozen["unchanged_input_classes"]))
        self.assertEqual(ours["details"]["parts"], frozen["details"]["parts"])
        self.assertEqual(ours["details"]["items"], frozen["details"]["items"])
        self.assertEqual(ours["details"]["no_new_financial_statement_declarations"],
                         [block["text"] for block in
                          frozen["details"]["no_new_financial_statement_declarations"]])

    def test_an_exhibit_link_correction_is_not_read_as_part_iii(self):
        prepared, original, (amendment,) = _Saved.get("southwest_airlines", "2025-12-31")
        with self.assertRaisesRegex(AmendmentNoteError, "AMENDMENT_NOTE_SENTENCE_NOT_RECOGNIZED"):
            read_part_iii_note(original=original, amendment=amendment,
                               company_id="southwest_airlines", cik=prepared["entity"],
                               refusal="AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN")


class NotesItMustRefuse(unittest.TestCase):
    """The predecessor's own bytes with one phrase changed."""

    @classmethod
    def setUpClass(cls):
        cls.prepared, cls.original, (cls.amendment,) = _Saved.get(PARAMOUNT, "2024-12-31")

    def _refused(self, old, new, reason, count=1):
        changed = _changed(self.amendment, old, new, count=count)
        with self.assertRaisesRegex(AmendmentNoteError, reason):
            _read(changed, self.original, self.prepared)

    def test_another_purpose_in_the_continuation(self):
        self._refused(", rather than incorporate such information into Part III by reference to"
                      " a proxy statement.",
                      ", and to amend Item 8 to restate the consolidated financial statements.",
                      "AMENDMENT_NOTE_SENTENCE_NOT_RECOGNIZED:0")

    def test_another_item_inside_what_the_approved_pattern_leaves_open(self):
        # The approved pattern's ".+?" would take this sentence; the reader's
        # narrower middle does not, which is the point of narrowing it.
        sentence = ("to amend Part III, Items 10, 11, 12, 13 and 14 and Item 8 of the Initial"
                    " Form 10-K to include the information required by such Items.")
        self.assertIsNotNone(re.search(POLICY["part_iii_purpose_pattern"], sentence, re.I))
        self._refused("Items 10, 11, 12, 13 and 14 of the Initial Form",
                      "Items 10, 11, 12, 13 and 14 and Item 8 of the Initial Form",
                      "AMENDMENT_NOTE_SENTENCE_NOT_RECOGNIZED:0")

    def test_an_extra_sentence_after_an_approved_one(self):
        self._refused("unless the context otherwise requires.",
                      "unless the context otherwise requires. This Amendment also restates the"
                      " consolidated balance sheet.",
                      "AMENDMENT_NOTE_SENTENCE_NOT_RECOGNIZED:2")

    def test_a_pointer_to_another_report(self):
        self._refused("on February&#160;26, 2025 (the", "on February&#160;26, 2024 (the",
                      "AMENDMENT_NOTE_NAMES_ANOTHER_REPORT:2024-12-31:2024-02-26")

    def test_no_no_change_statement(self):
        # Replaced by a sentence the reader does recognize, so what refuses the
        # note is the missing statement, not an unreadable sentence.
        self._refused("Except as explicitly set forth herein, this Amendment does not otherwise"
                      " change, modify or update the disclosures in, or exhibits to, the Initial"
                      " Form <div style=\"white-space:nowrap;display:inline;\">10-K.</div>",
                      "References to &#8220;we&#8221; refer to Paramount Global and its"
                      " consolidated subsidiaries, unless the context otherwise requires.",
                      "AMENDMENT_NOTE_PURPOSE_AND_NO_CHANGE_NOT_EACH_ONCE")

    def test_defined_terms_naming_another_registrant(self):
        self._refused("refer to Paramount Global and its consolidated subsidiaries",
                      "refer to Acme Holdings and its consolidated subsidiaries",
                      "AMENDMENT_NOTE_SENTENCE_NOT_RECOGNIZED:2")

    def test_a_note_that_reads_right_on_an_amendment_that_files_statements(self):
        # The note is untouched; Item 15 no longer declares that no financial
        # statements are filed. The structure the classifier checks refuses it.
        self._refused("No financial statements or supplemental data are filed with this Amendment.",
                      "Financial statements and supplemental data are filed with this Amendment.",
                      "PART_III_ONLY_SOURCE_SCOPE_NOT_PROVEN")

    def test_a_note_longer_than_the_bound(self):
        paragraph = ("refer to Paramount Global and its consolidated subsidiaries, unless the"
                     " context otherwise requires. </div>")
        extra = ("<div>References to &#8220;we&#8221; refer to Paramount Global and its"
                 " consolidated subsidiaries, unless the context otherwise requires. </div>") * 7
        self._refused(paragraph, paragraph + extra, "AMENDMENT_NOTE_PARAGRAPHS_OUT_OF_BOUND:10")


class TheAdmissionAsksIt(unittest.TestCase):

    def test_the_predecessor_s_event_window_is_cleared_and_its_statements_are_not(self):
        prepared, _, _ = _Saved.get(PARAMOUNT, "2024-12-31")
        record = amendment_admission(repo_root=ROOT, company_id=PARAMOUNT,
                                     metric_ids=list(EVENTS), prepared=prepared,
                                     event_metric_ids=EVENTS)
        self.assertTrue(record["admitted"])
        self.assertEqual([a["classification"] for a in record["amendments"]], [PART_III_CLASS])
        with self.assertRaisesRegex(AmendmentAdmissionError,
                                    "ORIGINAL_STATEMENT_VALUES:" + PART_III_CLASS):
            amendment_admission(repo_root=ROOT, company_id=PARAMOUNT, metric_ids=["B01"],
                                prepared=prepared, event_metric_ids=EVENTS)


if __name__ == "__main__":
    unittest.main()
