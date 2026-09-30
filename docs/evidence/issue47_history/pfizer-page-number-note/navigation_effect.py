"""Frozen vs page-number-aware note navigation on every saved annual report.

Usage: python3 navigation_effect.py <restored source root> <out.json>

Builds each saved annual report (DEI DocumentType 10-K) as a text document
through the release-aware builder, runs the frozen ``_note_references`` and
``historical_text_results.note_references`` on its Item 1A/3/8 ranges, and
records every difference with the page-number blocks and the identifier-built
headings. Zero calls.
"""
import sys, glob, re, json, os
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
from vnext.canonical import content_hash, sha256_bytes
from vnext.records import validate_record
from vnext.historical_dei import release_aware
from vnext import text_coverage
from vnext.text_business_candidates import _note_references, _ranges
from vnext.historical_text_results import note_references, page_number_blocks
from vnext.text_coverage import _Blocks
R = str(Path(sys.argv[1]) / "evidence")
build = release_aware(text_coverage.build_text_document)
pat = json.load(open(REPO / "catalog/r6/text_business_candidates_v1.json"))["patterns"]
NH = re.compile(pat["note_heading"], re.I); NI = re.compile(pat["note_identifier"], re.I)
out, seen = [], set()
paths = sorted(glob.glob(R + "/request_attempts/*/*/*.htm") + glob.glob(R + "/accession_materials/*/*.htm"))
for path in paths:
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    if name in seen or not re.search(rb'name="dei:DocumentType"[^>]*>(?:<[^>]+>)*\s*10-K\s*<', raw): continue
    seen.add(name)
    end = re.search(rb'name="dei:DocumentPeriodEndDate"[^>]*>(?:<[^>]+>)*\s*([^<]+?)\s*<', raw)
    cikm = re.search(rb'name="dei:EntityCentralIndexKey"[^>]*>(?:<[^>]+>)*\s*(\d+)\s*<', raw)
    hdr = glob.glob(os.path.dirname(path) + "/" + name + "*.headers.json")
    url = None
    if hdr:
        j = json.load(open(hdr[0])); url = j.get("url") or j.get("source_url") or j.get("request_url")
    if url is None:
        folder = os.path.basename(os.path.dirname(path)); parts = folder.rsplit("_", 2)
        url = "https://www.sec.gov/Archives/edgar/data/%s/%s/%s" % (int(parts[1]), parts[2], name)
    m = re.match(r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/(.+)$", url)
    cik, digits, doc = m.group(1), m.group(2), m.group(3)
    accession = digits[:10] + "-" + digits[10:12] + "-" + digits[12:]
    blob = validate_record(record={"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
                                   "byte_length": len(raw), "media_type": "text/html", "storage_uri": "evidence/x/" + name})
    ident = {"raw_asset_id": blob["raw_asset_id"], "company_id": "company", "source_url": url, "accession": accession,
             "document_name": doc, "source_role": "target_primary"}
    ref = validate_record(record={"record_type": "SOURCE_REFERENCE", "source_reference_id": content_hash(value=ident), **ident, "request_attempt_id": "attempt"})
    stamp = re.search(r"(\d{8})\.htm$", name).group(1)
    period_end = stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:]
    try:
        document = build(raw_bytes=raw, raw_blob=blob, source_reference=ref, expected_company_id="company", expected_cik=cik, expected_period_end=period_end)
    except Exception as e:
        out.append({"file": name, "error": str(e)[:160]}); print(name, "BUILD_ERR", str(e)[:120], flush=True); continue
    ranges, reasons = _ranges(document, ["ITEM_1A", "ITEM_3", "ITEM_8"])
    frozen = _note_references(document, ranges)
    succ = note_references(document, ranges)
    pages = page_number_blocks(document["blocks"])
    blocks = document["blocks"]
    ident_headings = [i for i, b in enumerate(blocks) if not b["linked"] and b.get("emphasized") and len(b["text"]) <= 300
                      and not NH.match(b["text"]) and NI.fullmatch(b["text"]) and i + 1 < len(blocks)
                      and blocks[i+1].get("emphasized") and re.match(r"[A-Za-z]", blocks[i+1]["text"])]
    row = {"file": name, "pages": len(pages), "identifier_headings": len(ident_headings),
           "identifier_headings_that_are_pages": len(set(ident_headings) & pages),
           "references": [(r["reference"], r["status"]) for r in frozen],
           "differs": frozen != succ,
           "successor": [(r["reference"], r["status"], [(c["start_block"], c["end_block_exclusive"], c["scope_relation"]) for c in r["range_candidates"]]) for r in succ] if frozen != succ else None,
           "frozen_candidates": [(r["reference"], [(c["start_block"], c["end_block_exclusive"]) for c in r["range_candidates"]]) for r in frozen] if frozen != succ else None}
    out.append(row)
    print(name, row["identifier_headings"], row["identifier_headings_that_are_pages"], row["references"], "DIFFERS" if row["differs"] else "", row["successor"] or "", row["frozen_candidates"] or "", flush=True)
Path(sys.argv[2]).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
