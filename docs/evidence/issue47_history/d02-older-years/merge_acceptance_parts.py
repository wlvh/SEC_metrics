"""Merge per-position acceptance readings of tools/read_d02_excerpts.py into one file.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/d02-older-years/merge_acceptance_parts.py <out> <part> [<part> ...]

The container this reading ran in was restarted every half hour or so, and a
single run over 26 positions never finished; so each position was read by its
own run of the tool, to its own file. Every position's answer is computed on
its own - the tool builds one packet per position and compares one result - so
the merged file is the file one run over all positions writes: the same
top-level fields, which must be identical in every part, and the union of the
positions, which must not overlap. Zero calls.
"""
import json
import sys
from pathlib import Path

SHARED = ("record_type", "reader", "requirement_closure_hash", "not_covered", "calls")


def main(out, *parts):
    if not parts:
        raise SystemExit("NO_PARTS")
    merged = None
    for part in parts:
        body = json.loads(Path(part).read_text(encoding="utf-8"))
        if set(body) != set(SHARED) | {"per_position"}:
            raise SystemExit("PART_SHAPE_DIFFERS:" + part)
        if merged is None:
            merged = {key: body[key] for key in SHARED}
            merged["per_position"] = {}
        elif any(merged[key] != body[key] for key in SHARED):
            raise SystemExit("PARTS_DISAGREE:" + part)
        overlap = set(merged["per_position"]) & set(body["per_position"])
        if overlap:
            raise SystemExit("POSITION_IN_TWO_PARTS:" + ",".join(sorted(overlap)))
        merged["per_position"].update(body["per_position"])
    Path(out).write_text(json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
    verdicts = {}
    for row in merged["per_position"].values():
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
    print(out, len(merged["per_position"]), verdicts)


if __name__ == "__main__":
    main(*sys.argv[1:])
