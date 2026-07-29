"""Replay frozen results and traces without accepting an AI adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping

from .canonical import (
    CanonicalError,
    content_hash,
    decimal_text,
    parse_decimal,
)
from .constraints import ConstraintError, evaluate_expression
from .constraints import verify_trace_observation_values
from .records import metric_result_contract_hash
from .run_store import RunStoreError, load_frozen_run


class ReplayError(RuntimeError):
    """Report missing, tampered, or internally inconsistent frozen content."""


def _replay_trace_steps(*, trace: Mapping[str, object]) -> None:
    """Recalculate every stored generic arithmetic step in one Trace.

    Args:
        trace: Strict ExecutionTrace.

    Raises:
        ReplayError: On malformed Decimal data or a changed result.
    """
    final_steps = []
    for step in trace["steps"]:
        if step["event"] == "DERIVED_BRANCH_SELECTED":
            values = {
                key: parse_decimal(value=step["component_values"][key])
                for key in step["component_values"]
            }
            value = evaluate_expression(
                expression={"op": step["operation"], "args": step["args"]},
                values=values,
            )
            if decimal_text(value=value) != step["value"]:
                raise ReplayError("Derived Trace step cannot be recalculated")
        if step["event"] == "FORMULA_RESULT":
            final_steps.append(step)
    if trace["result"] is None:
        if final_steps:
            raise ReplayError(
                "Null Trace unexpectedly contains a final formula"
            )
        return
    if len(final_steps) != 1:
        raise ReplayError("Published numeric Trace needs one final formula")
    final = final_steps[0]
    resolved = {
        role: parse_decimal(value=final["resolved_values"][role])
        for role in final["resolved_values"]
    }
    recalculated = evaluate_expression(
        expression=final["formula"], values=resolved,
    )
    if decimal_text(value=recalculated) != trace["result"]:
        raise ReplayError("Final Trace formula cannot be recalculated")


def _verify_trace_observations(
    *,
    trace: Mapping[str, object],
    observations: Mapping[str, Mapping[str, object]]
) -> None:
    """Bind direct/reused trace events to frozen observation values.

    Args:
        trace: Strict ExecutionTrace.
        observations: Frozen observations keyed by identity.

    Raises:
        ReplayError: On a missing input or event/value mismatch.
    """
    try:
        verify_trace_observation_values(
            trace=trace, observations=observations,
        )
    except ConstraintError as error:
        raise ReplayError(str(error)) from error


def replay_frozen_results(
    *, run_dir: Path, repo_root: Path
) -> Dict[str, object]:
    """Return frozen MetricResults after validating their Trace bindings.

    Args:
        run_dir: FROZEN Run; this API accepts no network or model object.
        repo_root: Repository containing exact frozen source and Spec bytes.

    Returns:
        Ordered results, traces, and a replay content hash.

    Raises:
        ReplayError: On missing trace, duplicate identity, or tampered Run.
    """
    try:
        manifest, records, _decisions = load_frozen_run(
            run_dir=run_dir, repo_root=repo_root,
        )
    except RunStoreError as error:
        raise ReplayError("Frozen Run verification failed") from error
    results = [
        record
        for record in records
        if record["record_type"] == "METRIC_RESULT"
    ]
    traces = [
        record
        for record in records
        if record["record_type"] == "EXECUTION_TRACE"
    ]
    trace_by_id = {str(trace["trace_id"]): trace for trace in traces}
    if len(trace_by_id) != len(traces):
        raise ReplayError("Frozen Run contains duplicate Trace identity")
    observations = {
        str(record["observation_id"]): record
        for record in records
        if record["record_type"] == "VERIFIED_OBSERVATION"
    }
    for result in results:
        if result["trace_id"] not in trace_by_id:
            raise ReplayError("MetricResult Trace is missing")
        trace = trace_by_id[str(result["trace_id"])]
        if trace["metric_id"] != result["metric_id"]:
            raise ReplayError("MetricResult Trace metric differs")
        if trace["result"] != result["value"]:
            raise ReplayError("MetricResult value differs from Trace")
        if trace["result_contract_hash"] != metric_result_contract_hash(
            result=result,
        ):
            raise ReplayError("MetricResult contract differs from Trace")
        try:
            _verify_trace_observations(
                trace=trace, observations=observations,
            )
            _replay_trace_steps(trace=trace)
        except (CanonicalError, ConstraintError, KeyError, TypeError) as error:
            raise ReplayError("ExecutionTrace cannot be replayed") from error
    replay_hash = content_hash(
        value={
            "run_content_manifest_hash": manifest["content_manifest_hash"],
            "results": results,
            "traces": traces,
        }
    )
    return {
        "results": results,
        "traces": traces,
        "replay_content_hash": replay_hash,
    }
