"""Read D02's excerpt sets in both directions against recorded judgements.

For a position, today's selection is recomputed from the saved annual report
through the route's own input and candidate builders, and a packet is made of
every block a reader has to judge:

* every excerpt taken, with the scope it came from - Item 3, a note scope the
  filing incorporates by reference, or Item 8 through the keyword proxy;
* every block inside the narrow scopes (Item 3 and each incorporated scope)
  that the selector skipped;
* every heading-shaped block of the document that names contingencies, legal
  proceedings, litigation or commitments - the approved definition's source
  words, not the proxy's keyword set - with where it sits and the distance to
  the next excerpt after it. This is the direction a reading of the excerpts
  cannot see: a note the selection never reaches.

A note Item 3 does not incorporate is still a source the definition names, so
a heading in Item 8 that names contingencies, legal proceedings or litigation
also brings the blocks under it (``context``). Where the filing's Item 8 is a
cross-reference page, its statements sit after it, outside every range the
route reads; the keyword blocks there are brought in too (``outside``).

A reading is data: one judgement per packet block, bound to the block's text
by SHA-256. Taken blocks are DISCLOSURE or NOT_DISCLOSURE; skipped and context
blocks CORRECTLY_SKIPPED (not litigation disclosure), COVERED_ELSEWHERE (a
matter the value states in the excerpts it cites) or WRONGLY_SKIPPED (a matter
the value lacks); headings REACHED, NOT_D02 or MISSED. A
packet block the reading does not judge, a judgement whose block is not in the
packet, or one whose text changed stops the reading: a reading that did not
see a block is never read as agreeing with it.

What it does not cover, and says so in every answer (``NOT_COVERED``): the
rest of Item 8. Inside Item 8 the packet holds the blocks the keyword proxy
took, the named headings and the blocks under an Item 8 heading that names
contingencies, legal proceedings, litigation or legal matters; after Item 8,
the keyword blocks outside every range. A contingency disclosure under a
heading worded otherwise, or under none, elsewhere in Item 8 is not in the
packet (the proxy's registered decision, d02-content-read/keyword-proxy-decision.json).

Against published results (``--runs-root`` and ``--closure``) the reading
becomes an acceptance reading: the position matches only when the reading
agrees and the result is this selection - the Run's candidate hash is the one
recomputed here and its excerpts are the taken blocks' texts in order. The
value is named by digest, and the identity of the result it was read against
is recorded at reading time.

Older years read their filings from an export-restored root (``--source-root``,
restored by this checkout so its trust journal knows it).

Usage:
    python3 tools/read_d02_excerpts.py --packet --position <company>:<report_end> \
        [--source-root <root>] --output <packet.json>
    python3 tools/read_d02_excerpts.py --position <company>:<report_end> [...] \
        [--source-root <root>] --runs-root <root> [--runs-root <root>] \
        --closure sha256:<closure> --acceptance-output <path>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

READING_DIR = REPO / "docs/evidence/issue47_history/d02-older-years/judgements"
ADJUDICATION_PATH = REPO / "docs/evidence/issue47_history/d02-older-years/adjudication.json"
VERDICTS = {"TAKEN": {"DISCLOSURE", "NOT_DISCLOSURE"},
            "SKIPPED": {"CORRECTLY_SKIPPED", "COVERED_ELSEWHERE", "WRONGLY_SKIPPED"},
            "CONTEXT": {"CORRECTLY_SKIPPED", "COVERED_ELSEWHERE", "WRONGLY_SKIPPED"},
            "OUTSIDE": {"CORRECTLY_SKIPPED", "COVERED_ELSEWHERE", "WRONGLY_SKIPPED"},
            "HEADING": {"REACHED", "NOT_D02", "MISSED"}}
KINDS = (("TAKEN", "taken"), ("SKIPPED", "skipped"), ("CONTEXT", "context"),
         ("OUTSIDE", "outside"), ("HEADING", "headings"))
# The approved definition's sources: Item 3, legal proceedings, contingencies
# notes; commitments because the notes are titled "Commitments and
# Contingencies". Not the proxy's _LEGAL set.
HEADING_WORDS = re.compile(r"contingenc|legal proceeding|litigation|commitment", re.I)
NOT_A_HEADING_END = (".", ":", ";", ",", "。")
# A note Item 3 does not incorporate is still a source the definition names
# ("contingencies notes"), and only its keyword blocks reach the value. So a
# heading inside Item 8 that names contingencies, legal proceedings or
# litigation brings the blocks under it into the packet: a numbered note
# heading up to the next numbered note heading, any other heading up to the
# next bold heading, each within a cap and within Item 8. A statement caption
# pointing at a note ("Commitments and contingencies (Note 14)") is listed but
# brings nothing - the note it points at is its own heading.
CONTEXT_WORDS = re.compile(r"contingenc|legal proceeding|litigation|legal matter", re.I)
NUMBERED_NOTE = re.compile(r"^\s*(?:note\s+)?\d{1,2}\s*[.:)\u2014\u2013-]?\s+[A-Za-z]", re.I)
STATEMENT_CAPTION = re.compile(r"\(\s*notes?\s+\d", re.I)
CONTEXT_CAP = {"NOTE": 150, "HEADING": 60}
# Ranges the route reads through the keyword, not whole: Item 8, and where Item 8
# only points to them, the statements printed after the items
# (historical_text_results.appended_statements_range). The others are narrow:
# Item 3 and the note scopes it incorporates, read whole.
KEYWORD_SECTIONS = ("ITEM_8", "ITEM_8_STATEMENTS_PRINTED_AFTER_THE_ITEMS")
WIDE_SECTIONS = ("ITEM_1A",) + KEYWORD_SECTIONS
NOT_COVERED = ("Item 8 outside the incorporated scopes, except the blocks the keyword "
               "proxy took, the headings naming contingencies, legal proceedings, "
               "litigation or commitments, and the blocks under an Item 8 heading naming "
               "contingencies, legal proceedings, litigation or legal matters; after Item 8, "
               "keyword blocks outside every range are read")


def text_sha256(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def route_selection(*, source_root: Path, company_id: str, report_end: str):
    """The annual document, its ranges and the D02 excerpts the historical route selects."""
    from vnext.historical_results import TEXT_SPEC_PATHS
    from vnext.historical_spec_revision import compile_historical_spec_file
    from vnext.historical_text_input import prepare_historical_business_text_input
    from vnext.historical_text_results import prepare_business_text_sources, text_api
    from vnext.normal_history_plan import checkpoint_replayed_once
    from vnext.normal_period_selection import resolve_period_selection
    with checkpoint_replayed_once():
        selection = resolve_period_selection(repo_root=source_root, company_id=company_id,
                                             report_end=report_end)
        prepared = prepare_historical_business_text_input(
            repo_root=source_root, company_id=company_id, metric_id="D02",
            period_selection=selection)
        spec = compile_historical_spec_file(repo_root=REPO,
                                            repo_relative_path=TEXT_SPEC_PATHS["D02"],
                                            dependency_specs={})
        api, _ = text_api("D02")
        candidate = api.create_deterministic_text_candidate(compiled_spec=spec,
                                                            **prepared["text_arguments"])
        built = prepare_business_text_sources(metric_id="D02", **prepared["text_arguments"])
    if len(built["proposals"]) != 1:
        raise SystemExit("D02_READING_EXPECTS_ONE_ANNUAL_DOCUMENT")
    reference_id = next(iter(built["proposals"]))
    return built["documents"][reference_id], built["proposals"][reference_id], candidate


def make_packet(*, document, proposal, candidate):
    """Every block a reader judges for one position, in document order."""
    blocks = document["blocks"]
    taken = sorted(candidate["selected"].values(), key=lambda claim: claim["order"])
    by_index = {claim["block_index"]: claim for claim in proposal["D02"]["candidates"]}
    taken_indices = [claim["block_index"] for claim in taken]
    if sorted(taken_indices) != sorted(by_index) or len(set(taken_indices)) != len(taken_indices):
        raise SystemExit("D02_CANDIDATE_IS_NOT_THE_PROPOSAL")
    narrow = [r for r in proposal["checked_ranges"] if r["section_id"] not in WIDE_SECTIONS]
    scope_of = {}
    for scope in narrow:
        for index in range(scope["start_block"], scope["end_block_exclusive"]):
            # An incorporated scope inside Item 3 does not occur; a later scope
            # nested in an earlier one (a sub-note) is the narrower name.
            scope_of[index] = scope["section_id"]
    rows = {"taken": [], "skipped": [], "headings": []}
    for claim in taken:
        index = claim["block_index"]
        rows["taken"].append({
            "i": index, "scope": by_index[index]["section_id"],
            "labels": by_index[index]["labels"], "text": blocks[index]["text"],
            "text_sha256": text_sha256(blocks[index]["text"])})
    chosen = set(taken_indices)
    for index in sorted(scope_of):
        if index in chosen:
            continue
        block = blocks[index]
        rows["skipped"].append({
            "i": index, "scope": scope_of[index], "text": block["text"],
            "text_sha256": text_sha256(block["text"]), "linked": bool(block.get("linked")),
            "emphasized": bool(block.get("emphasized"))})
    for block in blocks:
        text = block["text"].strip()
        if (block.get("linked") or len(text) > 120 or text.endswith(NOT_A_HEADING_END)
                or not HEADING_WORDS.search(text)):
            continue
        index = block["block_index"]
        after = [i for i in taken_indices if i > index]
        section = next((r["section_id"] for r in proposal["checked_ranges"]
                        if r["start_block"] <= index < r["end_block_exclusive"]
                        and r["section_id"] not in KEYWORD_SECTIONS), None)
        if section is None:
            section = next((r["section_id"] for r in proposal["checked_ranges"]
                            if r["start_block"] <= index < r["end_block_exclusive"]), None)
        rows["headings"].append({
            "i": index, "text": block["text"], "text_sha256": text_sha256(block["text"]),
            "section": section, "emphasized": bool(block.get("emphasized")),
            "next_excerpt_after": min(after) if after else None,
            "distance": (min(after) - index) if after else None})
    item_8 = next((r for r in proposal["checked_ranges"] if r["section_id"] == "ITEM_8"), None)
    keyword_ranges = [r for r in proposal["checked_ranges"] if r["section_id"] in KEYWORD_SECTIONS]
    context = set()
    for row in rows["headings"]:
        index = row["i"]
        holder = next((r for r in keyword_ranges
                       if r["start_block"] <= index < r["end_block_exclusive"]), None)
        if (holder is None or index in scope_of or not CONTEXT_WORDS.search(row["text"])
                or STATEMENT_CAPTION.search(row["text"])):
            continue
        whole_note = bool(NUMBERED_NOTE.match(row["text"]))
        stop = min(holder["end_block_exclusive"],
                   index + 1 + CONTEXT_CAP["NOTE" if whole_note else "HEADING"])
        for j in range(index + 1, stop):
            block = blocks[j]
            text = block["text"].strip()
            shaped = (not block.get("linked") and len(text) <= 120
                      and not text.endswith(NOT_A_HEADING_END) and block.get("emphasized"))
            if shaped and (NUMBERED_NOTE.match(text) if whole_note else True):
                break
            context.add(j)
    rows["context"] = [{"i": j, "text": blocks[j]["text"], "text_sha256": text_sha256(blocks[j]["text"])}
                       for j in sorted(context - chosen - set(scope_of))]
    # The keyword proxy scans only the Item 8 range. Where a filing's Item 8 is a
    # cross-reference page (Macy's FY2021: "Information called for by this item
    # is set forth in the Company's Consolidated Financial Statements"), the
    # statements sit after it, outside every range, and nothing reads them. The
    # keyword blocks there are brought in, found with the route's own keyword so
    # that "the proxy would have taken it had it looked" is the question asked.
    from vnext.text_business_candidates import _LEGAL
    ranges = proposal["checked_ranges"]
    item_8_end = item_8["end_block_exclusive"] if item_8 is not None else None
    rows["outside"] = [
        {"i": block["block_index"], "text": block["text"],
         "text_sha256": text_sha256(block["text"])}
        for block in blocks
        if item_8_end is not None and block["block_index"] >= item_8_end
        and not any(r["start_block"] <= block["block_index"] < r["end_block_exclusive"]
                    for r in ranges)
        and block["block_index"] not in chosen and _LEGAL.search(block["text"])]
    return {"document_id": document["text_document_id"],
            "source_reference_id": document["source_reference_id"],
            "ranges": [{key: r[key] for key in ("section_id", "start_block", "end_block_exclusive")}
                       for r in proposal["checked_ranges"]],
            "candidate_hash": candidate["candidate_hash"], **rows}


def read_position(*, packet, reading):
    """Compare one position's judgements with its packet; coverage must be exact."""
    expected = {}
    for kind, key in KINDS:
        for row in packet.get(key, ()):
            expected[(kind, row["i"])] = row["text_sha256"]
    seen, covered = set(), []
    taken = {row["i"] for row in packet["taken"]}
    problems = {"wrongly_taken": [], "wrongly_skipped": [], "missed_headings": []}
    for row in reading["judgements"]:
        key = (row["kind"], row["i"])
        if key not in expected:
            raise SystemExit("D02_JUDGED_BLOCK_NOT_IN_THE_PACKET:" + reading["position"] + ":" + str(key))
        if key in seen:
            raise SystemExit("D02_BLOCK_JUDGED_TWICE:" + reading["position"] + ":" + str(key))
        if row["text_sha256"] != expected[key] or (
                "text" in row and text_sha256(row["text"]) != row["text_sha256"]):
            raise SystemExit("D02_JUDGED_TEXT_CHANGED:" + reading["position"] + ":" + str(key))
        if row["verdict"] not in VERDICTS[row["kind"]]:
            raise SystemExit("D02_VERDICT_INVALID:" + reading["position"] + ":" + str(key))
        seen.add(key)
        if row["verdict"] == "COVERED_ELSEWHERE":
            # The block states a matter the value states elsewhere; the reading
            # has to say where, and there has to be an excerpt there.
            cited = row.get("covered_by") or []
            if not cited or not set(cited) <= taken:
                raise SystemExit("D02_COVERED_BY_IS_NOT_A_TAKEN_BLOCK:" + reading["position"]
                                 + ":" + str(key))
            covered.append({"i": row["i"], "kind": row["kind"], "covered_by": cited})
        if row["verdict"] == "NOT_DISCLOSURE":
            problems["wrongly_taken"].append({"i": row["i"], "why": row.get("why", "")})
        elif row["verdict"] == "WRONGLY_SKIPPED":
            problems["wrongly_skipped"].append({"i": row["i"], "kind": row["kind"],
                                                "why": row.get("why", "")})
        elif row["verdict"] == "MISSED":
            problems["missed_headings"].append({"i": row["i"], "why": row.get("why", "")})
    unread = sorted(set(expected) - seen)
    if unread:
        raise SystemExit("D02_PACKET_BLOCKS_NOT_JUDGED:" + reading["position"] + ":" + str(unread[:8]))
    counts = {"taken": len(packet["taken"]), "skipped": len(packet["skipped"]),
              "context": len(packet.get("context", ())), "outside": len(packet.get("outside", ())),
              "headings": len(packet["headings"]),
              "taken_through_item_8": sum(1 for row in packet["taken"] if row["scope"] in KEYWORD_SECTIONS)}
    counts["covered_elsewhere"] = len(covered)
    clean = not any(problems.values())
    return {"verdict": "READING_AGREES" if clean else "READING_DISAGREES",
            "counts": counts, "problems": problems, "covered_elsewhere": covered}


