#!/usr/bin/env python3
"""Export Issue #47's model ledger to the branch, verify an export, or restore one.

The owner decided the model calls run in the executor's cloud container, and
the ledger lives there with them. After each run the executor exports the
granted ledger here and pushes it, so what was spent and what came back
survive the container. Restoring puts a verified export back at the granted
root and never writes the ledger's start: spending more from a restored
ledger is the owner's decision (historical_ledger_start).

A process of its own: never the one that sends requests, which may load only
the code its authorization binds.

  export              the granted ledger into evidence/issue47_model_calls/
  verify [--export D] rebuild an export in a scratch root and check it
  restore [--export D]
                      put a verified export back at the granted root
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.historical_model_calls import (MODEL_EXPORT_DIRECTORY,  # noqa: E402 - path set above
                                          HistoricalModelCallError, _ledger, model_allowance)
from vnext.historical_model_export import (export_model_ledger,  # noqa: E402
                                           restore_model_ledger, verify_model_export)
from vnext.historical_source_export import HistoricalExportError  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["export", "verify", "restore"])
    parser.add_argument("--export", default=str(ROOT / MODEL_EXPORT_DIRECTORY))
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            allowance = model_allowance(repo_root=ROOT)
            ledger = _ledger(allowance=allowance, root=Path(allowance["budget_root"]), live=True)
            result = export_model_ledger(ledger=ledger, out_dir=Path(args.export))
        elif args.command == "verify":
            index = verify_model_export(export_dir=Path(args.export))
            result = {"status": "VERIFIED", "export_id": index["export_id"],
                      "counts": index["counts"], "stopped": index["stopped"], "calls": [0, 0, 0]}
        else:
            result = restore_model_ledger(export_dir=Path(args.export))
    except (HistoricalModelCallError, HistoricalExportError) as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error), "calls": [0, 0, 0]},
                         indent=1))
        return 1
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
