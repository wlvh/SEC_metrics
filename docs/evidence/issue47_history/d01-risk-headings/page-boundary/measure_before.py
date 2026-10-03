"""Before the port: what the page join did on every D01 filing of a batch, and what #28's detector sees.

Usage: python3 measure_before.py <runs root> <source root> <out.json>

For each D01 Run under the runs root, the filing is rebuilt from the Run's own
SOURCE_REFERENCE and RAW_BLOB records and the saved bytes under the source root
with D01's successor builder as it stood before the port (it joins a heading
split across a page). Each join is listed with the blocks between its halves,
each classed as a page number, the linked "Table of Contents" line, or other.
Beside it, #28's detector (865d8220, ``split_heading_requires_multispan``,
copied here as data about that commit) reports whether the filing has the one
page-split layout it refuses. Zero calls.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "scripts"))

from vnext import historical_text_emphasis as builder  # noqa: E402
from vnext.risk_signals import risk_factor_headings  # noqa: E402

_PAGE_NUMBER = re.compile(r"\d{1,3}")


def _kind(block):
    text = block["text"].strip()
    if _PAGE_NUMBER.fullmatch(text):
        return "PAGE_NUMBER"
    if block["linked"] and text.casefold() == "table of contents":
        return "LINKED_CONTENTS"
    return "OTHER"


def detector_28(*, blocks, section):
    """#28's four-block layout at 865d8220: heading, page number, linked contents, lower-case heading."""
    if not section or section.get("status") != "LOCATED" or len(section["candidates"]) != 1:
        return []
    scope = section["candidates"][0]
    start, end = scope["start_block"], scope["end_block_exclusive"]
    found = []
    for index in range(start, max(start, end - 3)):
        block = blocks[index]
        page, contents, continuation = blocks[index + 1:index + 4]
        if (builder._heading_only(block) and not builder._SENTENCE_END.search(block["text"])
                and _PAGE_NUMBER.fullmatch(page["text"].strip())
                and contents["linked"] and contents["text"].strip().casefold() == "table of contents"
                and builder._heading_only(continuation) and continuation["text"][:1].islower()):
            found.append(index)
    return found


def main(runs_root, source_root, out):
    rows = {}
    for run in sorted(Path(runs_root).glob("run-*-D01")):
        records = [json.loads(line) for line in (run / "records.jsonl").read_text(
            encoding="utf-8").splitlines() if line.strip()]
        candidates = [r for r in records if r.get("record_type") == "DETERMINISTIC_TEXT_CANDIDATE"]
        if not candidates:
            continue
        reference = next(r for r in records if r.get("record_type") == "SOURCE_REFERENCE"
                         and r.get("source_role") == "target_primary")
        blob = next(r for r in records if r.get("record_type") == "RAW_BLOB"
                    and r["raw_asset_id"] == reference["raw_asset_id"])
        target = candidates[0]["calculation_target"]
        raw = (Path(source_root) / blob["storage_uri"]).read_bytes()
        document = builder.build_text_document_admitting_underline(
            raw_bytes=raw, raw_blob=blob, source_reference=reference,
            expected_company_id=reference["company_id"], expected_cik=target["entity"],
            expected_period_end=target["period_end"])
        joins = []
        for join in document.get("headings_joined_across_a_page", []):
            between = [_kind(document["blocks"][index]) for index in join["furniture_blocks"]]
            joins.append({**join, "between": between,
                          "page_number_and_linked_contents": between == ["PAGE_NUMBER", "LINKED_CONTENTS"],
                          "heading": document["blocks"][join["first_block"]]["leading_emphasis"]["text"]})
        rows[run.name] = {
            "headings": len(risk_factor_headings(document=document)["headings"]),
            "joins": joins,
            "detector_28_first_blocks": detector_28(blocks=document["blocks"],
                                                    section=document["sections"].get("ITEM_1A"))}
        print(run.name, len(joins), rows[run.name]["detector_28_first_blocks"], flush=True)
    joined = {name: row for name, row in rows.items() if row["joins"]}
    Path(out).write_text(json.dumps(
        {"record_type": "ISSUE_47_D01_PAGE_BOUNDARY_BEFORE_PORT", "runs_root": str(runs_root),
         "filings": len(rows), "filings_with_a_join": sorted(joined),
         "joins_without_the_contents_link": sorted(
             name for name, row in joined.items()
             if not all(join["page_number_and_linked_contents"] for join in row["joins"])),
         "per_run": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
