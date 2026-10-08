"""F5: the start/export guard and no-redraw are keyed on one approval digest. An export of
approval A (with the requests it claimed) does not stop a start for approval B over the same
requests. Offline; repository modules read-only; writes only in a temp dir here."""
import json, os, sys, tempfile
from pathlib import Path
REPO = Path("/home/user/SEC_metrics"); sys.path.insert(0, str(REPO / "scripts"))
from vnext import historical_model_calls as calls

work = Path(tempfile.mkdtemp(prefix="f5-", dir=os.getcwd()))
checkout = work / "checkout"
index = checkout / calls.MODEL_EXPORT_DIRECTORY / calls.MODEL_EXPORT_INDEX
index.parent.mkdir(parents=True)
claimed = ["sha256:" + "a" * 64, "sha256:" + "b" * 64]
index.write_text(json.dumps({"execution_mode": "LIVE", "counts": [2, 2, 0], "requests": claimed,
                             "approval": {"delegation_body_sha256": "a" * 64}}))
approval_b = {"requirement_id": calls.REQUIREMENT_ID, "budget_root": str(work / "ledger"),
              "delegation_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-7",
              "delegation_body_sha256": "b" * 64}
started = calls.start_model_ledger(allowance=approval_b, reader=lambda path: [], checkout=checkout)
print("start for approval B beside approval A's export of", claimed, "->", started["status"])
