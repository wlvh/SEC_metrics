#!/usr/bin/env python3
"""Create or validate the decision-neutral sibling-request comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.table_context_comparison import (  # noqa: E402
    validate_sibling_request_context_analysis,
)
from vnext.table_context_comparison import (  # noqa: E402
    write_sibling_request_context_analysis,
)


def main(*, argv: list[str]) -> int:
    """Run only deterministic local request reconstruction and comparison."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.validate:
        analysis = validate_sibling_request_context_analysis(
            repo_root=REPO_ROOT,
        )
        result = {
            "analysis_id": analysis["analysis_id"],
            "status": next(
                value for key, value in analysis.items()
                if key.endswith("_CONTEXT_STATUS")
            ),
            "reason": analysis["reason"],
            "egress_counts": analysis["egress_counts"],
        }
    else:
        result = write_sibling_request_context_analysis(
            repo_root=REPO_ROOT,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
