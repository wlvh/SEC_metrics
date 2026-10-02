"""Where a saved 8-K's header index and its own document disagree about its items.

The event routes count items from EDGAR's header (hdr.sgml ``<ITEMS>``), which
is written from the filer's submission form; the document is the filing
itself. For every saved 8-K this lists the header's items, the items the
document heads (the route's own heading reading, ``headed_item_codes``) and,
as a check that does not depend on that reading, every ``Item x.yy`` the
document mentions anywhere. Each saved 8-K is found from the root's request
log (an acquired file is a request attempt) and from its accession-materials
folders.

Run on an export-restored root, which holds every 8-K the acquisition saved:
    python3 docs/evidence/issue47_history/e01-item-text/header_document_census.py \
        --source-root <restored source-inputs> --output <json>
Zero SEC or provider calls.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext.deterministic_router import _hdr_item_codes, _visible_text  # noqa: E402
from vnext.historical_event_items import headed_item_codes  # noqa: E402

CANDIDATE_CODES = ("1.01", "2.01", "8.01")
_ANY_MENTION = re.compile(r"Item\s*(\d\.\d\d)", re.I)


def saved_eight_ks(root):
    """accession digits -> {document name: path}, for every saved filing with a header."""
    files = {}
    with (root / "evidence/requests_log.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            found = re.search(r"/Archives/edgar/data/\d+/(\d{18})/([^/]+)$", row["source_url"])
            if found and row["status_code"] == "200" and row["repo_relative_path"]:
                # The last successful attempt for a URL is the saved one.
                files.setdefault(found.group(1), {})[found.group(2)] = root / row["repo_relative_path"]
    for header in (root / "evidence/accession_materials").glob("*/*.hdr.sgml"):
        digits = header.name.split(".")[0].replace("-", "")
        for path in header.parent.iterdir():
            if not path.name.endswith(".json"):
                files.setdefault(digits, {}).setdefault(path.name, path)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.source_root.resolve()
    documents, disagreements = 0, []
    for digits, files in sorted(saved_eight_ks(root).items()):
        headers = [path for name, path in files.items() if name.endswith(".hdr.sgml")]
        if not headers:
            continue
        header = headers[0].read_bytes()
        form = re.search(r"^<TYPE>(.+)$", header.decode("utf-8", "replace"), re.M)
        if form is None or form.group(1).strip() not in ("8-K", "8-K/A"):
            continue
        listed = set(_hdr_item_codes(raw_bytes=header))
        primaries = [path for name, path in files.items()
                     if not name.endswith(".hdr.sgml") and name.lower().endswith((".htm", ".html", ".txt"))]
        if len(primaries) != 1:
            raise SystemExit("EIGHT_K_PRIMARY_NOT_ONE:" + digits + ":" + str(len(primaries)))
        raw = primaries[0].read_bytes()
        documents += 1
        headed = headed_item_codes(raw_bytes=raw)
        mentioned = set(_ANY_MENTION.findall(_visible_text(raw_bytes=raw)))
        row = {"accession": digits[:10] + "-" + digits[10:12] + "-" + digits[12:],
               "document": primaries[0].name,
               "document_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
               "header_lists": sorted(listed), "document_heads": sorted(headed),
               "headed_not_listed": sorted(headed - listed),
               "listed_not_headed": sorted(listed - headed),
               "candidate_codes_mentioned_not_listed": sorted((mentioned & set(CANDIDATE_CODES)) - listed)}
        if row["headed_not_listed"] or row["listed_not_headed"] or row["candidate_codes_mentioned_not_listed"]:
            disagreements.append(row)
    body = {"record_type": "ISSUE_47_EIGHT_K_HEADER_DOCUMENT_CENSUS",
            "source_root_request_log_sha256": "sha256:" + hashlib.sha256(
                (root / "evidence/requests_log.csv").read_bytes()).hexdigest(),
            "candidate_codes": list(CANDIDATE_CODES), "eight_k_documents": documents,
            "headed_candidate_not_listed": [row for row in disagreements
                                            if set(row["headed_not_listed"]) & set(CANDIDATE_CODES)],
            "disagreements": disagreements, "calls": [0, 0, 0]}
    args.output.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"documents": documents, "disagreements": len(disagreements),
                      "headed_candidate_not_listed": [row["accession"] for row in body[
                          "headed_candidate_not_listed"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
