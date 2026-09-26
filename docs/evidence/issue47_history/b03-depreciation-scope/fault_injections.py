"""Apply each injection to the candidate rule, run its tests, restore; record what caught it.

Usage (from the repository root, clean tree):
    python3 docs/evidence/issue47_history/b03-depreciation-scope/fault_injections.py \
        docs/evidence/issue47_history/b03-depreciation-scope/fault-injections.json
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
T = "tests.vnext.test_historical_da_scope_candidate"
RULE = "scripts/vnext/historical_da_scope_candidate.py"
INJECTIONS = [
    ("IGNORE_REPORTED_PRECISION", RULE,
     "    return abs(Decimal(first[\"value\"]) - Decimal(second[\"value\"])) <= sum(tolerances)",
     "    return Decimal(first[\"value\"]) == Decimal(second[\"value\"])"),
    ("TAKE_THE_CHAIN_S_FIRST_WHATEVER_THE_OTHERS_SAY", RULE,
     "    if all(agree(direct[0], other) for other in direct[1:]):",
     "    if True:"),
    ("TAKE_THE_LARGER_WHEN_THEY_CONFLICT", RULE,
     "    return {\"status\": \"WITHHOLD\", \"reason_code\": WITHHELD_REASON,\n"
     "            \"why\": \"DIRECT_CANDIDATES_CONFLICT_AND_NOTHING_IN_THE_FILING_RESOLVES_IT\",",
     "    return {\"status\": \"TAKE\", \"selected\": max(direct, key=lambda c: Decimal(c[\"value\"])),\n"
     "            \"why\": \"DIRECT_CANDIDATES_CONFLICT_AND_NOTHING_IN_THE_FILING_RESOLVES_IT\","),
    ("A_SEGMENT_FACT_IS_A_CANDIDATE", RULE,
     "        if (context is None or context[\"dimensions\"] or context[\"typed_dimension_count\"]",
     "        if (context is None"),
    ("ANOTHER_PERIOD_IS_A_CANDIDATE", RULE,
     "                or context[\"period_start\"] != period_start\n"
     "                or context[\"period_end\"] != period_end\n",
     ""),
    ("ANY_UNIT_IS_A_CANDIDATE", RULE,
     "                or fact[\"unit_ref\"] not in usd):",
     "                ):"),
    ("NO_COMPOSITION_RESOLUTION", RULE,
     "    if None not in parts:",
     "    if False:"),
    ("PARSER_DROPS_THE_FROZEN_FACT", RULE,
     "        before = len(self.active)\n        super().handle_starttag(tag, attrs)\n",
     "        before = len(self.active)\n        if tag.endswith(\"nonnumeric\"):\n            return\n        super().handle_starttag(tag, attrs)\n"),
]


def main():
    out = []
    for name, path, old, new in INJECTIONS:
        target = REPO / path
        original = target.read_bytes()
        text = original.decode("utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        try:
            target.write_text(text.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "unittest", T], cwd=REPO,
                                 capture_output=True, text=True, timeout=1200)
            tail = run.stderr.strip().splitlines()
            failed = sorted({line.split(" (")[0].replace("FAIL: ", "").replace("ERROR: ", "")
                             for line in tail if line.startswith(("FAIL:", "ERROR:"))})
            out.append({"id": name, "file": path,
                        "outcome": "CAUGHT" if run.returncode else "NOT_CAUGHT",
                        "caught_by": failed, "suite_result": tail[-1] if tail else ""})
        finally:
            target.write_bytes(original)
        print(json.dumps(out[-1]), flush=True)
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
