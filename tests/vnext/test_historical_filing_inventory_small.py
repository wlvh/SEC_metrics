"""Small metadata controls; real historical rows are covered by the pilot CLI."""
import json
import unittest
from vnext.historical_filing_inventory import HistoricalFilingInventoryError, filing_inventory

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
                                   "filingTo": "2021-12-31", "filingCount": 1}]),
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
                                   "filingTo": "2019-12-31", "filingCount": 1}]),
                     name: {**_rows(ROW_B), "cik": "0000000002"}}
        self.assertIn("HISTORICAL_FILING_BLOCK_ENTITY_CONFLICT",
                      _refusal(documents, [MAIN, name], ROW_B[0]))

    def test_a_row_two_blocks_list_is_refused(self):
        first, second = ("CIK0000000001-submissions-001.json",
                         "CIK0000000001-submissions-002.json")
        # SEC declares every block's filing count; the blocks here hold what
        # they declare, so the only thing wrong is the row both of them list.
        declared = [{"name": first, "filingFrom": "2019-01-01", "filingTo": "2019-12-31",
                     "filingCount": 1},
                    {"name": second, "filingFrom": "2019-01-01", "filingTo": "2019-12-31",
                     "filingCount": 1}]
        documents = {MAIN: _main(declared), first: _rows(ROW_B), second: _rows(ROW_B)}
        self.assertIn("HISTORICAL_FILING_ROW_IN_MORE_THAN_ONE_BLOCK:" + ROW_B[0],
                      _refusal(documents, [MAIN, first, second], ROW_B[0]))

    def test_a_selection_that_does_not_start_at_the_main_document_is_refused(self):
        name = "CIK0000000001-submissions-001.json"
        documents = {MAIN: _main([{"name": name, "filingFrom": "2019-01-01",
                                   "filingTo": "2019-12-31", "filingCount": 1}]),
                     name: _rows(ROW_B)}
        self.assertIn("HISTORICAL_FILING_INVENTORY_ORDER_CHANGED",
                      _refusal(documents, [name, MAIN], ROW_B[0]))


