"""Frozen vs page-foot-aware item headings on every saved annual report.

Usage: python3 page_foot_headings.py <restored source root> <out.json>

Builds each saved annual report (DEI DocumentType 10-K) as a text document
through the release-aware builder, as ``pfizer-page-number-note/
navigation_effect.py`` does, and records for each: the item headings the
page-number blanking adds (``historical_text_results.page_bottom_item_headings``)
and three sets of Item 1A, 3 and 8 ranges: the frozen builder's, the route's
before this repair (the unnumbered-item narrowing alone, on the frozen
headings) and the route's after it. ``narrowing_moves_a_range`` compares the
first two and ``repair_moves_a_range`` the last two, so the repair's own effect
is not counted together with the narrowing that was already there. (The first
run of this script compared the frozen ranges with the repaired ones only and
so reported Pfizer's six reports, which the earlier narrowing moves, as moved.)
Zero calls.
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
from vnext.canonical import content_hash, sha256_bytes  # noqa: E402
from vnext.records import validate_record  # noqa: E402
from vnext.historical_dei import release_aware  # noqa: E402
from vnext import text_coverage  # noqa: E402
from vnext import historical_text_results as route  # noqa: E402

build = release_aware(text_coverage.build_text_document)


def ranges(sections):
    return {key: [(c["start_block"], c["end_block_exclusive"]) for c in value["candidates"]]
            for key, value in sections.items()}


def narrowing_only(document):
    """The route before this repair: the unnumbered-item narrowing over the frozen headings.

    ``narrow_document_sections`` asks ``page_bottom_item_headings`` by its
    module name; answering "no heading added" leaves it the narrowing alone.
    """
    original = route.page_bottom_item_headings
    route.page_bottom_item_headings = lambda *, document: (None, [])
    try:
        return route.narrow_document_sections(document=document)
    finally:
        route.page_bottom_item_headings = original


def annual_reports(root):
    """Every saved annual report under ``root`` as (file name, frozen text document or error)."""
    evidence = str(Path(root) / "evidence")
    paths = sorted(glob.glob(evidence + "/request_attempts/*/*/*.htm")
                   + glob.glob(evidence + "/accession_materials/*/*.htm"))
    seen = set()
    for path in paths:
        name = os.path.basename(path)
        raw = open(path, "rb").read()
        if name in seen or not re.search(rb'name="dei:DocumentType"[^>]*>(?:<[^>]+>)*\s*10-K\s*<', raw):
            continue
        seen.add(name)
        headers = glob.glob(os.path.dirname(path) + "/" + name + "*.headers.json")
        url = None
        if headers:
            record = json.load(open(headers[0]))
            url = record.get("url") or record.get("source_url") or record.get("request_url")
        if url is None:
            folder = os.path.basename(os.path.dirname(path)).rsplit("_", 2)
            url = "https://www.sec.gov/Archives/edgar/data/%s/%s/%s" % (int(folder[1]), folder[2], name)
        match = re.match(r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/(.+)$", url)
        cik, digits, document_name = match.group(1), match.group(2), match.group(3)
        accession = digits[:10] + "-" + digits[10:12] + "-" + digits[12:]
        blob = validate_record(record={"record_type": "RAW_BLOB",
                                       "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
                                       "byte_length": len(raw), "media_type": "text/html",
                                       "storage_uri": "evidence/x/" + name})
        identity = {"raw_asset_id": blob["raw_asset_id"], "company_id": "company", "source_url": url,
                    "accession": accession, "document_name": document_name,
                    "source_role": "target_primary"}
        reference = validate_record(record={"record_type": "SOURCE_REFERENCE",
                                            "source_reference_id": content_hash(value=identity),
                                            **identity, "request_attempt_id": "attempt"})
        stamp = re.search(r"(\d{8})\.htm$", name)
        if stamp is None:
            yield name, None, "NO_PERIOD_STAMP_IN_NAME"
            continue
        stamp = stamp.group(1)
        period_end = stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:]
        try:
            document = build(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                             expected_company_id="company", expected_cik=cik,
                             expected_period_end=period_end)
        except Exception as error:  # recorded, not hidden
            yield name, None, type(error).__name__ + ":" + str(error)[:200]
            continue
        yield name, document, None


def main(root, out_path):
    out = []
    for name, document, problem in annual_reports(root):
        if document is None:
            out.append({"file": name, "error": problem})
            print(name, "ERROR", problem[:160], flush=True)
            continue
        try:
            headings, added = route.page_bottom_item_headings(document=document)
            narrowed = narrowing_only(document)
            corrected = route.narrow_document_sections(document=document)
        except Exception as error:  # recorded, not hidden
            out.append({"file": name, "error": type(error).__name__ + ":" + str(error)[:200]})
            print(name, "ERROR", str(error)[:160], flush=True)
            continue
        blocks = document["blocks"]
        row = {"file": name, "period_end": document["period_end"],
               "page_numbers": len(route.page_number_blocks(blocks)),
               "added_headings": [{"block_index": h["block_index"], "item": h["item"],
                                   "text": blocks[h["block_index"]]["text"][:120],
                                   "next_block": blocks[h["heading_end_index"] + 1]["text"][:20]}
                                  for h in added],
               "frozen_ranges": ranges(document["sections"]),
               "narrowed_ranges": ranges(narrowed["sections"]),
               "corrected_ranges": ranges(corrected["sections"]),
               "narrowing_moves_a_range": ranges(document["sections"]) != ranges(narrowed["sections"]),
               "repair_moves_a_range": ranges(narrowed["sections"]) != ranges(corrected["sections"]),
               "page_foot_policy_recorded": "item_heading_policy" in corrected}
        out.append(row)
        print(name, len(added), row["narrowing_moves_a_range"], row["repair_moves_a_range"],
              row["page_foot_policy_recorded"],
              row["added_headings"] or "", flush=True)
    Path(out_path).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
