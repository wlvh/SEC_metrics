"""Compare two runs of the B06 cascade probe over a plan: frozen fallback against the successor.

Usage: python3 frame_compare.py <frozen probe.json> <successor probe.json> <out.json>

Both inputs are ../probe.py outputs over the same plan and restored root; the
successor run had OLDER_FALLBACK_FORMS applied to the fallback resolver (in
memory, the same text historical_debt_results compiles). Every position must be
present in both and neither may carry an error. Positions whose stage, reason,
value or selection differ are listed with both answers. Zero calls.
"""
import json
import sys
from pathlib import Path


def _answer(row):
    return {key: row.get(key) for key in ("stage", "reason_code", "publication", "quality", "value")}


def main(frozen_path, successor_path, out):
    frozen = json.loads(Path(frozen_path).read_text(encoding="utf-8"))
    successor = json.loads(Path(successor_path).read_text(encoding="utf-8"))
    assert set(frozen) == set(successor), sorted(set(frozen) ^ set(successor))
    errors = sorted(key for key in frozen if "error" in frozen[key] or "error" in successor[key])
    assert not errors, errors
    moved = {key: {"frozen": _answer(frozen[key]), "successor": _answer(successor[key]),
                   "frozen_reason": (frozen[key].get("selection") or {}).get("reason"),
                   "successor_reason": (successor[key].get("selection") or {}).get("reason")}
             for key in sorted(frozen)
             if (_answer(frozen[key]), frozen[key].get("selection"))
             != (_answer(successor[key]), successor[key].get("selection"))}
    Path(out).write_text(json.dumps(
        {"record_type": "ISSUE_47_B06_FALLBACK_FORMS_FRAME_EFFECT", "positions": len(frozen),
         "moved": moved,
         "new_values": sorted(key for key, row in moved.items()
                              if row["successor"]["value"] is not None
                              and row["frozen"]["value"] is None),
         "values_changed": sorted(key for key, row in moved.items()
                                  if row["frozen"]["value"] is not None),
         "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(len(frozen), "positions;", len(moved), "moved:", sorted(moved))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
