"""A saved history block is trusted only if it is the block its index declares.

SEC splits a registrant's older filings into history blocks and declares each
block's date range and filing count in the main submissions document. Two
things about those declarations were measured on the saved and acquired
indexes, and both made the frozen check (``history_body_alignment``) give the
wrong answer:

* SEC leaves one undeclared day between one block's declared end and the next
  newer block's start, and puts the filings dated on it in the older block. The
  frozen check refused every such block - JPMorgan's 69 blocks, fetched within
  two minutes of their index, stayed "incoherent" however often they were
  fetched again.
* A block saved at another time than its index, or cut from another partition,
  can be missing filings while every filing it holds is in range. The frozen
  check looked only at the dates of the forms the catalog keeps, so it passed
  them: JPMorgan's block 007 held none of those forms at all, and the newest
  blocks of Pfizer and Salesforce lack the filings that aged out of the recent
  list after they were saved.

The first classes use made-up blocks so each case says exactly what is
checked; the last reads the real saved and acquired blocks. Zero calls.
"""
import json
import sys
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.historical_filing_inventory import prior_filing
from vnext.normal_companyfacts_results import NormalCompanyfactsError, _prior_filing
from vnext.normal_governance_input import history_body_alignment
from vnext.normal_history_catalog import (_candidate, block_last_days,
                                          history_block_coherence)

sys.path.insert(0, str(ROOT / "tools"))
from acceptance_readings import _export_member_bytes, _export_members, saved_bytes  # noqa: E402

CIK = "0000000001"


def _rows(entries):
    """Column-shaped rows as SEC writes them: (form, filingDate, reportDate)."""
    columns = {key: [] for key in ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime",
                                   "form", "primaryDocument")}
    for number, (form, filed, report) in enumerate(entries, start=1):
        columns["accessionNumber"].append("0000000001-%s-%06d" % (filed[2:4], number))
        columns["filingDate"].append(filed)
        columns["reportDate"].append(report)
        columns["acceptanceDateTime"].append(filed + "T12:00:00.000Z")
        columns["form"].append(form)
        columns["primaryDocument"].append("doc%d.htm" % number)
    return columns


def _kept(body, name):
    from vnext.normal_governance_input import _filings
    return _filings(body, inventory_name=name)


