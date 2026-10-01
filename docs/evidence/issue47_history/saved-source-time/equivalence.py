"""The linear page-number footer test against the pattern it replaced, on every saved annual report of the frame.

Usage: python3 equivalence.py <source root> <plan.tsv> <out.json> <repaired route file> [<git revision>]

The route module as committed at <git revision> (default HEAD) is loaded beside
the repaired one, and for each frame period (one per plan line) both are given
the same pinned D02 input. Three comparisons, each over the whole filing:

- every block of the built document, as stored and with its whitespace
  joined the way the rule reads it: the old pattern's (stem, page) against
  ``_page_numbered``;
- the numbered-footer set over the whole document, old function against new;
- what the route makes of the filing: the D02 and D03 proposals, the checked
  ranges and the coverage, and the Item 8 review pool and its keyword part.

Each comparison is of the same document, so any difference is the rule's. The
time each module took to prepare the filing is recorded too. Zero calls.

Run it from a checkout whose source journal registered <source root>'s
acquisition checkpoint (the runtime clone that restored it). The output is
rewritten after every period, and a period already in it is not measured again;
a resumed run must name the same revision and repaired bytes.
"""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext.historical_text_input import prepare_historical_business_text_input  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

ROUTE = "scripts/vnext/historical_text_results.py"
REFERENCE = re.compile(r"^(?P<stem>.*?[A-Za-z].*?)[\s|\-–—]+(?P<page>\d{1,4})$")


def reference(text):
    found = REFERENCE.match(text)
    return None if found is None else (found["stem"], found["page"])


