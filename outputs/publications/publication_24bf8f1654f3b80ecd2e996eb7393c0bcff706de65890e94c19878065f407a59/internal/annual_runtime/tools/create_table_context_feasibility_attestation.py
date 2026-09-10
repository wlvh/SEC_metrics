#!/usr/bin/env python3
"""Create or validate the exact lodging context attestation offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.table_context_attestation import (  # noqa: E402
    validate_table_context_feasibility_attestation,
)
from vnext.table_context_attestation import (  # noqa: E402
    write_table_context_feasibility_attestation,
)


def main(*, argv: list[str]) -> int:
    """Run the deterministic no-network attestation workflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--task-contract-id",
        choices=(
            "lodging_occupancy_table_v2",
            "lodging_revpar_table_v2",
        ),
        default="lodging_occupancy_table_v2",
    )
    arguments = parser.parse_args(argv)
    if arguments.validate:
        attestation = validate_table_context_feasibility_attestation(
            repo_root=REPO_ROOT,
            task_contract_id=arguments.task_contract_id,
        )
        result = {
            "attestation_id": attestation["attestation_id"],
            "source_measurement_evidence_id": attestation[
                "source_measurement_evidence_id"
            ],
            "actual_prompt_tokens": attestation["actual_prompt_tokens"],
            "context_budget_tokens": attestation["context_budget_tokens"],
            "qualification_credit": attestation["qualification_credit"],
            "qualification_response_reuse_eligible": attestation[
                "qualification_response_reuse_eligible"
            ],
        }
    else:
        result = write_table_context_feasibility_attestation(
            repo_root=REPO_ROOT,
            task_contract_id=arguments.task_contract_id,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