class TheBlockEndsTheDayBeforeTheNextOneStarts(unittest.TestCase):
    def setUp(self):
        self.shards = [
            {"name": "CIK%s-submissions-001.json" % CIK, "filingFrom": "2024-03-03",
             "filingTo": "2024-05-31", "filingCount": 1},
            {"name": "CIK%s-submissions-002.json" % CIK, "filingFrom": "2024-01-02",
             "filingTo": "2024-03-01", "filingCount": 2},
        ]
        self.payload = {"filings": {"recent": _rows([("8-K", "2024-06-03", "")]),
                                    "files": self.shards}}

    def test_each_block_ends_the_day_before_the_next_newer_one_starts(self):
        last = block_last_days(payload=self.payload, shards=self.shards)
        # 002 is declared to 03-01 and 001 starts 03-03: 03-02 is the gap day.
        self.assertEqual("2024-03-02", last["CIK%s-submissions-002.json" % CIK])
        # The newest block's next newer one is the recent list.
        self.assertEqual("2024-06-02", last["CIK%s-submissions-001.json" % CIK])

    def test_a_block_never_ends_before_its_declared_end(self):
        overlapping = [dict(self.shards[0], filingFrom="2024-02-15"), self.shards[1]]
        last = block_last_days(payload=self.payload, shards=overlapping)
        self.assertEqual("2024-03-01", last["CIK%s-submissions-002.json" % CIK])

    def test_a_filing_on_the_gap_day_is_in_the_older_block(self):
        body = _rows([("8-K", "2024-01-05", ""), ("8-K", "2024-03-02", "")])
        shard = self.shards[1]
        last = block_last_days(payload=self.payload, shards=self.shards)[shard["name"]]
        self.assertIsNone(history_block_coherence(shard=shard, body=body,
                                                  rows=_kept(body, shard["name"]), last_day=last))
        # The frozen check refuses the same block for the gap-day filing.
        self.assertIsNotNone(history_body_alignment(shard=shard, rows=_kept(body, shard["name"])))

    def test_a_filing_on_the_next_block_s_first_day_is_outside(self):
        body = _rows([("8-K", "2024-01-05", ""), ("8-K", "2024-03-03", "")])
        shard = self.shards[1]
        conflict = history_block_coherence(
            shard=shard, body=body, rows=_kept(body, shard["name"]),
            last_day=block_last_days(payload=self.payload, shards=self.shards)[shard["name"]])
        self.assertEqual(["FILINGS_OUTSIDE_THE_BLOCK"], conflict["failed_checks"])
        self.assertEqual(1, conflict["filings_outside_the_block"])

    def test_a_filing_before_the_declared_start_is_outside(self):
        body = _rows([("8-K", "2023-12-29", ""), ("8-K", "2024-01-05", "")])
        shard = self.shards[1]
        conflict = history_block_coherence(shard=shard, body=body,
                                           rows=_kept(body, shard["name"]), last_day="2024-03-02")
        self.assertEqual(["FILINGS_OUTSIDE_THE_BLOCK"], conflict["failed_checks"])

    def test_a_block_missing_filings_is_not_the_declared_block(self):
        # Every filing it holds is in range - all the frozen check looks at.
        body = _rows([("8-K", "2024-01-05", "")])
        shard = self.shards[1]
        self.assertIsNone(history_body_alignment(shard=shard, rows=_kept(body, shard["name"])))
        conflict = history_block_coherence(shard=shard, body=body,
                                           rows=_kept(body, shard["name"]), last_day="2024-03-02")
        self.assertEqual(["FILING_COUNT_DIFFERS_FROM_DECLARED"], conflict["failed_checks"])
        self.assertEqual((2, 1), (conflict["declared_filing_count"], conflict["saved_filing_count"]))

    def test_the_count_is_every_filing_not_only_the_forms_the_catalog_keeps(self):
        # Two filings, neither of a kept form: the catalog keeps no row, the
        # block still has to hold as many filings as its index declares.
        body = _rows([("424B2", "2024-01-05", ""), ("424B2", "2024-01-08", "")])
        shard = self.shards[1]
        self.assertEqual([], _kept(body, shard["name"]))
        self.assertIsNone(history_block_coherence(shard=shard, body=body, rows=[],
                                                  last_day="2024-03-02"))
        conflict = history_block_coherence(shard=dict(shard, filingCount=3), body=body, rows=[],
                                           last_day="2024-03-02")
        self.assertEqual(["FILING_COUNT_DIFFERS_FROM_DECLARED"], conflict["failed_checks"])

    def test_the_dates_are_every_filing_s_not_only_the_kept_forms(self):
        # The right number of filings, none of a kept form, one dated after
        # the block's last day: nothing the catalog keeps is out of range.
        body = _rows([("424B2", "2024-01-05", ""), ("424B2", "2024-03-05", "")])
        shard = self.shards[1]
        self.assertEqual([], _kept(body, shard["name"]))
        conflict = history_block_coherence(shard=shard, body=body, rows=[],
                                           last_day="2024-03-02")
        self.assertEqual(["FILINGS_OUTSIDE_THE_BLOCK"], conflict["failed_checks"])
        self.assertEqual(1, conflict["filings_outside_the_block"])

    def test_a_block_without_a_declared_count_is_not_trusted(self):
        body = _rows([("8-K", "2024-01-05", ""), ("8-K", "2024-01-08", "")])
        shard = {key: value for key, value in self.shards[1].items() if key != "filingCount"}
        conflict = history_block_coherence(shard=shard, body=body,
                                           rows=_kept(body, shard["name"]), last_day="2024-03-02")
        self.assertEqual(["FILING_COUNT_DIFFERS_FROM_DECLARED"], conflict["failed_checks"])


