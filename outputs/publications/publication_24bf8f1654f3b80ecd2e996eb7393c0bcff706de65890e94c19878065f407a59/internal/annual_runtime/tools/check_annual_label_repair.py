#!/usr/bin/env python3
"""Offline regression of the original response and business-error counterexamples."""
from pathlib import Path
import argparse, json, sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vnext.annual_regression import build_regression_receipt

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--output", type=Path, required=True)
args = p.parse_args()
result = build_regression_receipt(repo_root=Path(__file__).resolve().parents[1])
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open("x") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["status"] == "PASS" else 2)
