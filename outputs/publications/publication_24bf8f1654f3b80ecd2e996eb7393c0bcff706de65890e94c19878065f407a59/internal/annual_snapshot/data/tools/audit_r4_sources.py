#!/usr/bin/env python3
"""Print immutable source inventory or native Evidence probes without network."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from vnext.canonical import strict_json_file
from vnext.r4_source_audit import audit_scope_alias_coverage
from vnext.r4_source_audit import inventory_immutable_sources, probe_native_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--full-asset", type=Path)
    parser.add_argument("--scope-coverage-task")
    parser.add_argument("--inventory-cik", action="append", default=[])
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    if args.inventory_cik and not (args.recipe or args.full_asset or args.scope_coverage_task):
        result = inventory_immutable_sources(repo_root=repo_root,
                                             issuer_ciks=args.inventory_cik)
    elif (args.recipe and args.scope_coverage_task
          and not (args.full_asset or args.inventory_cik)):
        result = audit_scope_alias_coverage(
            repo_root=repo_root, declaration=strict_json_file(path=args.recipe)["source"],
            task_contract_id=args.scope_coverage_task)
    elif args.recipe and args.full_asset and not (args.inventory_cik or args.scope_coverage_task):
        result = probe_native_candidates(
            repo_root=repo_root, recipe=strict_json_file(path=args.recipe),
            full_derived_asset=strict_json_file(path=args.full_asset))
    else:
        parser.error("Choose inventory CIKs, recipe/full-asset, or recipe/scope-coverage-task")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
