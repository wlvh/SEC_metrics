"""Apply each injection to the wired B03 D&A check, run the route's tests, restore; record what caught it.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/b03-depreciation-scope/route_fault_injections.py \
        docs/evidence/issue47_history/b03-depreciation-scope/route-fault-injections.json
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SUITE = "tests.vnext.test_historical_da_scope_route"
ROUTE = "scripts/vnext/historical_zero_ai_results.py"
INJECTIONS = [
    ("THE_CHECK_IS_SKIPPED",
     '        if metric_id == "B03" and result["publication"] == "PUBLISHED":\n',
     '        if False:\n'),
    ("A_WITHHOLD_IS_KEPT",
     '                raise _DepreciationScopeUnproven(da_scope)\n',
     '                pass\n'),
    ("A_RETAKE_IS_IGNORED",
     '            if da_scope["status"] == "RETAKE":\n',
     '            if False:\n'),
    ("A_RETAKE_DOES_NOT_REMOVE_THE_DISPROVED_CANDIDATES",
     '                disproved = set(DIRECT) - {da_scope["concept"]}\n',
     '                disproved = set()\n'),
    ("A_DIRECT_TOTAL_THE_FILING_DOES_NOT_TAG_IS_KEPT",
     '        if direct:\n            return {**body, "status": "WITHHOLD",\n'
     '                    "why": "THE_CHAIN_TOOK_A_DIRECT_TOTAL_THE_FILING_DOES_NOT_TAG_FOR_THIS_PERIOD"}\n',
     ''),
    ("A_COMPOSITION_TAKEN_WHILE_THE_FILING_TAGS_A_TOTAL_IS_KEPT",
     '    if not direct:\n        return {**body, "status": "WITHHOLD",\n'
     '                "why": "THE_CHAIN_COMPOSED_WHILE_THE_FILING_TAGS_A_DIRECT_TOTAL"}\n',
     ''),
    ("THE_CHAIN_S_VALUE_IS_NOT_COMPARED",
     '    if not agree({"value": chain["value"], "decimals": "INF"}, selected):\n',
     '    if False:\n'),
]


def main():
    out = []
    target = REPO / ROUTE
    for name, old, new in INJECTIONS:
        original = target.read_bytes()
        text = original.decode("utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        try:
            target.write_text(text.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", SUITE], cwd=REPO,
                                 capture_output=True, text=True, timeout=2400)
        finally:
            target.write_bytes(original)
        lines = run.stderr.strip().splitlines()
        caught = sorted({line.split(" (")[0].replace("FAIL: ", "").replace("ERROR: ", "")
                         for line in lines if line.startswith(("FAIL:", "ERROR:"))})
        row = {"id": name, "file": ROUTE, "outcome": "CAUGHT" if run.returncode else "NOT_CAUGHT",
               "caught_by": caught, "suite_result": lines[-1] if lines else ""}
        out.append(row)
        print(json.dumps(row), flush=True)
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
