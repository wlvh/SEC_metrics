"""Which submissions document lists a pinned filing.

The positive cases run on a recorded root built from Marriott's saved material
with every ``recent`` row filed on or before 2024-06-30 moved into a new
history block (``historical_block_fixture``), so FY2023's own 10-K row, and
FY2024's prior-year row, now sit in a block - the situation six of the frame's
target periods are in and none of them can show, because none has a saved
original. The refusals run on documents built in memory: they are about what
the lookup does with a block, not about any filing.
"""
from pathlib import Path
import atexit
import json
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from sec_urls import submissions_file_url, submissions_url
from vnext.annual_update import saved_source
from vnext.historical_filing_inventory import (HistoricalFilingInventoryError,
                                               filing_inventory)
from vnext.normal_governance_input import _Sources
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_source_authority import ROOT

from tests.vnext.historical_block_fixture import build_repartitioned_root

COMPANY, CIK = "marriott_international", 1048286
BLOCK = "CIK0001048286-submissions-003.json"
FY2023_10K = "0001628280-24-004372"
FY2025_10K = "0001048286-26-000007"


def _no_network():
    return (patch.object(socket.socket, "connect", side_effect=AssertionError("no net")),
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("no dns")))


class _Root:
    """The re-partitioned root, built once for the module."""

    built = None

    @classmethod
    def get(cls):
        if cls.built is None:
            work = Path(tempfile.mkdtemp(prefix="issue47-blocks-"))
            atexit.register(shutil.rmtree, work, ignore_errors=True)
            net, dns = _no_network()
            with net, dns:
                cls.built = build_repartitioned_root(work=work, company_id=COMPANY, cik=CIK,
                                                     cutoff="2024-06-30", block_name=BLOCK)
        return cls.built


def _lookup(root, report_end, accession, *, loaded=None):
    selection = resolve_period_selection(repo_root=root, company_id=COMPANY,
                                         report_end=report_end)
    if loaded is not None:
        selection = {**selection, "loaded_inventories": loaded}
    reader = _Sources(root, COMPANY, str(CIK))
    inventory = reader.read(submissions_url(cik=CIK), role="sec_submissions_inventory",
                            media_type="application/json")
    return inventory, filing_inventory(reader=reader, inventory=inventory,
                                       period_selection=selection, cik=str(CIK),
                                       accession=accession)


class TheRowDecidesWhichDocument(unittest.TestCase):

    def test_the_fixture_moved_the_row_and_kept_the_bytes(self):
        # The premise, checked rather than assumed: the FY2023 10-K row is no
        # longer in the index's recent block, and the block lists it.
        built = _Root.get()
        index = json.loads(built["index_bytes"])
        block = json.loads(built["block_bytes"])
        self.assertNotIn(FY2023_10K, index["filings"]["recent"]["accessionNumber"])
        self.assertIn(FY2023_10K, block["accessionNumber"])
        self.assertEqual([0, 0, 0], built["calls"])

    def test_a_row_in_recent_answers_with_the_main_document_itself(self):
        # The same object the route read, not an equal one: for every period
        # whose row is in recent nothing may change, not even an identity.
        inventory, found = _lookup(_Root.get()["data_root"], "2025-12-31", FY2025_10K)
        self.assertIs(found, inventory)

    def test_a_row_in_a_loaded_block_answers_with_that_block(self):
        inventory, found = _lookup(_Root.get()["data_root"], "2023-12-31", FY2023_10K)
        self.assertIsNot(found, inventory)
        self.assertEqual(BLOCK, found["source_reference"]["document_name"])
        self.assertEqual("sec_submissions_history", found["source_reference"]["source_role"])
        self.assertIn(FY2023_10K, json.loads(found["raw_bytes"])["accessionNumber"])

    def test_the_repository_root_still_answers_with_the_main_document(self):
        # The saved index lists the row in recent, so the unmodified root is
        # the no-change case on the same filing.
        inventory, found = _lookup(ROOT, "2023-12-31", FY2023_10K)
        self.assertIs(found, inventory)

    def test_a_block_the_selection_did_not_load_is_not_searched(self):
        # The selection chose this filing from the blocks it loaded; a row it
        # never read cannot be the one it selected.
        root = _Root.get()["data_root"]
        with self.assertRaises(HistoricalFilingInventoryError) as caught:
            _lookup(root, "2023-12-31", FY2023_10K, loaded=["CIK0001048286.json"])
        self.assertIn("HISTORICAL_FILING_ROW_IN_NO_LOADED_BLOCK:" + FY2023_10K,
                      str(caught.exception))


