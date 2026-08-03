"""Run the scalability gate for company-specific production branches.

Purpose:
    Write outputs/scalability_audit.csv and fail when scripts/ production
    branches use company names, CIKs, tickers, fixed accessions, or fixed
    fiscal dates. Company identity may live in config/ and tests/fixtures/, but
    adding a peer eleventh company must not require sec_pipeline.py changes.

Call relationships:
    main imports sec_pipeline.write_scalability_audit, then exits nonzero if
    any audit row is not allowed.
"""

import argparse
import sys
from pathlib import Path
from typing import Sequence


WORKDIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKDIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path = [str(SCRIPTS_DIR), *sys.path]

from sec_pipeline import write_scalability_audit  # noqa: E402


def main(*, argv: Sequence[str]) -> int:
    """Run the scalability audit and return nonzero on violations.

    Args:
        argv: Command-line arguments excluding the executable name.

    Expected output:
        A PASS/FAIL console result plus outputs/scalability_audit.csv.

    Returns:
        Zero only when the real scanner reports no forbidden identity rows.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default="outputs/scalability_audit.csv",
    )
    arguments = parser.parse_args(list(argv))
    output_path = Path(arguments.output)
    if not output_path.is_absolute():
        output_path = WORKDIR / output_path
    rows = write_scalability_audit(output_path=output_path)
    failures = [row for row in rows if row["allowed"] != "1"]
    if failures:
        print(f"Scalability gate failed; violations={len(failures)}")
        for row in failures[:20]:
            print(
                f"{row['file']}:{row['line']} {row['type']} "
                f"{row['literal']} -> {row['replacement_plan']}"
            )
        return 1
    print("Scalability gate passed; audit CSV written")
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
