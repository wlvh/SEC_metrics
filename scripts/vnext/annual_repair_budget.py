"""Two bounded repair slots over one immutable owner delegation and old failure.

This is a thin guard around annual_runtime's existing one-shot stage and WB-3.
The pinned GitHub delegation owns the only budget root. New stage/head/input
identities cannot create a different total allowance.
"""
from pathlib import Path
import os
import re
from .canonical import (
    canonical_json_bytes,
    content_hash,
    sha256_file,
    strict_json_file,
    strict_json_loads,
    parse_utc_timestamp,
)

ORIGINAL_MANIFEST = "docs/evidence/annual_runtime/live/live-native-manifest.json"
ORIGINAL_STAGE = "docs/evidence/annual_runtime/stage-approved-proposal.json"


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate_comment(comment, *, repository, url):
    match = re.fullmatch(
        r"https://github\.com/"
        + re.escape(repository)
        + r"/issues/28#issuecomment-([1-9][0-9]*)",
        url,
    )
    need(match is not None, "REPAIR_DELEGATION_URL_INVALID")
    need(
        comment.get("html_url") == url
        and str(comment.get("id")) == match[1]
        and comment.get("issue_url")
        == "https://api.github.com/repos/" + repository + "/issues/28"
        and comment.get("user", {}).get("login") == repository.split("/")[0]
        and comment.get("created_at") == comment.get("updated_at"),
        "REPAIR_DELEGATION_PROVENANCE_INVALID",
    )
    parse_utc_timestamp(value=comment["created_at"])
    return strict_json_loads(text=comment["body"])


def original_failure():
    from .annual_runtime import CODE_ROOT, _external

    manifest = strict_json_file(path=CODE_ROOT / ORIGINAL_MANIFEST)
    stage = strict_json_file(path=CODE_ROOT / ORIGINAL_STAGE)
    original_root = _external(Path(manifest["original_candidate_root"]))
    root = CODE_ROOT / "docs/evidence/annual_runtime/live/native-candidate"
    for relative, binding in manifest["files"].items():
        from .sources import resolve_repository_file

        for candidate_root in (
            [root, original_root] if original_root.exists() else [root]
        ):
            p = resolve_repository_file(
                repo_root=candidate_root, repo_relative_path=relative
            )
            need(
                sha256_file(path=p) == binding["sha256"]
                and p.stat().st_size == binding["size"],
                "REPAIR_ORIGINAL_FAILURE_CHANGED",
            )
    executions = list((root / "invocation_control/executions").glob("*.json"))
    need(len(executions) == 1, "REPAIR_ORIGINAL_EXECUTION_SET_INVALID")
    receipt = strict_json_file(path=executions[0])
    need(
        receipt["status"] == "FAILED_TERMINAL"
        and receipt["counters"]
        == {
            "mock_transport_invocation_count": 0,
            "paid_model_provider_call_count": 1,
            "real_model_provider_egress_count": 1,
        },
        "REPAIR_ORIGINAL_COUNTS_INVALID",
    )
    return stage, receipt


def delegation_fields(comment, *, requirement):
    from .annual_runtime import _external
    from .requirement_profile_v7 import DECISION_ID

    policy = requirement["effective_decisions"][DECISION_ID]["choice"]
    body = validate_comment(
        comment,
        repository=requirement["baseline"]["repository"]["identity"],
        url=policy["repair_budget_delegation_url"],
    )
    old, receipt = original_failure()
    need(
        body["record_type"] == "ANNUAL_REPAIR_BUDGET_DELEGATION"
        and body["approval_kind"] == "USER_DELEGATED_POLICY_AND_BUDGET_ONLY"
        and body["original_stage_id"] == old["stage_id"]
        and body["original_stage_root"] == old["stage_root"]
        and body["maximum_additional_provider_paid_sec_calls"] == [2, 2, 0]
        and body["maximum_total_provider_paid_sec_calls"] == [3, 3, 0]
        and body["automatic_retry_count"] == 0
        and body["execution_authorized_by_this_record"] is False
        and body["formal_publication_authorized"] is False
        and body["merge_authorized"] is False,
        "REPAIR_DELEGATION_SCOPE_INVALID",
    )
    return body, _external(Path(body["budget_root"])), receipt