def load_adjudications(path=ADJUDICATION_PATH):
    """The executor's decisions on a class of block, keyed by (position, kind, block index).

    A decision is not a reading: it names its rule, and it is bound to the
    block's text, so it applies to that text only.
    """
    if not Path(path).exists():
        return {}
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    table = {}
    for row in record["decisions"]:
        if row["rule"] not in record["rules"] or row["verdict"] not in VERDICTS.get(row["kind"], ()):
            raise SystemExit("D02_ADJUDICATION_INVALID:" + json.dumps(row)[:160])
        table[(row["position"], row["kind"], row["i"])] = row
    return table


def merge_answer(*, packet, answer, reader, adjudications=None):
    """A reader's answer made into the committed reading: every judged block's text beside it.

    The reader returns verdicts by block index; the packet holds the texts.
    The merged reading carries both, so it can be read on its own and its
    taken blocks render the value it was about. It must cover the packet
    exactly - the same check the acceptance run makes against the filing.
    """
    blocks = {}
    for kind, key in KINDS:
        for order, row in enumerate(packet.get(key, ())):
            blocks[(kind, row["i"])] = (order, row)
    judgements = []
    for row in answer["judgements"]:
        key = (row["kind"], row["i"])
        if key not in blocks:
            raise SystemExit("D02_ANSWER_JUDGES_A_BLOCK_NOT_IN_THE_PACKET:" + packet["position"]
                             + ":" + str(key))
        order, block = blocks[key]
        merged = {"kind": row["kind"], "i": row["i"], "verdict": row["verdict"],
                  "why": row.get("why", ""), "text": block["text"],
                  "text_sha256": block["text_sha256"]}
        decided = (adjudications or {}).get((packet["position"], row["kind"], row["i"]))
        if decided is not None:
            if decided["text_sha256"] != block["text_sha256"]:
                raise SystemExit("D02_ADJUDICATED_TEXT_CHANGED:" + packet["position"] + ":" + str(key))
            merged.update(verdict=decided["verdict"], why=decided["why"],
                          reader_verdict=row["verdict"], reader_why=row.get("why", ""),
                          adjudication_rule=decided["rule"])
        if row["kind"] == "TAKEN":
            merged["order"] = order
        if "scope" in block:
            merged["scope"] = block["scope"]
        if row.get("covered_by") and merged["verdict"] == "COVERED_ELSEWHERE":
            merged["covered_by"] = row["covered_by"]
        judgements.append(merged)
    rank = {kind: n for n, (kind, _) in enumerate(KINDS)}
    reading = {"record_type": "ISSUE_47_D02_READING", "position": packet["position"],
               "reader": reader, "reader_note": answer.get("reader_note", ""),
               "packet_document_id": packet["document_id"],
               "packet_candidate_hash": packet["candidate_hash"],
               "judgements": sorted(judgements, key=lambda row: (rank[row["kind"]], row["i"]))}
    read_position(packet=packet, reading=reading)
    return reading


