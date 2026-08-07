"""Run the stage 11 legacy builder or pinned active report reader.

The pipeline stage itself selects the active PublicationView before any legacy
write boundary. This wrapper deliberately performs no pre/post processing, so
an active report read cannot invalidate provenance or rewrite root mirrors.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build active read-back or isolated legacy-candidate arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-dir")
    return parser


def main(*, argv: Sequence[str]) -> None:
    """Dispatch active read-back or one isolated candidate transaction."""
    from sec_pipeline import run_legacy_candidate_stage, run_stage

    arguments = build_parser().parse_args(list(argv))
    if arguments.workspace_dir is None:
        run_stage(stage_name="11_build_report")
        return
    run_legacy_candidate_stage(
        stage_name="11_build_report",
        workspace_dir=Path(arguments.workspace_dir),
    )


if __name__ == "__main__":
    main(argv=sys.argv[1:])
