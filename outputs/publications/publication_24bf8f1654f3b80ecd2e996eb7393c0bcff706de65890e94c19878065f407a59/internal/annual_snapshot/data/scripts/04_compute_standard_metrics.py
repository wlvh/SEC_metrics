"""Run M2 standard metric computation.

Purpose:
    Compute retained companyfacts-supported non-migrated candidate rows for
    later text, DEF 14A, and 8-K stages.

Call relationships:
    main calls sec_pipeline.run_legacy_candidate_stage for the retained
    non-migrated portion of 04_compute_standard_metrics.
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
    """Execute Stage 04 only below the supplied isolated candidate root."""
    arguments = build_parser().parse_args(list(argv))
    run_legacy_candidate_stage(
        stage_name="04_compute_standard_metrics",
        workspace_dir=Path(arguments.workspace_dir),
    )


if __name__ == "__main__":
    main(argv=sys.argv[1:])
