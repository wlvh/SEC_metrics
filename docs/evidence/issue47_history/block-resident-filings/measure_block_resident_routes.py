"""Does moving a filing's row into a history block change any pinned route's answer?

It must not: where SEC lists a filing is bookkeeping, and every answer is about
the filing. Six of the frame's fifty target periods have their 10-K row only in
a history block, and none has a saved original, so this builds the situation
from Marriott's saved material (``tests/vnext/historical_block_fixture.py``):
every ``recent`` row filed on or before 2024-06-30 moves into a new block.
That gives the three cases on real filings - FY2025 whose rows are all still in
``recent``, FY2024 whose prior-year 10-K row moved, FY2023 whose own 10-K row
moved - and each period is answered on this repository's root and on the
re-partitioned one, family by family, zero calls.

Usage (from the repository root; ``work`` outside the tree, reused if built):
    python3 docs/evidence/issue47_history/block-resident-filings/measure_block_resident_routes.py \
        <work> <label> [<report_end> ...]
"""
import json
import socket
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
COMPANY, CIK = "marriott_international", 1048286
CUTOFF, BLOCK = "2024-06-30", "CIK0001048286-submissions-003.json"
PERIODS = ("2023-12-31", "2024-12-31", "2025-12-31")
# One resolve answers the whole family, so it is asked once rather than once
# per metric; every other metric is asked through the Run's own preparation.
FAMILIES = {"companyfacts": ("A05", "A06", "A07", "A08", "A10", "B02", "B04", "B05",
                             "B07", "B08", "B09"),
            "accession": ("A01", "A02", "B12")}
SINGLE = ("A03", "A04", "A09", "A11", "A12", "A13", "B01", "B03", "B06", "B10", "B11",
          "B13", "C01", "C02", "C03", "C04", "D01", "D02", "D03", "D04",
          "E01", "E02", "E03", "E04", "E05")


def outcome(result):
    return {key: result.get(key) for key in ("applicability", "quality", "publication",
                                             "reason_code", "value", "period_start",
                                             "period_end", "unit")}


def answers(repo_root, report_end):
    from vnext.historical_accession_results import resolve_historical_accession_metrics
    from vnext.historical_results import (prepare_historical_run_input,
                                          resolve_historical_companyfacts_metrics)
    from vnext.normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=repo_root, company_id=COMPANY,
                                         report_end=report_end)
    found = {"selection": {"current": selection["current_filing"]["accessionNumber"],
                           "prior": (selection.get("prior_filing") or {}).get("accessionNumber"),
                           "loaded_inventories": selection["loaded_inventories"]},
             "metrics": {}}
    for family, resolve in (("companyfacts", resolve_historical_companyfacts_metrics),
                            ("accession", resolve_historical_accession_metrics)):
        try:
            component = resolve(repo_root=repo_root, company_id=COMPANY,
                                period_selection=selection)
            for metric_id in FAMILIES[family]:
                found["metrics"][metric_id] = outcome(component["metrics"][metric_id]["result"])
        except Exception as error:  # a refusal is the measurement
            for metric_id in FAMILIES[family]:
                found["metrics"][metric_id] = {"error": type(error).__name__ + ":" + str(error)}
    for metric_id in SINGLE:
        try:
            prepared = prepare_historical_run_input(repo_root=repo_root, company_id=COMPANY,
                                                    metric_id=metric_id,
                                                    period_selection=selection)
            found["metrics"][metric_id] = (
                outcome(prepared["primary_result"]) if prepared["kind"] != "TEXT"
                else text_outcome(repo_root, metric_id, selection, prepared))
        except Exception as error:
            found["metrics"][metric_id] = {"error": type(error).__name__ + ":" + str(error)}
    return found


def text_outcome(repo_root, metric_id, selection, prepared):
    """A text Run input carries no result: the Run derives it from a candidate.

    Its ``primary_result`` is None by design, so comparing that field would
    compare None with None - the first version of this script did exactly
    that and reported D01 and D02 "equal" as two identical AttributeErrors.
    The candidate is what the Run factory derives first, from the same
    rebuilt input, so that is what is compared: which excerpts, in which
    order, with which identity.
    """
    from vnext.historical_run import _rebuilt_text_input
    from vnext.historical_text_results import text_api
    _, arguments = _rebuilt_text_input(data_root=repo_root, company_id=COMPANY,
                                       metric_id=metric_id, period_selection=selection)
    api, _ = text_api(metric_id)
    candidate = api.create_deterministic_text_candidate(
        compiled_spec=prepared["compiled_specs"][metric_id], **arguments)
    items = sorted(candidate["selected"].values(), key=lambda item: item["order"])
    # The answer and the identity are kept apart. D02 binds the metadata row
    # its filing was found in - which document, which row - and moving the
    # row moves that, so its identity changes while its excerpts do not.
    return {"text_candidate_status": candidate["status"],
            "text_items": len(items), "text": [item["text"] for item in items],
            "identity": {"candidate_hash": candidate["candidate_hash"],
                         "row_origins": sorted(
                             (row.get("metadata_origin") or {}).get("inventory_name", "")
                             for row in (arguments.get("source_filings") or {}).values())}}


def main():
    work, label = Path(sys.argv[1]).resolve(), sys.argv[2]
    periods = tuple(sys.argv[3:]) or PERIODS
    assert ROOT not in work.parents and work != ROOT, "work directory must be outside the tree"
    no_net = patch.object(socket.socket, "connect", side_effect=AssertionError("no net"))
    no_dns = patch.object(socket, "getaddrinfo", side_effect=AssertionError("no dns"))
    report = {"record_type": "ISSUE_47_BLOCK_RESIDENT_ROUTE_MEASUREMENT", "label": label,
              "company_id": COMPANY, "cutoff": CUTOFF, "block": BLOCK,
              "source_root_is": "RECORDED_TEST_ONLY: this repository's saved bytes with "
                                "Marriott's submissions rows filed on or before the cutoff "
                                "moved into a new history block",
              "compared": "the answer - applicability, quality, publication, reason, value, "
                          "period and unit for a Result; status and excerpts in order for a "
                          "text candidate. Identities are reported apart: a filing proved "
                          "against another document is bound to that document, so a "
                          "Result's source set and a D02 candidate's metadata row move "
                          "with the row, and that is provenance, not a changed answer.",
              "calls": {"provider": 0, "paid": 0, "sec": 0}, "periods": {}}
    with no_net, no_dns:
        from tests.vnext.historical_block_fixture import build_repartitioned_root
        built = work / "ledger" / "source-inputs"
        if not (built / "source-baseline.json").is_file():
            build_repartitioned_root(work=work, company_id=COMPANY, cik=CIK, cutoff=CUTOFF,
                                     block_name=BLOCK)
        for report_end in periods:
            started = time.time()
            normal = answers(ROOT, report_end)
            moved = answers(built, report_end)
            answer = lambda found: {k: v for k, v in found.items() if k != "identity"}  # noqa: E731
            differing = sorted(m for m in normal["metrics"]
                               if answer(normal["metrics"][m]) != answer(moved["metrics"][m]))
            identity = sorted(m for m in normal["metrics"]
                              if normal["metrics"][m].get("identity")
                              != moved["metrics"][m].get("identity"))
            report["periods"][report_end] = {
                "repository_root": normal, "repartitioned_root": moved,
                "metrics_whose_answer_differs": differing,
                "text_metrics_whose_identity_differs": identity,
                "seconds": round(time.time() - started, 1)}
            print(report_end, "answer differs:", differing, "identity differs:", identity,
                  flush=True)
    out = Path(__file__).with_name("measured-" + label + ".json")
    out.write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
