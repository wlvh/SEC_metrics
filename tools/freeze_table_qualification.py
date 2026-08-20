"""Create the offline WB-4/5/6 table qualification freeze receipt.

The CLI calls ``vnext.table_qualification_freeze`` only.  It performs local
round-trip measurement and deterministic WB-3 mock regressions, writes no SEC
ledger row, opens no model-provider socket, and never runs qualification.
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

from vnext.table_qualification_freeze import (  # noqa: E402
    TableQualificationFreezeError,
)
from vnext.table_qualification_freeze import (  # noqa: E402
    write_table_qualification_freeze_receipt,
)


def main(*, argv: Sequence[str]) -> int:
    """Parse offline freeze arguments and emit one stable JSON result.

    Args:
        argv: CLI tokens excluding the executable path.

    Returns:
        Zero only when the content-addressed offline receipt was created.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-commit", required=True)
    parser.add_argument("--frozen-at-utc", required=True)
    arguments = parser.parse_args(list(argv))
    try:
        receipt = write_table_qualification_freeze_receipt(
            repo_root=REPO_ROOT,
            freeze_commit=arguments.freeze_commit,
            frozen_at_utc=arguments.frozen_at_utc,
        )
    except TableQualificationFreezeError as error:
        print(json.dumps(
            {
                "status": "BLOCKED",
                "error_code": type(error).__name__,
                "message": str(error),
            },
            ensure_ascii=False,
            sort_keys=True,
        ))
        return 2
    print(json.dumps(
        {
            "status": (
                "D07_DECISION_REQUIRED"
                if receipt["d07_decision_required"]
                else "FROZEN"
            ),
            "receipt_id": receipt["table_qualification_freeze_receipt_id"],
            "receipt_path": receipt["receipt_path"],
            "authorized_family_ids": receipt["wb6_task_contracts"][
                "authorized_family_ids"
            ],
            "maximum_estimated_input_tokens": receipt[
                "wb4_compact_transport"
            ]["maximum_estimated_input_tokens"],
            "real_model_provider_egress_count": receipt["provider_state"][
                "qualification_cycle_real_model_egress_count"
            ],
            "paid_model_provider_call_count": receipt["provider_state"][
                "qualification_cycle_paid_model_call_count"
            ],
            "real_sec_egress_count": receipt["provider_state"][
                "qualification_cycle_sec_egress_count"
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
