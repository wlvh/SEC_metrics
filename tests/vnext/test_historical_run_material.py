"""One pinned period goes to a frozen native Run and a public row.

Opt-in twice over, and the second gate is the point. The chain needs the
``issue_47_v1`` engine to be registered in ``requirement_profile.PROFILE_ENGINES``
and dispatched from ``run_store``; those are three hunks in two files that are
inside ``issue_28_v13``'s execution authority, delivered as
``docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch``
rather than applied here. Until that patch lands this test skips, and it must
not be reported as passing while it does.

It also needs an explicit fresh external directory, like the other material
tests, and it makes no network call.
"""
import json
import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_run_material import _fresh_output, _protected
from tests.vnext.test_normal_zero_ai_results import original_sources_only


MARRIOTT = "marriott_international"
FY2024_END = "2024-12-31"
# Independent of the selector under test: computed in
# test_historical_period_results from the original Company Facts JSON.
MARRIOTT_FY2024_NET_INCOME = "2375000000"
MARRIOTT_FY2024_REVENUE = "25100000000"

FROZEN_REPLAY = """
import json, socket, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, {scripts!r})
with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \\
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS forbidden')):
    from vnext.run_store import load_frozen_run
    manifest, records, _ = load_frozen_run(run_dir=Path({run!r}), repo_root=Path({data!r}))
    results = [r for r in records if r['record_type'] == 'METRIC_RESULT']
print(json.dumps({{'run_id': manifest['run_id'], 'status': manifest['status'],
                  'requirement_id': manifest['requirement_id'],
                  'target_period': manifest['target_period'],
                  'value': results[0]['value'], 'quality': results[0]['quality']}}))
"""


def _seam_registered():
    """Is the historical engine reachable in this checkout at all?"""
    try:
        from vnext.requirement_profile import PROFILE_ENGINES
    except ImportError:
        return False
    return "PROFILE_DRIVEN_V16" in PROFILE_ENGINES


@unittest.skipUnless(_seam_registered(),
                     "issue_47_v1 is not registered; apply the registration patch first")
@unittest.skipUnless(os.environ.get("HISTORICAL_RUN_MATERIAL_ROOT"),
                     "Requires an explicit fresh external material root")
