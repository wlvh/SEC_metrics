"""An installed historical period replays cold from its own data root.

Opt-in: this test writes into a fresh external directory named by
HISTORICAL_PACKAGE_MATERIAL_ROOT, exactly like the other ordinary material
tests. It never touches the source checkout and makes no network call.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_run_material import _fresh_output, _protected
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_package import (BINDING_DIRECTORY, install_historical_inputs,
                                      replay_historical_inputs)
from vnext.normal_period_selection import resolve_period_selection


MARRIOTT = "marriott_international"
FY2024_END = "2024-12-31"

COLD_REPLAY = """
import json, socket, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, {scripts!r})
from vnext.historical_package import replay_historical_inputs
with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \\
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS forbidden')):
    out = replay_historical_inputs(data_root=Path({root!r}), company_id={company!r},
                                   metric_id={metric!r}, binding_id={binding!r})
print(json.dumps({{'binding_id': out['binding']['binding_id'],
                  'target_period': out['binding']['target_period'],
                  'period_selection_id': out['period_selection']['selection_id'],
                  'value': out['result']['value'], 'quality': out['result']['quality'],
                  'calls': out['calls']}}))
"""


@unittest.skipUnless(os.environ.get("HISTORICAL_PACKAGE_MATERIAL_ROOT"),
                     "Requires an explicit fresh external material root")
class HistoricalPackageMaterialTest(unittest.TestCase):
    def test_installed_history_replays_cold_and_rejects_a_changed_period(self):
        output = _fresh_output(os.environ["HISTORICAL_PACKAGE_MATERIAL_ROOT"])
        before = _protected()
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
             patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")):
            installed = install_historical_inputs(data_root=output / "mar-2024-B04",
                                                  company_id=MARRIOTT, metric_id="B04",
                                                  period_selection=selection)
        data_root = Path(installed["data_root"])
        binding_id = installed["binding"]["binding_id"]
        self.assertEqual({"fiscal_year": 2024, "period_start": "2024-01-01",
                          "period_end": "2024-12-31"},
                         installed["binding"]["target_period"])
        self.assertEqual(selection["selection_id"], installed["binding"]["period_selection_id"])
        self.assertFalse(installed["binding"]["native_run_created"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, installed["receipt"]["calls"])
        self.assertTrue((data_root / BINDING_DIRECTORY / (binding_id[7:] + ".json")).is_file())
        # The source checkout is untouched by an installation.
        self.assertEqual(before, _protected())

        completed = subprocess.run(
            [sys.executable, "-c", COLD_REPLAY.format(
                scripts=str(ROOT / "scripts"), root=str(data_root), company=MARRIOTT,
                metric="B04", binding=binding_id)],
            capture_output=True, text=True, cwd=str(output),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(0, completed.returncode, completed.stderr[-2000:])
        replayed = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(binding_id, replayed["binding_id"])
        self.assertEqual(installed["binding"]["target_period"], replayed["target_period"])
        self.assertEqual(selection["selection_id"], replayed["period_selection_id"])
        self.assertEqual(installed["installed"]["primary_result"]["value"], replayed["value"])
        self.assertEqual("EXACT", replayed["quality"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, replayed["calls"])

        # Re-entering the same installed input adds no business call and keeps
        # the same identity, and an unknown binding is refused rather than
        # resolved to some other period.
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            again = replay_historical_inputs(data_root=data_root, company_id=MARRIOTT,
                                             metric_id="B04", binding_id=binding_id)
            self.assertEqual(installed["binding"], again["binding"])
            with self.assertRaises(Exception):
                replay_historical_inputs(data_root=data_root, company_id=MARRIOTT,
                                         metric_id="B05", binding_id=binding_id)

    def test_a_second_period_installs_beside_the_first_without_overwriting_it(self):
        output = _fresh_output(os.environ["HISTORICAL_PACKAGE_MATERIAL_ROOT"] + "-second")
        with original_sources_only():
            newer = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                             report_end=FY2024_END)
            older = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                             report_end="2023-12-31")
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            first = install_historical_inputs(data_root=output / "fy2024",
                                              company_id=MARRIOTT, metric_id="B04",
                                              period_selection=newer)
            second = install_historical_inputs(data_root=output / "fy2023",
                                               company_id=MARRIOTT, metric_id="B04",
                                               period_selection=older)
        self.assertNotEqual(first["binding"]["binding_id"], second["binding"]["binding_id"])
        self.assertEqual(2024, first["binding"]["target_period"]["fiscal_year"])
        self.assertEqual(2023, second["binding"]["target_period"]["fiscal_year"])
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            for installed in (first, second):
                replayed = replay_historical_inputs(
                    data_root=Path(installed["data_root"]), company_id=MARRIOTT,
                    metric_id="B04", binding_id=installed["binding"]["binding_id"])
                self.assertEqual(installed["binding"], replayed["binding"])


if __name__ == "__main__":
    unittest.main()
