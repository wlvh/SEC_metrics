"""The XBRL instances an annual accession's index lists, declared for C04 and B06.

The declaration runs the frozen governance reader's ``auditor_filing`` with a
reader that records the instance documents instead of reading them, so the
list is the frozen reader's own. Checked here against the same reader run for
real on an accession whose instances are saved (Marriott's latest two years in
the checkout). Zero calls.
"""
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import historical_instance_sources as declaration
from vnext.historical_sec_resume import TERMINAL_CLASSES
from vnext.historical_source_acquisition import (HistoricalAcquisitionError, declared_frame,
                                                 historical_dependency)
from vnext.normal_governance_input import _Sources
from vnext.normal_history_plan import checkpoint_replayed_once

COMPANY = "marriott_international"


class TheDeclarationIsWhatTheFrozenReaderReadsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with checkpoint_replayed_once():
            cls.frame = declared_frame(repo_root=ROOT, company_id=COMPANY)
        cls.rows = [row for row in cls.frame["requirements"]
                    if row["dependency_class"] == declaration.DEPENDENCY_CLASS]
        cls.primaries = {row["accession"]: row for row in cls.frame["requirements"]
                         if row["dependency_class"] == declaration.PRIMARY_CLASS}

    def test_every_saved_index_names_exactly_what_the_reader_reads(self):
        by_accession = {}
        for row in self.rows:
            by_accession.setdefault(row["accession"], set()).add(row["source_url"])
        self.assertTrue(by_accession)
        for accession, declared in by_accession.items():
            with self.subTest(accession=accession):
                reader = _Sources(ROOT, COMPANY, "1048286")
                sources = reader.auditor_filing({
                    "accessionNumber": accession, "form": "10-K",
                    "primaryDocument": self.primaries[accession]["document_name"]})
                read = {item["source_reference"]["source_url"] for item in sources
                        if item["source_reference"]["source_url"].endswith(".xml")}
                self.assertEqual(read, declared)
                self.assertEqual(reader.file_sets[-1]["expected_xml_documents"],
                                 sorted(url.rsplit("/", 1)[1] for url in declared))

    def test_the_saved_instances_are_classified_as_saved(self):
        self.assertTrue(self.rows)
        for row in self.rows:
            with self.subTest(url=row["source_url"]):
                self.assertEqual(("VERIFIED_SAVED_SOURCE", False),
                                 (row["saved_status"], row["new_acquisition_required"]))
                self.assertEqual([declaration.ROLE], row["source_roles"])

    def test_an_index_not_saved_is_a_limitation_not_an_empty_set(self):
        unsaved = {row["accession"] for row in self.frame["requirements"]
                   if row["dependency_class"] == declaration.INDEX_CLASS
                   and row["saved_status"] != "VERIFIED_SAVED_SOURCE"}
        self.assertTrue(unsaved)
        named = {item["accession"] for item in self.frame["instance_declaration_limitations"]
                 if item["reason"] == "ACCESSION_INDEX_NOT_SAVED"}
        self.assertEqual(unsaved, named)

    def test_a_sibling_the_reader_does_not_read_is_not_declared(self):
        instance = self.rows[0]["source_url"]
        sibling = instance.replace("_htm.xml", "_cal.xml")
        self.assertIsNotNone(historical_dependency(repo_root=ROOT, company_id=COMPANY,
                                                   url=instance))
        with self.assertRaisesRegex(HistoricalAcquisitionError, "NOT_A_DECLARED_DEPENDENCY"):
            historical_dependency(repo_root=ROOT, company_id=COMPANY, url=sibling)

    def test_capturing_an_instance_declares_nothing_new(self):
        self.assertIn(declaration.DEPENDENCY_CLASS, TERMINAL_CLASSES)


if __name__ == "__main__":
    unittest.main()
