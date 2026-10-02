"""Every candidate item of every saved 8-K, read the way the historical E01 route reads it.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/e01-item-text/all_saved_items.py <source root> <out.json>

census.py reads the forty 8-Ks with an 8.01 that the checkout itself saves.
The acquisition saved hundreds more for the older years' event windows, and
those are the items an E01 confirmation request would carry. This walks every
8-K header the source root's request ledger holds (``.hdr.sgml``), takes the
candidate items (1.01, 2.01, 8.01) the header lists, finds the 8-K document the
header names, and reads each item with ``historical_event_items.item_text`` -
recording where it starts and ends and the text's digest, or the named reason
it is refused. Run before and after a change to the reader, the two outputs say
exactly which items the change moves. Zero calls: every byte is the saved one -
the latest successful attempt the root's request ledger records for the URL,
read from the checkout or the acquisition's export
(``tools/acceptance_readings.saved_bytes``) and checked against the ledger's
SHA-256.
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import saved_bytes  # noqa: E402
from vnext.deterministic_router import _hdr_item_codes  # noqa: E402
from vnext.historical_event_items import EventItemTextError, item_text  # noqa: E402

CANDIDATES = ("1.01", "2.01", "8.01")
def _latest_saved(root):
    """URL -> (repo-relative path, SHA-256) of the latest successful attempt."""
    latest = {}
    for row in csv.DictReader((root / "evidence/requests_log.csv").open(encoding="utf-8")):
        if row["status_code"] == "200" and row["repo_relative_path"]:
            latest[row["source_url"]] = (row["repo_relative_path"], row["content_sha256"])
    return latest


def _read(saved, url):
    path, digest = saved[url]
    raw = saved_bytes(repo_root=REPO, relative=path)
    if hashlib.sha256(raw).hexdigest() != digest.split(":")[-1]:
        raise SystemExit("SAVED_BYTES_DIFFER_FROM_THE_LEDGER:" + url)
    return raw


def main(root, out):
    root = Path(root)
    saved = _latest_saved(root)
    urls = sorted(url for url in saved if url.endswith(".hdr.sgml"))
    rows, skipped = [], {"NO_CANDIDATE_ITEM": 0, "EIGHT_K_DOCUMENT_NOT_ONE": 0,
                         "EIGHT_K_DOCUMENT_NOT_SAVED": 0}
    for url in urls:
        header = _read(saved, url)
        codes = [code for code in CANDIDATES if code in _hdr_item_codes(raw_bytes=header)]
        if not codes:
            skipped["NO_CANDIDATE_ITEM"] += 1
            continue
        # The header names no documents; the filing's primary document is the
        # one HTML or text file the ledger saved from the same accession folder
        # (an event filing is fetched as its header and its primary document).
        folder = url.rsplit("/", 1)[0] + "/"
        documents = sorted(other for other in saved if other.startswith(folder)
                           and other.lower().endswith((".htm", ".html", ".txt"))
                           and not other.endswith(".hdr.sgml"))
        if len(documents) != 1:
            skipped["EIGHT_K_DOCUMENT_NOT_ONE" if documents else "EIGHT_K_DOCUMENT_NOT_SAVED"] += 1
            continue
        document_url = documents[0]
        raw = _read(saved, document_url)
        for code in codes:
            row = {"header_url": url, "document_url": document_url, "item_code": code}
            try:
                read = item_text(raw_bytes=raw, item_code=code)
            except EventItemTextError as refused:
                row.update(outcome="REFUSED", reason=str(refused), category=refused.category)
            else:
                row.update(outcome="READ", start=read["start"], end=read["end"],
                           end_marker=read["end_marker"], text_sha256=read["text_sha256"],
                           shares_the_body_of=read["shares_the_body_of"])
            rows.append(row)
    Path(out).write_text(json.dumps({
        "record_type": "ISSUE_47_E01_ALL_SAVED_ITEMS", "source_root": str(root),
        "items": len(rows), "read": sum(1 for row in rows if row["outcome"] == "READ"),
        "refused": sum(1 for row in rows if row["outcome"] == "REFUSED"),
        "headers_skipped": skipped, "rows": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(len(rows), skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