class AStaleBlockBlocksThePeriodsItCouldHold(unittest.TestCase):
    """The catalog blocks a period only when the stale block reaches past its prior end."""

    def _history(self, last_day):
        return {"primary_cik": CIK, "declared_shards": [], "registrant_role": "PRIMARY",
                "limitations": [{"kind": "HISTORY_SHARD_SNAPSHOT_CONFLICT",
                                 "history_name": "CIK%s-submissions-001.json" % CIK,
                                 "declared_filing_from": "2018-11-26",
                                 "declared_filing_to": "2023-07-29", "block_last_day": last_day}]}

    def _periods(self):
        def period(report):
            return {"report_date": report, "original": {"accessionNumber": report},
                    "original_status": "SINGLE_ORIGINAL_ANNUAL", "amendments": []}
        return [period("2025-01-31"), period("2024-01-31"), period("2023-01-31")]

    def _status(self, last_day, index):
        return _candidate(company_id="c", history=self._history(last_day), periods=self._periods(),
                          index=index, ordinal=index + 1)["metadata_blocking_reasons"]

    def test_a_block_ending_before_the_prior_period_blocks_nothing(self):
        # The FY2025 target's filings are all dated after 2024-01-31.
        self.assertEqual([], self._status("2023-07-30", 0))

    def test_a_block_reaching_past_the_prior_period_blocks_the_period(self):
        self.assertEqual(["HISTORY_SNAPSHOT_CONFLICT"], self._status("2023-07-30", 1))

    def test_the_oldest_period_is_blocked_by_any_stale_block(self):
        self.assertEqual(["HISTORY_SNAPSHOT_CONFLICT"], self._status("2019-01-01", 2))

    def test_the_block_s_last_day_not_its_declared_end_decides(self):
        # Declared to 2023-07-29, last day 2024-01-31: it could hold filings
        # dated on the FY2025 target's prior end, never after it.
        self.assertEqual([], self._status("2024-01-31", 0))
        self.assertEqual(["HISTORY_SNAPSHOT_CONFLICT"], self._status("2024-02-01", 0))


class _Reader:
    def __init__(self, bodies):
        self.bodies = bodies

    def read(self, url, role, media_type):
        name = url.rsplit("/", 1)[-1]
        return {"raw_bytes": json.dumps(self.bodies[name]).encode("utf-8"),
                "source_reference": {"document_name": name}}


class ThePriorWalkHoldsBlocksToTheSameCheck(unittest.TestCase):
    """The Company Facts route's prior-year walk, successor and frozen, on made-up blocks."""

    def _case(self, older, older_count):
        name = "CIK%s-submissions-001.json" % CIK
        index = {"cik": CIK, "filings": {
            "recent": _rows([("10-K", "2024-02-20", "2023-12-31")]),
            "files": [{"name": name, "filingFrom": "2022-01-03", "filingTo": "2023-12-29",
                       "filingCount": older_count}]}}
        inventory = {"raw_bytes": json.dumps(index).encode("utf-8"),
                     "source_reference": {"document_name": "CIK%s.json" % CIK}}
        prepared = {"entity": CIK, "filing": {"reportDate": "2023-12-31"}}
        return _Reader({name: older}), inventory, prepared

    def test_a_coherent_block_gives_the_frozen_answer(self):
        older = _rows([("10-K", "2023-02-21", "2022-12-31"), ("8-K", "2023-05-01", "")])
        reader, inventory, prepared = self._case(older, 2)
        prepared = dict(prepared, filing={"reportDate": "2024-12-31"})
        self.assertEqual(_prior_filing(reader, inventory, prepared)[0],
                         prior_filing(reader, inventory, prepared)[0])

    def test_a_filing_on_the_gap_day_no_longer_stops_the_walk(self):
        # Recent starts 2023-12-31's filing on 2024-02-20; the block is declared
        # to 2023-12-29 and so ends 2024-02-19. A 10-K dated 2023-12-30 is on
        # the gap day, inside the block.
        older = _rows([("10-K", "2023-02-21", "2022-12-31"), ("8-K", "2023-12-30", "")])
        reader, inventory, prepared = self._case(older, 2)
        with self.assertRaisesRegex(NormalCompanyfactsError, "PRIOR_HISTORY_SNAPSHOT_CONFLICT"):
            _prior_filing(reader, inventory, prepared)
        row, _source = prior_filing(reader, inventory, prepared)
        self.assertEqual("2022-12-31", row["reportDate"])

    def test_a_block_missing_filings_stops_the_walk(self):
        older = _rows([("10-K", "2023-02-21", "2022-12-31")])
        reader, inventory, prepared = self._case(older, 2)
        # The frozen walk answers from a block that is missing a filing.
        self.assertEqual("2022-12-31", _prior_filing(reader, inventory, prepared)[0]["reportDate"])
        with self.assertRaisesRegex(NormalCompanyfactsError, "PRIOR_HISTORY_SNAPSHOT_CONFLICT"):
            prior_filing(reader, inventory, prepared)


