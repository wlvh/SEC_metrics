"""Create and validate a native Run for one pinned historical annual period.

The Run machinery is the existing one. ``run_store.create_run``,
``append_run_record``, ``validate_and_freeze_run`` and the mechanical open-Run
replay are imported unchanged, and so are the Specs, the Calculator output and
the source records that the historical adapters already produce. What this
module owns is three things the ordinary route cannot express for a past year:

* the Run declares ``issue_47_v1``, whose execution authority names the
  historical modules, instead of a Requirement that does not mention them;
* the input binding written beside the Run carries the period selection, so a
  replay restores the same year rather than re-deriving the latest one;
* ``replay_case`` rebuilds from the pinned selection, which is precisely what
  ``normal_run_v3.replay_case`` cannot do - it re-prepares the latest period
  and would reject a historical binding as changed.

It is a successor file because ``scripts/vnext/normal_run_v3.py`` is byte-bound
by the ``issue_28_v13`` rule set. Reaching this module from ``run_store``
requires one further ``elif`` on the Run's own ``requirement_id``, in the same
place and the same shape as the existing ``issue_28_v14`` branch; that edit is
delivered as a patch rather than made here, because ``run_store.py`` is inside
two execution authorities.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
from .historical_package import historical_binding
from .historical_results import prepare_historical_run_input
from .normal_annual_input_v2 import exact_json_value
from .normal_period_selection import restore_period_selection
from .normal_run_v3 import _external, _install_case_inputs
from .normal_source_authority import ROOT
from .requirements import load_requirement_snapshot
from .sources import resolve_repository_file
from .traits import repository_company_traits


REQUIREMENT_ID = "issue_47_v1"
PREFIX = "run:historical-period:"
BINDING_DIRECTORY = "historical_period_bindings"


class HistoricalRunError(ValueError):
    """A Run wiring limitation; never a financial or disclosure conclusion."""


def _need(condition, reason):
    if not condition:
        raise HistoricalRunError(reason)


def _bytes(value):
    return (json.dumps(exact_json_value(value), ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _requirement(repo_root):
    return load_requirement_snapshot(snapshot_dir=Path(repo_root) / "requirements"
                                     / REQUIREMENT_ID)


def install_historical_run_inputs(*, data_root, company_id, metric_id, period_selection,
                                  source_root=None):
    """Install one pinned period's inputs under the historical Requirement.

    Identical in shape to the ordinary installer and reusing it: the same
    immutable copy, the same source admission, the same rebuild-and-compare.
    The Requirement it installs is the historical one, so the data root ends up
    carrying the historical modules' own bytes as execution authority.
    """
    data_root = _external(Path(data_root))
    source_root = ROOT if source_root is None else _external(Path(source_root))
    _need(source_root != data_root and source_root not in data_root.parents
          and data_root not in source_root.parents, "HISTORICAL_RUN_SOURCE_AND_OUTPUT_OVERLAP")
    prepared = prepare_historical_run_input(repo_root=source_root, company_id=company_id,
                                            metric_id=metric_id,
                                            period_selection=period_selection)
    requirement = _requirement(source_root)
    case = {"source_proofs": prepared["source_proofs"], "primary_metric_id": metric_id}
    _install_case_inputs(data_root=data_root, source_root=source_root, company_id=company_id,
                         case=case, requirement=requirement)
    rebuilt = prepare_historical_run_input(repo_root=data_root, company_id=company_id,
                                           metric_id=metric_id,
                                           period_selection=period_selection)
    binding = _binding(rebuilt, requirement)
    _need(_binding(prepared, requirement) == binding, "HISTORICAL_RUN_IMPORTED_INPUT_CHANGED")
    from sec_http import write_immutable_bytes
    write_immutable_bytes(path=data_root / BINDING_DIRECTORY / (binding["binding_id"][7:] + ".json"),
                          content=_bytes(binding))
    return {"binding": binding, "installed": rebuilt, "requirement": requirement,
            "data_root": str(data_root), "calls": {"provider": 0, "paid": 0, "sec": 0},
            "production_authorized": False}


def _binding(prepared, requirement):
    """The installed input's identity, including the period it is pinned to."""
    return historical_binding(prepared=prepared, requirement=requirement)


