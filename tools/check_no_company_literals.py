"""Run the scalability gate for company-specific production branches.

Purpose:
    Write outputs/scalability_audit.csv and fail when scripts/ production
    branches use company names, CIKs, tickers, fixed accessions, or fixed fiscal
    dates. Company identity may live in config/ and tests/fixtures/, but adding
    a peer eleventh company must not require scripts/sec_pipeline.py changes.

Call relationships:
    main imports sec_pipeline.write_scalability_audit, then exits nonzero if
    any audit row is not allowed.
"""

import sys
from pathlib import Path


WORKDIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKDIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path = [str(SCRIPTS_DIR), *sys.path]

from sec_pipeline import write_scalability_audit  # noqa: E402


def main() -> None:
    """Run the scalability audit and exit nonzero on violations.

    Expected output:
        A PASS/FAIL console result plus outputs/scalability_audit.csv.
    """
    rows = write_scalability_audit()
    failures = [row for row in rows if row["allowed"] != "1"]
    if failures:
        print(f"Scalability gate failed; violations={len(failures)}")
        for row in failures[:20]:
            print(
                f"{row['file']}:{row['line']} {row['type']} "
                f"{row['literal']} -> {row['replacement_plan']}"
            )
        raise SystemExit(1)
    print("Scalability gate passed; outputs/scalability_audit.csv written")


if __name__ == "__main__":
    main()