class EveryOtherReaderOfABlockHoldsItToTheSameCheck(unittest.TestCase):
    """The two other readers of history blocks: the target-row lookup and C04's walk.

    Each gets the two made-up blocks that separate the rules - a fresh block
    with a filing on the gap day, which the frozen check refuses, and a block
    missing a filing, which it passes - so a reader left on the frozen check
    fails one of its cases here.
    """
    NAME = "CIK%s-submissions-001.json" % CIK
    MAIN = "CIK%s.json" % CIK

    def _documents(self, older, older_count):
        index = {"cik": CIK, "filings": {
            "recent": _rows([("10-K", "2024-02-20", "2023-12-31")]),
            "files": [{"name": self.NAME, "filingFrom": "2022-01-03", "filingTo": "2023-12-29",
                       "filingCount": older_count}]}}
        return index, _Reader({self.MAIN: index, self.NAME: older})

    def _frozen_answer(self, index, older):
        shard = index["filings"]["files"][0]
        return history_body_alignment(shard=shard, rows=_kept(older, self.NAME))

    def _lookup(self, older, older_count):
        from vnext.historical_filing_inventory import filing_inventory
        index, reader = self._documents(older, older_count)
        target = older["accessionNumber"][0]
        found = filing_inventory(
            reader=reader, inventory=reader.read(self.MAIN, role="x", media_type="x"),
            period_selection={"loaded_inventories": [self.MAIN, self.NAME]}, cik=CIK,
            accession=target)
        return index, found

    def _walk(self, older, older_count):
        from vnext import historical_governance_results as governance
        index, reader = self._documents(older, older_count)
        return index, governance._blocks(
            reader=reader, cik=CIK, payload=index,
            period={"period_start": "2023-01-01", "period_end": "2023-12-31"},
            current={"source_reference": {"document_name": self.MAIN}})

    def test_the_target_lookup_takes_a_fresh_block_with_a_gap_day_filing(self):
        older = _rows([("10-K", "2023-02-21", "2022-12-31"), ("8-K", "2023-12-30", "")])
        index, found = self._lookup(older, 2)
        self.assertIsNotNone(self._frozen_answer(index, older))
        self.assertEqual(self.NAME, found["source_reference"]["document_name"])

    def test_the_target_lookup_refuses_a_block_missing_filings(self):
        from vnext.historical_filing_inventory import HistoricalFilingInventoryError
        older = _rows([("10-K", "2023-02-21", "2022-12-31")])
        index, _reader = self._documents(older, 2)
        self.assertIsNone(self._frozen_answer(index, older))
        with self.assertRaisesRegex(HistoricalFilingInventoryError,
                                    "HISTORICAL_FILING_BLOCK_SNAPSHOT_CONFLICT:" + self.NAME):
            self._lookup(older, 2)

    def test_c04_s_walk_takes_a_fresh_block_with_a_gap_day_filing(self):
        older = _rows([("10-K", "2023-02-21", "2022-12-31"), ("8-K", "2023-12-30", "")])
        index, (inventories, rows, _files) = self._walk(older, 2)
        self.assertIsNotNone(self._frozen_answer(index, older))
        self.assertEqual([self.MAIN, self.NAME], [item["name"] for item in inventories])
        self.assertIn("2023-12-30", [row["filingDate"] for row in rows])

    def test_c04_s_walk_refuses_a_block_missing_filings(self):
        from vnext.historical_governance_input import HistoricalGovernanceError
        older = _rows([("10-K", "2023-02-21", "2022-12-31")])
        index, _reader = self._documents(older, 2)
        self.assertIsNone(self._frozen_answer(index, older))
        with self.assertRaisesRegex(HistoricalGovernanceError,
                                    "HISTORICAL_GOVERNANCE_HISTORY_SNAPSHOT_COVERAGE_CONFLICT"):
            self._walk(older, 2)


