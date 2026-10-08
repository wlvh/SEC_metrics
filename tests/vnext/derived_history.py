"""A recorded root whose submissions index describes the history blocks saved here.

Cases about reading a pinned period from the history blocks that hold it need
a company whose blocks are the blocks its index declares. None of the saved
ones is: every period in this repository whose 10-K row is in a history block
sits in a block saved at another time than its index (Salesforce's and
Pfizer's newest blocks lack the filings that aged out of the recent list after
they were saved; JPMorgan's block 007 was cut from another partition), and
``normal_history_catalog.history_block_coherence`` now refuses them by name.
Fixing that is an acquisition.

These cases are about the mechanism, so the index is re-derived from the
saved blocks: each saved block's declared range and filing count become its
own earliest filing date, latest filing date and number of filings; entries
for blocks never saved are left as declared. The derived index is recorded
through the ordinary recorded session (``RECORDED_TEST_ONLY``), so everything
that reads it reads it with its request proof, like any saved document. What a
case on this root proves is the mechanism, not SEC's metadata - the same claim
the metadata refresh chain in ``test_historical_sec_session`` makes.
"""
import atexit
import json
import shutil
import tempfile
from pathlib import Path

from sec_urls import submissions_file_url, submissions_url
from tests.vnext.common import REPO_ROOT as ROOT
from vnext.annual_update import saved_source
from vnext.historical_sec_session import (install_historical_source_inputs,
                                          recorded_historical_session)
from vnext.normal_governance_input import _history_index
from vnext.normal_history_catalog import _company

_ROOTS = {}


def derived_index(*, root, company_id):
    """The company's saved index, with every saved block's declaration read off the block."""
    cik = int(_company(root, company_id)["primary_cik"])
    index = saved_source(repo_root=root, url=submissions_url(cik=cik), accession="")
    payload = json.loads(index["raw"].decode("utf-8"))
    derived = json.loads(json.dumps(payload))
    for entry, shard in zip(derived["filings"]["files"], payload["filings"]["files"]):
        assert entry["name"] == shard["name"]
        item = saved_source(repo_root=root, url=submissions_file_url(file_name=shard["name"]),
                            accession="")
        if item is None:
            continue
        dates = json.loads(item["raw"].decode("utf-8"))["filingDate"]
        entry.update(filingFrom=min(dates), filingTo=max(dates), filingCount=len(dates))
    # The declared ranges must still be ordered the way SEC orders them.
    _history_index(derived, str(cik))
    return cik, json.dumps(derived, ensure_ascii=False).encode("utf-8")


def derived_history_root(*company_ids):
    """A data root carrying the baseline and one recorded derived index per company.

    Built once per process for each set of companies and removed at exit.
    """
    key = tuple(sorted(company_ids))
    if key in _ROOTS:
        return _ROOTS[key]
    indexes = {company_id: derived_index(root=ROOT, company_id=company_id)
               for company_id in key}
    scratch = Path(tempfile.mkdtemp(prefix="issue47-derived-history-"))
    atexit.register(shutil.rmtree, scratch, ignore_errors=True)
    session = recorded_historical_session(
        root=scratch / "ledger", company_ids=key,
        response={submissions_url(cik=cik): body for cik, body in indexes.values()})
    install_historical_source_inputs(root=session.data_root)
    for company_id, (cik, _body) in indexes.items():
        result = session.capture(company_id=company_id, url=submissions_url(cik=cik))
        assert result["status"] == "SUCCEEDED", result
    _ROOTS[key] = session.data_root
    return session.data_root
