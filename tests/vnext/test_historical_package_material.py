"""An installed historical period rebuilds from its own data root, in a new process.

What this proves, precisely: a fresh interpreter with no warm state and no
network reads the installed data root and reproduces the same binding identity,
period and value. What it does not prove, and is not claimed to prove, is a
self-contained package: the replaying process imports ``vnext`` from this
development checkout, so the code comes from the checkout while only the
inputs, sources and rule bytes come from the data root. A package that carries
its own executable code is a separate question, and it is open on Issue #47
together with the native Run identity.

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

# The replaying process is new, but its code is this checkout's: the inserted
# path is the development ``scripts`` directory, not anything inside the data
# root. Only the inputs and sources below come from the installed root.
SEPARATE_PROCESS_REBUILD = """
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
    def test_installed_history_rebuilds_in_a_new_process_and_rejects_a_changed_metric(self):
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
            [sys.executable, "-c", SEPARATE_PROCESS_REBUILD.format(
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

    def test_a_tampered_or_unknown_historical_binding_is_refused_before_any_rebuild(self):
        """The identity checks that do not need the Requirement engine.

        `historical_run.replay_case` reads the saved binding, checks its
        identity, restores the period selection and only then loads the
        Requirement. Everything before that load is reachable from a package
        installed by the ordinary historical installer, so these four refusals
        are covered here rather than behind the registration patch - a negative
        that only runs where the patch is applied is a negative that does not
        run.

        Each case re-computes the binding hash after tampering, so none of them
        is caught by a stale digest.
        """
        from vnext.historical_run import BINDING_DIRECTORY as RUN_BINDINGS, replay_case
        from vnext.canonical import content_hash

        output = _fresh_output(os.environ["HISTORICAL_PACKAGE_MATERIAL_ROOT"] + "-negatives")
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                 report_end=FY2024_END)
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            installed = install_historical_inputs(data_root=output / "pkg", company_id=MARRIOTT,
                                                  metric_id="B04", period_selection=selection)
        data_root = Path(installed["data_root"])
        binding_id = installed["binding"]["binding_id"]
        self.assertEqual(RUN_BINDINGS, BINDING_DIRECTORY)

        refusals = {}

        def refuse(label, **kwargs):
            with self.assertRaises(Exception) as caught:
                replay_case(data_root=data_root, manifest=None, **kwargs)
            refusals[label] = str(caught.exception)

        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            refuse("unknown_binding", binding_id="sha256:" + "0" * 64,
                   company_id=MARRIOTT, metric_id="B04")
            refuse("wrong_company", binding_id=binding_id,
                   company_id="ford_motor_company", metric_id="B04")
            refuse("wrong_metric", binding_id=binding_id, company_id=MARRIOTT, metric_id="B05")

            # A binding re-signed onto a different year: the hash is recomputed
            # so it is internally consistent, and it is still refused because
            # the selection it names does not rebuild to the recorded identity.
            saved = json.loads(
                (data_root / BINDING_DIRECTORY / (binding_id[7:] + ".json")).read_text())
            forged = {**saved, "target_report_end": "2023-12-31"}
            forged.pop("binding_id")
            forged["binding_id"] = content_hash(value=forged)
            (data_root / BINDING_DIRECTORY / (forged["binding_id"][7:] + ".json")).write_text(
                json.dumps(forged, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            refuse("resigned_onto_another_year", binding_id=forged["binding_id"],
                   company_id=MARRIOTT, metric_id="B04")

        self.assertEqual(4, len(refusals))
        self.assertIn("HISTORICAL_RUN_BINDING_IDENTITY_REQUIRED", refusals["wrong_company"])
        self.assertIn("HISTORICAL_RUN_BINDING_IDENTITY_REQUIRED", refusals["wrong_metric"])
        self.assertIn("HISTORICAL_RUN_PERIOD_SELECTION_CHANGED",
                      refusals["resigned_onto_another_year"])
        # The unknown binding is refused by the source layer, not by a fallback.
        self.assertNotIn("HISTORICAL_RUN_PERIOD_SELECTION_CHANGED", refusals["unknown_binding"])
        # And the honest package is untouched by any of this.
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            again = replay_historical_inputs(data_root=data_root, company_id=MARRIOTT,
                                             metric_id="B04", binding_id=binding_id)
        self.assertEqual(installed["binding"], again["binding"])

    def test_a_period_installed_by_issuer_label_replays_as_the_same_request(self):
        """A label request is part of the identity, so the package must keep it.

        Marriott's year ending 2024-12-31 is asked for here as fiscal 2024, not
        as a date. Restoring only the report end would rebuild a different
        selection and report the package as changed, so this is the case that
        proves the installed binding carries the request it was made with.
        """
        output = _fresh_output(os.environ["HISTORICAL_PACKAGE_MATERIAL_ROOT"] + "-label")
        with original_sources_only():
            by_label = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                                fiscal_year=2024)
            by_end = resolve_period_selection(repo_root=ROOT, company_id=MARRIOTT,
                                              report_end=FY2024_END)
        self.assertEqual(FY2024_END, by_label["target_report_end"])
        self.assertEqual(2024, by_label["requested_fiscal_year"])
        self.assertNotEqual(by_label["selection_id"], by_end["selection_id"])
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
             patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")):
            installed = install_historical_inputs(data_root=output / "mar-fy2024-B04",
                                                  company_id=MARRIOTT, metric_id="B04",
                                                  period_selection=by_label)
        data_root = Path(installed["data_root"])
        binding_id = installed["binding"]["binding_id"]
        self.assertEqual(2024, installed["binding"]["requested_fiscal_year"])
        self.assertEqual(by_label["selection_id"], installed["binding"]["period_selection_id"])

        completed = subprocess.run(
            [sys.executable, "-c", SEPARATE_PROCESS_REBUILD.format(
                scripts=str(ROOT / "scripts"), root=str(data_root), company=MARRIOTT,
                metric="B04", binding=binding_id)],
            capture_output=True, text=True, cwd=str(output),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(0, completed.returncode, completed.stderr[-2000:])
        replayed = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(binding_id, replayed["binding_id"])
        self.assertEqual(by_label["selection_id"], replayed["period_selection_id"])
        self.assertEqual(installed["installed"]["primary_result"]["value"], replayed["value"])
        self.assertEqual({"provider": 0, "paid": 0, "sec": 0}, replayed["calls"])
        # The same filing asked for the other way is a different package, and
        # neither binding can be replayed as the other.
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            other = install_historical_inputs(data_root=output / "mar-2024-end-B04",
                                              company_id=MARRIOTT, metric_id="B04",
                                              period_selection=by_end)
        self.assertNotEqual(binding_id, other["binding"]["binding_id"])
        self.assertIsNone(other["binding"]["requested_fiscal_year"])
        self.assertEqual(installed["binding"]["target_period"], other["binding"]["target_period"])
        self.assertEqual(installed["installed"]["primary_result"]["value"],
                         other["installed"]["primary_result"]["value"])
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            with self.assertRaises(Exception):
                replay_historical_inputs(data_root=data_root, company_id=MARRIOTT,
                                         metric_id="B04",
                                         binding_id=other["binding"]["binding_id"])


if __name__ == "__main__":
    unittest.main()
