"""What the dated US GAAP namespace changes, on every frame position that declares one.

Usage: python3 effect.py <source root> <positions file> <out.json>

For each position (``company:report_end``): whether its annual report declares
a dated US GAAP release (``us-gaap/YYYY-MM-DD``), then B06 through the
historical cascade, B03 through the zero-AI route, the D02/D03 proposal the
text route builds and the D04 requests, each asked twice in one process: with
the release-aware view's US GAAP entry taken out (the answer before this
repair - the view's table is consulted on every call) and as committed. A
position whose report declares a year-only release must come out the same both
ways. Zero calls.

The committed answer is asked first, and the view caches are put back after
the answer without the entry. The view module caches, per object, whether it
reaches the question, from the table as it stood at the first call; the first
version of this script asked the answer without the entry first, so every
function first viewed then was cached as not reaching the question and the
committed answer ran it unviewed too: every FY2021 B06 came out
B06_GUARD_EQUITY_NAMESPACE_CONFLICT both ways. Production never patches the
table, so only the measurement depended on the order.

The output is rewritten after every position and a position already in it is
not measured again, so a restart loses only the position in progress; a resumed
run must find the same view table (``_WIDENED``) the output was started with.
"""
import contextlib
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext import historical_dei  # noqa: E402
from vnext.canonical import content_hash  # noqa: E402
from vnext.historical_annual_input import prepare_historical_annual_input  # noqa: E402
from vnext.historical_debt_results import resolve_historical_debt_metric  # noqa: E402
from vnext.historical_semantic_results import pinned_requests  # noqa: E402
from vnext.historical_semantic_source import prepare_historical_d04_semantic_source  # noqa: E402
from vnext.historical_text_input import prepare_historical_business_text_input  # noqa: E402
from vnext.historical_text_results import prepare_business_text_sources  # noqa: E402
from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402
from vnext.sources import resolve_repository_file  # noqa: E402

_WITHOUT = {pattern: widened for pattern, widened in historical_dei._WIDENED.items()
            if pattern not in historical_dei.FROZEN_US_GAAP_NAMESPACE_PATTERNS}


@contextlib.contextmanager
def _without_the_us_gaap_entry():
    """The view table without the US GAAP entry; every view cache put back afterwards."""
    caches = {name: getattr(historical_dei, name) for name in ("_REACH", "_VIEWS", "_VIEW_IDS",
                                                                 "_OVERRIDE_VIEWS")}
    saved = {name: (dict(cache) if isinstance(cache, dict) else set(cache))
             for name, cache in caches.items()}
    try:
        with mock.patch.dict(historical_dei._WIDENED, _WITHOUT, clear=True):
            yield
    finally:
        for name, cache in caches.items():
            cache.clear()
            cache.update(saved[name])


def _answer(fn):
    try:
        return fn()
    except Exception as error:  # the stop is that side's answer
        return {"error": type(error).__name__ + ":" + str(error)[:200]}


def _metric(component):
    if "error" in component:
        return component
    result = component.get("result") or {}
    return {"stage": component.get("stage"), "quality": result.get("quality"),
            "reason_code": result.get("reason_code"), "value": result.get("value"),
            "publication": result.get("publication")}


def _text(root, company_id, selection):
    prepared = prepare_historical_business_text_input(repo_root=root, company_id=company_id,
                                                      metric_id="D02", period_selection=selection)
    built = prepare_business_text_sources(metric_id="D02", **prepared["text_arguments"])
    proposal = next(iter(built["proposals"].values()))
    return {"d02": [c["block_index"] for c in proposal["D02"]["candidates"]],
            "d03": [c["block_index"] for c in proposal["D03"]["candidates"]],
            "proposal_id": proposal["proposal_id"]}


def _requests(root, company_id, selection):
    source = prepare_historical_d04_semantic_source(repo_root=root, company_id=company_id,
                                                    period_selection=selection)
    return {"requests": [request["request_id"] for request in pinned_requests(source)]}


def measure(root, company_id, report_end):
    selection = resolve_period_selection(repo_root=root, company_id=company_id, report_end=report_end)
    prepared = prepare_historical_annual_input(repo_root=root, company_id=company_id,
                                               period_selection=selection)
    proof = next(p for p in prepared["source_proofs"]
                 if p.get("document_name", "").lower().endswith((".htm", ".html"))
                 and p.get("accession") == prepared["filing"]["accessionNumber"])
    raw = resolve_repository_file(repo_root=root, repo_relative_path=proof["request_repo_relative_path"]).read_bytes()
    declared = re.search(rb'xmlns:us-gaap="([^"]+)"', raw)
    asks = {
        "B06": lambda: _metric(resolve_historical_debt_metric(
            repo_root=root, company_id=company_id, metric_id="B06", period_selection=selection)),
        "B03": lambda: _metric(resolve_historical_zero_ai_metric(
            repo_root=root, company_id=company_id, metric_id="B03", period_selection=selection)),
        "D02_D03": lambda: _text(root, company_id, selection),
        "D04_REQUESTS": lambda: _requests(root, company_id, selection)}
    row = {"us_gaap_namespace": declared.group(1).decode() if declared else None}
    for name, ask in asks.items():
        after = _answer(ask)
        with _without_the_us_gaap_entry():
            before = _answer(ask)
        row[name] = {"before": before, "after": after, "changed": before != after}
    return row


def main(root, positions_path, out_path):
    root = Path(root).resolve()
    table = content_hash(value=sorted(historical_dei._WIDENED.items()))
    out = {"record_type": "ISSUE_47_US_GAAP_RELEASE_EFFECT", "calls": {"provider": 0, "paid": 0, "sec": 0},
           "view_table_hash": table, "positions": {}}
    if Path(out_path).exists():
        earlier = json.loads(Path(out_path).read_text(encoding="utf-8"))
        if earlier.get("view_table_hash") != table:
            raise SystemExit("US_GAAP_EFFECT_OUTPUT_IS_ANOTHER_MEASUREMENT:" + str(out_path))
        out["positions"] = earlier["positions"]
    positions = [line.strip() for line in open(positions_path) if line.strip()]
    with checkpoint_replayed_once():
        for position in positions:
            if position in out["positions"]:
                continue
            company_id, report_end = position.rsplit(":", 1)
            started = time.time()
            try:
                row = measure(root, company_id, report_end)
            except Exception as error:
                row = {"input_error": type(error).__name__ + ":" + str(error)[:240]}
            out["positions"][position] = row
            print(position, row.get("us_gaap_namespace"),
                  {k: v["changed"] for k, v in row.items() if isinstance(v, dict) and "changed" in v},
                  row.get("input_error", ""), int(time.time() - started), "s", flush=True)
            _write(out_path, out)
    _write(out_path, out)


def _write(out_path, out):
    """The whole output so far, replaced in one rename."""
    staged = Path(str(out_path) + ".partial")
    staged.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    staged.replace(out_path)


if __name__ == "__main__":
    main(*sys.argv[1:])