class HistoricalRunMaterialTest(unittest.TestCase):
    def test_a_pinned_period_reaches_a_frozen_run_and_a_public_row(self):
        from vnext.historical_projection import render_historical_run
        from vnext.historical_run import create_historical_run, install_historical_run_inputs
        from vnext.normal_period_selection import resolve_period_selection

        output = _fresh_output(os.environ["HISTORICAL_RUN_MATERIAL_ROOT"])
        before = _protected()
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
             patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")):
            installed = install_historical_run_inputs(
                data_root=output / "data", company_id=MARRIOTT, metric_id="B04",
                period_selection=selection)
            self.assertEqual("issue_47_v1", installed["requirement"]["requirement_id"])
            self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, installed["calls"])

            run = create_historical_run(data_root=output / "data", run_dir=output / "run",
                                        company_id=MARRIOTT, metric_id="B04",
                                        binding_id=installed["binding"]["binding_id"],
                                        freeze=True)
        manifest = run["manifest"]
        self.assertEqual("FROZEN", manifest["status"])
        self.assertEqual("SUCCESSOR_RUN", manifest["record_type"])
        self.assertEqual("issue_47_v1", manifest["requirement_id"])
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-01-01",
                          "period_end": "2024-12-31"}, manifest["target_period"])
        self.assertEqual(MARRIOTT_FY2024_NET_INCOME, run["result"]["value"])
        self.assertEqual("EXACT", run["result"]["quality"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, run["new_calls"])
        # The source checkout is untouched by any of this.
        self.assertEqual(before, _protected())

        completed = subprocess.run(
            [sys.executable, "-c", FROZEN_REPLAY.format(
                scripts=str(ROOT / "scripts"), run=str(output / "run"),
                data=str(output / "data"))],
            capture_output=True, text=True, cwd=str(output),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(0, completed.returncode, completed.stderr[-2000:])
        replayed = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(manifest["run_id"], replayed["run_id"])
        self.assertEqual("FROZEN", replayed["status"])
        self.assertEqual(manifest["target_period"], replayed["target_period"])
        self.assertEqual(MARRIOTT_FY2024_NET_INCOME, replayed["value"])

        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            rendered = render_historical_run(data_root=output / "data",
                                             run_dir=output / "run", frozen=True)
        row, receipt = rendered["row"], rendered["receipt"]
        # The row carries the pinned year, not the company's latest one.
        self.assertEqual("2024", row["fiscal_year"])
        self.assertEqual("ANNUAL", row["fiscal_period"])
        self.assertEqual("2024-01-01", row["period_start"])
        self.assertEqual("2024-12-31", row["period_end"])
        self.assertEqual(MARRIOTT_FY2024_NET_INCOME, row["value"])
        self.assertEqual("USD", row["unit"])
        self.assertEqual(selection["current_filing"]["accessionNumber"], row["accession"])
        self.assertEqual("FULL_NATIVE_HISTORICAL_RUN_REPLAY", receipt["source_validation"])
        self.assertEqual(selection["selection_id"], receipt["period_selection_id"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, receipt["calls"])
        self.assertFalse(receipt["production_authorized"])
        self.assertTrue(rendered["evidence"])

    def test_a_structured_fact_without_a_verified_claim_still_renders_its_evidence(self):
        """An XBRL fact is bound to itself, not to a claim someone verified.

        The ordinary renderer has always had two arms here: observations that
        name verified claim ids, and observations that name none and carry a
        source-derived evidence row instead. The historical renderer had only
        the first, so every Company Facts metric produced a Run its own store
        resolved as EXACT and then refused to render, with
        HISTORICAL_PROJECTION_OBSERVATION_WITHOUT_CLAIMS. Nothing about the Run
        was wrong; the row could not be built from it.

        B04 above goes through the claims arm, so it never touched this.
        """
        from vnext.historical_projection import render_historical_run
        from vnext.historical_run import create_historical_run, install_historical_run_inputs
        from vnext.normal_period_selection import resolve_period_selection

        output = _fresh_output(os.environ["HISTORICAL_RUN_MATERIAL_ROOT"] + "-structured")
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
             patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")):
            installed = install_historical_run_inputs(
                data_root=output / "data", company_id=MARRIOTT, metric_id="B01",
                period_selection=selection)
            run = create_historical_run(data_root=output / "data", run_dir=output / "run",
                                        company_id=MARRIOTT, metric_id="B01",
                                        binding_id=installed["binding"]["binding_id"],
                                        freeze=True)
            rendered = render_historical_run(data_root=output / "data",
                                             run_dir=output / "run", frozen=True)
        self.assertEqual(MARRIOTT_FY2024_REVENUE, run["result"]["value"])
        self.assertEqual("EXACT", run["result"]["quality"])
        self.assertEqual(MARRIOTT_FY2024_REVENUE, rendered["row"]["value"])
        self.assertEqual("2024", rendered["row"]["fiscal_year"])

        # The arm under test is the one that runs, and it is reached because the
        # binding names no claim at all - not because a claim lookup was skipped.
        observations = [r for r in installed["installed"]["records"]
                        if r["record_type"] == "VERIFIED_OBSERVATION"]
        self.assertTrue(observations)
        for observation in observations:
            binding = observation["source_binding"]
            self.assertFalse(binding.get("verified_claim_ids"))
            self.assertFalse(binding.get("matched_verified_claim_ids"))
        self.assertEqual(1, len(rendered["evidence"]))
        entry = rendered["evidence"][0]
        self.assertTrue(entry["evidence_quote"].startswith(
            "Normalized source-derived observation: "), entry["evidence_quote"])
        # A structured fact has no literal source cell, so its raw value stays
        # empty rather than being invented from the normalized number.
        self.assertEqual("", entry["value_raw"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, rendered["receipt"]["calls"])


if __name__ == "__main__":
    unittest.main()
