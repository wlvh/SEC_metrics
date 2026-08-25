#!/usr/bin/env python3
"""Create or validate the post-attestation Stage-C packet offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.stage_c_context_packet import (  # noqa: E402
    validate_stage_c_context_attestation_packet,
)
from vnext.stage_c_context_packet import (  # noqa: E402
    write_stage_c_context_attestation_packet,
)


def main(*, argv: list[str]) -> int:
    """Run the deterministic packet workflow with no transport construction."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.validate:
        packet = validate_stage_c_context_attestation_packet(
            repo_root=REPO_ROOT,
        )
        result = {
            "stage_c_context_packet_id": packet[
                "stage_c_context_packet_id"
            ],
            "packet_status": packet["packet_status"],
            "live_ready_family_ids": packet["readiness"][
                "live_ready_family_ids"
            ],
            "current_pr_egress_counts": packet[
                "current_pr_egress_counts"
            ],
            "blockers": packet["BLOCKERS"],
        }
    else:
        result = write_stage_c_context_attestation_packet(
            repo_root=REPO_ROOT,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
