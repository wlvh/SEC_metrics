"""Issue #47: fiscal-year definitions older annual reports write in forms the frozen scan cannot read.

The real cases are the two Macy's annual reports the acquisition saved
(``evidence/issue47_acquired``), read from the export's own archives and
checked against the digests its index records: FY2022, whose notes sentence
appends the week count after "respectively", and FY2021, which has that and a
reference sentence naming the registrant without its legal form. The
constructed cases are small documents run through the frozen scan itself, so
what they are measured against is the frozen reading, not a copy of it.
"""
import copy
import hashlib
import html
import json
import re
import tarfile
import unittest
from unittest.mock import patch

from sec_urls import companyfacts_url

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import fiscal_year_labels as frozen
from vnext import historical_annual_input
from vnext import historical_fiscal_labels as successor
from vnext.annual_update import saved_source
from vnext.historical_dei import release_aware
from vnext.normal_period_selection import resolve_period_selection

EXPORT = ROOT / "evidence/issue47_acquired"
UNRESOLVED = "EXPLICIT_DEFINITION_UNRESOLVED"


def _exported(document_name):
    """One saved original from the export's archives, checked against the index's digest."""
    index = json.loads((EXPORT / "export.json").read_text(encoding="utf-8"))
    found = [(archive["name"], path, meta) for archive in index["row_archives"]
             for path, meta in archive["members"].items()
             if path.rsplit("/", 1)[-1] == document_name]
    assert len(found) == 1, document_name
    name, path, meta = found[0]
    with tarfile.open(EXPORT / name) as archive:
        data = archive.extractfile(path).read()
    assert hashlib.sha256(data).hexdigest() == meta["sha256"], document_name
    return data


def _sha(data):
    return hashlib.sha256(data).hexdigest()


_FROZEN_INSPECTION = release_aware(frozen.inspect_fiscal_year_labels)


def _inspect(report_end):
    """The frozen inspection of a saved Macy's annual report, through the DEI view."""
    selection = resolve_period_selection(repo_root=ROOT, company_id="macys",
                                         report_end=report_end)
    filing = selection["current_filing"]
    cik = selection["reporting_cik"]
    primary = _exported(filing["primaryDocument"])
    facts = saved_source(repo_root=ROOT, url=companyfacts_url(cik=int(cik)),
                         accession=filing["accessionNumber"])["raw"]
    inspected = _FROZEN_INSPECTION(
        primary_bytes=primary, companyfacts_bytes=facts, expected_primary_sha256=_sha(primary),
        expected_companyfacts_sha256=_sha(facts), expected_cik=cik, filing=filing)
    return inspected, primary


def _document(*paragraphs):
    body = "".join("<div><span>" + text + "</span></div>" for text in paragraphs)
    return ("<html><body>" + body + "</body></html>").encode("utf-8")


def _constructed(raw, *, end="2023-01-28", names=("Example Stores, Inc.",), dei=2022):
    """An inspection of ``raw`` built the way the frozen inspector builds one."""
    definitions, unparsed = frozen._definitions(raw, end, list(names))
    inspected = {"status": None, "primary_sha256": _sha(raw), "source_definitions": definitions,
                 "unsupported_definition_leads": unparsed, "registrant_names": list(names),
                 "actual_period": {"period_start": "2022-01-30", "period_end": end},
                 "dei_fiscal_year": dei, "companyfacts_fiscal_year_values": [dei],
                 "invalid_companyfacts_fy_rows": []}
    labels, status, proposed = successor._status(inspected, definitions, unparsed)
    inspected.update(current_definition_labels=labels, status=status,
                     source_defined_fiscal_year=proposed, new_rule_label_proposal=proposed,
                     inspection_id="sha256:" + "0" * 64)
    return inspected


ALIAS = ("Unless the context requires otherwise, references to &#8220;{alias}&#8221; or the "
         "&#8220;Company&#8221; are references to {alias} and its subsidiaries and references to "
         "&#8220;2022,&#8221; &#8220;2021,&#8221; and &#8220;2020&#8221; are references to the "
         "Company&#8217;s fiscal years ended January 28, 2023, January 29, 2022 and January 30, "
         "2021, respectively.")
ORDERED = ("The Company&#8217;s fiscal year ends on the Saturday closest to January 31. Fiscal "
           "years {labels} ended on January 28, 2023, January 29, 2022 and January 30, 2021, "
           "respectively{tail}")


