#!/usr/bin/env python3
"""Inspect configured annual inputs using saved SEC bytes, without execution."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from sec_http import write_immutable_bytes
from vnext.normal_annual_input import inspect_saved_annual_inputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT,
                        help="Saved registry and request ledger root; read only")
    parser.add_argument("--output", type=Path,
                        help="Optional new file outside the source checkout")
    args = parser.parse_args(argv)
    if args.output:
        target = args.output.resolve()
        if target == ROOT or ROOT in target.parents or args.output.is_symlink():
            parser.error("output must be a new external file")
        if target.exists() or any((p / "outputs/active_publication.json").exists()
                                  for p in target.parents):
            parser.error("output exists or belongs to a publication workspace")
    report = inspect_saved_annual_inputs(repo_root=args.data_root.resolve())
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    if args.output:
        write_immutable_bytes(path=args.output, content=raw)
    print(raw.decode(), end="")
    return 2 if any(c["status"] == "INPUT_BLOCKED" for c in report["companies"]) else 0


if __name__ == "__main__":
    sys.exit(main())
