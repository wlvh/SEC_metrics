"""Run M6 MD&A, KPI, risk, and legal text extraction.

Purpose:
    Extract text evidence from target 10-K primary documents for MD&A industry
    KPIs, risk factors, legal proceedings, regulatory investigations, and going
    concern statements.

Call relationships:
    main calls sec_pipeline.run_legacy_candidate_stage for the retained
    non-migrated portion of 09_extract_mda_and_risk_text.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from sec_pipeline import run_legacy_candidate_stage


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit isolated-candidate command contract."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-dir", required=True)
    return parser


def main(*, argv: Sequence[str]) -> None:
    """Execute Stage 09 only below the supplied isolated candidate root."""
    arguments = build_parser().parse_args(list(argv))
    run_legacy_candidate_stage(
        stage_name="09_extract_mda_and_risk_text",
        workspace_dir=Path(arguments.workspace_dir),
    )


if __name__ == "__main__":
    main(argv=sys.argv[1:])
