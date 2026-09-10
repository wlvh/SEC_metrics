"""Create the offline current-source validation overlay for PR-3 Stage A.

The command creates only a content-addressed artifact under the existing table
freeze namespace.  It does not call SEC, construct a provider transport, run
qualification, change an active pointer, or rewrite R2 validation provenance.
"""

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

from vnext.stage_a_snapshot import StageASnapshotError  # noqa: E402
from vnext.stage_a_snapshot import write_stage_a_snapshot  # noqa: E402


def main(*, argv: Sequence[str]) -> int:
    """Write one Stage-A current-source overlay with stable JSON output.

    Args:
        argv: Command-line tokens excluding the executable path.

    Returns:
        Zero only after a local content-addressed overlay is durable.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-at-utc", required=True)
    arguments = parser.parse_args(list(argv))
    try:
        receipt = write_stage_a_snapshot(
            repo_root=REPO_ROOT,
            frozen_at_utc=arguments.frozen_at_utc,
        )
    except StageASnapshotError as error:
        print(json.dumps(
            {"status": "BLOCKED", "message": str(error)},
            ensure_ascii=False,
            sort_keys=True,
        ))
        return 2
    print(json.dumps(
        {
            "status": "STAGE_A_SNAPSHOT_WRITTEN",
            "stage_a_snapshot_id": receipt["stage_a_snapshot_id"],
            "snapshot_path": receipt["snapshot_path"],
            "freeze_receipt_id": receipt["freeze_receipt_id"],
        },
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
