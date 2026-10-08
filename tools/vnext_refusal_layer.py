"""Say which layer refused a tampered Run, not merely that something did.

A negative that only records "it was refused" proves less than it looks. The
first attempt at the text negatives on this branch was refused six times out of
six by the frozen-file seal, and the second attempt three times out of six by
schema validation — in both cases every semantic check the case existed to
exercise never ran, and "all refused" read exactly like success.

Excluding one wrong explanation is not the same as confirming the right one, so
this classifies a refusal to the layer that produced it and lets a case declare
which layer it meant to reach. A case blocked earlier is recorded as
``inner_check_not_covered``: not a pass, not evidence the inner check is broken,
just untested by that input.
"""
import re

# Ordered outermost first: a Run is opened, its bytes are sealed, its records
# must parse and validate, its graph must agree, and only then do the
# Requirement's own rules speak.
LAYERS = (
    ("FROZEN_FILE_SEAL", (r"records_file_hash", r"Frozen Run file hash mismatch",
                          r"manifest_file_hash")),
    ("RECORD_SCHEMA", (r"JSONL record is invalid", r"Record is invalid",
                       r"required field", r"unknown field")),
    ("RECORD_GRAPH", (r"ExecutionTrace is absent", r"observation exact set differs",
                      r"foreign unit binding", r"Review decisions contain",
                      r"is absent", r"differs from original-byte review")),
    ("REQUIREMENT_AUTHORITY", (r"^HISTORICAL_RUN_", r"^ORDINARY_INTEGRATED_",
                               r"^NORMAL_CURRENT_", r"^B13_")),
    ("TEXT_PROTOCOL", (r"Text observation protocol", r"Native text input replay",
                       r"Text Evidence differs", r"Text review lacks")),
)


def classify(reason):
    """The outermost layer whose signature the reason matches."""
    if not reason:
        return "NONE"
    for layer, patterns in LAYERS:
        for pattern in patterns:
            if re.search(pattern, reason):
                return layer
    return "UNCLASSIFIED"


def attribute(*, attempts):
    """Annotate each attempt with the layer that answered and whether it was the one meant.

    ``attempts`` are mappings with ``case``, ``refused``, ``reason`` and
    ``expected_layer``. A control declares ``expected_layer`` of ``NONE`` and
    must not be refused.
    """
    annotated, covered, missed = [], [], []
    for attempt in attempts:
        actual = classify(attempt.get("reason"))
        expected = attempt.get("expected_layer", "UNCLASSIFIED")
        control = expected == "NONE"
        hit = (not attempt["refused"]) if control else (actual == expected)
        entry = {**attempt, "actual_layer": actual, "reached_expected_layer": hit}
        if not control:
            (covered if hit else missed).append(attempt["case"])
        annotated.append(entry)
    return {"attempts": annotated,
            "layers_reached": sorted({e["actual_layer"] for e in annotated
                                      if e.get("expected_layer") != "NONE"}),
            "cases_reaching_their_layer": covered,
            "inner_check_not_covered": missed,
            "every_case_reached_its_layer": not missed}
