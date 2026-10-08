"""What the two D02 navigation repairs move, on every saved annual report.

Usage: python3 effect.py <restored source root> <out.json>

Each saved annual report (DEI DocumentType 10-K) is built as a text document
with the release-aware builder, narrowed as the route narrows it, and given to
``historical_text_results.referenced_note_candidates`` four times: with
neither repair (the split-emphasis note heading never counts and the appended
statements start at the first title after Item 8, as before), with each alone,
and with both. Every difference in the D02 and D03 candidate block sets, the
note references and the appended range is recorded per report, so a repair is
held to moving only what it names. Zero calls.
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext import historical_text_results as route  # noqa: E402
from vnext import text_coverage  # noqa: E402
from vnext.canonical import content_hash, sha256_bytes  # noqa: E402
from vnext.historical_dei import release_aware  # noqa: E402
from vnext.records import validate_record  # noqa: E402

BUILD = release_aware(text_coverage.build_text_document)
SPLIT, START = route.split_emphasis_note_heading, route.statements_start


def _first_title(titles):
    return titles[0][0] if titles else None


def _documents(evidence):
    seen = set()
    paths = sorted(glob.glob(evidence + "/request_attempts/*/*/*.htm")
                   + glob.glob(evidence + "/accession_materials/*/*.htm"))
    for path in paths:
        name = os.path.basename(path)
        raw = open(path, "rb").read()
        if name in seen or not re.search(rb'name="dei:DocumentType"[^>]*>(?:<[^>]+>)*\s*10-K\s*<', raw):
            continue
        seen.add(name)
        headers = glob.glob(os.path.dirname(path) + "/" + name + "*.headers.json")
        url = None
        if headers:
            body = json.load(open(headers[0]))
            url = body.get("url") or body.get("source_url") or body.get("request_url")
        if url is None:
            parts = os.path.basename(os.path.dirname(path)).rsplit("_", 2)
            url = "https://www.sec.gov/Archives/edgar/data/%s/%s/%s" % (int(parts[1]), parts[2], name)
        match = re.match(r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/(.+)$", url)
        cik, digits, document_name = match.group(1), match.group(2), match.group(3)
        blob = validate_record(record={
            "record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
            "byte_length": len(raw), "media_type": "text/html", "storage_uri": "evidence/x/" + name})
        identity = {"raw_asset_id": blob["raw_asset_id"], "company_id": "company", "source_url": url,
                    "accession": digits[:10] + "-" + digits[10:12] + "-" + digits[12:],
                    "document_name": document_name, "source_role": "target_primary"}
        reference = validate_record(record={
            "record_type": "SOURCE_REFERENCE", "source_reference_id": content_hash(value=identity),
            **identity, "request_attempt_id": "attempt"})
        stamp = re.search(r"(\d{8})\.htm$", name).group(1)
        yield name, raw, blob, reference, cik, stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:]


def _run(document, raw, *, split, start):
    route.split_emphasis_note_heading = SPLIT if split else (lambda block: False)
    route.statements_start = START if start else _first_title
    try:
        proposal = route.referenced_note_candidates(document=document, raw_bytes=raw)
    finally:
        route.split_emphasis_note_heading, route.statements_start = SPLIT, START
    return {
        "D02": sorted(c["block_index"] for c in proposal["D02"]["candidates"]),
        "D03": sorted(c["block_index"] for c in proposal["D03"]["candidates"]),
        "notes": [(r["reference"], r["status"],
                   [(c["start_block"], c["end_block_exclusive"], c["scope_relation"])
                    for c in r["range_candidates"]]) for r in proposal.get("note_references", [])],
        "appended": [(r["start_block"], r["end_block_exclusive"]) for r in proposal["checked_ranges"]
                     if r["section_id"] == route.APPENDED_STATEMENTS],
        "reasons": proposal.get("coverage_reasons", []),
    }


def _difference(before, after):
    out = {}
    for key in ("D02", "D03"):
        gained, lost = sorted(set(after[key]) - set(before[key])), sorted(set(before[key]) - set(after[key]))
        if gained or lost:
            out[key] = {"gained": gained, "lost": lost}
    for key in ("notes", "appended", "reasons"):
        if before[key] != after[key]:
            out[key] = {"before": before[key], "after": after[key]}
    return out


def main(root, out):
    rows = []
    for name, raw, blob, reference, cik, period_end in _documents(str(Path(root) / "evidence")):
        try:
            document = BUILD(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                             expected_company_id="company", expected_cik=cik,
                             expected_period_end=period_end)
            document = route.narrow_document_sections(document=document)
            variants = {(split, start): _run(document, raw, split=split, start=start)
                        for split in (False, True) for start in (False, True)}
        except Exception as error:  # recorded, not hidden
            rows.append({"file": name, "error": type(error).__name__ + ":" + str(error)[:200]})
            print(name, "ERROR", str(error)[:120], flush=True)
            continue
        neither = variants[(False, False)]
        row = {"file": name,
               "split_heading_alone": _difference(neither, variants[(True, False)]),
               "statements_start_alone": _difference(neither, variants[(False, True)]),
               "both": _difference(neither, variants[(True, True)])}
        rows.append(row)
        print(name, json.dumps(row["both"])[:300] or "", flush=True)
    Path(out).write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
