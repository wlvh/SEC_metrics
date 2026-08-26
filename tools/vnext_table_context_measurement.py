#!/usr/bin/env python3
"""Plan or explicitly execute the authorized one-shot table measurement."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path = [str(SCRIPTS_DIR), *sys.path]

from vnext.table_context_measurement import (  # noqa: E402
    execute_table_context_measurement,
)
from vnext.table_context_measurement import (  # noqa: E402
    issue_table_context_measurement_authorization,
)
from vnext.table_context_measurement import (  # noqa: E402
    TableContextMeasurementError,
)
from vnext.table_context_measurement import (  # noqa: E402
    write_table_context_measurement_plan,
)


def _utc_now() -> str:
    """Return one timezone-aware UTC timestamp for terminal receipts."""
    return datetime.now(tz=timezone.utc).isoformat()


def main(*, argv: Sequence[str]) -> int:
    """Run the offline planner or independently authorized real executor."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--task-contract-id", required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--task-contract-id", required=True)
    execute.add_argument("--authorization", required=True)
    execute.add_argument("--authorized-head", required=True)
    execute.add_argument("--authorized-request-sha256", required=True)
    execute.add_argument("--review-comment-url", required=True)
    execute.add_argument("--authorized-at-utc", required=True)
    arguments = parser.parse_args(list(argv))
    try:
        if arguments.command == "plan":
            result = write_table_context_measurement_plan(
                repo_root=REPO_ROOT,
                task_contract_id=arguments.task_contract_id,
            )
        else:
            authorization = issue_table_context_measurement_authorization(
                repo_root=REPO_ROOT,
                task_contract_id=arguments.task_contract_id,
                external_authorization_statement=arguments.authorization,
                authorized_repository_head=arguments.authorized_head,
                authorized_provider_request_body_sha256=(
                    arguments.authorized_request_sha256
                ),
                external_review_comment_url=arguments.review_comment_url,
                authorized_at_utc=arguments.authorized_at_utc,
            )
            result = execute_table_context_measurement(
                repo_root=REPO_ROOT,
                authorization=authorization,
                clock=_utc_now,
            )
    except TableContextMeasurementError as error:
        print(json.dumps(
            {"status": "FAILED", "error_code": error.code},
            ensure_ascii=False,
            sort_keys=True,
        ))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
