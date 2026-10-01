"""Check C02's composition-fact selection against a two-direction reading.

The reading is kept as data: for each position, what a reader judged every
selected block to be, and every block outside the selection that the reader
found states a composition fact. This tool recomputes today's selection from
the saved governance filing through the route's own input and candidate
builders, then answers two questions per position:

* wrongly taken - a selected block the reading says states no composition fact;
* missed - a block the reading says states a composition fact, not selected,
  whose facts are not all stated by selected blocks it names.

Every judged block is bound to its text by SHA-256, so a reading cannot be
applied to a block whose text it did not see. The reading also lists its pool:
every block its reader was given and read. The reader's instructions say a
pool block judged not to state a composition fact is simply left out of the
facts, so a selected block that is in the pool, with the same text, and not
among the reader's facts, is reported as wrongly taken on that reading. A
selected block no reader was given is reported as unread, never assumed to be
right.

Two further inputs refine a reading and are reported as such:

* ``supplementary`` rows in the reading - a later independent reader's
  judgements of blocks a changed selection takes that the first reader was not
  asked about (or left silent). They are judged like selected blocks.
* the adjudication file - the executor's decision where readers disagree on a
  class of block (``c02-composition-facts/adjudicate.py`` lists the classes).
  Each entry names its rule and reason and is bound to the block's text. A NOT
  decision makes a selected block wrongly taken; a FACT decision makes a block
  the reading did not take (or never read) missed unless it, or a block the
  decision names as stating the same fact, is selected. The answer lists every
  position whose agreement rests on one.

Against published results, the same reading becomes an acceptance reading.
With ``--runs-root`` and ``--closure`` each judged position's result is taken
from the named Runs, and the position is a match only when the reading agrees
with today's selection and the result is that selection: the Run's candidate
hash is the one recomputed here, and its excerpts are the selected blocks'
texts in the selected order. The value is named by digest, because it is the
whole text payload, and the identity of the result it was read against is
recorded at reading time.

Older years are read the same way from a packet this tool builds
(``--packet``): every selected block and a pool of the blocks around them, in
document order, for a reader given ``c02-older-years/reader-brief.md``. The
pool is the blocks that use the owner's words for composition facts, and
every short block within ``POOL_REACH`` of one; the rule was chosen because, with the
selection, it holds every fact block the latest-year readers found
(``c02-older-years/pool_rule.py``, ``pool-rule.json``). A reader's answer is
merged into a reading (``--merge``) only if it judges every selected block and
lists only pool blocks as found facts; it is written to ``OLDER_READING_DIR``,
apart from the latest years' readings, and compared with ``--readings-dir``
naming that directory. Older years' filings are read from an export-restored
root (``--source-root``, restored by this checkout).

Usage:
    python3 tools/read_c02_composition.py [--position <company>:<report_end>] [--output PATH]
    python3 tools/read_c02_composition.py --packet --position <company>:<report_end> \
        [--source-root <root>] --output <packet.json>
    python3 tools/read_c02_composition.py --merge --packet-file <packet.json> \
        --answer <answer.json> --reader "<who read it>"
    python3 tools/read_c02_composition.py --runs-root <root> [--runs-root <root>] \
        [--source-root <root>] [--readings-dir <dir>] [--position <company>:<report_end> ...] \
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

READING_DIR = REPO / "docs/evidence/issue47_history/c02-composition-facts/judgements"
# Older years are the first material the selection rules were not written on,
# so their readings are kept apart from the latest years' (which the rules were
# fitted on and whose cases assert agreement on all ten).
OLDER_READING_DIR = REPO / "docs/evidence/issue47_history/c02-older-years/judgements"
ADJUDICATION_PATH = REPO / "docs/evidence/issue47_history/c02-composition-facts/adjudication.json"
VERDICTS_TAKEN = {"FACT", "MIXED", "NOT"}
VERDICTS_FOUND = {"FACT", "MIXED"}
# The owner's decision in the words a proxy uses for it (c02-older-years/pool_rule.py).
POOL_VOCABULARY = re.compile(
    r"\b(?:directors?|board|committees?|independen(?:t|ce)|chair(?:man|woman|person|s)?|vice[- ]chair"
    r"|lead(?:ing)?\s+director|presiding\s+director|members?(?:hip)?|nominees?|nominat(?:ed|ing|ion))\b",
    re.I)
# Every block using those words, and every short block (a name, a committee's name
# in a card or matrix, a card label) within POOL_REACH blocks of one. Measured on the
# latest-year readings, this pool with the selection holds every fact block their
# readers found (c02-older-years/pool-rule.json).
POOL_REACH = 16
POOL_SHORT = 80
_LETTER = re.compile(r"[A-Za-z]")


def text_sha256(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def route_selection(*, repo_root: Path, company_id: str, report_end: str, source_root=None, with_period=False):
    """The governance document and the C02 excerpts the historical route selects.

    ``source_root`` is where the filings' saved bytes are - this checkout, or
    for an older year a root restored from the acquisition's export by this
    checkout (its trust journal knows it); the Spec is this checkout's.
    ``with_period`` adds the target year's first day, which the selector
    needs to call it directly on the returned document.
    """
    from vnext.historical_results import TEXT_SPEC_PATHS
    from vnext.historical_spec_revision import compile_historical_spec_file
    from vnext.historical_text_input import prepare_historical_business_text_input
    from vnext.historical_text_results import prepare_business_text_sources, text_api
    from vnext.normal_history_plan import checkpoint_replayed_once
    from vnext.normal_period_selection import resolve_period_selection
    source_root = repo_root if source_root is None else source_root
    with checkpoint_replayed_once():
        selection = resolve_period_selection(repo_root=source_root, company_id=company_id,
                                             report_end=report_end)
        prepared = prepare_historical_business_text_input(
            repo_root=source_root, company_id=company_id, metric_id="C02",
            period_selection=selection)
        spec = compile_historical_spec_file(repo_root=repo_root,
                                            repo_relative_path=TEXT_SPEC_PATHS["C02"],
                                            dependency_specs={})
        api, _ = text_api("C02")
        candidate = api.create_deterministic_text_candidate(compiled_spec=spec,
                                                            **prepared["text_arguments"])
        built = prepare_business_text_sources(metric_id="C02", **prepared["text_arguments"])
    governance = [sid for sid in built["proposals"]]
    if len(governance) != 1:
        raise SystemExit("C02_READING_EXPECTS_ONE_GOVERNANCE_DOCUMENT")
    document = built["documents"][governance[0]]
    chosen = sorted((claim["block_index"] for claim in candidate["selected"].values()))
    if with_period:
        return document, chosen, candidate, prepared["text_arguments"]["target"]["period_start"]
    return document, chosen, candidate


def pool_blocks(blocks):
    """Every block that uses the owner's words for composition facts, and every short block near one."""
    matched = [index for index, block in enumerate(blocks) if POOL_VOCABULARY.search(block["text"])]
    pool = set(matched)
    for index in matched:
        for near in range(max(0, index - POOL_REACH), min(len(blocks), index + POOL_REACH + 1)):
            text = blocks[near]["text"].strip()
            if len(text) <= POOL_SHORT and _LETTER.search(text):
                pool.add(near)
    return pool


