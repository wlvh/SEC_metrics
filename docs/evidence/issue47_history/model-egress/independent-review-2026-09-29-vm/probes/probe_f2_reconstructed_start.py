"""F2: the local start record is public - it is the marker's json block - and the live
path's start check never asks whether the checkout carries this approval's export.

Offline, repository modules imported read-only; every write is in a temp dir here.
"""
import json, os, sys, tempfile
from pathlib import Path

REPO = Path("/home/user/SEC_metrics")
sys.path.insert(0, str(REPO / "scripts"))
from vnext import historical_model_calls as calls
from vnext.historical_ledger_start import (exported_here, marker_record, start_record_path)

work = Path(tempfile.mkdtemp(prefix="f2-", dir=os.getcwd()))
checkout = work / "checkout"
allowance = {"requirement_id": calls.REQUIREMENT_ID, "budget_root": str(work / "ledger"),
             "delegation_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5800000002",
             "delegation_body_sha256": "c" * 64}
none = lambda path: []

# Container A starts; the executor posts the marker (a comment anyone can read).
started = calls.start_model_ledger(allowance=allowance, reader=none, checkout=checkout)
marker = {"id": 5900000101, "author_association": "OWNER", "body": started["marker_comment_body"],
          "created_at": "2026-09-29T01:00:00Z", "updated_at": "2026-09-29T01:00:00Z",
          "html_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5900000101"}
on_issue = lambda path: [dict(marker)] if "page=1" in path else []
# ...spends, exports to the branch (only the index's approval matters to the guard)...
index = checkout / calls.MODEL_EXPORT_DIRECTORY / calls.MODEL_EXPORT_INDEX
index.parent.mkdir(parents=True)
index.write_text(json.dumps({"execution_mode": "LIVE", "counts": [16, 16, 0],
                             "approval": {"delegation_body_sha256": "c" * 64}}))
# ...and container A is reclaimed with its disk: the start record and the ledger are gone.
start_record_path(Path(allowance["budget_root"])).unlink()

kind = calls._model_start()
print("exported_here(checkout):", exported_here(kind, allowance=allowance, checkout=checkout))
for label, call in (("start on the new container",
                     lambda: calls.start_model_ledger(allowance=allowance, reader=on_issue, checkout=checkout)),
                    ("live-path start check on the new container",
                     lambda: calls.require_published_model_start(allowance=allowance, reader=on_issue))):
    try:
        call(); print(label, "-> ACCEPTED")
    except ValueError as error:
        print(label, "-> refused", str(error)[:70])

# The new container writes the record back from the marker's own json block.
record = marker_record(kind, marker["body"])
start_record_path(Path(allowance["budget_root"])).write_text(json.dumps(record))
print("live-path start check after copying the marker's record ->",
      calls.require_published_model_start(allowance=allowance, reader=on_issue)["marker_url"])
print("ledger root exists:", Path(allowance["budget_root"]).exists(),
      "| the checkout still carries the export:", exported_here(kind, allowance=allowance, checkout=checkout))
