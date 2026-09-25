"""What the FY2025 event walk needs on the recorded bank root, file by file.

The sweep reported one reason for seven positions - the latest request for one
8-K header failed. A first blocking reason is not the only one, so this asks
the event route's own reader about every document the walk would read: each
8-K and 8-K/A filed inside the window, in every submissions block the window
overlaps, and each one's primary document and SEC header. It says nothing
about steps after the walk, which are reached only once the walk completes.

Usage (from the repository root; the root is the one ``recorded_bank_run.py``
builds, with its missing rule inputs installed):
    python3 docs/evidence/issue47_history/financial-route/measure_bank_event_material.py \
        <recorded source root>
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from sec_urls import (accession_document_url, hdr_sgml_url, submissions_file_url,  # noqa: E402
                      submissions_url)
from vnext.annual_update import AnnualUpdateError  # noqa: E402
from vnext.normal_governance_input import _Sources, _filings, _history_index  # noqa: E402

CIK, COMPANY, START, END = 19617, "jpmorgan_chase", "2025-01-01", "2025-12-31"


def main():
    root = Path(sys.argv[1])
    reader = _Sources(root, COMPANY, str(CIK))
    index = reader.read(submissions_url(cik=CIK), role="sec_submissions_inventory",
                        media_type="application/json")
    main_body = json.loads(index["raw_bytes"])
    blocks = [("CIK%010d.json" % CIK, main_body)]
    for shard in _history_index(main_body, str(CIK)):
        if shard["filingFrom"] <= END and shard["filingTo"] >= START:
            item = reader.read(submissions_file_url(file_name=shard["name"]),
                               role="sec_submissions_history", media_type="application/json")
            blocks.append((shard["name"], json.loads(item["raw_bytes"])))
    filings = [row for name, body in blocks for row in _filings(body, inventory_name=name)
               if row["form"] in ("8-K", "8-K/A") and START <= row["filingDate"] <= END]

    def state(url, accession, role, media):
        try:
            return "SAVED" if reader.read(url, accession=accession, role=role, media_type=media,
                                          required=False) else "NOT_SAVED"
        except AnnualUpdateError as error:
            if "LATEST_SOURCE_REQUEST_FAILED" in str(error):
                return "LATEST_REQUEST_FAILED"
            raise

    counts, unusable = Counter(), []
    for row in filings:
        accession = row["accessionNumber"]
        for kind, url, role, media in (
                ("primary", accession_document_url(cik=CIK, accession=accession,
                                                   document_name=row["primaryDocument"]),
                 "fy_8k_primary", "text/html"),
                ("header", hdr_sgml_url(cik=CIK, accession=accession), "fy_8k_header",
                 "text/plain")):
            found = state(url, accession, role, media)
            counts[kind + ":" + found] += 1
            if found != "SAVED":
                unusable.append({"url": url, "state": found})
    body = {"record_type": "ISSUE_47_BANK_EVENT_MATERIAL", "company_id": COMPANY,
            "window": [START, END], "blocks_overlapping_the_window": [n for n, _ in blocks],
            "filings_in_window": len(filings), "documents": dict(sorted(counts.items())),
            "unusable": unusable, "source_root_is": "RECORDED_TEST_ONLY",
            "does_not_measure": "any step after the walk, and C04's other reads (the prior "
                                "year's auditor filing), which are reached only once the "
                                "walk completes",
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
    out = Path(__file__).with_name("bank-event-material.json")
    out.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: body[k] for k in ("filings_in_window", "documents", "unusable")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