def make_packet(*, document, chosen, candidate):
    """The blocks a reader judges: the selection and the pool, in document order."""
    blocks = document["blocks"]
    selected = set(chosen)
    pool = pool_blocks(blocks) - selected
    stream = [{"i": index, "kind": "SELECTED" if index in selected else "POOL",
               "text": blocks[index]["text"], "text_sha256": text_sha256(blocks[index]["text"])}
              for index in sorted(selected | pool)]
    return {"document_id": document["text_document_id"], "candidate_hash": candidate["candidate_hash"],
            "pool_rule": {"vocabulary": POOL_VOCABULARY.pattern, "reach": POOL_REACH,
                          "short_block_characters": POOL_SHORT},
            "selected_count": len(selected), "pool_count": len(pool), "blocks": stream}


def merge_answer(*, packet, answer, reader):
    """A reader's answer made into a reading in the latest-year readings' shape.

    Every selected block must be judged once, and only pool blocks can be found
    facts: a reading that did not see a block is never read as agreeing with
    it, and a verdict on a block the packet does not hold has nothing to bind to.
    """
    blocks = {row["i"]: row for row in packet["blocks"]}
    selected = [row for row in packet["blocks"] if row["kind"] == "SELECTED"]
    judged = {}
    for row in answer["selected"]:
        block = blocks.get(row["i"])
        if block is None or block["kind"] != "SELECTED":
            raise SystemExit("C02_ANSWER_JUDGES_A_BLOCK_NOT_SELECTED:" + packet["position"] + ":" + str(row["i"]))
        if row["i"] in judged:
            raise SystemExit("C02_ANSWER_JUDGES_A_BLOCK_TWICE:" + packet["position"] + ":" + str(row["i"]))
        if row["verdict"] not in VERDICTS_TAKEN or not row.get("why"):
            raise SystemExit("C02_ANSWER_VERDICT_INVALID:" + packet["position"] + ":" + str(row["i"]))
        judged[row["i"]] = {"i": row["i"], "verdict": row["verdict"], "why": row["why"],
                            "text_sha256": block["text_sha256"]}
    missing = [row["i"] for row in selected if row["i"] not in judged]
    if missing:
        raise SystemExit("C02_ANSWER_LEAVES_SELECTED_BLOCKS_UNJUDGED:" + packet["position"] + ":" + str(missing))
    facts = {}
    for row in answer["facts"]:
        block = blocks.get(row["i"])
        if block is None or block["kind"] != "POOL":
            raise SystemExit("C02_ANSWER_FACT_IS_NOT_A_POOL_BLOCK:" + packet["position"] + ":" + str(row["i"]))
        if row["i"] in facts:
            raise SystemExit("C02_ANSWER_LISTS_A_FACT_TWICE:" + packet["position"] + ":" + str(row["i"]))
        if row["verdict"] not in VERDICTS_FOUND or not row.get("why"):
            raise SystemExit("C02_ANSWER_VERDICT_INVALID:" + packet["position"] + ":" + str(row["i"]))
        cover = row.get("redundant_with", [])
        if any(other not in blocks or other == row["i"] for other in cover):
            raise SystemExit("C02_ANSWER_CITES_A_BLOCK_NOT_IN_THE_PACKET:" + packet["position"] + ":" + str(row["i"]))
        facts[row["i"]] = {"i": row["i"], "verdict": row["verdict"], "why": row["why"],
                           "text_sha256": block["text_sha256"], "redundant_with": sorted(set(cover))}
    pool = [{"i": row["i"], "text_sha256": row["text_sha256"]} for row in packet["blocks"]
            if row["kind"] == "POOL"]
    return {"position": packet["position"], "reader": reader,
            "read_as": ("independent subagent reading: a fresh agent given c02-older-years/reader-brief.md "
                        "and the packet, not the selector's rules or any earlier reading"),
            "reader_note": answer.get("reader_note", ""),
            "packet_document_id": packet["document_id"], "packet_candidate_hash": packet["candidate_hash"],
            "packet_pool_rule": packet["pool_rule"],
            "packet_selection": len(selected), "packet_pool_size": len(pool), "pool_blocks_read": len(pool),
            "selected": [judged[i] for i in sorted(judged)],
            "pool_facts": [facts[i] for i in sorted(facts)], "outside_pool_facts": [], "pool": pool}