def load_delegation(requirement):
    from .annual_runtime import _github
    from .requirement_profile_v7 import DECISION_ID

    url = requirement["effective_decisions"][DECISION_ID]["choice"][
        "repair_budget_delegation_url"
    ]
    cid = url.rsplit("-", 1)[1]
    repository = requirement["baseline"]["repository"]["identity"]
    comment = _github("repos/" + repository + "/issues/comments/" + cid)
    delegation_fields(comment, requirement=requirement)
    return comment


def counts(budget_root):
    from .annual_runtime import _external, stage_counts

    budget_root = _external(budget_root)
    total = [1, 1, 0]
    for p in (budget_root / "stages").glob("*"):
        need(
            p.name in {"1", "2"} and p.is_dir() and not p.is_symlink(),
            "REPAIR_STAGE_DIRECTORY_INVALID",
        )
        observed = stage_counts(p)
        from .sources import resolve_repository_file

        receipts = list(p.glob("candidates/*/invocation_control/executions/*.json"))
        if receipts:
            need(len(receipts) == 1, "REPAIR_EXECUTION_COUNT_UNCERTAIN")
            receipt = strict_json_file(
                path=resolve_repository_file(
                    repo_root=p,
                    repo_relative_path=receipts[0].relative_to(p).as_posix(),
                )
            )
            need(
                receipt.get("execution_receipt_id")
                == content_hash(
                    value={
                        k: v for k, v in receipt.items() if k != "execution_receipt_id"
                    }
                ),
                "REPAIR_EXECUTION_RECEIPT_CHANGED",
            )
            need(
                receipt["counters"]["real_model_provider_egress_count"] == observed[0]
                and receipt["counters"]["paid_model_provider_call_count"]
                == observed[1],
                "REPAIR_COUNT_UNCERTAIN",
            )
        elif list(p.glob("candidates/*/outcome.json")):
            need(observed == [0, 0, 0], "REPAIR_TERMINAL_RECEIPT_MISSING")
        total = [a + b for a, b in zip(total, observed)]
    need(
        total[0] <= 3 and total[1] <= 3 and total[2] == 0,
        "REPAIR_TOTAL_BUDGET_EXCEEDED",
    )
    return total


def _prior_for_second(budget_root, repair, reviewed_code):
    from .sources import resolve_repository_file

    first = budget_root / "stages/1"
    approval = strict_json_file(
        path=resolve_repository_file(
            repo_root=first, repo_relative_path="stage-approval.json"
        )
    )
    plans = list((first / "candidates").glob("*/plan.json"))
    need(len(plans) == 1, "REPAIR_FIRST_PLAN_MISSING")
    executions = list(
        (plans[0].parent / "invocation_control/executions").glob("*.json")
    )
    need(len(executions) == 1, "REPAIR_FIRST_OUTCOME_UNKNOWN")
    receipt = strict_json_file(path=executions[0])
    need(
        receipt.get("execution_receipt_id")
        == content_hash(
            value={k: v for k, v in receipt.items() if k != "execution_receipt_id"}
        ),
        "REPAIR_PRIOR_RECEIPT_INVALID",
    )
    need(
        receipt["status"] in {"FAILED_TERMINAL", "FAILED_RETRYABLE_FINAL"},
        "REPAIR_SECOND_REQUIRES_KNOWN_FAILURE",
    )
    markers = list((plans[0].parent / "invocation_control/egress").glob("*/*.json"))
    need(
        len(markers) == 1 and len(receipt["attempts"]) == 1,
        "REPAIR_PRIOR_COUNT_UNCERTAIN",
    )
    marker = strict_json_file(path=markers[0])
    need(
        marker["egress_marker_id"]
        == content_hash(
            value={k: v for k, v in marker.items() if k != "egress_marker_id"}
        )
        and receipt["attempts"][0]["egress_marker_id"] == marker["egress_marker_id"]
        and marker["execution_id"] == receipt["execution_id"]
        and marker["attempt_ordinal"] == 1
        and receipt["counters"]
        == {
            "mock_transport_invocation_count": 0,
            "paid_model_provider_call_count": 1,
            "real_model_provider_egress_count": 1,
        },
        "REPAIR_PRIOR_COUNT_UNCERTAIN",
    )
    need(
        reviewed_code["runtime_tree"]
        != approval["stage"]["reviewed_code"]["runtime_tree"],
        "REPAIR_UNCHANGED_REROLL_FORBIDDEN",
    )
    need(
        repair["previous_failure_execution_id"] == receipt["execution_id"]
        and repair["new_failure_fixed"] is True,
        "REPAIR_SECOND_FIX_EVIDENCE_REQUIRED",
    )


