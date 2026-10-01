"""What a change to the C02 selector moves, judged by every two-direction reading.

The selector (``scripts/vnext/historical_board_composition_v2.py``; at a
``--base`` from before the split, the first path, which holds the same reader
there) is run twice on each judged position's governance document - once as
committed at ``--base``, once as it is in the working tree - and both selections are held
to the position's reading with ``tools/read_c02_composition.read_position``.
The answer lists every block that moved, with what the reading says it is, and
each position's problems before and after. A repair aimed at one problem
should move only the blocks of that problem; anything else it moves is listed
here too, read or unread.

The positions are the 27 older years (``c02-older-years/judgements``, read
from an export-restored root, ``--source-root``) and the ten latest
(``c02-composition-facts/judgements``, read from this checkout). Building a
document takes the route's whole input preparation, so each one is written
once to ``--documents`` (outside the checkout) and reused; the selector itself
takes about a second per document.

Usage:
    python3 docs/evidence/issue47_history/c02-selector-repairs/measure.py \
        --source-root <restored source-inputs> --documents <cache dir> \
        [--base <git ref>] [--output <json>]
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from tools import read_c02_composition as reading  # noqa: E402
from vnext import historical_board_composition_v2 as working  # noqa: E402

MODULE = "scripts/vnext/historical_board_composition_v2.py"
# Until the base merge that brought #28's bound copy in, #47's reader lived at
# this path; a --base from before that commit holds it there.
FIRST_PATH = "scripts/vnext/historical_board_composition.py"


def selector_at(ref):
    """The selector module as committed at ``ref``, loaded beside the working one."""
    shown = subprocess.run(["git", "-C", str(REPO), "show", ref + ":" + MODULE], capture_output=True)
    path = MODULE
    if shown.returncode != 0:
        path = FIRST_PATH
        shown = subprocess.run(["git", "-C", str(REPO), "show", ref + ":" + path], check=True,
                               capture_output=True)
    source = shown.stdout
    module = types.ModuleType("vnext._c02_selector_at_base")
    module.__package__ = "vnext"
    module.__file__ = str(REPO / path)
    exec(compile(source, path + "@" + ref, "exec"), module.__dict__)
    return module, "sha256:" + hashlib.sha256(source).hexdigest()


def documents(*, cache: Path, source_root: Path):
    """Each judged position's governance document and the route's selection, built once."""
    from vnext.historical_xbrl_parse import xbrl_parsed_once
    from vnext.normal_history_plan import checkpoint_replayed_once
    jobs = [(path, source_root) for path in sorted(reading.OLDER_READING_DIR.glob("*.json"))]
    jobs += [(path, REPO) for path in sorted(reading.READING_DIR.glob("*.json"))]
    cache.mkdir(parents=True, exist_ok=True)
    with checkpoint_replayed_once(), xbrl_parsed_once():
        for path, root in jobs:
            position = json.loads(path.read_text(encoding="utf-8"))["position"]
            target = cache / (position.replace(":", "_") + ".json")
            company, end = position.rsplit(":", 1)
            if not target.exists():
                document, chosen, candidate, period_start = reading.route_selection(
                    repo_root=REPO, company_id=company, report_end=end, source_root=root, with_period=True)
                target.write_text(json.dumps({"position": position, "reading": str(path.relative_to(REPO)),
                                              "document": document, "chosen": chosen,
                                              "candidate_hash": candidate["candidate_hash"],
                                              "period_start": period_start,
                                              "selector_sha256": "sha256:" + hashlib.sha256(
                                                  (REPO / MODULE).read_bytes()).hexdigest()}),
                                  encoding="utf-8")
            dumped = json.loads(target.read_text(encoding="utf-8"))
            if "period_start" not in dumped:
                # Cached before the selector needed the target year's first day:
                # take it from the same annual input the route's target uses.
                dumped["period_start"] = target_period_start(root=root, company_id=company, report_end=end)
                target.write_text(json.dumps(dumped), encoding="utf-8")
            yield dumped


def target_period_start(*, root, company_id, report_end):
    """The first day of the year the route targets, as its text input derives it."""
    from vnext.historical_annual_input import prepare_historical_annual_input
    from vnext.normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=root, company_id=company_id, report_end=report_end)
    prepared = prepare_historical_annual_input(repo_root=root, company_id=company_id,
                                               period_selection=selection)
    return prepared["table_input"]["target_period"]["period_start"]


def select(module, document, period_start):
    """A selector's block indices; a version from before the period argument takes none."""
    arguments = {"document": document}
    if "period_start" in inspect.signature(module.board_composition_facts).parameters:
        arguments["period_start"] = period_start
    return sorted(c["block_index"] for c in module.board_composition_facts(**arguments)["candidates"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    base, base_sha = selector_at(args.base)
    adjudications = reading.load_adjudications()
    positions, totals = {}, {"base": {}, "working": {}}
    for dumped in documents(cache=args.documents, source_root=args.source_root.resolve()):
        document, position = dumped["document"], dumped["position"]
        record = json.loads((REPO / dumped["reading"]).read_text(encoding="utf-8"))
        chosen = {name: select(module, document, dumped["period_start"])
                  for name, module in (("base", base), ("working", working))}
        judged = {row["i"]: row["verdict"] for row in [*record["pool_facts"], *record.get("outside_pool_facts", []),
                                                       *record["selected"], *record.get("supplementary", [])]}
        pool = {row["i"] for row in record.get("pool", [])}
        moved = {str(i): {"moved": "ADDED" if i in chosen["working"] else "REMOVED",
                          "reading": judged.get(i, "POOL_NOT_A_FACT" if i in pool else "UNREAD"),
                          "text": document["blocks"][i]["text"][:200]}
                 for i in sorted(set(chosen["base"]) ^ set(chosen["working"]))}
        problems = {}
        for name in chosen:
            answer = reading.read_position(document=document, chosen=chosen[name], reading=record,
                                           adjudications=adjudications)
            problems[name] = {kind: sorted(item["i"] if isinstance(item, dict) else item for item in items)
                              for kind, items in answer["problems"].items() if items}
            for kind, items in problems[name].items():
                totals[name][kind] = totals[name].get(kind, 0) + len(items)
            totals[name]["positions_disagreeing"] = (totals[name].get("positions_disagreeing", 0)
                                                     + (answer["verdict"] != "READING_AGREES"))
        # The cached "chosen" is what the route selected when the entry was built,
        # with the selector of that moment. It says whether --base is the rule
        # the route ran only when that selector was --base's; otherwise there
        # is nothing to compare, which is not a mismatch.
        same_rule = dumped.get("selector_sha256") == base_sha
        positions[position] = {"reading": dumped["reading"],
                               "base_matches_route": (chosen["base"] == dumped["chosen"]) if same_rule else None,
                               "moved": moved, "problems_base": problems["base"],
                               "problems_working": problems["working"]}
    body = {"record_type": "ISSUE_47_C02_SELECTOR_CHANGE_MEASURED", "selector": MODULE,
            "base_ref": subprocess.run(["git", "-C", str(REPO), "rev-parse", args.base], check=True,
                                       capture_output=True, text=True).stdout.strip(),
            "base_selector_sha256": base_sha,
            "working_selector_sha256": "sha256:" + hashlib.sha256((REPO / MODULE).read_bytes()).hexdigest(),
            "positions_judged": len(positions),
            "positions_where_something_moved": sorted(p for p, row in positions.items() if row["moved"]),
            "totals": totals, "positions": positions}
    text = json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps({"moved_in": body["positions_where_something_moved"], "totals": totals}, indent=1))
    return 1 if any(row["base_matches_route"] is False for row in positions.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