def load_adjudications(path=ADJUDICATION_PATH):
    """The executor's class decisions, keyed by (position, block index)."""
    if not Path(path).exists():
        return {}
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    table = {}
    for row in record["decisions"]:
        if row["decision"] not in ("FACT", "NOT") or row["rule"] not in record["rules"]:
            raise SystemExit("C02_ADJUDICATION_INVALID:" + json.dumps(row)[:120])
        table[(row["position"], row["i"])] = row
    return table


def read_position(*, document, chosen, reading, adjudications=None):
    """Compare one position's reading with today's selection."""
    blocks = document["blocks"]
    adjudicated = {i: row for (position, i), row in (adjudications or {}).items()
                   if position == reading["position"]}
    taken = {row["i"]: row for row in [*reading["selected"], *reading.get("supplementary", [])]}
    found = {row["i"]: row for row in [*reading["pool_facts"], *reading.get("outside_pool_facts", [])]}
    pool = {row["i"]: row["text_sha256"] for row in reading.get("pool", [])}
    problems = {"unread": [], "text_changed": [], "wrongly_taken": [], "missed": [],
                "verdict_invalid": []}
    partly, used = [], set()

    def adjudication(index):
        row = adjudicated.get(index)
        if row is None:
            return None
        if row["text_sha256"] != text_sha256(blocks[index]["text"]):
            problems["text_changed"].append(index)
            return None
        used.add(index)
        return row

    for index in chosen:
        decided = adjudication(index)
        if decided is not None:
            if decided["decision"] == "NOT":
                problems["wrongly_taken"].append({"i": index, "why": "adjudicated: " + decided["rule"]})
            continue
        row = taken.get(index) or found.get(index)
        if row is None:
            if pool.get(index) == text_sha256(blocks[index]["text"]):
                problems["wrongly_taken"].append({"i": index, "why": "read in the pool and left out of the facts"})
            else:
                problems["unread"].append(index)
            continue
        if row["text_sha256"] != text_sha256(blocks[index]["text"]):
            problems["text_changed"].append(index)
        elif row["verdict"] not in VERDICTS_TAKEN:
            problems["verdict_invalid"].append(index)
        elif row["verdict"] == "NOT":
            problems["wrongly_taken"].append({"i": index, "why": row.get("why", "")})
    selected = set(chosen)
    # A block the reading judged a fact while it was selected is a found fact
    # too: if a later selection drops it, the fact has to be stated by a block
    # still selected, and the reading gave no such block for it.
    judged_facts = {**{i: {**row, "redundant_with": []} for i, row in taken.items()
                       if row["verdict"] in VERDICTS_FOUND}, **found}
    for index, row in sorted(judged_facts.items()):
        if row["text_sha256"] != text_sha256(blocks[index]["text"]):
            problems["text_changed"].append(index)
            continue
        if row["verdict"] not in VERDICTS_FOUND:
            problems["verdict_invalid"].append(index)
            continue
        if index in selected:
            continue
        decided = adjudication(index)
        if decided is not None and decided["decision"] == "NOT":
            continue
        cover = row.get("redundant_with") or []
        cover_selected = [other for other in cover if other in selected]
        # The reader cites every block that states the same facts, often as
        # alternatives to one another, so one selected citation is taken to
        # carry them; the partly covered are listed so they can be looked at.
        if not cover_selected:
            problems["missed"].append({"i": index, "why": row.get("why", ""),
                                       "redundant_with": cover})
        elif len(cover_selected) < len(cover):
            partly.append({"i": index, "cover_selected": cover_selected,
                           "cover_not_selected": [o for o in cover if o not in selected]})
    # A block the adjudication decides is a fact where the reading did not take
    # it as one (or never read it) is missed too, unless it is selected or a
    # block the decision names as stating the same fact is.
    for index, row in sorted(adjudicated.items()):
        if row["decision"] != "FACT" or index in selected or index in judged_facts:
            continue
        if adjudication(index) is None:
            continue
        cover = row.get("redundant_with") or []
        if not any(other in selected for other in cover):
            problems["missed"].append({"i": index, "why": "adjudicated: " + row["rule"], "redundant_with": cover})
    verdict_of = lambda i: (taken.get(i) or found.get(i) or {}).get("verdict")
    counts = {"selected": len(chosen),
              "selected_fact": sum(1 for i in chosen if verdict_of(i) == "FACT"),
              "selected_mixed": sum(1 for i in chosen if verdict_of(i) == "MIXED"),
              "found_outside_the_selection": sum(1 for i in found if i not in selected),
              "resting_on_adjudication": len(used)}
    clean = not any(problems.values())
    return {"verdict": "READING_AGREES" if clean else "READING_DISAGREES", "counts": counts,
            "problems": problems, "covered_by_some_citations_only": partly,
            "adjudicated_blocks": sorted(used)}


