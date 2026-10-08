"""A recorded root in which a registrant's own filing rows live in a history block.

SEC splits a registrant's submissions index into a ``filings.recent`` block and
history blocks, and re-partitions them over time. Six of the frame's fifty
target periods (JPMorgan FY2021-FY2024, Salesforce FY2022-FY2023) have their
10-K row only in a history block, and none of them has a saved original, so no
saved period can show what a pinned route does with such a row.

This builds one from real material. It takes a registrant whose originals are
saved, moves every ``recent`` row filed on or before ``cutoff`` into a new
history block, and records the re-partitioned index and the new block through
the recorded session - the same claim, persist, receipt, terminal and frozen
checkpoint replay a capture always runs. Every filing's bytes are this
repository's saved bytes; only where a row is listed changes. The result is
``RECORDED_TEST_ONLY``: a test of the mechanism, not a delivery.

The one seam is the planner's answer to "is a fetch due" for the index itself.
The saved index is coherent, so the planner rightly says no, and the capture
would reuse it; here it is told yes for that one URL, because the scenario
being built is SEC having re-partitioned the index. The new block needs no
seam: once the re-partitioned index is saved the planner declares the block
itself, unsaved, and the capture is admitted the ordinary way.
"""
import copy
import json
from pathlib import Path
from unittest.mock import patch

from sec_urls import submissions_file_url, submissions_url
from vnext import historical_sec_session as session_module
from vnext.annual_update import saved_source
from vnext.historical_sec_session import (install_historical_source_inputs,
                                          recorded_historical_session)
from vnext.normal_source_authority import ROOT


def repartition(payload, *, cik, cutoff, name):
    """The index with rows filed on or before ``cutoff`` moved into block ``name``.

    Returns the new index bytes and the new block bytes. Rows keep their order
    and every parallel array moves together; the block's declared range is its
    own first and last filing date, as SEC declares it.
    """
    body = copy.deepcopy(payload)
    recent = body["filings"]["recent"]
    count = len(recent["accessionNumber"])
    if not all(isinstance(values, list) and len(values) == count for values in recent.values()):
        raise AssertionError("recent block arrays are not parallel")
    moved = [index for index in range(count) if recent["filingDate"][index] <= cutoff]
    kept = [index for index in range(count) if recent["filingDate"][index] > cutoff]
    if not moved or not kept:
        raise AssertionError("the cutoff must split the recent block")
    block = {key: [values[index] for index in moved] for key, values in recent.items()}
    body["filings"]["recent"] = {key: [values[index] for index in kept]
                                 for key, values in recent.items()}
    existing = body["filings"]["files"]
    if any(entry["name"] == name for entry in existing):
        raise AssertionError("block name already declared: " + name)
    if not name.startswith("CIK%010d-submissions-" % cik):
        raise AssertionError("block name must follow SEC's pattern for this registrant")
    body["filings"]["files"] = [{"name": name, "filingCount": len(moved),
                                 "filingFrom": min(block["filingDate"]),
                                 "filingTo": max(block["filingDate"])}] + existing
    return (json.dumps(body, separators=(",", ":")).encode("utf-8"),
            json.dumps(block, separators=(",", ":")).encode("utf-8"))


def build_repartitioned_root(*, work, company_id, cik, cutoff, block_name):
    """Record the re-partitioned index and its new block; return the data root."""
    index_url = submissions_url(cik=cik)
    block_url = submissions_file_url(file_name=block_name)
    saved = saved_source(repo_root=ROOT, url=index_url, accession="")
    index_bytes, block_bytes = repartition(json.loads(saved["raw"].decode("utf-8")),
                                           cik=cik, cutoff=cutoff, name=block_name)
    session = recorded_historical_session(
        root=Path(work) / "ledger", company_ids=(company_id,),
        response={index_url: index_bytes, block_url: block_bytes})
    install_historical_source_inputs(root=session.data_root)
    planner = session_module.declared_frame

    def index_is_due(**kwargs):
        frame = planner(**kwargs)
        rows = [dict(row, new_acquisition_required=True) if row["source_url"] == index_url
                else row for row in frame["requirements"]]
        return {**frame, "requirements": rows}

    with patch.object(session_module, "declared_frame", side_effect=index_is_due):
        index_capture = session.capture(company_id=company_id, url=index_url)
    block_capture = session.capture(company_id=company_id, url=block_url)
    return {"data_root": Path(session.data_root), "index_capture": index_capture,
            "block_capture": block_capture, "index_bytes": index_bytes,
            "block_bytes": block_bytes, "calls": session.calls_this_session()}