class _MemoryReader:
    """Serves in-memory documents under their SEC names; nothing else."""

    def __init__(self, documents):
        self.documents = documents

    def read(self, url, *, role, media_type, accession=""):
        name = url.rsplit("/", 1)[-1]
        return {"raw_bytes": json.dumps(self.documents[name]).encode("utf-8"),
                "source_reference": {"document_name": name, "source_role": role}}


def _rows(*rows):
    keys = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")
    return {key: [row[index] for row in rows] for index, key in enumerate(keys)}


ROW_A = ("0000000001-20-000001", "2020-02-10", "2019-12-31", "10-K", "a.htm")
ROW_B = ("0000000001-19-000001", "2019-02-10", "2018-12-31", "10-K", "b.htm")
MAIN = "CIK0000000001.json"


def _main(files):
    return {"cik": "0000000001", "filings": {"recent": _rows(ROW_A), "files": files}}


def _refusal(documents, loaded, accession):
    reader = _MemoryReader(documents)
    inventory = reader.read(MAIN, role="sec_submissions_inventory", media_type="x")
    with unittest.TestCase().assertRaises(HistoricalFilingInventoryError) as caught:
        filing_inventory(reader=reader, inventory=inventory,
                         period_selection={"loaded_inventories": loaded},
                         cik="1", accession=accession)
    return str(caught.exception)


class ABlockIsHeldToThePriorYearWalksChecks(unittest.TestCase):

    def test_a_block_outside_its_declared_range_is_refused(self):
        # The saved JPMorgan blocks are like this: their bodies predate the
        # ranges the saved index declares for them.
        name = "CIK0000000001-submissions-001.json"
        documents = {MAIN: _main([{"name": name, "filingFrom": "2021-01-01",
                                   "filingTo": "2021-12-31"}]),
                     name: _rows(ROW_B)}
        self.assertIn("HISTORICAL_FILING_BLOCK_SNAPSHOT_CONFLICT:" + name,
                      _refusal(documents, [MAIN, name], ROW_B[0]))

    def test_a_block_the_index_does_not_declare_is_refused(self):
        name = "CIK0000000001-submissions-009.json"
        documents = {MAIN: _main([]), name: _rows(ROW_B)}
        self.assertIn("HISTORICAL_FILING_BLOCK_NOT_DECLARED:" + name,
                      _refusal(documents, [MAIN, name], ROW_B[0]))

    def test_another_registrants_block_is_refused(self):
        name = "CIK0000000001-submissions-001.json"
        documents = {MAIN: _main([{"name": name, "filingFrom": "2019-01-01",
                                   "filingTo": "2019-12-31"}]),
                     name: {**_rows(ROW_B), "cik": "0000000002"}}
        self.assertIn("HISTORICAL_FILING_BLOCK_ENTITY_CONFLICT",
                      _refusal(documents, [MAIN, name], ROW_B[0]))

    def test_a_row_two_blocks_list_is_refused(self):
        first, second = ("CIK0000000001-submissions-001.json",
                         "CIK0000000001-submissions-002.json")
        declared = [{"name": first, "filingFrom": "2019-01-01", "filingTo": "2019-12-31"},
                    {"name": second, "filingFrom": "2019-01-01", "filingTo": "2019-12-31"}]
        documents = {MAIN: _main(declared), first: _rows(ROW_B), second: _rows(ROW_B)}
        self.assertIn("HISTORICAL_FILING_ROW_IN_MORE_THAN_ONE_BLOCK:" + ROW_B[0],
                      _refusal(documents, [MAIN, first, second], ROW_B[0]))

    def test_a_selection_that_does_not_start_at_the_main_document_is_refused(self):
        name = "CIK0000000001-submissions-001.json"
        documents = {MAIN: _main([{"name": name, "filingFrom": "2019-01-01",
                                   "filingTo": "2019-12-31"}]),
                     name: _rows(ROW_B)}
        self.assertIn("HISTORICAL_FILING_INVENTORY_ORDER_CHANGED",
                      _refusal(documents, [name, MAIN], ROW_B[0]))


FIELDS = ("applicability", "quality", "publication", "reason_code", "value", "period_start",
          "period_end", "unit")


def _answer(result):
    return {key: result.get(key) for key in FIELDS}


def _listed_in(manifest, source_records):
    """The document a source set was proved against, by its reference id."""
    references = {r["source_reference_id"]: r for r in source_records
                  if r["record_type"] == "SOURCE_REFERENCE"}
    return references[manifest["inventory_source_reference_id"]]["document_name"]


