#!/usr/bin/env python3
"""Operate the repository-owned Issue #15 zero-AI release ratchet.

Purpose:
    ``r1`` performs the authorized zero-AI cold start; ``r2`` commits the
    deterministic cumulative successor.  Neither accepts a workspace, source,
    company, metric, provider, or publication-root override, so a caller
    cannot mint alternative formal authority.

Call relationships:
    The CLI validates the current checkout identity and delegates to
    ``vnext.zero_ai_release.publish_r1``.  Errors are returned as stable JSON
    without a traceback; the module performs all publication mutations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.zero_ai_release import ZeroAiReleaseError, publish_r1  # noqa: E402
from vnext.zero_ai_r2 import publish_r2  # noqa: E402
from vnext.publication import PublicationError  # noqa: E402


def _head_sha() -> str:
    """Return the exact committed repository HEAD.

    Returns:
        Full 40-character Git commit SHA.
    """
    completed = subprocess.run(
        args=["git", "rev-parse", "HEAD"],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or len(value) != 40:
        raise ZeroAiReleaseError("ZERO_AI_SOURCE_COMMIT_UNAVAILABLE")
    return value


def main(*, argv: Sequence[str]) -> int:
    """Parse one bounded zero-AI release command.

    Args:
        argv: Command tokens excluding the executable name.

    Returns:
        Zero only after the complete requested transaction succeeds.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    r1 = subparsers.add_parser("r1")
    r1.add_argument("--committed-at-utc", required=True)
    r2 = subparsers.add_parser("r2")
    r2.add_argument("--committed-at-utc", required=True)
    arguments = parser.parse_args(list(argv))
    try:
        if arguments.command == "r1":
            result = publish_r1(
                repo_root=REPO_ROOT,
                source_commit=_head_sha(),
                committed_at_utc=str(arguments.committed_at_utc),
            )
        elif arguments.command == "r2":
            result = publish_r2(
                repo_root=REPO_ROOT,
                source_commit=_head_sha(),
                committed_at_utc=str(arguments.committed_at_utc),
            )
        else:
            raise ZeroAiReleaseError("ZERO_AI_COMMAND_UNSUPPORTED")
    except (OSError, PublicationError, ValueError, ZeroAiReleaseError) as error:
        print(
            json.dumps(
                {"status": "FAILED", "error_code": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
