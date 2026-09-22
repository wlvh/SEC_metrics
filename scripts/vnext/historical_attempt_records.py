"""What a batch recorded about positions that produced no Run.

A refusal leaves no Run receipt, so a position an approved policy declined and
a position nothing ever reached both arrive at the same place in the coverage
summary, and the table reads "never run" about a determinate blocker.

The first attempt at this asked the route again. That was wrong twice over.
It re-computed business results inside the reporting path - measured, six
calls to the calculator for one position that can prepare - which is the
boundary the summary was refactored to establish; and "the route prepares this
today" does not answer "was this attempted then". A position that ran
yesterday and failed at freeze leaves no result receipt, and today's fixed code
prepares it happily; a position nothing ever touched can be refused by today's
policy. Those are two different facts and neither implies the other.

So this reads what the batch recorded. An attempt record is a statement about
the past, made by the runner, and it is reported as such:

* a record of a failure is accepted as a record of that attempt and never as a
  claim about the current implementation;
* a record cannot confer run status. Only a verified receipt does that, so a
  record claiming a Run with no receipt behind it is a reportable problem;
* a position with no record says the distinction is unproven rather than
  implying nothing was attempted.

The execution identity of an attempt is not in these records - the batch
driver writes the position, the stage and the route's own error, not the
Requirement closure - so this does not invent one. It reports the closure the
report itself is scoped to and says where that came from.

This module reads JSON and nothing else. It creates no Run, executes no route
and makes no SEC or model request.
"""
import json
from pathlib import Path

RECORD_TYPE = "HISTORICAL_NATIVE_RUN_MATRIX"
ARTIFACT_NAME = "native-run-matrix.json"
FAILED_STAGE = "FAILED"
# Stages the runner writes for a position that did produce a Run. A record
# carrying one of these is not evidence of a Run here: the receipt is.
RAN_STAGES = ("NATIVE_RUN_FROZEN", "PUBLIC_ROW")
_POSITION_FIELDS = ("company_id", "report_end", "metric_id", "stage")


class AttemptRecordError(ValueError):
    """An attempt artifact is not the shape this reader accepts."""


def _need(condition, reason):
    if not condition:
        raise AttemptRecordError(reason)


def collect_attempt_records(*, attempts_root: Path) -> dict:
    """Index every batch artifact under a root by position.

    Args:
        attempts_root: Directory holding batch outputs. Each batch writes one
            ``native-run-matrix.json``; nested directories are searched so a
            root holding one directory per company-period works unchanged.

    Returns:
        ``records`` maps (company_id, metric_id, report_end) to the recorded
        position, with the artifact it came from named on each. ``unreadable``
        names artifacts that could not be read, and ``rejected`` names records
        whose stage this reader does not recognise - neither is dropped
        silently, because a summary that quietly ignores a malformed record
        reports the same thing as one that had no record at all.
    """
    root = Path(attempts_root)
    _need(root.is_dir() and not root.is_symlink(),
          "ATTEMPT_ROOT_IS_NOT_A_DIRECTORY:" + str(root))
    records, unreadable, rejected = {}, [], []
    for path in sorted(root.rglob(ARTIFACT_NAME)):
        if path.is_symlink():
            unreadable.append({"artifact": str(path), "refusal": "ARTIFACT_IS_A_SYMLINK"})
            continue
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            unreadable.append({"artifact": str(path),
                               "refusal": "ARTIFACT_UNREADABLE:" + str(error)[:160]})
            continue
        if artifact.get("record_type") != RECORD_TYPE:
            unreadable.append({"artifact": str(path),
                               "refusal": "ARTIFACT_RECORD_TYPE_IS_NOT_A_RUN_MATRIX"})
            continue
        for position in artifact.get("positions") or []:
            if not all(key in position for key in _POSITION_FIELDS):
                rejected.append({"artifact": str(path), "position": position,
                                 "refusal": "POSITION_FIELDS_INCOMPLETE"})
                continue
            stage = position["stage"]
            if stage != FAILED_STAGE and stage not in RAN_STAGES:
                rejected.append({"artifact": str(path),
                                 "position": {key: position[key] for key in _POSITION_FIELDS},
                                 "refusal": "POSITION_STAGE_UNRECOGNISED:" + str(stage)})
                continue
            key = (position["company_id"], position["metric_id"], position["report_end"])
            records.setdefault(key, []).append({**position, "artifact": str(path)})
    return {"records": records, "unreadable": unreadable, "rejected": rejected}


def attempt_for_position(*, records, company_id: str, metric_id: str, report_end: str,
                         report_closure=None):
    """The recorded attempt for one position, or None when nothing recorded it.

    A position recorded more than once - the same coordinate attempted in two
    batches under the same root - keeps every record rather than choosing one,
    because choosing would report whichever artifact sorted first.
    """
    found = records.get((company_id, metric_id, report_end))
    if not found:
        return None
    failures = [entry for entry in found if entry["stage"] == FAILED_STAGE]
    ran = [entry for entry in found if entry["stage"] in RAN_STAGES]
    return {
        "record_type": "HISTORICAL_ATTEMPT_RECORD",
        "recorded_by": "the batch runner, about a past attempt",
        "re_derived_now": False,
        "records": len(found),
        "artifacts": sorted({entry["artifact"] for entry in found}),
        # What the record actually holds is kept apart from what is derived
        # from it. The batch wrote a case, an error and an error type; it did
        # not write a stop stage or an execution version. Presenting a derived
        # stage beside a recorded error, in one flat shape, makes the two read
        # as equally observed - which is the same mistake as reporting a
        # closure the record never carried.
        "failed_records": [{"recorded": {"case": entry.get("case"),
                                         "error": entry.get("error"),
                                         "error_type": entry.get("error_type"),
                                         "selection_id": entry.get("selection_id")},
                            "inferred": {"stop_stage": _stop_stage(entry.get("error_type")),
                                         "from": "the recorded error type alone",
                                         "recorded_by_the_batch": False}}
                           for entry in failures],
        "records_claiming_a_run": len(ran),
        "execution_version_recorded_by_the_batch": None,
        "why_the_execution_version_is_unproven": (
            "the batch artifacts carry the position, the case and the route's own "
            "error; they do not carry the Requirement closure or engine the attempt "
            "ran under. A later batch can record it; it cannot be recovered from "
            "these records."),
        "report_context": {
            "requirement_closure_hash": report_closure,
            "this_is": ("the closure this report was scoped to, supplied by its "
                        "caller. It is context for reading the record, not a fact "
                        "the record asserted about the attempt."),
        },
    }


def _stop_stage(error_type):
    """Where the attempt probably stopped, derived from the recorded error type.

    The runner records the exception class, which separates the two stages it
    can stop in - assembling the Run's inputs, or creating and freezing the Run
    - without the runner having labelled them. That makes this an inference
    from one recorded field, not a stage the batch observed, and callers are
    handed it under an ``inferred`` key for that reason.
    """
    if error_type is None:
        return None
    if error_type in {"HistoricalRunError"}:
        return "RUN_CREATION_OR_FREEZE"
    return "RUN_INPUT_ASSEMBLY"
