#!/usr/bin/env python3
"""Persist or validate the authorized Issue #15 Stage C-B packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.stage_c_b_packet import StageCBPacketError  # noqa: E402
from vnext.stage_c_b_packet import validate_stage_c_b_packet  # noqa: E402
from vnext.stage_c_b_packet import write_stage_c_b_packet  # noqa: E402


def main(*, argv: Sequence[str]) -> int:
    """Write a staged candidate packet or validate the committed overlay."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    arguments = parser.parse_args(list(argv))
    try:
        result = (
            validate_stage_c_b_packet(repo_root=REPO_ROOT)
            if arguments.validate
            else write_stage_c_b_packet(repo_root=REPO_ROOT)
        )
    except StageCBPacketError as error:
        print(json.dumps(
            {"status": "FAILED", "error_code": str(error)},
            ensure_ascii=False,
            sort_keys=True,
        ))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