def loaded_route(source, label):
    spec = importlib.util.spec_from_loader("vnext._route_" + label, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "vnext"
    exec(compile(source, label, "exec"), module.__dict__)
    return module


def prepared_by(module, arguments):
    started = time.time()
    try:
        built = module.prepare_business_text_sources(metric_id="D02", **arguments)
    except Exception as error:  # the stop is the answer for that version
        return {"error": type(error).__name__ + ":" + str(error)[:240]}, None, time.time() - started
    seconds = time.time() - started
    reference_id = next(iter(built["proposals"]))
    proposal = built["proposals"][reference_id]
    document = built["documents"][reference_id]
    try:
        pool = module.item_8_review_pool(
            document=document, raw_bytes=arguments["raw_bytes_by_id"][document["raw_asset_id"]],
            proposal=proposal)
    except Exception as error:
        pool = type(error).__name__ + ":" + str(error)[:240]
    return {"proposal_sha256": hashlib.sha256(json.dumps(
                built["proposals"], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "d02": [c["block_index"] for c in proposal["D02"]["candidates"]],
            "d03": [c["block_index"] for c in proposal["D03"]["candidates"]],
            "ranges": [(r["section_id"], r["start_block"], r["end_block_exclusive"])
                       for r in proposal["checked_ranges"]],
            "coverage": proposal["coverage_status"], "reasons": proposal["coverage_reasons"],
            "item_8_pool": pool}, built, seconds


def blocks_compared(committed, repaired, built):
    found = {"documents": 0, "blocks": 0, "readings": 0, "numbered": 0, "differences": [],
             "footer_sets_equal": True, "footers": 0}
    for document in built["documents"].values():
        found["documents"] += 1
        blocks = document["blocks"]
        for index, block in enumerate(blocks):
            found["blocks"] += 1
            for text in {block["text"], " ".join(block["text"].split())}:
                found["readings"] += 1
                expected, answer = reference(text), repaired._page_numbered(text)
                found["numbered"] += expected is not None
                if expected != answer:
                    found["differences"].append({"block": index, "text": text[:200],
                                                 "old": expected, "new": answer})
        old = committed._numbered_page_footers(blocks=blocks, start=0, stop=len(blocks))
        new = repaired._numbered_page_footers(blocks=blocks, start=0, stop=len(blocks))
        found["footers"] += len(new)
        if old != new:
            found["footer_sets_equal"] = False
            found["differences"].append({"footer_sets": {"old": sorted(old), "new": sorted(new)}})
    return found


def main(root, plan_path, out_path, route_file, revision="HEAD"):
    root = Path(root).resolve()
    committed_source = subprocess.run(["git", "show", revision + ":" + ROUTE], cwd=REPO,
                                      check=True, capture_output=True).stdout
    repaired_source = Path(route_file).read_bytes()
    committed = loaded_route(committed_source.decode("utf-8"), "committed")
    repaired = loaded_route(repaired_source.decode("utf-8"), "repaired")
    out = {"revision": revision,
           "committed_route_sha256": hashlib.sha256(committed_source).hexdigest(),
           "repaired_route_sha256": hashlib.sha256(repaired_source).hexdigest(),
           "calls": {"provider": 0, "paid": 0, "sec": 0}, "periods": {}}
    if Path(out_path).exists():
        earlier = json.loads(Path(out_path).read_text(encoding="utf-8"))
        if any(earlier.get(key) != out[key] for key in
               ("revision", "committed_route_sha256", "repaired_route_sha256")):
            raise SystemExit("PAGE_NUMBERED_EQUIVALENCE_OUTPUT_IS_ANOTHER_MEASUREMENT:" + str(out_path))
        out["periods"] = earlier["periods"]
    periods = [line.rstrip("\n").split("\t") for line in open(plan_path) if line.strip()]
    with checkpoint_replayed_once():
        for label, company_id, report_end, *_ in periods:
            if label in out["periods"]:
                continue
            try:
                selection = resolve_period_selection(repo_root=root, company_id=company_id,
                                                     report_end=report_end)
                prepared = prepare_historical_business_text_input(
                    repo_root=root, company_id=company_id, metric_id="D02",
                    period_selection=selection)
            except Exception as error:
                out["periods"][label] = {"input_error": type(error).__name__ + ":" + str(error)[:240]}
                print(label, "INPUT_ERROR", str(error)[:120], flush=True)
                _write(out_path, out)
                continue
            arguments = prepared["text_arguments"]
            before, built_before, seconds_before = prepared_by(committed, arguments)
            after, built_after, seconds_after = prepared_by(repaired, arguments)
            row = {"route_equal": before == after,
                   "seconds": {"committed": round(seconds_before, 1),
                               "repaired": round(seconds_after, 1)}}
            if not row["route_equal"]:
                row["committed"], row["repaired"] = before, after
            if built_after is not None:
                row["blocks"] = blocks_compared(committed, repaired, built_after)
            out["periods"][label] = row
            print(label, "same" if row["route_equal"] else "ROUTE_DIFFERS",
                  row.get("blocks", {}).get("readings"),
                  len(row.get("blocks", {}).get("differences", [])),
                  row["seconds"], after.get("error", "")[:100], flush=True)
            _write(out_path, out)
    rows = [row for row in out["periods"].values() if "blocks" in row]
    out["summary"] = {
        "periods": len(out["periods"]),
        "periods_measured": len(rows),
        "input_errors": sum("input_error" in row for row in out["periods"].values()),
        "route_differences": sum(not row["route_equal"] for row in out["periods"].values()
                                 if "route_equal" in row),
        "block_readings": sum(row["blocks"]["readings"] for row in rows),
        "readings_ending_in_a_page_number": sum(row["blocks"]["numbered"] for row in rows),
        "reading_differences": sum(len(row["blocks"]["differences"]) for row in rows),
        "seconds_committed": round(sum(row["seconds"]["committed"] for row in rows), 1),
        "seconds_repaired": round(sum(row["seconds"]["repaired"] for row in rows), 1)}
    _write(out_path, out)


def _write(out_path, out):
    staged = Path(str(out_path) + ".partial")
    staged.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    staged.replace(out_path)


if __name__ == "__main__":
    main(*sys.argv[1:])