class OlderAnnualReportsDefineTheirYearsInTwoMoreForms(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cases = {end: _inspect(end) for end in ("2023-01-28", "2022-01-29")}

    def test_the_ordered_form_with_its_week_count_is_read(self):
        inspected, primary = self.cases["2023-01-28"]
        self.assertEqual(UNRESOLVED, inspected["status"])
        self.assertEqual(["DEFINITION_SYNTAX_NOT_SUPPORTED"],
                         [lead["reason"] for lead in inspected["unsupported_definition_leads"]])
        widened = successor.widen_inspection(inspected=inspected, primary_bytes=primary)
        self.assertEqual(("SOURCE_LABELS_CONSISTENT", 2022, [2022]),
                         (widened["status"], widened["source_defined_fiscal_year"],
                          widened["current_definition_labels"]))
        added = widened["definitions_read_by_the_widened_forms"]
        self.assertEqual(["EXPLICIT_ORDERED_YEARS"], [item["kind"] for item in added])
        self.assertEqual([{"fiscal_year": 2022, "period_end": "2023-01-28"},
                          {"fiscal_year": 2021, "period_end": "2022-01-29"},
                          {"fiscal_year": 2020, "period_end": "2021-01-30"}],
                         added[0]["mapping"])
        self.assertIn("respectively, and included 52 weeks.", added[0]["text"])
        # What the frozen scan read is kept as it read it.
        for item in inspected["source_definitions"]:
            self.assertIn(item, widened["source_definitions"])
        self.assertEqual([], widened["unsupported_definition_leads"])
        self.assertEqual({"inspection_id": inspected["inspection_id"], "status": UNRESOLVED,
                          "unsupported_definition_leads":
                              inspected["unsupported_definition_leads"]},
                         widened["frozen_inspection"])
        self.assertEqual(successor.FORMS_RULE, widened["definition_forms_rule"])
        self.assertNotEqual(inspected["inspection_id"], widened["inspection_id"])

    def test_the_alias_without_its_legal_form_is_read(self):
        inspected, primary = self.cases["2022-01-29"]
        self.assertEqual(UNRESOLVED, inspected["status"])
        self.assertEqual(["Macy's, Inc."], inspected["registrant_names"])
        self.assertEqual({"DEFINITION_ISSUER_ALIAS_NOT_PROVEN", "DEFINITION_SYNTAX_NOT_SUPPORTED"},
                         {lead["reason"] for lead in inspected["unsupported_definition_leads"]})
        widened = successor.widen_inspection(inspected=inspected, primary_bytes=primary)
        self.assertEqual(("SOURCE_LABELS_CONSISTENT", 2021),
                         (widened["status"], widened["source_defined_fiscal_year"]))
        self.assertEqual({"EXPLICIT_REFERENCE_YEARS", "EXPLICIT_ORDERED_YEARS"},
                         {item["kind"] for item in
                          widened["definitions_read_by_the_widened_forms"]})
        self.assertEqual([], widened["unsupported_definition_leads"])

    def test_every_added_definition_returns_to_the_original_bytes(self):
        for end, (inspected, primary) in self.cases.items():
            widened = successor.widen_inspection(inspected=inspected, primary_bytes=primary)
            for item in widened["definitions_read_by_the_widened_forms"]:
                with self.subTest(end=end, kind=item["kind"]):
                    span = primary[item["raw_start_byte"]:item["raw_end_byte"]]
                    self.assertEqual(_sha(span), item["raw_span_sha256"])
                    text = " ".join(html.unescape(re.sub("<[^>]+>", "", span.decode())).split())
                    self.assertEqual(item["text"], text)

    def test_the_frozen_rule_is_what_decides(self):
        # Over what the frozen scan read, the rule here gives the frozen answer.
        for end, (inspected, _) in self.cases.items():
            with self.subTest(end=end):
                _, status, label = successor._status(
                    inspected, inspected["source_definitions"],
                    inspected["unsupported_definition_leads"])
                self.assertEqual((inspected["status"], inspected["source_defined_fiscal_year"]),
                                 (status, label))

    def test_the_bytes_must_be_the_inspected_ones(self):
        inspected, primary = self.cases["2023-01-28"]
        with self.assertRaises(successor.HistoricalFiscalLabelError) as caught:
            successor.widen_inspection(inspected=inspected, primary_bytes=primary + b" ")
        self.assertIn("PRIMARY_BYTES_ARE_NOT_THE_INSPECTED_ONES", str(caught.exception))


class OnlyAnUnresolvedPeriodIsReadAgain(unittest.TestCase):

    def test_a_resolved_period_is_the_frozen_inspection_itself(self):
        raw = _document(ALIAS.format(alias="Example Stores, Inc."))
        inspected = _constructed(raw)
        self.assertEqual("SOURCE_LABELS_CONSISTENT", inspected["status"])
        # Not even read: the bytes given are not the inspected ones.
        self.assertIs(inspected, successor.widen_inspection(inspected=inspected,
                                                            primary_bytes=b""))

    def test_the_pinned_input_reads_its_label_here(self):
        self.assertIs(successor.inspect_prepared_fiscal_year_labels,
                      historical_annual_input.inspect_prepared_fiscal_year_labels)


class TheWidenedFormsAreNarrow(unittest.TestCase):

    def test_both_forms_are_read_in_a_constructed_document(self):
        raw = _document(ALIAS.format(alias="Example Stores"),
                        ORDERED.format(labels="2022, 2021 and 2020",
                                       tail=", and included 52 weeks."))
        inspected = _constructed(raw)
        self.assertEqual(UNRESOLVED, inspected["status"])
        widened = successor.widen_inspection(inspected=inspected, primary_bytes=raw)
        self.assertEqual(("SOURCE_LABELS_CONSISTENT", 2022),
                         (widened["status"], widened["source_defined_fiscal_year"]))

    def test_another_clause_after_respectively_still_stops_the_period(self):
        for tail in (", and included 52 weeks, 53 weeks and 52 weeks.",
                     ", and each included 52 weeks.", ", except as noted."):
            with self.subTest(tail=tail):
                raw = _document(ORDERED.format(labels="2022, 2021 and 2020", tail=tail))
                inspected = _constructed(raw)
                widened = successor.widen_inspection(inspected=inspected, primary_bytes=raw)
                self.assertEqual(UNRESOLVED, widened["status"])

    def test_an_alias_naming_another_entity_still_stops_the_period(self):
        raw = _document(ALIAS.format(alias="Other Holdings"),
                        ORDERED.format(labels="2022, 2021 and 2020",
                                       tail=", and included 52 weeks."))
        inspected = _constructed(raw)
        widened = successor.widen_inspection(inspected=inspected, primary_bytes=raw)
        # The ordered form is read; the reference sentence still does not name the
        # registrant, and it mentions the period's end year, so the period stops.
        self.assertEqual(UNRESOLVED, widened["status"])
        self.assertEqual(["DEFINITION_ISSUER_ALIAS_NOT_PROVEN"],
                         [lead["reason"] for lead in widened["unsupported_definition_leads"]])

    def test_a_legal_form_is_dropped_only_from_the_end_of_the_name(self):
        self.assertEqual(["example stores", "example stores inc"],
                         successor._name_forms(["Example Stores, Inc."]))
        self.assertEqual(["co"], successor._name_forms(["Co"]))
        self.assertEqual(["company stores"], successor._name_forms(["Company Stores"]))

    def test_a_widened_reading_that_names_a_second_label_stops_the_period(self):
        raw = _document(ALIAS.format(alias="Example Stores, Inc."),
                        ORDERED.format(labels="2023, 2021 and 2020",
                                       tail=", and included 52 weeks."))
        inspected = _constructed(raw)
        self.assertEqual(([2022], UNRESOLVED),
                         (inspected["current_definition_labels"], inspected["status"]))
        widened = successor.widen_inspection(inspected=inspected, primary_bytes=raw)
        self.assertEqual(UNRESOLVED, widened["status"])
        self.assertEqual([2022, 2023], widened["current_definition_labels"])
        self.assertIsNone(widened["source_defined_fiscal_year"])

    def test_a_widened_scan_that_changes_a_frozen_definition_is_refused(self):
        raw = _document(ALIAS.format(alias="Example Stores, Inc."),
                        ORDERED.format(labels="2022, 2021 and 2020",
                                       tail=", and included 52 weeks."))
        inspected = _constructed(raw)
        scan = successor._widened_definitions()

        def dropping(*arguments):
            definitions, unparsed = scan(*arguments)
            return definitions[1:], unparsed
        with patch.object(successor, "_widened_definitions", return_value=dropping):
            with self.assertRaises(successor.HistoricalFiscalLabelError) as caught:
                successor.widen_inspection(inspected=inspected, primary_bytes=raw)
        self.assertIn("CHANGED_A_FROZEN_DEFINITION", str(caught.exception))

    def test_a_widened_scan_that_leaves_a_new_lead_is_refused(self):
        raw = _document(ORDERED.format(labels="2022, 2021 and 2020",
                                       tail=", and included 52 weeks."))
        inspected = _constructed(raw)
        scan = successor._widened_definitions()

        def adding(*arguments):
            definitions, unparsed = scan(*arguments)
            return definitions, unparsed + [{"block_index": 99, "text": "x", "reason": "NEW"}]
        with patch.object(successor, "_widened_definitions", return_value=adding):
            with self.assertRaises(successor.HistoricalFiscalLabelError) as caught:
                successor.widen_inspection(inspected=inspected, primary_bytes=raw)
        self.assertIn("LEFT_A_NEW_LEAD", str(caught.exception))

    def test_the_frozen_ordered_form_must_still_end_where_it_did(self):
        changed = re.compile(frozen._MULTI.pattern[:-len(r"respectively\.")] + r"respectively",
                             frozen._MULTI.flags)
        with patch.object(frozen, "_MULTI", changed):
            with self.assertRaises(successor.HistoricalFiscalLabelError) as caught:
                successor._ordered_pattern()
        self.assertIn("FROZEN_ORDERED_FORM_CHANGED", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
