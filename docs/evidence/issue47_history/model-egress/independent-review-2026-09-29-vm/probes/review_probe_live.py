"""Reviewer's probes, in the review copy only. LIVE path, controlled opener, no network."""
import json, os, shutil, subprocess, sys
from pathlib import Path
from unittest.mock import patch

from tests.vnext import test_historical_model_egress as E   # loads the runner first, as the suite does
from tests.vnext.test_historical_model_egress import (ROOT, adapter, calls, egress, reset_ledger,
                                                      reference_prompt_tokens, wire)


def tool(command, out):
    done = subprocess.run([sys.executable, str(ROOT / "tools/vnext_historical_model_export.py"),
                           command, "--export", str(out)], cwd=ROOT, capture_output=True,
                          text=True, timeout=600)
    return done.returncode, json.loads(done.stdout)


class ReviewProbes(E._LiveOpener):

    def call(self, prepared, ledger):
        self.reply = wire(self.output(prepared), prompt_tokens=reference_prompt_tokens(prepared))
        with patch.object(adapter._DEEPSEEK_OPENER, "open", side_effect=self.open):
            return egress.execute_historical_semantic(prepared=prepared, ledger=ledger)

    def export_dir(self, name):
        checkout = self.temporary / name
        self.addCleanup(shutil.rmtree, checkout, True)
        return checkout, checkout / calls.MODEL_EXPORT_DIRECTORY

    def test_p1_a_reconstructed_start_spends_the_same_request_again(self):
        from vnext.historical_ledger_start import exported_here, marker_record, start_record_path
        prepared = self.smallest()
        self.call(prepared, self.live())
        checkout, out = self.export_dir("p1-checkout")
        code, exported = tool("export", out)
        print("\nP1 export:", code, exported["status"], exported["counts"])
        reset_ledger(self.budget)                       # the container is reclaimed with its disk
        record = marker_record(calls._model_start(), self.markers[0]["body"])   # public json block
        start_record_path(self.budget).write_text(json.dumps(record), encoding="utf-8")
        print("P1 checkout carries this approval's export:",
              exported_here(calls._model_start(), allowance=self.allowance, checkout=checkout))
        ledger = self.live()
        with ledger.locked():
            print("P1 live ledger on the new host:", ledger.snapshot()["counts"])
        self.call(prepared, ledger)
        bodies = [body for body in self.opened]
        print("P1 opener calls:", len(bodies), "| same body twice:",
              len(bodies) == 2 and bodies[0] == bodies[1] == prepared.provider_request_body_bytes)

    def test_p2_export_on_a_lost_host_initializes_and_overwrites(self):
        from vnext.historical_ledger_start import start_record_path
        prepared = self.smallest()
        self.call(prepared, self.live())
        checkout, out = self.export_dir("p2-checkout")
        print("\nP2 first export:", tool("export", out)[1]["counts"])
        reset_ledger(self.budget)                       # lost host, before any restore
        code, again = tool("export", out)
        print("P2 export on the new host:", code, again.get("status"), again.get("counts"),
              "| index says", json.loads((out / calls.MODEL_EXPORT_INDEX).read_text())["counts"])
        print("P2 new host root now holds:", sorted(p.name for p in self.budget.iterdir()),
              "| anchor:", calls.HistoricalModelLedger.anchor_path(self.budget).exists())
        code, verified = tool("verify", out)
        print("P2 verify of the overwritten export:", code, verified["status"], verified["counts"])
        self.assertFalse(start_record_path(self.budget).exists())

    def test_p3_restore_beside_a_surviving_start_resumes(self):
        from vnext.historical_ledger_start import start_record_path
        first, second = sorted(self.requests, key=lambda r: len(r.provider_request_body_bytes))[:2]
        self.call(first, self.live())
        checkout, out = self.export_dir("p3-checkout")
        tool("export", out)
        # the root and the files beside it go; the start record beside them stays
        shutil.rmtree(self.budget)
        calls.HistoricalModelLedger.anchor_path(self.budget).unlink()
        calls.HistoricalModelLedger.mirror_path(self.budget).unlink()
        print("\nP3 start record survived:", start_record_path(self.budget).exists())
        code, restored = tool("restore", out)
        print("P3 restore:", code, restored["status"], restored["counts"], "start_restored:",
              restored["start_restored"])
        ledger = self.live()                             # no refusal: the start is still here
        self.call(second, ledger)
        with ledger.locked():
            print("P3 after restore the ledger spent again:", ledger.snapshot()["counts"],
                  "| opener calls:", len(self.opened))

    def test_p4_the_export_module_in_the_sending_process_is_refused(self):
        import vnext.historical_model_export  # noqa: F401 - the thing that must never be here
        prepared = self.smallest()
        try:
            self.call(prepared, self.live())
            print("\nP4 call went through with the export module loaded")
        except ValueError as error:
            print("\nP4 refused:", str(error)[:110], "| opener calls:", len(self.opened))


class ReviewProbeExportContents(E._LiveOpener):

    def test_p5_the_pushed_export_carries_no_key(self):
        import io, tarfile
        prepared = self.smallest()
        self.reply = wire(self.output(prepared), prompt_tokens=reference_prompt_tokens(prepared))
        with patch.object(adapter._DEEPSEEK_OPENER, "open", side_effect=self.open):
            egress.execute_historical_semantic(prepared=prepared, ledger=self.live())
        checkout = self.temporary / "p5-checkout"
        self.addCleanup(shutil.rmtree, checkout, True)
        out = checkout / calls.MODEL_EXPORT_DIRECTORY
        code, exported = tool("export", out)
        key = os.environ["DEEPSEEK_API_KEY"].encode()
        hits, names = [], []
        for path in sorted(out.iterdir()):
            data = path.read_bytes()
            if key in data or b"Authorization" in data or b"Bearer" in data:
                hits.append(path.name)
            if path.suffix == ".gz":
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                    for info in tar.getmembers():
                        body = tar.extractfile(info).read()
                        names.append(info.name)
                        if key in body or b"Authorization" in body or b"Bearer" in body:
                            hits.append(info.name)
        print("\nP5 export:", code, exported["status"], "| members:", len(names),
              "| files holding the key or an auth header:", hits)
