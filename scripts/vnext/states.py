"""Define independent vNext object states and fail-closed transitions."""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, Mapping, Set


TRANSITIONS: Dict[str, Dict[str, Set[str]]] = {
    "AI_EXTRACTION_ATTEMPT": {
        "STARTED": {"SUCCEEDED", "FAILED"},
        "SUCCEEDED": set(),
        "FAILED": set(),
    },
    "PUBLICATION_TRANSACTION": {
        "PREPARED": {"COMMITTED", "ABORTED"},
        "COMMITTED": {"SUPERSEDED"},
        "ABORTED": set(),
        "SUPERSEDED": set(),
    },
    "REVIEW_UNIT": {
        "PENDING": {"APPROVED", "REJECTED", "INVALIDATED"},
        "APPROVED": {"INVALIDATED"},
        "REJECTED": set(),
        "INVALIDATED": set(),
    },
    "RUN": {
        "OPEN": {"FROZEN", "FAILED"},
        "FROZEN": set(),
        "FAILED": set(),
    },
    "VALIDATION_RECEIPT": {
        "NOT_RUN": {"PASSED", "FAILED"},
        "PASSED": set(),
        "FAILED": set(),
    },
}

FREEZEABLE_VALIDATION_STATUSES: FrozenSet[str] = frozenset(
    TRANSITIONS["VALIDATION_RECEIPT"]
)
PUBLISHABLE_VALIDATION_STATUSES: FrozenSet[str] = frozenset({"PASSED"})


class StateError(ValueError):
    """Report an unknown or forbidden object-state transition."""


def validate_state(*, object_type: str, status: str) -> None:
    """Require one known state for an independently modeled object.

    Args:
        object_type: State-machine key such as ``RUN``.
        status: State to validate.

    Raises:
        StateError: When the object type or state is unknown.
    """
    if object_type not in TRANSITIONS:
        raise StateError("Unknown state object type: {}".format(object_type))
    if status not in TRANSITIONS[object_type]:
        raise StateError("Unknown {} state: {}".format(object_type, status))


def validate_transition(
    *, object_type: str, current_status: str, target_status: str
) -> None:
    """Reject a transition not named by the object's state machine.

    Args:
        object_type: State-machine key.
        current_status: Existing immutable-record state.
        target_status: Proposed successor state.

    Expected output:
        The function returns only for an explicitly allowed transition.
    """
    validate_state(object_type=object_type, status=current_status)
    validate_state(object_type=object_type, status=target_status)
    if target_status not in TRANSITIONS[object_type][current_status]:
        raise StateError(
            "Forbidden {} transition: {} -> {}".format(
                object_type, current_status, target_status,
            )
        )


def publication_candidate_status(
    *, results: Iterable[Mapping[str, object]]
) -> str:
    """Return batch-level publishability for migrated result records.

    Args:
        results: Metric results with explicit ``applicability`` and
            ``publication`` fields.

    Returns:
        ``BLOCKED`` when any APPLICABLE result is WITHHELD; otherwise
        ``PUBLISHABLE``. Structural non-applicability does not block.

    Raises:
        StateError: On a missing or unknown state combination.
    """
    for result in results:
        required = {"applicability", "publication"}
        if not required.issubset(result):
            raise StateError("Metric result lacks applicability/publication")
        applicability = result["applicability"]
        publication = result["publication"]
        if applicability not in {"APPLICABLE", "N_A_STRUCTURAL"}:
            raise StateError("Unknown applicability: {}".format(applicability))
        if publication not in {"PUBLISHED", "WITHHELD"}:
            raise StateError(
                "Unknown publication state: {}".format(publication)
            )
        if applicability == "APPLICABLE" and publication == "WITHHELD":
            return "BLOCKED"
    return "PUBLISHABLE"