def _saved_submissions():
    """The latest saved attempt of every submissions URL: the checkout's, then the export's."""
    import csv
    found = {}
    with open(ROOT / "evidence" / "requests_log.csv", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if "/submissions/" in row["source_url"] and row["status_code"] == "200":
                found[row["source_url"]] = (row["timestamp_utc"], row["repo_relative_path"])
    if (ROOT / "evidence" / "issue47_acquired" / "export.json").exists():
        members = _export_members(ROOT)
        for member in sorted(members):
            if member.endswith(".headers.json"):
                headers = json.loads(_export_member_bytes(repo_root=ROOT, member=member,
                                                          members=members))
                url = headers["url"]
                if "/submissions/" in url and headers["status_code"] == 200:
                    body = member.rsplit("/", 1)[0] + "/" + url.rsplit("/", 1)[-1]
                    if url not in found or found[url][0] < headers["saved_at_utc"]:
                        found[url] = (headers["saved_at_utc"], body[len("source-inputs/"):])
    return found


class TheSavedBlocks(unittest.TestCase):
    """Every saved block, checked against the latest saved index that declares it."""

    @classmethod
    def setUpClass(cls):
        from vnext.normal_governance_input import _history_index, NormalGovernanceInputError
        saved = _saved_submissions()
        cls.results = {}
        for url, (_when, path) in saved.items():
            if "-submissions-" in url:
                continue
            payload = json.loads(saved_bytes(repo_root=ROOT, relative=path))
            cik = str(payload["cik"]).zfill(10)
            shards = _history_index(payload, cik)
            last = block_last_days(payload=payload, shards=shards)
            base = url.rsplit("/", 1)[0] + "/"
            for shard in shards:
                if base + shard["name"] not in saved:
                    continue
                body = json.loads(saved_bytes(repo_root=ROOT, relative=saved[base + shard["name"]][1]))
                try:
                    kept = _kept(body, shard["name"])
                except NormalGovernanceInputError:
                    continue
                cls.results[shard["name"]] = {
                    "new": history_block_coherence(shard=shard, body=body, rows=kept,
                                                   last_day=last[shard["name"]]),
                    "frozen": history_body_alignment(shard=shard, rows=kept)}

    def test_jpmorgan_s_acquired_blocks_are_the_blocks_their_index_declares(self):
        jpm = {name: r for name, r in self.results.items() if name.startswith("CIK0000019617-")}
        self.assertGreaterEqual(len(jpm), 65)
        frozen_refused = sorted(name for name, r in jpm.items() if r["frozen"])
        new_refused = sorted(name for name, r in jpm.items() if r["new"])
        # The frozen check refuses blocks fetched together with their index...
        self.assertEqual(8, len(frozen_refused))
        # ...for gap-day filings only; the one refused now is the block the
        # acquisition never fetched again: saved from another partition,
        # holding 2084 filings where its index declares 2023, none of a kept form.
        self.assertEqual(["CIK0000019617-submissions-007.json"], new_refused)
        conflict = jpm["CIK0000019617-submissions-007.json"]["new"]
        self.assertEqual((2023, 2084), (conflict["declared_filing_count"],
                                        conflict["saved_filing_count"]))
        self.assertIsNone(jpm["CIK0000019617-submissions-007.json"]["frozen"])

    def test_the_newest_blocks_of_pfizer_and_salesforce_miss_filings(self):
        for name, counts in (("CIK0000078003-submissions-001.json", (2005, 2001)),
                             ("CIK0001108524-submissions-001.json", (2016, 2010))):
            result = self.results[name]
            self.assertIsNotNone(result["new"], name)
            self.assertIn("FILING_COUNT_DIFFERS_FROM_DECLARED", result["new"]["failed_checks"])
            self.assertEqual(counts, (result["new"]["declared_filing_count"],
                                      result["new"]["saved_filing_count"]))


if __name__ == "__main__":
    unittest.main()
