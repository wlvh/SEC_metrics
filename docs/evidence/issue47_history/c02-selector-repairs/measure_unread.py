"""What a change to the C02 selector moves at positions no reading covers.

``measure.py`` holds both selections to the 37 two-direction readings. The
batch also published C02 values at positions nobody has read; a change can
move blocks there that no reading would see. This runs the selector as
committed at ``--base`` and as it is in the working tree on each named
position's governance document and lists every block that moves, with its
text. It says nothing about whether the rest of each selection is right.

Each document is built once with the route's own input preparation
(``tools/read_c02_composition.route_selection``) into ``--documents``, the same
cache ``measure.py`` uses, so a position either script built is reused.

Usage:
    python3 docs/evidence/issue47_history/c02-selector-repairs/measure_unread.py \
        --source-root <restored source-inputs> --documents <cache dir> \
        --position <company>:<report end> [--position ...] [--base <git ref>] \
        [--output <json>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import measure  # noqa: E402
from tools import read_c02_composition as reading  # noqa: E402
from vnext import historical_board_composition_v3 as working  # noqa: E402


def document(*, cache, source_root, position):
    """The position's governance document, built once by the route's preparation."""
    target = cache / (position.replace(":", "_") + ".json")
    if not target.exists():
        from vnext.historical_xbrl_parse import xbrl_parsed_once
        from vnext.normal_history_plan import checkpoint_replayed_once
        company, end = position.rsplit(":", 1)
        with checkpoint_replayed_once(), xbrl_parsed_once():
            built, chosen, candidate, period_start = reading.route_selection(
                repo_root=REPO, company_id=company, report_end=end, source_root=source_root,
                with_period=True)
        target.write_text(json.dumps({"position": position, "document": built, "chosen": chosen,
                                      "candidate_hash": candidate["candidate_hash"],
                                      "period_start": period_start}), encoding="utf-8")
    return json.loads(target.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--position", action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    base, base_sha = measure.selector_at(args.base)
    args.documents.mkdir(parents=True, exist_ok=True)
    positions = {}
    for position in sorted(set(args.position)):
        # A position the route stops on before selecting has nothing to move;
        # name only positions with a published value.
        dumped = document(cache=args.documents, source_root=args.source_root.resolve(),
                          position=position)
        built, start = dumped["document"], dumped["period_start"]
        chosen = {name: measure.select(module, built, start)
                  for name, module in (("base", base), ("working", working))}
        positions[position] = {
            "document_raw_asset_id": built.get("raw_asset_id"),
            "base_selected": len(chosen["base"]), "working_selected": len(chosen["working"]),
            "moved": [{"i": i, "moved": "ADDED" if i in chosen["working"] else "REMOVED",
                       "text": built["blocks"][i]["text"]}
                      for i in sorted(set(chosen["base"]) ^ set(chosen["working"]))]}
    body = {"record_type": "ISSUE_47_C02_SELECTOR_CHANGE_MEASURED_ON_UNREAD_POSITIONS",
            "selector": measure.MODULE,
            "base_ref": subprocess.run(["git", "-C", str(REPO), "rev-parse", args.base], check=True,
                                       capture_output=True, text=True).stdout.strip(),
            "base_selector_sha256": base_sha,
            "working_selector_sha256": "sha256:" + hashlib.sha256(
                (REPO / measure.MODULE).read_bytes()).hexdigest(),
            "what_this_is": __doc__.split("\n\n")[1].replace("\n", " "),
            "positions_measured": len(positions),
            "positions_where_something_moved": sorted(p for p, row in positions.items() if row["moved"]),
            "positions": positions}
    text = json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps({"moved_in": body["positions_where_something_moved"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