def governance_accession(*, run_dir: Path, document, source_root=REPO):
    """The filing the judged governance document was read from, from the Run's own records."""
    sys.path.insert(0, str(REPO / "tools"))
    from acceptance_readings import accession_of_document
    records = [json.loads(line) for line in
               (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    references = {r["source_reference_id"]: r for r in records
                  if r.get("record_type") == "SOURCE_REFERENCE"}
    blobs = {r["raw_asset_id"]: r for r in records if r.get("record_type") == "RAW_BLOB"}
    reference = references.get(document["source_reference_id"])
    if reference is None:
        raise SystemExit("C02_GOVERNANCE_DOCUMENT_NOT_IN_THE_RUN:" + str(run_dir))
    storage = blobs[reference["raw_asset_id"]]["storage_uri"]
    raw = (Path(source_root) / storage).read_bytes()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != reference["raw_asset_id"]:
        raise SystemExit("SAVED_DOCUMENT_BYTES_CHANGED:" + storage)
    return accession_of_document(repo_root=Path(source_root), document=storage)[0], storage


def accepted_position(*, index, closure, company_id, report_end, answer, document, chosen,
                      candidate, source_root=REPO):
    """One position compared with its published result, and the identity it was read against."""
    sys.path.insert(0, str(REPO / "tools"))
    from bind_acceptance_readings import identity_for
    from vnext.historical_coverage import select_receipt
    selection = select_receipt(found=index.get((company_id, "C02", report_end), []),
                               closure=closure)
    if selection["result"] is None:
        raise SystemExit("NO_RESULT:" + company_id + ":" + report_end + ":"
                         + str(selection["ambiguity"]))
    result, receipt = selection["result"], selection["receipt"]
    run_dir = Path(receipt["_runs_root"]) / receipt["run_directory_name"]
    run_result = next(json.loads(line) for line in
                      (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
                      if line.strip() and json.loads(line).get("record_type") == "METRIC_RESULT"
                      and json.loads(line).get("result_id") == result["result_id"])
    payload = run_result["text_payload"]
    published = [item["text"] for item in sorted(payload["items"], key=lambda i: i["order"])]
    selected = [document["blocks"][block]["text"] for block in chosen]
    accession, storage = governance_accession(run_dir=run_dir, document=document,
                                              source_root=source_root)
    position = {
        "company_id": company_id, "period_end": report_end,
        "governance_accession": accession, "governance_document": storage,
        "reading_verdict": answer["verdict"], "counts": answer["counts"],
        "adjudicated_blocks": answer["adjudicated_blocks"],
        "result_candidate_hash_is_the_recomputed_one":
            payload["candidate_hash"] == candidate["candidate_hash"],
        "published_excerpts_are_the_selected_blocks_in_order": published == selected,
        "published_excerpts": len(published),
        "value_sha256": "sha256:" + hashlib.sha256(str(result["value"]).encode("utf-8")).hexdigest()}
    position["verdict"] = ("MATCH" if answer["verdict"] == "READING_AGREES"
                           and position["result_candidate_hash_is_the_recomputed_one"]
                           and position["published_excerpts_are_the_selected_blocks_in_order"]
                           else "DIFFERS")
    identity, refusal = identity_for(
        position={"company_id": company_id, "metric_id": "C02", "period_end": report_end,
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
    parser.add_argument("--output")
    parser.add_argument("--packet", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--packet-file", type=Path)
    parser.add_argument("--answer", type=Path)
    parser.add_argument("--reader")
    parser.add_argument("--source-root", type=Path, default=REPO)
    parser.add_argument("--runs-root", action="append", type=Path, default=[])
    parser.add_argument("--closure")
    parser.add_argument("--acceptance-output")
    parser.add_argument("--readings-dir", type=Path, default=READING_DIR)
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve()
    if args.merge:
        if not (args.packet_file and args.answer and args.reader):
            raise SystemExit("A_MERGE_NAMES_ITS_PACKET_ANSWER_AND_READER")
        packet = json.loads(args.packet_file.read_text(encoding="utf-8"))
        answer = json.loads(args.answer.read_text(encoding="utf-8"))
        if answer.get("position") != packet["position"]:
            raise SystemExit("C02_ANSWER_IS_FOR_ANOTHER_POSITION")
        reading = merge_answer(packet=packet, answer=answer, reader=args.reader)
        company_id, report_end = packet["position"].rsplit(":", 1)
        target = OLDER_READING_DIR / (company_id + "-" + report_end + ".json")
        if target.exists():
            raise SystemExit("C02_READING_EXISTS:" + str(target.relative_to(REPO)))
        target.write_text(json.dumps(reading, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(target.relative_to(REPO), len(reading["selected"]), len(reading["pool_facts"]))
        return 0
    if args.packet:
        if len(args.position) != 1 or not args.output or args.runs_root:
            raise SystemExit("A_PACKET_IS_ONE_POSITION_WRITTEN_TO_ITS_OWN_FILE")
        company_id, report_end = args.position[0].rsplit(":", 1)
        document, chosen, candidate = route_selection(repo_root=REPO, company_id=company_id,
                                                      report_end=report_end, source_root=source_root)
        packet = {"record_type": "ISSUE_47_C02_READING_PACKET", "position": args.position[0],
                  "reader_tool": "tools/read_c02_composition.py",
                  **make_packet(document=document, chosen=chosen, candidate=candidate)}
        Path(args.output).write_text(json.dumps(packet, ensure_ascii=False, indent=1) + "\n",
                                     encoding="utf-8")
        print(args.position[0], {"selected": packet["selected_count"], "pool": packet["pool_count"]})
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
    accepted = {}
    readings = sorted((REPO / args.readings_dir).glob("*.json"))
    if not readings:
        raise SystemExit("C02_NO_READINGS_IN:" + str(args.readings_dir))
    adjudications = load_adjudications()
    report = {}
    # One replay of a restored root's acquisition checkpoint for the whole loop.
    # route_selection opens its own block, and a block inside another keeps the
    # outer memo; without this every position replayed the whole ledger again
    # (about ten minutes each on the final acquisition's root).
    from vnext.normal_history_plan import checkpoint_replayed_once
    with checkpoint_replayed_once():
        for path in readings:
            reading = json.loads(path.read_text(encoding="utf-8"))
            company_id, report_end = reading["position"].rsplit(":", 1)
            if args.position and reading["position"] not in args.position:
                continue
            document, chosen, candidate = route_selection(repo_root=REPO, company_id=company_id,
                                                          report_end=report_end, source_root=source_root)
            answer = read_position(document=document, chosen=chosen, reading=reading, adjudications=adjudications)
            answer["document_id"] = document["text_document_id"]
            answer["candidate_hash"] = candidate["candidate_hash"]
            answer["reading_sha256"] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            report[reading["position"]] = answer
            if index is not None:
                label = company_id.split("_")[0] + "-" + report_end[:4]
                accepted[label] = {**accepted_position(
                    index=index, closure=args.closure, company_id=company_id, report_end=report_end,
                    answer=answer, document=document, chosen=chosen, candidate=candidate,
                    source_root=source_root),
                    "reading": str(path.relative_to(REPO)), "reading_sha256": answer["reading_sha256"]}
                print(label, accepted[label]["verdict"], flush=True)
    text = json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    if args.acceptance_output:
        body = {"record_type": "ISSUE_47_C02_COMPOSITION_READ", "reader": "tools/read_c02_composition.py",
                "requirement_closure_hash": args.closure,
                "adjudication": str(ADJUDICATION_PATH.relative_to(REPO)),
                "adjudication_sha256": "sha256:" + hashlib.sha256(
                    ADJUDICATION_PATH.read_bytes()).hexdigest(),
                "per_position": accepted, "calls": {"provider": 0, "paid": 0, "sec": 0}}
        (REPO / args.acceptance_output).write_text(
            json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return 0 if all(row["verdict"] == "MATCH" for row in accepted.values()) else 1
    sys.stdout.write(text)
    return 0 if all(value["verdict"] == "READING_AGREES" for value in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