def _text_execution(*, data_root, company_id, metric_id, prepared, requirement=None,
                    traits=None, derivation_only=False):
    """Compute one text metric's result from the installed sources.

    Every step is the current route's: the candidate builder, the evidence
    check, the review-unit builder, ``create_system_review_decision`` and
    ``replay_text_result`` are imported unchanged. What is explicit here is that
    the input is the pinned period's own filing rather than the latest one.
    """
    from datetime import datetime, timezone

    from .historical_text_input import prepare_historical_business_text_input
    from .historical_text_results import shared_source_preparation, text_api
    from .review import create_system_review_decision

    rebuilt = prepare_historical_business_text_input(
        repo_root=data_root, company_id=company_id, metric_id=metric_id,
        period_selection=prepared["period_selection"])
    _need(rebuilt["input_binding"]["input_binding_id"]
          == prepared["component"]["input_binding_id"],
          "HISTORICAL_TEXT_RUN_INPUT_BINDING_CHANGED")
    api, review_builder = text_api(metric_id)
    spec = prepared["compiled_specs"][metric_id]
    arguments = {"compiled_spec": spec, **rebuilt["text_arguments"]}
    # The candidate is derived three times here - once directly, once inside
    # build_text_evidence and once inside replay_text_result - and each
    # derivation parsed the same immutable bytes again. The derivations stay;
    # the parse is shared for the length of this one execution. Nothing outside
    # this block reuses anything, so run_store's cold replay re-parses from the
    # original evidence exactly as before.
    with shared_source_preparation():
        candidate = api.create_deterministic_text_candidate(**arguments)
        evidence = api.build_text_evidence(candidate=candidate, **arguments)
        unit, assets = review_builder(compiled_spec=spec, candidate=candidate,
                                      evidence_check=evidence,
                                      source_bindings=arguments["source_references"])
        if derivation_only:
            return {"candidate": candidate, "evidence": evidence, "review_unit": unit}
        decision = create_system_review_decision(
            review_unit=unit, required_claims=spec["compiled"]["required_claims"],
            decided_at_utc=datetime.now(timezone.utc).isoformat(), requirement=requirement)
        result, trace, observations = api.replay_text_result(
            company_traits=traits, candidate=candidate, evidence_check=evidence,
            review_unit=unit, review_decisions=[decision], **arguments)
    return {"records": [*prepared["records"], candidate, evidence, unit],
            "terminal_records": [*observations, trace, result],
            "review_unit": unit, "assets": assets, "decision": decision, "result": result}


def create_historical_run(*, data_root, run_dir, company_id, metric_id, binding_id,
                          freeze=False):
    """Create one native Run for an installed historical period.

    Nothing is recomputed from a summary: the input is rebuilt from the data
    root through the same adapters, and the Run is written only if the rebuilt
    binding is byte-identical to the one the installation recorded.
    """
    from .historical_text_results import shared_source_preparation
    from .run_store import create_run, append_run_record, validate_and_freeze_run, \
        load_frozen_run, _mechanically_replay_open_run, write_review_assets, \
        append_review_decision
    data_root, run_dir = _external(Path(data_root)), _external(Path(run_dir))
    _need(not run_dir.exists(), "HISTORICAL_RUN_PATH_EXISTS")
    with shared_source_preparation():
        return _create_historical_run(
            data_root=data_root, run_dir=run_dir, company_id=company_id,
            metric_id=metric_id, binding_id=binding_id, freeze=freeze,
            create_run=create_run, append_run_record=append_run_record,
            validate_and_freeze_run=validate_and_freeze_run,
            load_frozen_run=load_frozen_run,
            _mechanically_replay_open_run=_mechanically_replay_open_run,
            write_review_assets=write_review_assets,
            append_review_decision=append_review_decision)


