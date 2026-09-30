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
  class of block (card tenure fields, card subject names). Each entry names
  its rule and reason and is bound to the block's text; the answer lists every
  position whose agreement rests on one.

Against published results, the same reading becomes an acceptance reading.
With ``--runs-root`` and ``--closure`` each judged position's result is taken
from the named Runs, and the position is a match only when the reading agrees
with today's selection and the result is that selection: the Run's candidate
hash is the one recomputed here, and its excerpts are the selected blocks'
texts in the selected order. The value is named by digest, because it is the
whole text payload, and the identity of the result it was read against is
recorded at reading time.

Usage:
    python3 tools/read_c02_composition.py [--position <company>:<report_end>] [--output PATH]
    python3 tools/read_c02_composition.py --runs-root <root> [--runs-root <root>] \
        --closure sha256:<closure> --acceptance-output <path>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

READING_DIR = REPO / "docs/evidence/issue47_history/c02-composition-facts/judgements"
ADJUDICATION_PATH = REPO / "docs/evidence/issue47_history/c02-composition-facts/adjudication.json"
VERDICTS_TAKEN = {"FACT", "MIXED", "NOT"}
VERDICTS_FOUND = {"FACT", "MIXED"}


def text_sha256(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def route_selection(*, repo_root: Path, company_id: str, report_end: str, source_root=None):
    """The governance document and the C02 excerpts the historical route selects.

    ``source_root`` is where the filings' saved bytes are - this checkout, or
    for an older year a root restored from the acquisition's export by this
    checkout (its trust journal knows it); the Spec is this checkout's.
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
    return document, chosen, candidate


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
    parser.add_argument("--runs-root", action="append", type=Path, default=[])
    parser.add_argument("--closure")
    parser.add_argument("--acceptance-output")
    args = parser.parse_args(argv)
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
    readings = sorted(READING_DIR.glob("*.json"))
    adjudications = load_adjudications()
    report = {}
    for path in readings:
        reading = json.loads(path.read_text(encoding="utf-8"))
        company_id, report_end = reading["position"].rsplit(":", 1)
        if args.position and reading["position"] not in args.position:
            continue
        document, chosen, candidate = route_selection(repo_root=REPO, company_id=company_id,
                                                      report_end=report_end)
        answer = read_position(document=document, chosen=chosen, reading=reading, adjudications=adjudications)
        answer["document_id"] = document["text_document_id"]
        answer["candidate_hash"] = candidate["candidate_hash"]
        answer["reading_sha256"] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        report[reading["position"]] = answer
        if index is not None:
            label = company_id.split("_")[0] + "-" + report_end[:4]
            accepted[label] = {**accepted_position(
                index=index, closure=args.closure, company_id=company_id, report_end=report_end,
                answer=answer, document=document, chosen=chosen, candidate=candidate),
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
