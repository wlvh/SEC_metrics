"""Measure, per company, what an acquisition pass would claim from a restored ledger state.

Usage: python3 measure_due_sets.py <data root> <restored ledger dir> <out.json> [company ...]

Zero calls: network and DNS blocked. For each company the planner's declared
frame is computed on the data root, exactly as HistoricalSecSession.capture_pending
does: rows that need a new acquisition, minus URLs the restored ledger's slots
already claimed, each asked of request_is_in_scope under the registered
allowance. Counts by tier and dependency class; the admitted count is the most
one acquisition invocation could claim for the company before a new pass
re-plans.
"""
import collections
import json
import socket
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "scripts"))
DATA, LEDGER, OUT = (Path(p) for p in sys.argv[1:4])
ONLY = sys.argv[4:]

from vnext.canonical import strict_json_file  # noqa: E402
from vnext.historical_sec_session import _tier  # noqa: E402
from vnext.historical_source_acquisition import (HistoricalAcquisitionError,  # noqa: E402
                                                 acquisition_allowance, declared_frame,
                                                 request_is_in_scope)

allowance = acquisition_allowance(repo_root=REPO)
claimed = {strict_json_file(path=slot / "sec-plan.json")["request"]["url"]
           for slot in sorted((LEDGER / "calls").iterdir())}
companies = [c for c in allowance["scope"]["company_ids"] if not ONLY or c in ONLY]
purpose = allowance["scope"]["purposes"][0]
result, started = {}, time.time()
with patch.object(socket.socket, "connect", side_effect=AssertionError("net")), \
        patch.object(socket, "getaddrinfo", side_effect=AssertionError("dns")):
    for company in companies:
        began = time.time()
        try:
            frame = declared_frame(repo_root=DATA, company_id=company, years=5)
        except Exception as error:  # noqa: BLE001 - measured, reported
            result[company] = {"error": type(error).__name__ + ":" + str(error)[:400],
                               "where": [f.name for f in
                                         traceback.extract_tb(error.__traceback__)][-4:]}
            print(company, "ERROR", str(error)[:160], flush=True)
            continue
        rows = frame["requirements"]
        admitted, outside, already = [], [], []
        for row in rows:
            if not row["new_acquisition_required"]:
                continue
            if row["source_url"] in claimed:
                already.append(row["source_url"])
                continue
            try:
                request_is_in_scope(allowance=allowance, company_id=company, dependency=row,
                                    purpose=purpose,
                                    frame_report_dates=frame["target_report_dates"])
            except HistoricalAcquisitionError as refusal:
                outside.append({"url": row["source_url"], "class": row["dependency_class"],
                                "reason": str(refusal)[:200]})
                continue
            admitted.append(row)
        result[company] = {
            "declared_rows": len(rows),
            "due_admitted": len(admitted),
            "due_admitted_by_tier": dict(collections.Counter(_tier(r) for r in admitted)),
            "due_admitted_by_class": dict(collections.Counter(r["dependency_class"]
                                                              for r in admitted)),
            "due_outside_grants": len(outside),
            "outside_by_class": dict(collections.Counter(o["class"] for o in outside)),
            "due_but_already_claimed": len(already),
            "limitations": len(frame.get("limitations", [])),
            "seconds": int(time.time() - began)}
        print(company, json.dumps(result[company], sort_keys=True), flush=True)
        OUT.write_text(json.dumps({"companies": result, "claimed_urls": len(claimed)},
                                  indent=1, sort_keys=True) + "\n", encoding="utf-8")
OUT.write_text(json.dumps({"companies": result, "claimed_urls": len(claimed),
                           "seconds": int(time.time() - started), "calls": [0, 0, 0]},
                          indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("DONE", int(time.time() - started), flush=True)
