"""Does each C02 value carry the three things the definition names?

The approved definition lists what C02 may output: the number of directors,
the number of independent directors and committee information. However widely
"committee information" is finally read, those three are inside it under every
option, so whether the current selection carries them does not wait for that
decision. This checks it at the ten committed positions.

``core-fact-judgements.json`` records, per position and per named output, the
selected excerpts that state it and a status; the committee pages the proxy
prints that the route did not select; and other composition statements it
missed. This tool re-derives the selection under the current code - through the
reading tool's ``route_selection`` - and the governance document's blocks -
through the frozen source preparation, the same bytes a Run reads - and refuses
a judgement that no longer describes them: an in-the-value block must be
selected, carry the recorded text and be judged a composition fact in
``excerpt-judgements.json``; a not-selected block must not be selected and must
carry the recorded text.

What it is not: a reading of every block. The not-selected statements were
found by searching the saved proxies with patterns and then reading the
committee pages those searches led to. It is a lower bound on what the
selection misses; the full missed-direction reading stays required once the
meaning is chosen.

Usage:
    python3 docs/evidence/issue47_history/c02-board-read/core_fact_reach.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

HERE = "docs/evidence/issue47_history/c02-board-read/"
JUDGEMENTS = HERE + "core-fact-judgements.json"
EXCERPTS = HERE + "excerpt-judgements.json"
OUTPUT = HERE + "core-fact-reach.json"
NAMED = ("board_size", "board_independence", "committee_information")


def governance_blocks(*, company_id, report_end):
    """The governance document's blocks - the source every C02 excerpt comes from."""
    from vnext import text_results_v2
    from vnext.historical_text_input import prepare_historical_business_text_input
    from vnext.normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                         report_end=report_end)
    prepared = prepare_historical_business_text_input(repo_root=REPO, company_id=company_id,
                                                      metric_id="C02",
                                                      period_selection=selection)
    sources = text_results_v2.prepare_business_text_sources(metric_id="C02",
                                                            **prepared["text_arguments"])
    # Only the governance source carries a proposal; the annual report is an
    # identity anchor with no excerpts (text_results_v2._derive_candidate).
    (governance_id,) = sources["proposals"]
    return sources["documents"][governance_id]["blocks"]


def check_position(*, judged, facts, selected, blocks):
    """Problems with this position's judgements against today's bytes; empty if none."""
    problems = []

    def text_holds(entry):
        return blocks[entry["block_index"]]["text"].startswith(entry["text_start"])

    for field in NAMED:
        for entry in judged[field]["in_the_value"]:
            index = entry["block_index"]
            if index not in selected:
                problems.append(field + ":NOT_SELECTED:" + str(index))
            elif not text_holds(entry):
                problems.append(field + ":TEXT_CHANGED:" + str(index))
            elif facts.get(index) != "COMPOSITION_FACT":
                problems.append(field + ":NOT_JUDGED_A_COMPOSITION_FACT:" + str(index))
    missed = [entry for page in judged["committee_pages_not_selected"] for entry in page["blocks"]]
    for entry in missed + judged["other_missed"]:
        index = entry["block_index"]
        if index in selected:
            problems.append("MISSED_BLOCK_IS_SELECTED:" + str(index))
        elif not text_holds(entry):
            problems.append("MISSED_BLOCK_TEXT_CHANGED:" + str(index))
    return problems


def main():
    from read_c02_board_statements import route_selection
    judgements = json.loads((REPO / JUDGEMENTS).read_text(encoding="utf-8"))["positions"]
    excerpts = json.loads((REPO / EXCERPTS).read_text(encoding="utf-8"))["positions"]
    if set(judgements) != set(excerpts):
        raise SystemExit("JUDGEMENTS_DO_NOT_COVER_THE_COMMITTED_POSITIONS")
    positions, statuses = {}, {field: Counter() for field in NAMED}
    for key in sorted(judgements):
        company_id, report_end = key.split(":")
        judged = judgements[key]
        selected = {row["block_index"] for row in route_selection(
            repo_root=REPO, company_id=company_id, report_end=report_end)}
        facts = {row["block_index"]: row["category"] for row in excerpts[key]}
        blocks = governance_blocks(company_id=company_id, report_end=report_end)
        problems = check_position(judged=judged, facts=facts, selected=selected, blocks=blocks)
        if problems:
            raise SystemExit("JUDGEMENTS_DO_NOT_DESCRIBE_THE_SELECTION:" + key + ":"
                             + ",".join(problems))
        for field in NAMED:
            statuses[field][judged[field]["status"]] += 1
        positions[key] = {
            **{field: {"status": judged[field]["status"], "states": judged[field]["states"],
                       "in_the_value": [e["block_index"] for e in judged[field]["in_the_value"]]}
               for field in NAMED},
            "committee_pages_not_selected": {
                page["committee"]: [e["block_index"] for e in page["blocks"]]
                for page in judged["committee_pages_not_selected"]},
            "other_missed_composition_statements": [
                {key_: e[key_] for key_ in ("block_index", "kind", "states")}
                for e in judged["other_missed"]]}
        print(key, {field: judged[field]["status"] for field in NAMED}, flush=True)
    body = {
        "record_type": "ISSUE_47_C02_CORE_FACT_REACH",
        "question": ("Under every meaning option the value must carry the number of directors, "
                     "the number of independent directors and committee information. Does the "
                     "current selection carry them at the ten committed positions?"),
        "statuses": {field: dict(sorted(counter.items())) for field, counter in statuses.items()},
        "positions": positions,
        "judged_against": ["the route's selection re-derived under the current code",
                           "the governance document's blocks from the saved bytes",
                           EXCERPTS],
        "not_a_full_reading": ("the not-selected statements were found by searching the saved "
                               "proxies with patterns and reading the committee pages the "
                               "searches led to; this is a lower bound on what the selection "
                               "misses, and the full missed-direction reading stays required "
                               "once the meaning is chosen"),
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (REPO / OUTPUT).write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(body["statuses"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