def proposal_fields(
    *, requirement, stage_root, reviewed_code, review, evidence_path, ordinal
):
    from .annual_regression import build_regression_receipt
    from .annual_runtime import CODE_ROOT

    need(type(ordinal) is int and ordinal in (1, 2), "REPAIR_ORDINAL_INVALID")
    need(evidence_path is not None, "REPAIR_REGRESSION_REQUIRED")
    submitted = strict_json_file(path=evidence_path)
    rebuilt = build_regression_receipt(repo_root=CODE_ROOT)
    need(
        submitted == rebuilt and rebuilt["status"] == "PASS",
        "REPAIR_REGRESSION_BINDING_INVALID",
    )
    need(
        review["repair_regression_id"] == rebuilt["receipt_id"]
        and bool(review["root_cause"])
        and review["necessity_and_business_counterexamples_reviewed"] is True,
        "REPAIR_INDEPENDENT_REVIEW_INCOMPLETE",
    )
    comment = load_delegation(requirement)
    _, root, _ = delegation_fields(comment, requirement=requirement)
    need(
        stage_root == root / "stages" / str(ordinal),
        "REPAIR_STAGE_ROOT_NOT_BUDGET_OWNED",
    )
    repair = {
        "ordinal": ordinal,
        "delegation_comment": comment,
        "regression_receipt": rebuilt,
        "root_cause": review["root_cause"],
        "previous_failure_execution_id": review.get("previous_failure_execution_id"),
        "new_failure_fixed": review.get("new_failure_fixed", False),
    }
    if ordinal == 2:
        _prior_for_second(root, repair, reviewed_code)
    return repair


def validate_stage(stage, requirement):
    from .annual_regression import verify_regression_receipt

    repair = stage["repair"]
    ordinal = repair["ordinal"]
    _, root, _ = delegation_fields(
        repair["delegation_comment"], requirement=requirement
    )
    need(
        type(ordinal) is int
        and ordinal in (1, 2)
        and stage["stage_root"] == str(root / "stages" / str(ordinal)),
        "REPAIR_STAGE_ROOT_NOT_BUDGET_OWNED",
    )
    verify_regression_receipt(repair["regression_receipt"])
    review = stage["independent_review"]
    need(
        review["repair_regression_id"] == repair["regression_receipt"]["receipt_id"]
        and review["root_cause"] == repair["root_cause"]
        and bool(repair["root_cause"])
        and review["necessity_and_business_counterexamples_reviewed"] is True,
        "REPAIR_REVIEW_REGRESSION_MISMATCH",
    )
    if ordinal == 2:
        _prior_for_second(root, repair, stage["reviewed_code"])
    counts(root)
    return root


def claim_slot(stage, plan, requirement):
    root = validate_stage(stage, requirement)
    ordinal = stage["repair"]["ordinal"]
    root.mkdir(parents=True, exist_ok=True)
    path = root / ("repair-slot-" + str(ordinal) + ".json")
    # Deliberately non-idempotent: a new head or stage cannot reuse an old slot.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError("REPAIR_SLOT_ALREADY_CONSUMED") from error
    with os.fdopen(fd, "wb") as file:
        file.write(
            canonical_json_bytes(
                value={
                    "stage_id": stage["stage_id"],
                    "plan_id": plan["plan_id"],
                    "ordinal": ordinal,
                    "delegation_url": stage["policy"]["repair_budget_delegation_url"],
                }
            )
        )
        file.flush()
        os.fsync(file.fileno())


def validate_slot(stage, plan, requirement):
    from .sources import resolve_repository_file

    root = validate_stage(stage, requirement)
    ordinal = stage["repair"]["ordinal"]
    value = strict_json_file(
        path=resolve_repository_file(
            repo_root=root, repo_relative_path="repair-slot-" + str(ordinal) + ".json"
        )
    )
    need(
        value
        == {
            "stage_id": stage["stage_id"],
            "plan_id": plan["plan_id"],
            "ordinal": ordinal,
            "delegation_url": stage["policy"]["repair_budget_delegation_url"],
        },
        "REPAIR_SLOT_BINDING_CHANGED",
    )
