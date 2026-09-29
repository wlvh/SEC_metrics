"""F3: exporting where the ledger is gone initializes a new, empty ledger at the root and
overwrites the export directory with it. Recorded ledger (same export code as LIVE; LIVE only
adds granted()). Offline; repository modules read-only; writes only under a temp dir here.
"""
import json, os, shutil, sys, tempfile
from pathlib import Path

REPO = Path("/home/user/SEC_metrics")
sys.path.insert(0, str(REPO / "scripts"))
from vnext import historical_model_calls as calls
from vnext import historical_model_export as export

work = Path(tempfile.mkdtemp(prefix="f3-", dir=os.getcwd()))
grant = {"grant": "G1", "request_digests": ["sha256:" + "a" * 64, "sha256:" + "b" * 64]}
allowance = {"requirement_id": calls.REQUIREMENT_ID, "budget_root": "/nonexistent-granted-model-root",
             "maximum_additional_provider_paid_sec_calls": [3, 3, 0],
             "scope": {"purposes": [calls.PURPOSE], "grants": [grant]},
             "delegation_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-1",
             "delegation_body_sha256": "d" * 64}
root = work / "ledger"
out = work / "checkout" / calls.MODEL_EXPORT_DIRECTORY
ledger = calls.recorded_model_ledger(root=root, allowance=allowance)
with ledger.locked():
    ledger.claim(request_digest=grant["request_digests"][0], plan_id="p1", purpose=calls.PURPOSE,
                 grants=["G1"], request_identity="r1", authority_files_hash="sha256:" + "e" * 64)
first = export.export_model_ledger(ledger=ledger, out_dir=out)
print("export after one claim:", first["counts"], first["export_id"][:19])

# The host is lost: root, anchor and mirror go with it (the start record too, not used here).
shutil.rmtree(root)
calls.HistoricalModelLedger.anchor_path(root).unlink()
calls.HistoricalModelLedger.mirror_path(root).unlink()

again = export.export_model_ledger(ledger=calls.recorded_model_ledger(root=root, allowance=allowance),
                                   out_dir=out)
index = json.loads((out / calls.MODEL_EXPORT_INDEX).read_text())
print("second export on the new host:", again["status"], again["counts"], "| index now says", index["counts"])
print("the new host now has an initialized ledger:",
      sorted(p.name for p in root.iterdir()), calls.HistoricalModelLedger.anchor_path(root).exists())
print("verify of the committed export now:", export.verify_model_export(export_dir=out)["counts"])