def rendered_value_sha256(reading):
    """The digest of the value the reading's taken blocks render, in their order.

    A committed reading carries each taken block's text, so this needs no
    filing and no Run: it is the check that the judged excerpts are the value
    that was accepted, which the ORDERED_NEWLINE_V1 renderer joins by newline.
    """
    taken = sorted((row for row in reading["judgements"] if row["kind"] == "TAKEN"),
                   key=lambda row: row["order"])
    return "sha256:" + hashlib.sha256("\n".join(row["text"] for row in taken)
                                      .encode("utf-8")).hexdigest()


def accepted_position(*, index, closure, source_root, company_id, report_end, answer,
                      packet):
    """One position compared with its published result, and the identity it was read against."""
    from acceptance_readings import accession_of_document
    from bind_acceptance_readings import identity_for
    from vnext.historical_coverage import select_receipt
    selection = select_receipt(found=index.get((company_id, "D02", report_end), []),
                               closure=closure)
    if selection["result"] is None:
        raise SystemExit("NO_RESULT:" + company_id + ":" + report_end + ":"
                         + str(selection["ambiguity"]))
    result, receipt = selection["result"], selection["receipt"]
    run_dir = Path(receipt["_runs_root"]) / receipt["run_directory_name"]
    records = [json.loads(line) for line in
               (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    run_result = next(r for r in records if r.get("record_type") == "METRIC_RESULT"
                      and r.get("result_id") == result["result_id"])
    payload = run_result["text_payload"]
    published = [item["text"] for item in sorted(payload["items"], key=lambda i: i["order"])]
    references = {r["source_reference_id"]: r for r in records
                  if r.get("record_type") == "SOURCE_REFERENCE"}
    blobs = {r["raw_asset_id"]: r for r in records if r.get("record_type") == "RAW_BLOB"}
    # The judged document is the route's annual report; the Run must record
    # the same source reference and its bytes.
    reference = references.get(packet["source_reference_id"])
    if reference is None:
        raise SystemExit("D02_JUDGED_DOCUMENT_NOT_IN_THE_RUN:" + company_id + ":" + report_end)
    storage = blobs[reference["raw_asset_id"]]["storage_uri"]
    raw = (Path(source_root) / storage).read_bytes()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != reference["raw_asset_id"]:
        raise SystemExit("SAVED_DOCUMENT_BYTES_CHANGED:" + storage)
    accession, _ = accession_of_document(repo_root=Path(source_root), document=storage)
    position = {
        "company_id": company_id, "period_end": report_end, "document": storage,
        "accession": accession, "reading_verdict": answer["verdict"], "counts": answer["counts"],
        "result_candidate_hash_is_the_recomputed_one":
            payload["candidate_hash"] == packet["candidate_hash"],
        "published_excerpts_are_the_taken_blocks_in_order":
            published == [row["text"] for row in packet["taken"]],
        "published_excerpts": len(published),
        "taken_texts_render_the_published_value":
            "\n".join(row["text"] for row in packet["taken"]) == str(result["value"]),
        "value_sha256": "sha256:" + hashlib.sha256(str(result["value"]).encode("utf-8")).hexdigest()}
    position["verdict"] = ("MATCH" if answer["verdict"] == "READING_AGREES"
                           and position["result_candidate_hash_is_the_recomputed_one"]
                           and position["published_excerpts_are_the_taken_blocks_in_order"]
                           and position["taken_texts_render_the_published_value"]
                           else "DIFFERS")
    identity, refusal = identity_for(
        position={"company_id": company_id, "metric_id": "D02", "period_end": report_end,
                  "published": position["value_sha256"], "reading_filings": [accession],
                  "reading_window": None, "filings_are_the_whole_set": False},
        index=index, closure=closure)
    if refusal is not None:
        raise SystemExit("IDENTITY_NOT_RECORDED:" + company_id + ":" + report_end + ":" + refusal)
    identity["established_by"] = "RECORDED_AT_READING_TIME"
    position["checked_identity"] = identity
    return position


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--position", action="append", default=[])
    parser.add_argument("--packet", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--packet-file", type=Path)
    parser.add_argument("--answer", type=Path)
    parser.add_argument("--reader")
    parser.add_argument("--output")
    parser.add_argument("--source-root", type=Path, default=REPO)
    parser.add_argument("--runs-root", action="append", type=Path, default=[])
    parser.add_argument("--closure")
    parser.add_argument("--acceptance-output")
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve()
    if args.merge:
        if not (args.packet_file and args.answer and args.reader):
            raise SystemExit("A_MERGE_NAMES_ITS_PACKET_ANSWER_AND_READER")
        packet = json.loads(args.packet_file.read_text(encoding="utf-8"))
        answer = json.loads(args.answer.read_text(encoding="utf-8"))
        if answer.get("position") != packet["position"]:
            raise SystemExit("D02_ANSWER_IS_FOR_ANOTHER_POSITION")
        reading = merge_answer(packet=packet, answer=answer, reader=args.reader,
                               adjudications=load_adjudications())
        company_id, report_end = packet["position"].rsplit(":", 1)
        READING_DIR.mkdir(parents=True, exist_ok=True)
        target = READING_DIR / (company_id + "-" + report_end + ".json")
        target.write_text(json.dumps(reading, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(target.relative_to(REPO), read_position(packet=packet, reading=reading)["verdict"])
        return 0
    if args.packet:
        if len(args.position) != 1 or not args.output or args.runs_root:
            raise SystemExit("A_PACKET_IS_ONE_POSITION_WRITTEN_TO_ITS_OWN_FILE")
        company_id, report_end = args.position[0].rsplit(":", 1)
        document, proposal, candidate = route_selection(
            source_root=source_root, company_id=company_id, report_end=report_end)
        packet = {"record_type": "ISSUE_47_D02_READING_PACKET", "position": args.position[0],
                  "reader_tool": "tools/read_d02_excerpts.py",
                  **make_packet(document=document, proposal=proposal, candidate=candidate)}
        Path(args.output).write_text(json.dumps(packet, ensure_ascii=False, indent=1) + "\n",
                                     encoding="utf-8")
        print(args.position[0], {key: len(packet[key]) for key in ("taken", "skipped", "context", "outside", "headings")})
        return 0
    if bool(args.runs_root) != bool(args.closure) or bool(args.closure) != bool(args.acceptance_output):
        raise SystemExit("RUNS_ROOT_CLOSURE_AND_ACCEPTANCE_OUTPUT_GO_TOGETHER")
    index = None
    if args.runs_root:
        from vnext.historical_run_receipts import collect_run_receipts, index_receipts
        receipts = []
        for root in args.runs_root:
            for receipt in collect_run_receipts(runs_root=root)["receipts"]:
                receipts.append({**receipt, "_runs_root": str(root)})
        index = index_receipts(receipts=receipts)
    report, accepted = {}, {}
    for path in sorted(READING_DIR.glob("*.json")):
        reading = json.loads(path.read_text(encoding="utf-8"))
        if args.position and reading["position"] not in args.position:
            continue
        company_id, report_end = reading["position"].rsplit(":", 1)
        document, proposal, candidate = route_selection(
            source_root=source_root, company_id=company_id, report_end=report_end)
        packet = make_packet(document=document, proposal=proposal, candidate=candidate)
        answer = read_position(packet=packet, reading=reading)
        answer["document_id"] = packet["document_id"]
        answer["candidate_hash"] = packet["candidate_hash"]
        answer["reading_sha256"] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        answer["not_covered"] = NOT_COVERED
        report[reading["position"]] = answer
        if index is not None:
            label = company_id.split("_")[0] + "-" + report_end[:4]
            accepted[label] = {**accepted_position(
                index=index, closure=args.closure, source_root=source_root,
                company_id=company_id, report_end=report_end, answer=answer, packet=packet),
                "reading": str(path.relative_to(REPO)), "reading_sha256": answer["reading_sha256"]}
            print(label, accepted[label]["verdict"], flush=True)
    if args.acceptance_output:
        body = {"record_type": "ISSUE_47_D02_EXCERPTS_READ", "reader": "tools/read_d02_excerpts.py",
                "requirement_closure_hash": args.closure, "per_position": accepted,
                "not_covered": NOT_COVERED,
                "calls": {"provider": 0, "paid": 0, "sec": 0}}
        (REPO / args.acceptance_output).write_text(
            json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return 0 if all(row["verdict"] == "MATCH" for row in accepted.values()) else 1
    text = json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if all(value["verdict"] == "READING_AGREES" for value in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
