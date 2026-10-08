"""Filings dated on the day between two history blocks that a declared-range block choice skips.

For every company and every target period with a derivable event window: the
8-K rows event_filings finds (block chosen by declared filingFrom/filingTo, as
the frozen walk chooses) against the rows found when each block's range runs
to the day before the next block starts (block_last_days). Zero calls.
"""
import json, os, socket, sys
from pathlib import Path
from unittest.mock import patch
REPO = Path(sys.argv[1]); ROOT = Path(os.environ["SOURCE_ROOT"])
sys.path.insert(0, str(REPO / "scripts"))
from sec_urls import submissions_file_url, submissions_url
from vnext.canonical import strict_json_loads
from vnext import historical_event_sources as E
from vnext.normal_governance_input import _filings, _history_index
from vnext.normal_history_catalog import block_last_days, frame_period_candidates
from vnext.normal_history_plan import checkpoint_replayed_once
from vnext.projector import _load_registry
from vnext.normal_annual_input import _subject_policy

def by_last_day(cik, window):
    index, reason = E._read_saved(repo_root=ROOT, url=submissions_url(cik=int(cik)))
    if index is None:
        return None
    payload = strict_json_loads(text=index["raw"].decode("utf-8"))
    shards = _history_index(payload, str(cik))
    last = block_last_days(payload=payload, shards=shards)
    found, sources = [], [(None, payload)]
    for shard in shards:
        if shard["filingFrom"] > window["period_end"] or last[shard["name"]] < window["period_start"]:
            continue
        item, reason = E._read_saved(repo_root=ROOT, url=submissions_file_url(file_name=shard["name"]))
        if item is None:
            continue
        sources.append((shard["name"], strict_json_loads(text=item["raw"].decode("utf-8"))))
    for name, data in sources:
        inv = name if name is not None else "CIK%010d.json" % int(cik)
        for f in _filings(data, inventory_name=inv):
            if f["form"] in E.EVENT_FORMS and window["period_start"] <= f["filingDate"] <= window["period_end"]:
                found.append(f["accessionNumber"])
    return sorted(set(found))

out = {}
with patch.object(socket.socket, "connect", side_effect=AssertionError("net")), \
        patch.object(socket, "getaddrinfo", side_effect=AssertionError("dns")), checkpoint_replayed_once():
    for company in _load_registry(repo_root=REPO):
        cid = company["company_id"]
        row = E._registry_row(repo_root=ROOT, company_id=cid)
        policy = _subject_policy(row)
        try:
            candidates, _, _ = frame_period_candidates(repo_root=ROOT, company_id=cid, count=5, history=None)
        except Exception as error:
            out[cid] = {"refused": type(error).__name__ + ":" + str(error)[:200]}; continue
        rows = []
        for c in candidates:
            window, ciks, reason = E._window(repo_root=ROOT, company_id=cid, candidate=c, subject_policy=policy)
            if window is None:
                rows.append({"report_date": c["report_date"], "window": None, "reason": str(reason)[:120]}); continue
            for cik in ciks:
                declared = sorted({f["accessionNumber"] for f in E.event_filings(repo_root=ROOT, cik=cik, window=window)["filings"]})
                wide = by_last_day(cik, window)
                rows.append({"report_date": c["report_date"], "cik": str(cik),
                             "window": [window["period_start"], window["period_end"]],
                             "declared": len(declared), "by_last_day": None if wide is None else len(wide),
                             "missed": None if wide is None else sorted(set(wide) - set(declared)),
                             "extra": None if wide is None else sorted(set(declared) - set(wide))})
        out[cid] = rows
        print(cid, json.dumps([{k: r.get(k) for k in ("report_date", "declared", "by_last_day", "missed")} for r in rows]), flush=True)
Path(sys.argv[2]).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