class TheRoutesAnswerTheSameWhereverTheRowIsListed(unittest.TestCase):
    """FY2023's own 10-K row moved; every answer must stay what it was.

    Measured before the change: these sixteen metrics - the accession three,
    the Company Facts eleven and the revenue pair - all stopped on the moved
    root with "Filing accession is absent from submissions", while the other
    twenty-three answered as on the repository root. Where SEC lists a filing
    is bookkeeping; the answers are about the filing.
    """

    @classmethod
    def setUpClass(cls):
        cls.moved = _Root.get()["data_root"]
        net, dns = _no_network()
        with net, dns:
            cls.selections = {
                root: resolve_period_selection(repo_root=root, company_id=COMPANY,
                                               report_end="2023-12-31")
                for root in (ROOT, cls.moved)}

    def _both(self, resolve, **arguments):
        net, dns = _no_network()
        with net, dns:
            return {root: resolve(repo_root=root, company_id=COMPANY,
                                  period_selection=self.selections[root], **arguments)
                    for root in (ROOT, self.moved)}

    def test_the_selection_loaded_the_block_and_chose_the_same_filing(self):
        repository, moved = self.selections[ROOT], self.selections[self.moved]
        self.assertEqual(["CIK0001048286.json"], repository["loaded_inventories"])
        self.assertEqual(["CIK0001048286.json", BLOCK], moved["loaded_inventories"])
        self.assertEqual(repository["current_filing"], moved["current_filing"])

    def test_company_facts(self):
        from vnext.historical_results import resolve_historical_companyfacts_metrics
        both = self._both(resolve_historical_companyfacts_metrics)
        repository, moved = both[ROOT], both[self.moved]
        self.assertEqual(sorted(repository["metrics"]), sorted(moved["metrics"]))
        for metric_id in repository["metrics"]:
            self.assertEqual(_answer(repository["metrics"][metric_id]["result"]),
                             _answer(moved["metrics"][metric_id]["result"]), metric_id)
        self.assertEqual("CIK0001048286.json",
                         _listed_in(repository["source_sets"][0], repository["source_records"]))
        self.assertEqual(BLOCK, _listed_in(moved["source_sets"][0], moved["source_records"]))
        # A value, so the equality is not two identical refusals.
        self.assertEqual("EXACT", moved["metrics"]["B04"]["result"]["quality"])

    def test_the_accession_instance(self):
        from vnext.historical_accession_results import resolve_historical_accession_metrics
        both = self._both(resolve_historical_accession_metrics)
        repository, moved = both[ROOT], both[self.moved]
        for metric_id in repository["metrics"]:
            self.assertEqual(_answer(repository["metrics"][metric_id]["result"]),
                             _answer(moved["metrics"][metric_id]["result"]), metric_id)
        self.assertEqual(BLOCK, _listed_in(moved["source_set"], moved["source_records"]))

    def test_revenue(self):
        from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
        both = self._both(resolve_historical_zero_ai_metric, metric_id="B01")
        repository, moved = both[ROOT], both[self.moved]
        self.assertEqual(_answer(repository["result"]), _answer(moved["result"]))
        self.assertEqual("EXACT", moved["result"]["quality"])
        self.assertEqual(BLOCK, _listed_in(moved["source_set_manifests"][0],
                                           moved["source_records"]))

    def test_the_financial_route_with_the_gate_forced_open(self):
        # No financial registrant has a reachable period, so Marriott stands in
        # with the bank's traits - a constructed input, and the assertions are
        # only about which document the filing was proved against. Without the
        # selection the route asks only the main index, as the ordinary route
        # does, so the moved root refuses there: it is the selection's loaded
        # blocks that let the pinned period through.
        from vnext import historical_financial_results as pinned
        from vnext.traits import repository_company_traits
        bank = repository_company_traits(repo_root=ROOT, company_id="jpmorgan_chase")
        net, dns = _no_network()
        with net, dns, patch.object(pinned, "repository_company_traits", return_value=bank):
            component = pinned.resolve_historical_financial_metric(
                repo_root=self.moved, company_id=COMPANY, metric_id="A04",
                period_selection=self.selections[self.moved])
            self.assertEqual(BLOCK, component["source_references"][0]["document_name"])
            self.assertEqual(FY2023_10K, component["source_references"][1]["accession"])
            with self.assertRaises(HistoricalFilingInventoryError) as caught:
                pinned.resolve_prepared_financial_metric(
                    repo_root=self.moved, company_id=COMPANY, metric_id="A04",
                    prepared=component["input_binding"]["prepared_input"])
        self.assertIn("HISTORICAL_FILING_ROW_IN_NO_LOADED_BLOCK:" + FY2023_10K,
                      str(caught.exception))


if __name__ == "__main__":
    unittest.main()
