"""Hold the C02 excerpt judgements to what the route selects from the saved proxies.

C02's value is the set of proxy excerpts the frozen selector
(``text_business_candidates.board_composition_candidates``) admits as board
composition. The judgements in
``docs/evidence/issue47_history/c02-board-read/excerpt-judgements.json`` were
made excerpt by excerpt against the approved definition. This tool re-derives
each position's selection from the saved filings under the current code -
through the route's own text input and candidate builder, so it reads exactly
what a Run would - and requires the judged excerpts to be that selection, block
for block and text for text. A judgement file that no longer describes the
selection is refused rather than reported on.

Verdict per position: MATCH only if every excerpt is a composition fact;
DIFFERS if any is outside board composition under every reading (the two
middle categories depend on how broadly "committee information" is read and do
not decide it). The other direction - statements the selector missed - is not
read, and the output says so.

Usage:
    python3 tools/read_c02_board_statements.py [--output <json>]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

JUDGEMENTS = "docs/evidence/issue47_history/c02-board-read/excerpt-judgements.json"
OUTPUT = "docs/evidence/issue47_history/c02-board-read/c02-board-read.json"
OUTSIDE = "NOT_BOARD_COMPOSITION"
FACT = "COMPOSITION_FACT"


def route_selection(*, repo_root: Path, company_id: str, report_end: str):
    """The C02 excerpts the route selects for the pinned period, in order."""
    from vnext.historical_results import TEXT_SPEC_PATHS
    from vnext.historical_spec_revision import compile_historical_spec_file
    from vnext.historical_text_input import prepare_historical_business_text_input
    from vnext.historical_text_results import text_api
    from vnext.normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=repo_root, company_id=company_id,
                                         report_end=report_end)
    prepared = prepare_historical_business_text_input(repo_root=repo_root,
                                                      company_id=company_id, metric_id="C02",
                                                      period_selection=selection)
    spec = compile_historical_spec_file(repo_root=repo_root,
                                        repo_relative_path=TEXT_SPEC_PATHS["C02"],
                                        dependency_specs={})
    api, _ = text_api("C02")
    candidate = api.create_deterministic_text_candidate(compiled_spec=spec,
                                                        **prepared["text_arguments"])
    return [{"block_index": claim["block_index"], "text": claim["text"]}
            for claim in sorted(candidate["selected"].values(), key=lambda c: c["order"])]


def read_position(*, judged, selected):
    """Compare one position's judgements with the route's selection."""
    if [row["block_index"] for row in judged] != [row["block_index"] for row in selected]:
        return {"verdict": "JUDGEMENTS_DO_NOT_DESCRIBE_THE_SELECTION",
                "judged_blocks": [row["block_index"] for row in judged],
                "selected_blocks": [row["block_index"] for row in selected]}
    stale = [row["block_index"] for row, now in zip(judged, selected)
             if not now["text"].startswith(row["text_start"])]
    if stale:
        return {"verdict": "JUDGEMENTS_DO_NOT_DESCRIBE_THE_SELECTION", "text_changed": stale}
    counts = Counter(row["category"] for row in judged)
    outside = [{"block_index": row["block_index"], "reason": row["reason"]}
               for row in judged if row["category"] == OUTSIDE]
    return {"verdict": ("DIFFERS" if outside else
                        "MATCH" if set(counts) == {FACT} else "DEPENDS_ON_THE_DEFINITION"),
            "excerpts": len(judged), "categories": dict(sorted(counts.items())),
            "outside_board_composition": outside,
            "missed_direction": "NOT_READ"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=OUTPUT)
    arguments = parser.parse_args()
    judgements = json.loads((REPO / JUDGEMENTS).read_text(encoding="utf-8"))
    positions = {}
    for key, judged in sorted(judgements["positions"].items()):
        company_id, report_end = key.split(":")
        positions[key] = read_position(
            judged=judged, selected=route_selection(repo_root=REPO, company_id=company_id,
                                                    report_end=report_end))
        print(key, positions[key]["verdict"], positions[key].get("categories"), flush=True)
    totals = Counter()
    for row in positions.values():
        totals.update(row.get("categories", {}))
    body = {"record_type": "ISSUE_47_C02_BOARD_STATEMENT_READING",
            "reader": "tools/read_c02_board_statements.py", "judgements": JUDGEMENTS,
            "selection_derived_from": "the saved proxies and annual reports, through the route's "
                                      "own text input and candidate builder under the current code",
            "positions": positions, "category_totals": dict(sorted(totals.items())),
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (REPO / arguments.output).write_text(
        json.dumps(body, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    refused = [k for k, v in positions.items()
               if v["verdict"] == "JUDGEMENTS_DO_NOT_DESCRIBE_THE_SELECTION"]
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
