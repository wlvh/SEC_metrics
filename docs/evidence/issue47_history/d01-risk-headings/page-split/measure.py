"""What the page-split join moves, on every D01 filing a batch Run read.

Usage: python3 measure.py <runs root> <source root> <out.json>

For each D01 Run under the runs root, the filing is rebuilt from the Run's own
SOURCE_REFERENCE and RAW_BLOB records and the saved bytes under the source
root, twice: with D01's successor builder as it is, and with the join switched
off (which is the builder before the join existed - the join is the only thing
it adds). The frozen heading selector reads both. A filing where nothing is
joined must give a byte-identical document; a filing where something is
joined must lose exactly the joined halves and gain the joined headings.
Zero calls.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "scripts"))

from vnext import historical_text_emphasis as builder  # noqa: E402
from vnext.risk_signals import risk_factor_headings  # noqa: E402


def _document(records, source_root):
    reference = next(r for r in records if r.get("record_type") == "SOURCE_REFERENCE"
                     and r.get("source_role") == "target_primary")
    blob = next(r for r in records if r.get("record_type") == "RAW_BLOB"
                and r["raw_asset_id"] == reference["raw_asset_id"])
    target = next(r for r in records
                  if r.get("record_type") == "DETERMINISTIC_TEXT_CANDIDATE")["calculation_target"]
    raw = (source_root / blob["storage_uri"]).read_bytes()
    return lambda: builder.build_text_document_admitting_underline(
        raw_bytes=raw, raw_blob=blob, source_reference=reference,
        expected_company_id=reference["company_id"], expected_cik=target["entity"],
        expected_period_end=target["period_end"])


def main(runs_root, source_root, out):
    rows = {}
    for run in sorted(Path(runs_root).glob("run-*-D01")):
        records = [json.loads(line) for line in (run / "records.jsonl").read_text(
            encoding="utf-8").splitlines() if line.strip()]
        if not any(r.get("record_type") == "DETERMINISTIC_TEXT_CANDIDATE" for r in records):
            continue
        build = _document(records, Path(source_root))
        after = build()
        with patch.object(builder, "join_headings_split_across_a_page", lambda **_: []):
            before = build()
        headings_before = [h["text"] for h in risk_factor_headings(document=before)["headings"]]
        headings_after = [h["text"] for h in risk_factor_headings(document=after)["headings"]]
        joined = after.get("headings_joined_across_a_page", [])
        rows[run.name] = {
            "joined": joined, "headings_before": len(headings_before),
            "headings_after": len(headings_after),
            "document_identical": before["text_document_id"] == after["text_document_id"],
            "lost": [text for text in headings_before if text not in headings_after],
            "gained": [text for text in headings_after if text not in headings_before]}
        assert rows[run.name]["document_identical"] == (not joined), run.name
        print(run.name, len(joined), len(headings_before), "->", len(headings_after), flush=True)
    Path(out).write_text(json.dumps(
        {"record_type": "ISSUE_47_D01_PAGE_SPLIT_JOIN_MEASUREMENT", "runs_root": str(runs_root),
         "filings": len(rows), "moved": sorted(k for k, v in rows.items() if v["joined"]),
         "per_run": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