def _create_historical_run(*, data_root, run_dir, company_id, metric_id, binding_id,
                           freeze, create_run, append_run_record, validate_and_freeze_run,
                           load_frozen_run, _mechanically_replay_open_run,
                           write_review_assets, append_review_decision):
    """The body of one creation, inside one shared-parse scope.

    A D02 creation prepares the same source set sixteen times: the execution,
    the authority re-derivation, the text-context rebuild and the mechanical
    replay of the open Run each derive the candidate again, and each one parsed
    the same immutable bytes again - eighty parse calls on one document.

    Every derivation is kept. What the scope removes is re-parsing bytes that
    cannot have changed inside one creation. The independent check that does
    not share anything is the one that matters: a cold read in a separate
    process enters no scope and re-parses from the original evidence.
    """
    case = replay_case(data_root=data_root, manifest=None, binding_id=binding_id,
                       company_id=company_id, metric_id=metric_id)
    requirement = case["requirement"]
    traits = repository_company_traits(repo_root=data_root, company_id=company_id)
    prepared = case["input"]
    text = None
    if prepared["kind"] == "TEXT":
        # The binding cannot carry the filing's bytes, so they are read again
        # from the data root here. The review decision is created now rather
        # than at preparation time because it binds this Requirement, which only
        # the Run factory holds.
        text = _text_execution(data_root=data_root, company_id=company_id,
                               metric_id=metric_id, prepared=prepared,
                               requirement=requirement, traits=traits)
    create_run(run_dir=run_dir, run_id=PREFIX + binding_id[7:], company_id=company_id,
               company_traits=traits, target_period=prepared["target_period"],
               source_references=prepared["source_references"],
               missing_required_source_roles=[],
               spec_file_hashes={p: sha256_file(path=data_root / p)
                                 for p in prepared["spec_paths"].values()},
               requirement_hashes=requirement["hashes"],
               requirement_id=requirement["requirement_id"],
               requirement_closure_hash=requirement["requirement_closure_hash"],
               artifact_requirement_generation="EXPLICIT_REQUIREMENT_V1")
    seen = {}
    written = prepared["records"] if text is None else text["records"]
    for record in written:
        identity = content_hash(value=record)
        _need(identity not in seen or seen[identity] == record,
              "HISTORICAL_RUN_RECORD_COLLISION")
        if identity not in seen:
            append_run_record(run_dir=run_dir, record=record)
            seen[identity] = record
    if text is not None:
        write_review_assets(run_dir=run_dir, review_unit=text["review_unit"],
                            review_context_bytes=text["assets"]["review_context_bytes"],
                            rendered_review_bytes=text["assets"]["rendered_review_bytes"])
        append_review_decision(run_dir=run_dir, decision=text["decision"])
        for record in text["terminal_records"]:
            append_run_record(run_dir=run_dir, record=record)
    if freeze:
        validate_and_freeze_run(run_dir=run_dir, repo_root=data_root)
        manifest, stored, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
    else:
        manifest, stored, _ = _mechanically_replay_open_run(
            run_dir=run_dir, repo_root=data_root, require_complete_results=True)
    # A structured case carried its result through the binding; a text case
    # produced one here, so take whichever this case actually has.
    result = prepared["primary_result"] if text is None else text["result"]
    _need(result in stored, "HISTORICAL_RUN_RESULT_CHANGED")
    return {"manifest": manifest, "result": result, "binding": case["binding"],
            "period_selection": case["period_selection"], "requirement_id": REQUIREMENT_ID,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "new_calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}


def replay_case(*, data_root, manifest, spec=None, binding_id=None, company_id=None,
                metric_id=None):
    """Rebuild one historical Run's case from the data root alone.

    Called both when the Run is created and, through ``run_store``'s dispatch on
    the Run's own ``requirement_id``, whenever that Run is validated afterwards.
    The saved binding names the period; the selection is re-derived from the
    installed sources and must hash back to the identity the binding recorded.
    """
    data_root = _external(Path(data_root))
    if manifest is not None:
        _need(manifest.get("requirement_id") == REQUIREMENT_ID
              and str(manifest["run_id"]).startswith(PREFIX),
              "HISTORICAL_RUN_IDENTITY_REQUIRED")
        binding_id = "sha256:" + str(manifest["run_id"])[len(PREFIX):]
        company_id = manifest["company_id"]
    _need(bool(binding_id) and bool(company_id), "HISTORICAL_RUN_BINDING_REQUIRED")
    saved = strict_json_file(path=resolve_repository_file(
        repo_root=data_root,
        repo_relative_path=BINDING_DIRECTORY + "/" + binding_id[7:] + ".json"))
    _need(saved["binding_id"] == binding_id and saved["company_id"] == company_id
          and (metric_id is None or saved["primary_metric_id"] == metric_id),
          "HISTORICAL_RUN_BINDING_IDENTITY_REQUIRED")
    selection = restore_period_selection(
        repo_root=data_root, company_id=company_id,
        target_report_end=saved["target_report_end"],
        requested_fiscal_year=saved["requested_fiscal_year"])
    _need(selection["selection_id"] == saved["period_selection_id"],
          "HISTORICAL_RUN_PERIOD_SELECTION_CHANGED")
    # The ordinary historical installer writes its bindings into this same
    # directory under ``issue_28_v13``. Such a record would be rebuilt here
    # against ``issue_47_v1``'s rules and fail below as an unexplained content
    # change; the manifest check above only covers the Run's own claim, never
    # the binding's. This sits after the period check rather than before it so
    # that a record which does not rebuild its own period is reported as
    # corrupt by whichever reader picks it up, instead of the diagnosis
    # depending on which Requirement happened to read it.
    _need(saved["requirement_id"] == REQUIREMENT_ID,
          "HISTORICAL_RUN_BINDING_BELONGS_TO_ANOTHER_REQUIREMENT")
    requirement = _requirement(data_root)
    rebuilt = prepare_historical_run_input(repo_root=data_root, company_id=company_id,
                                           metric_id=saved["primary_metric_id"],
                                           period_selection=selection)
    _need(_binding(rebuilt, requirement) == saved, "HISTORICAL_RUN_INSTALLED_INPUT_CHANGED")
    if manifest is not None:
        _need(manifest["target_period"] == rebuilt["target_period"]
              and manifest["source_references"] == rebuilt["source_references"]
              and manifest["requirement_closure_hash"] == requirement["requirement_closure_hash"]
              and manifest["spec_file_hashes"] == {p: sha256_file(path=data_root / p)
                                                   for p in rebuilt["spec_paths"].values()},
              "HISTORICAL_RUN_SOURCE_SPEC_OR_PERIOD_CHANGED")
    if spec is not None:
        _need(rebuilt["compiled_specs"].get(spec["compiled"]["metric_id"]) == spec,
              "HISTORICAL_RUN_SPEC_NOT_IN_GRAPH")
    observations = [r for r in rebuilt["records"]
                    if r["record_type"] == "VERIFIED_OBSERVATION"]
    return {"binding": saved, "input": rebuilt, "period_selection": selection,
            "requirement": requirement, "compiled_specs": rebuilt["compiled_specs"],
            "kind": rebuilt["kind"], "primary_metric_id": rebuilt["primary_metric_id"],
            "source_records": rebuilt["source_records"],
            "expected_records": rebuilt["records"], "target_period": rebuilt["target_period"],
            "results": rebuilt["results"], "traces": rebuilt["traces"],
            "observations": observations}


def prepare_text_contexts(*, repo_root, manifest, records, compiled_specs, **unused):
    """Hand ``run_store`` the bytes a text observation has to be replayed from.

    The counterpart of ``normal_run_v3.prepare_text_contexts``, and the reason a
    seventh registration hunk exists: the text arguments carry the filing's
    bytes, which no Run record can hold, so the store asks the Requirement's own
    module to produce them again. The candidate is re-derived and compared first,
    so the bytes handed back are the ones that Run was actually built from.
    """
    candidates = [r for r in records if r["record_type"] == "DETERMINISTIC_TEXT_CANDIDATE"]
    if not candidates:
        return {}
    _need(len(candidates) == len(compiled_specs) == 1,
          "HISTORICAL_RUN_TEXT_EXACT_SET_REQUIRED")
    spec = next(iter(compiled_specs.values()))
    case = replay_case(data_root=repo_root, manifest=manifest)
    _need(case["kind"] == "TEXT", "HISTORICAL_RUN_TEXT_ROUTE_REQUIRED")
    from .historical_text_input import prepare_historical_business_text_input
    from .historical_text_results import text_api
    metric_id = spec["compiled"]["metric_id"]
    rebuilt = prepare_historical_business_text_input(
        repo_root=repo_root, company_id=case["input"]["company_id"], metric_id=metric_id,
        period_selection=case["period_selection"])
    arguments = {"compiled_spec": spec, **rebuilt["text_arguments"]}
    api, _ = text_api(metric_id)
    expected = api.create_deterministic_text_candidate(**arguments)
    _need(candidates[0] == expected, "HISTORICAL_RUN_TEXT_CANDIDATE_CHANGED")
    return {expected["candidate_hash"]: arguments}


def validate_run_authority(*, repo_root, manifest, records, compiled_specs):
    """Re-derive a historical Run's whole case and compare it to what it holds.

    This is the function ``run_store`` reaches for a Run that declares
    ``issue_47_v1``. It is the historical counterpart of
    ``normal_run_v3.validate_normal_run_authority`` and applies the same two
    checks: the exact Spec set, and the complete computation graph.
    """
    case = replay_case(data_root=repo_root, manifest=manifest)
    if compiled_specs is not None:
        _need(compiled_specs == case["compiled_specs"], "HISTORICAL_RUN_EXACT_SPEC_SET_REQUIRED")
    if records is None:
        return case
    source_records = [r for r in records if r["record_type"] in {"RAW_BLOB", "SOURCE_REFERENCE"}]
    _need(sorted(source_records, key=lambda r: content_hash(value=r))
          == sorted(case["source_records"], key=lambda r: content_hash(value=r)),
          "HISTORICAL_RUN_SOURCE_RECORD_SET_CHANGED")
    if case["kind"] == "TEXT":
        # A text case computes its result inside the Run factory, so
        # expected_records cannot carry it and comparing against them would
        # always fail. What this authority owns is that the Run's candidate,
        # evidence check and review unit are exactly what re-deriving from this
        # data root produces. The observations beneath them are then bound to
        # that same unit by run_store's own text replay, and the trace and
        # result to those observations, so nothing is taken on trust - the
        # chain is just anchored one record higher.
        derived = _text_execution(data_root=repo_root,
                                  company_id=case["input"]["company_id"],
                                  metric_id=case["primary_metric_id"],
                                  prepared=case["input"], derivation_only=True)
        for key, record_type in (("candidate", "DETERMINISTIC_TEXT_CANDIDATE"),
                                 ("evidence", "EVIDENCE_CHECK"),
                                 ("review_unit", "REVIEW_UNIT")):
            present = [r for r in records if r["record_type"] == record_type]
            _need(present == [derived[key]],
                  "HISTORICAL_RUN_TEXT_DERIVATION_CHANGED:" + record_type)
        result = [r for r in records if r["record_type"] == "METRIC_RESULT"]
        _need(len(result) == 1 and result[0].get("value_kind") == "TEXT_V1"
              and result[0]["metric_id"] == case["primary_metric_id"],
              "HISTORICAL_RUN_TEXT_RESULT_SHAPE_CHANGED")
        return case
    kinds = {"DETERMINISTIC_VERIFIED_CLAIM", "VERIFIED_OBSERVATION", "EXECUTION_TRACE",
             "METRIC_RESULT"}
    expected = {content_hash(value=r): r for r in case["expected_records"]
                if r["record_type"] in kinds}
    actual = [r for r in records if r["record_type"] in kinds]
    _need(sorted(actual, key=lambda r: content_hash(value=r))
          == [expected[key] for key in sorted(expected)],
          "HISTORICAL_RUN_COMPLETE_COMPUTATION_GRAPH_CHANGED")
    return case
