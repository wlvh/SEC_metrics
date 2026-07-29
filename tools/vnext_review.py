"""Append a context-bound HUMAN ReviewDecision to one OPEN vNext Run.

The reviewer explicitly provides identity, decision, reason, UTC time, and the
reviewed unit. Claims are derived from that immutable ReviewUnit: APPROVE means
all required claims, while REJECT means none. The command never infers an OS
identity and never modifies Candidate values or publication state.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.review import (  # noqa: E402
    create_review_decision,
    effective_review_decision,
)
from vnext.run_store import (  # noqa: E402
    append_review_decision,
    load_open_run,
)


class ReviewCliError(RuntimeError):
    """Report ambiguous units or stale decision chains."""


def append_human_decision(
    *,
    run_dir: Path,
    review_unit_hash: str,
    decision: str,
    reviewer_id: str,
    decided_at_utc: str,
    reason: str,
    supersedes_decision_id: Optional[str],
) -> Dict[str, object]:
    """Create and append one decision after validating the chain tip.

    Args:
        run_dir: OPEN Run root.
        review_unit_hash: Exact immutable unit reviewed by the human.
        decision: APPROVE or REJECT.
        reviewer_id: Stable opaque HUMAN ID.
        decided_at_utc: Explicit UTC timestamp.
        reason: Human rationale.
        supersedes_decision_id: Existing effective tip or ``None``.

    Returns:
        Appended strict ReviewDecision.

    Raises:
        ReviewCliError: On an absent/ambiguous unit or stale supersedes tip.
    """
    _manifest, records, decisions = load_open_run(run_dir=run_dir)
    units = [
        record
        for record in records
        if record["record_type"] == "REVIEW_UNIT"
        and record["review_unit_hash"] == review_unit_hash
    ]
    if len(units) != 1:
        raise ReviewCliError("Review unit is missing or ambiguous")
    bound = [
        item
        for item in decisions
        if item["review_unit_hash"] == review_unit_hash
    ]
    if bound:
        tip = effective_review_decision(review_unit=units[0], decisions=bound,)
        if supersedes_decision_id != tip["review_decision_id"]:
            raise ReviewCliError(
                "supersedes_decision_id is not the effective tip"
            )
    elif supersedes_decision_id is not None:
        raise ReviewCliError("First ReviewDecision cannot supersede a record")
    unit = units[0]
    required_claims = dict(unit["required_claims"])
    approved_claims = required_claims if decision == "APPROVE" else {}
    created = create_review_decision(
        review_unit=unit,
        decision=decision,
        approved_claims=approved_claims,
        required_claims=required_claims,
        reviewer_id=reviewer_id,
        decided_at_utc=decided_at_utc,
        reason=reason,
        supersedes_decision_id=supersedes_decision_id,
    )
    append_review_decision(run_dir=run_dir, decision=created)
    return created


def main(*, argv: Sequence[str]) -> int:
    """Parse explicit review inputs and append one immutable decision.

    Args:
        argv: Command-line arguments excluding executable name.

    Returns:
        Zero after a successful append.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--review-unit-hash", required=True)
    parser.add_argument(
        "--decision", choices=("APPROVE", "REJECT"), required=True
    )
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--decided-at-utc", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--supersedes-decision-id")
    arguments = parser.parse_args(list(argv))
    decision = append_human_decision(
        run_dir=Path(arguments.run_dir),
        review_unit_hash=arguments.review_unit_hash,
        decision=arguments.decision,
        reviewer_id=arguments.reviewer_id,
        decided_at_utc=arguments.decided_at_utc,
        reason=arguments.reason,
        supersedes_decision_id=arguments.supersedes_decision_id,
    )
    print(decision["review_decision_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
