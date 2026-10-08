"""A pinned period whose selection reads history blocks, installed and replayed.

Two defects sat on this path and neither could show on any reachable period,
because every period with a saved original is covered by its registrant's main
submissions document alone:

* the pinned input carried the main document, the primary and the company
  facts, but not the history blocks the selection had loaded - so a data root
  installed from it could not re-derive its own selection, and stopped with
  ``Request-ledger locator evidence is invalid`` (the failure the predecessor
  years hit before their catalogs were carried);
* the installer read the Requirement from the *source* root, so installing
  from any external root - the kind an acquisition session produces - stopped
  with "Requirement JSON is missing" before copying anything.

The one real-bytes period that reads blocks is JPMorgan FY2025 on the recorded
root whose index is re-derived from the saved blocks themselves (the refresh
chain's root). Its selection loads six blocks, because its prior 10-K sits in
block 004. That root is ``RECORDED_TEST_ONLY``; everything else it reads is this
repository's saved bytes.
"""
import atexit
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_run
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_period_selection import resolve_period_selection

BANK, CIK, REPORT_END = "jpmorgan_chase", 19617, "2025-12-31"
_ROOT = []


def refreshed_root():
    """The recorded root with the re-derived index, built once per process."""
    if _ROOT:
        return _ROOT[0]
    from sec_urls import submissions_url
    from tests.vnext.test_historical_sec_session import (
        ARefreshIsFinishedWhenThePlanStopsAskingForIt as Chain)
    from vnext.historical_sec_session import (install_historical_source_inputs,
                                              recorded_historical_session)
    scratch = Path(tempfile.mkdtemp(prefix="issue47-blocks-"))
    atexit.register(shutil.rmtree, scratch, ignore_errors=True)
    payload, measured = Chain._measure(ROOT)
    session = recorded_historical_session(
        root=scratch / "ledger", company_ids=(BANK,),
        response={submissions_url(cik=CIK): Chain._derived_index(payload, measured)})
    install_historical_source_inputs(root=session.data_root)
    session.capture(company_id=BANK, url=submissions_url(cik=CIK))
    _ROOT.append(Path(session.data_root))
    return _ROOT[0]


class TheSelectionsBlocksTravelWithThePinnedInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = refreshed_root()
        with original_sources_only():
            cls.selection = resolve_period_selection(repo_root=cls.root, company_id=BANK,
                                                     report_end=REPORT_END)
            cls.prepared = prepare_historical_annual_input(
                repo_root=cls.root, company_id=BANK, period_selection=cls.selection)

    def test_the_period_reads_blocks_at_all(self):
        """Without this the rest would pass on a period that loads none."""
        loaded = self.selection["loaded_inventories"]
        self.assertEqual("CIK%010d.json" % CIK, loaded[0])
        self.assertGreater(len(loaded), 1)
        self.assertEqual("0000019617-25-000270",
                         self.selection["prior_filing"]["accessionNumber"])

    def test_every_loaded_block_s_proof_is_carried(self):
        names = [proof["document_name"] for proof in self.prepared["source_proofs"]]
        for block in self.selection["loaded_inventories"][1:]:
            self.assertIn(block, names)
        # Once each, and after the three the inspectors read, so the proofs a
        # main-document period carries keep their positions.
        self.assertEqual(len(names), len(set(proof["request_attempt_id"]
                                             for proof in self.prepared["source_proofs"])))
        self.assertEqual(["CIK%010d.json" % CIK, "jpm-20251231.htm", "CIK%010d.json" % CIK],
                         names[:3])

    def test_a_main_document_period_carries_exactly_what_it_did(self):
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT,
                                                 company_id="marriott_international",
                                                 report_end="2023-12-31")
            prepared = prepare_historical_annual_input(
                repo_root=ROOT, company_id="marriott_international",
                period_selection=selection)
        self.assertEqual(["CIK0001048286.json"], selection["loaded_inventories"])
        self.assertEqual(3, len(prepared["source_proofs"]))


class TheInstallerReadsTheRuntimesRequirement(unittest.TestCase):
    def test_an_external_source_root_is_data_not_authority(self):
        """The Requirement comes from ROOT whatever the source root is.

        Preparation and the copy are replaced: this asks only which root the
        installer loads its Requirement from, which is where it failed.
        """
        asked = []

        def requirement(root):
            asked.append(Path(root))
            raise LookupError("REQUIREMENT_READ")

        with tempfile.TemporaryDirectory(prefix="issue47-install-") as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            with patch.object(historical_run, "prepare_historical_run_input",
                              return_value={"source_proofs": []}), \
                    patch.object(historical_run, "_requirement", requirement), \
                    self.assertRaises(LookupError):
                historical_run.install_historical_run_inputs(
                    data_root=Path(temporary) / "data", company_id=BANK, metric_id="A04",
                    period_selection={}, source_root=source)
        self.assertEqual([historical_run.ROOT], asked)


if __name__ == "__main__":
    unittest.main()
