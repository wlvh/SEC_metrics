"""Small metadata controls; real historical rows are covered by the pilot CLI."""
import json
import unittest
from vnext.historical_filing_inventory import HistoricalFilingInventoryError, filing_inventory, prior_filing

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


class ExplicitPriorOriginalSelection(unittest.TestCase):
    """Constructed metadata controls, not financial amendment admission."""

    def setUp(self):
        self.amendment = ("0000000001-19-000002", "2019-03-10", "2018-12-31", "10-K/A", "ba.htm")
        body = {"cik": "1", "filings": {"recent": _rows(ROW_A, ROW_B, self.amendment), "files": []}}
        self.reader = _MemoryReader({MAIN: body})
        self.inventory = self.reader.read(MAIN, role="sec_submissions_inventory", media_type="x")
        names = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")
        self.prior = dict(zip(names, ROW_B))
        self.amended = dict(zip(names, self.amendment))
        self.prepared = {"entity": "1", "filing": {"reportDate": ROW_A[2]}}
        self.selection = {"prior_filing": self.prior, "prior_report_end": ROW_B[2],
                          "prior_amendments": [self.amended]}

    def test_default_still_refuses_a_prior_amendment(self):
        with self.assertRaisesRegex(ValueError, "PRIOR_AMENDMENT_REPLAY_NOT_IMPLEMENTED"):
            prior_filing(self.reader, self.inventory, self.prepared)

    def test_explicit_complete_chain_selects_only_the_original(self):
        row, inventory = prior_filing(self.reader, self.inventory, self.prepared,
                                     period_selection=self.selection)
        self.assertEqual(self.prior, {key: row[key] for key in self.prior})
        self.assertEqual({"inventory_name": MAIN, "row_index": 1}, row["metadata_origin"])
        self.assertIs(self.inventory, inventory)
        self.assertEqual("10-K", row["form"])

    def test_missing_extra_or_wrong_chain_cannot_select_values(self):
        for changed in ({"prior_amendments": []}, {"prior_amendments": [self.amended, self.amended]},
                        {"prior_filing": self.amended}, {"prior_report_end": "2017-12-31"}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "PRIOR_SELECTION_CHAIN_CHANGED"):
                prior_filing(self.reader, self.inventory, self.prepared,
                             period_selection={**self.selection, **changed})

    def test_all_amendments_are_required_in_selected_order(self):
        second=("0000000001-19-000003","2019-04-10","2018-12-31","10-K/A","bb.htm")
        body={"cik":"1","filings":{"recent":_rows(ROW_A,ROW_B,second,self.amendment),"files":[]}}
        reader=_MemoryReader({MAIN:body})
        inventory=reader.read(MAIN,role="sec_submissions_inventory",media_type="x")
        names=("accessionNumber","filingDate","reportDate","form","primaryDocument")
        second_identity=dict(zip(names,second))
        complete={**self.selection,"prior_amendments":[self.amended,second_identity]}
        self.assertEqual(ROW_B[0],prior_filing(reader,inventory,self.prepared,
                                            period_selection=complete)[0]["accessionNumber"])
        for amendments in ([self.amended],[second_identity,self.amended]):
            with self.subTest(amendments=amendments),self.assertRaisesRegex(ValueError,"PRIOR_SELECTION_CHAIN_CHANGED"):
                prior_filing(reader,inventory,self.prepared,
                             period_selection={**complete,"prior_amendments":amendments})
