#!/usr/bin/env python3
"""Inspect saved annual inputs or discover their source dependencies."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from sec_http import write_immutable_bytes
from vnext.normal_annual_input import inspect_saved_annual_inputs
from vnext.normal_source_requirements import inspect_source_requirements


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT,
                        help="Saved registry and request ledger root; read only")
    parser.add_argument("--discover-sources", action="store_true",
                        help="List known annual, proxy and fiscal 8-K source dependencies; no fetch")
    parser.add_argument("--company", action="append",
                        help="Configured company id; source discovery only, default all ten")
    parser.add_argument("--output", type=Path,
                        help="Optional new file outside the source checkout")
    args = parser.parse_args(argv)
    if args.company and not args.discover_sources:
        parser.error("--company requires --discover-sources")
    if args.output:
        target = args.output.resolve()
        if target == ROOT or ROOT in target.parents or args.output.is_symlink():
            parser.error("output must be a new external file")
        if target.exists() or any((p / "outputs/active_publication.json").exists()
                                  for p in target.parents):
            parser.error("output exists or belongs to a publication workspace")
    report = (inspect_source_requirements(repo_root=args.data_root.resolve(),company_ids=args.company)
              if args.discover_sources else inspect_saved_annual_inputs(repo_root=args.data_root.resolve()))
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    if args.output:
        write_immutable_bytes(path=args.output, content=raw)
    print(raw.decode(), end="")
    failed = (any(c["status"] != "SAVED_SOURCE_DEPENDENCIES_AVAILABLE" for c in report["companies"])
              if args.discover_sources else any(c["status"] == "INPUT_BLOCKED" for c in report["companies"]))
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
