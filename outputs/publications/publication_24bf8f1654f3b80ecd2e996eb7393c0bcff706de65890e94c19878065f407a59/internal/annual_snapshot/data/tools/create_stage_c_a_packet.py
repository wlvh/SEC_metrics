#!/usr/bin/env python3
"""Create or validate the content-addressed Issue #15 Stage C-A packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path = [str(SCRIPTS_DIR), *sys.path]

from vnext.stage_c_packet import StageCAPacketError  # noqa: E402
from vnext.stage_c_packet import validate_stage_c_a_packet  # noqa: E402
from vnext.stage_c_packet import write_stage_c_a_packet  # noqa: E402


def main(*, argv: Sequence[str]) -> int:
    """Write from a staged source candidate or validate a committed packet."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    arguments = parser.parse_args(list(argv))
    try:
        result = (
            validate_stage_c_a_packet(repo_root=REPO_ROOT)
            if arguments.validate
            else write_stage_c_a_packet(repo_root=REPO_ROOT)
        )
    except (OSError, StageCAPacketError, ValueError) as error:
        print(json.dumps(
            {"status": "FAILED", "error": str(error)},
            ensure_ascii=False,
            sort_keys=True,
        ))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
