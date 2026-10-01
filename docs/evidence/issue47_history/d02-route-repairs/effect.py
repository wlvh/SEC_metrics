"""D02 and D03 before and after the route repairs, on every frame position, in one process.

Usage: python3 effect.py <source root> <positions file> <out.json> [<git revision> [<route file>]]

The route module as committed at <git revision> (default HEAD) is loaded beside
the repaired one (<route file>, default the working tree's), and both are given
the same pinned input for each position
(``company:report_end`` per line). For each: the D02 excerpt blocks, the D03
candidate blocks, the checked ranges and the coverage status, or the error the
preparation stops with. The comparison is of the proposals the frozen candidate
builder reads, so an unchanged proposal means an unchanged value. Zero calls.

The output is rewritten after every position, and a position already in it is
not measured again, so a restart loses only the position in progress. A
resumed run must name the same revision and the same repaired route bytes as
the output it continues; anything else starts a different measurement and is
refused.
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext import historical_text_results as working  # noqa: E402
from vnext.historical_text_input import prepare_historical_business_text_input  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

ROUTE = "scripts/vnext/historical_text_results.py"


def loaded_route(source, label):
    spec = importlib.util.spec_from_loader("vnext._route_" + label, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "vnext"
    exec(compile(source, label, "exec"), module.__dict__)
    return module


def committed_route(revision):
    source = subprocess.run(["git", "show", revision + ":" + ROUTE], cwd=REPO, check=True,
                            capture_output=True, text=True).stdout
    return loaded_route(source, "committed")


def summary(module, arguments):
    try:
        built = module.prepare_business_text_sources(metric_id="D02", **arguments)
    except Exception as error:  # the stop is the answer for that version
        return {"error": type(error).__name__ + ":" + str(error)[:240]}
    reference_id = next(iter(built["proposals"]))
    proposal = built["proposals"][reference_id]
    document = built["documents"][reference_id]
    return {"d02": [c["block_index"] for c in proposal["D02"]["candidates"]],
            "d03": [c["block_index"] for c in proposal["D03"]["candidates"]],
            "ranges": [(r["section_id"], r["start_block"], r["end_block_exclusive"])
                       for r in proposal["checked_ranges"]],
            "coverage": proposal["coverage_status"], "reasons": proposal["coverage_reasons"],
            "texts": {c["block_index"]: document["blocks"][c["block_index"]]["text"]
                      for c in proposal["D02"]["candidates"]}}


def main(root, positions_path, out_path, revision="HEAD", route_file=None):
    root = Path(root).resolve()
    committed = committed_route(revision)
    repaired = (working if route_file is None
                else loaded_route(Path(route_file).read_text(encoding="utf-8"), "repaired"))
    out = {"revision": revision, "repaired_route_sha256": hashlib.sha256(
               (Path(route_file) if route_file else REPO / ROUTE).read_bytes()).hexdigest(),
           "committed_route_sha256": hashlib.sha256(subprocess.run(
               ["git", "show", revision + ":" + ROUTE], cwd=REPO, check=True,
               capture_output=True).stdout).hexdigest(),
           "source_root_kind": "export-restored or checkout",
           "calls": {"provider": 0, "paid": 0, "sec": 0}, "positions": {}}
    if Path(out_path).exists():
        earlier = json.loads(Path(out_path).read_text(encoding="utf-8"))
        same = all(earlier.get(key) == out[key] for key in
                   ("revision", "repaired_route_sha256", "committed_route_sha256"))
        if not same:
            raise SystemExit("D02_EFFECT_OUTPUT_IS_ANOTHER_MEASUREMENT:" + str(out_path))
        out["positions"] = earlier["positions"]
    positions = [line.strip() for line in open(positions_path) if line.strip()]
    with checkpoint_replayed_once():
        for position in positions:
            if position in out["positions"]:
                continue
            company_id, report_end = position.rsplit(":", 1)
            started = time.time()
            try:
                selection = resolve_period_selection(repo_root=root, company_id=company_id,
                                                     report_end=report_end)
                prepared = prepare_historical_business_text_input(
                    repo_root=root, company_id=company_id, metric_id="D02",
                    period_selection=selection)
            except Exception as error:
                out["positions"][position] = {"input_error": type(error).__name__ + ":" + str(error)[:240]}
                print(position, "INPUT_ERROR", str(error)[:120], flush=True)
                _write(out_path, out)
                continue
            before = summary(committed, prepared["text_arguments"])
            after = summary(repaired, prepared["text_arguments"])
            row = {"before": before, "after": after}
            if "error" in before or "error" in after:
                row["changed"] = before.get("error") != after.get("error") or before != after
            else:
                row["d02_removed"] = {i: before["texts"][i] for i in before["d02"] if i not in after["d02"]}
                row["d02_added"] = {i: after["texts"][i] for i in after["d02"] if i not in before["d02"]}
                row["d03_changed"] = before["d03"] != after["d03"]
                row["ranges_changed"] = before["ranges"] != after["ranges"]
                row["changed"] = before != after
            for side in (before, after):
                side.pop("texts", None)
            out["positions"][position] = row
            print(position, "CHANGED" if row["changed"] else "same",
                  {k: row[k] for k in ("d02_removed", "d02_added") if row.get(k)} or "",
                  after.get("error", "")[:100], int(time.time() - started), "s", flush=True)
            _write(out_path, out)
    _write(out_path, out)


def _write(out_path, out):
    """The whole output so far, replaced in one rename."""
    staged = Path(str(out_path) + ".partial")
    staged.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    staged.replace(out_path)


if __name__ == "__main__":
    main(*sys.argv[1:])
