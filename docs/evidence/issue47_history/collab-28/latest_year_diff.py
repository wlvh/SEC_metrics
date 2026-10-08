"""How #47's C02 selector differs from the version #28 bound, on the ten latest years.

#28 bound ``scripts/vnext/historical_board_composition_v2.py`` (#47's repairs
1-18) and reads only the latest year of each company; #47's selector continues
in ``historical_board_composition_v3.py``. This runs both on the ten
latest-year governance documents the C02 readings were made on and records,
per position, the blocks the newer selector adds or drops, so #28 can see what
taking a later ``_v3`` would move before it decides. Nothing here is a
reading: whether a moved block is a composition fact is for the readings and
the adjudication to say.

Usage:
    python3 docs/evidence/issue47_history/collab-28/latest_year_diff.py \
        --source-root <root> --documents <cache dir> [--output <json>]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from vnext import historical_board_composition_v2 as bound  # noqa: E402
from vnext import historical_board_composition_v3 as working  # noqa: E402

HERE = Path(__file__).resolve().parent


def _measure():
    path = HERE.parent / "c02-selector-repairs" / "measure.py"
    spec = importlib.util.spec_from_file_location("c02_selector_measure", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(module):
    return "sha256:" + hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "latest-year-diff.json")
    args = parser.parse_args(argv)
    measure = _measure()
    positions = {}
    for dumped in measure.documents(cache=args.documents, source_root=args.source_root.resolve()):
        if not dumped["reading"].startswith("docs/evidence/issue47_history/c02-composition-facts/judgements/"):
            continue
        document, start = dumped["document"], dumped["period_start"]
        before = {c["block_index"] for c in bound.board_composition_facts(document=document, period_start=start)["candidates"]}
        after = {c["block_index"] for c in working.board_composition_facts(document=document, period_start=start)["candidates"]}
        positions[dumped["position"]] = {"bound_selects": len(before), "working_selects": len(after),
                                         "added": sorted(after - before), "dropped": sorted(before - after)}
    out = {"record_type": "C02_LATEST_YEAR_SELECTION_DIFF",
           "bound": {"path": "scripts/vnext/historical_board_composition_v2.py", "sha256": _sha(bound)},
           "working": {"path": "scripts/vnext/historical_board_composition_v3.py", "sha256": _sha(working)},
           "positions": positions,
           "positions_that_move": sorted(p for p, row in positions.items() if row["added"] or row["dropped"])}
    args.output.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({p: positions[p] for p in out["positions_that_move"]}, indent=1))


if __name__ == "__main__":
    main()
