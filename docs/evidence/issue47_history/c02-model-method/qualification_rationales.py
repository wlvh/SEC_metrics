"""Give #28 the four qualification-rationale blocks in full, with their place in the filing.

#28's reply on Issue #47 (comment 5968966522) asked, for the four Pfizer FY2022
blocks review.json classed QUALIFICATION_MEANING (413, 3131, 3137, 3138), for
the full text with fixed source pointers and the complete model statements
that cite them; review.json kept only a short excerpt. This reads the
development input (``prepare_inputs.py`` output, checked byte for byte against
``inputs-index.json``) and the committed answer, and writes, for every
``member_qualification`` statement of that answer (the four blocks belong to two
of them; two more statements of the same kind cite blocks the route took for
another fact, so the block comparison did not flag them):

- the statement exactly as the answer gave it;
- every block it cites, in full, with the block's raw byte span in the original
  proxy and that span's hash (``locators.json``);
- the passages around those blocks, in full, as the input shows them (the
  windows are the executor's choice, listed in the output so they can be
  widened);
- for every block shown, whether the historical route's selector took it, how
  #47's older-year reading judged it (the reading is matched block by block
  through the text hash it recorded; a block whose text differs is marked, not
  matched), and the unified adjudication's decision where one overrides the
  reader (``../c02-composition-facts/adjudication.json``): #47's acceptance
  reads the reading through the adjudication, so the reader's verdict alone is
  not #47's judgement.

Nothing here decides the meaning; the alignment is item by item with #28.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/c02-model-method/qualification_rationales.py <inputs dir>
"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))
from sec_urls import accession_document_url  # noqa: E402

POSITION = "pfizer-2022-12-31"
READING = REPO / "docs/evidence/issue47_history/c02-older-years/judgements" / (POSITION + ".json")
ADJUDICATION = REPO / "docs/evidence/issue47_history/c02-composition-facts/adjudication.json"
DISPUTED = (413, 3131, 3137, 3138)
# The passages shown around the cited blocks: (first, last, what the passage is).
WINDOWS = (
    (355, 364, "Item 1 - Election of Directors: the slate, the general criteria for Board "
               "membership and the annual evaluation against them"),
    (412, 414, "Item 1 - Election of Directors: 'Our 2023 Director Nominees' and the head of "
               "the nominee table"),
    (3095, 3099, "Item 6 - Independent Board Chairman Policy: a shareholder proposal and its "
                 "resolution"),
    (3116, 3117, "The Board of Directors' Statement in Opposition to the Proposal"),
    (3127, 3140, "The statement in opposition, continued: why the Board keeps a flexible "
                 "leadership structure, its annual review, the reasons for keeping the "
                 "combined Chairman and CEO, and the Lead Independent Director"),
    (720, 724, "Governance: Board Leadership Structure and its 2022 annual review"),
    (894, 898, "Governance: the Governance & Sustainability Committee Report"),
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _checked_inputs(inputs_dir):
    folder = Path(inputs_dir) / POSITION
    index = json.loads((HERE / "inputs-index.json").read_text(encoding="utf-8"))["files"][POSITION]
    for name, meta in index.items():
        data = (folder / name).read_bytes()
        if _sha(data) != meta["sha256"] or len(data) != meta["size"]:
            raise SystemExit(f"QUALIFICATION_RATIONALES_INPUT_IS_NOT_THE_INDEXED_ONE: {name}")
    return folder


def _blocks(source_text):
    blocks = {}
    for match in re.finditer(r"\[B(\d+)\]\n(.*?)(?=\n\n\[B\d+\]\n|\Z)", source_text, re.S):
        blocks[int(match.group(1))] = match.group(2)
    return blocks


def _reading():
    reading = json.loads(READING.read_text(encoding="utf-8"))
    judged = {}
    for key in ("pool", "pool_facts", "selected"):
        for row in reading[key]:
            entry = judged.setdefault(row["i"], {"text_sha256": row["text_sha256"]})
            if key == "pool":
                entry["in_packet"] = True
            else:
                entry.update(verdict=row["verdict"], why=row["why"], listed_as=key)
    return reading, judged


def _adjudicated(position):
    decisions = json.loads(ADJUDICATION.read_text(encoding="utf-8"))["decisions"]
    return {row["i"]: row for row in decisions if row["position"] == position}


def _registry_cik(company_id):
    with (REPO / "config/company_registry.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["company_id"] == company_id:
                return int(row["primary_cik"])
    raise SystemExit("QUALIFICATION_RATIONALES_COMPANY_NOT_REGISTERED: " + company_id)


def _shown(index, text, *, locators, selected, judged, adjudicated):
    reading_row = judged.get(index)
    text_hash = "sha256:" + _sha(text.encode("utf-8"))
    if reading_row is None:
        reading = "NOT_IN_THE_READING_PACKET"
    elif reading_row["text_sha256"] != text_hash:
        reading = "TEXT_DIFFERS_FROM_THE_READING"
    elif "verdict" in reading_row:
        reading = {"verdict": reading_row["verdict"], "why": reading_row["why"],
                   "listed_as": reading_row["listed_as"]}
    else:
        reading = "IN_THE_PACKET_NOT_LISTED_AS_A_FACT"
    locator = locators[index]
    adjudication = adjudicated.get(index)
    if adjudication is not None and adjudication["text_sha256"] != text_hash:
        raise SystemExit(f"QUALIFICATION_RATIONALES_ADJUDICATED_TEXT_DIFFERS: {index}")
    return {"block": index, "text": text, "text_sha256": text_hash,
            "raw_start_byte": locator["raw_start_byte"], "raw_end_byte": locator["raw_end_byte"],
            "raw_span_sha256": locator["raw_span_sha256"],
            "taken_by_the_route_selector": index in selected,
            "older_year_reading": reading,
            "unified_adjudication": (None if adjudication is None else
                                     {"rule": adjudication["rule"],
                                      "decision": adjudication["decision"]})}


def main(inputs_dir):
    folder = _checked_inputs(inputs_dir)
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    blocks = _blocks((folder / "source.txt").read_text(encoding="utf-8"))
    locators = {row["block_index"]: row
                for row in json.loads((folder / "locators.json").read_text(encoding="utf-8"))}
    selected = set(metadata["route_selection"])
    reading, judged = _reading()
    adjudicated = _adjudicated(metadata["company_id"] + ":" + metadata["report_end"])
    answer = json.loads((HERE / "answers" / (POSITION + ".json")).read_text(encoding="utf-8"))
    filing = metadata["filing"]
    cik = _registry_cik(metadata["company_id"])

    def shown(index):
        return _shown(index, blocks[index], locators=locators, selected=selected, judged=judged,
                      adjudicated=adjudicated)

    statements = [{"statement": fact,
                   "disputed_blocks": [b for b in fact["source_blocks"] if b in DISPUTED],
                   "cited_blocks": [shown(b) for b in fact["source_blocks"]]}
                  for fact in answer["facts"] if fact["kind"] == "member_qualification"]
    cited_disputed = {b for row in statements for b in row["disputed_blocks"]}
    if cited_disputed != set(DISPUTED):
        raise SystemExit("QUALIFICATION_RATIONALES_STATEMENTS_DO_NOT_CITE_THE_FOUR_BLOCKS")
    value = {
        "record_type": "ISSUE_47_C02_QUALIFICATION_RATIONALES",
        "for": "#28's reply on Issue #47, comment 5968966522",
        "position": metadata["company_id"] + ":" + metadata["report_end"],
        "filing": {"form": filing["form"], "accession": filing["accessionNumber"],
                   "filing_date": filing["filingDate"], "primary_document": filing["primaryDocument"],
                   "url": accession_document_url(cik=cik, accession=filing["accessionNumber"],
                                                 document_name=filing["primaryDocument"]),
                   "raw_asset_id": metadata["raw_asset_id"],
                   "document_id": metadata["document_id"],
                   "source_reference_id": metadata["source_reference_id"]},
        "input": {"input_sha256": metadata["input_sha256"], "task_sha256": metadata["task_sha256"],
                  "answer_sha256": _sha((HERE / "answers" / (POSITION + ".json")).read_bytes()),
                  "how_to_rebuild": "prepare_inputs.py on a root restored from the committed SEC "
                                    "export; files must match inputs-index.json"},
        "reading": {"file": str(READING.relative_to(REPO)), "reader": reading["reader"],
                    "read_as": reading["read_as"],
                    "matched_by": "block index and the block text hash the reading recorded",
                    "adjudication": str(ADJUDICATION.relative_to(REPO))},
        "disputed_blocks": list(DISPUTED),
        "statements": statements,
        "passages": [{"first": first, "last": last, "what": what,
                      "blocks": [shown(i) for i in range(first, last + 1)]}
                     for first, last, what in WINDOWS],
        "calls": [0, 0, 0],
    }
    out = HERE / "qualification-rationales.json"
    out.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"statements": len(statements),
                      "disputed": sorted(cited_disputed),
                      "readings": {str(b["block"]): b["older_year_reading"]
                                   if isinstance(b["older_year_reading"], str)
                                   else b["older_year_reading"]["verdict"]
                                   for row in statements for b in row["cited_blocks"]},
                      "adjudicated": {str(b["block"]): b["unified_adjudication"]
                                      for row in statements for b in row["cited_blocks"]
                                      if b["unified_adjudication"]}}))


if __name__ == "__main__":
    main(sys.argv[1])
