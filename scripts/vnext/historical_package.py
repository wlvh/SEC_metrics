"""Install one selected historical period's inputs and replay them cold.

The installation reuses the ordinary immutable installer, so a historical data
root receives exactly the same authority, rule and source bytes a current one
does, under the same source-admission and checkpoint rules. Nothing here copies
executable code into the data root or nominates a new authority.

What this module deliberately does NOT do yet is create a native Run record
store entry. A Run carries an explicit Requirement identity, and
``load_run_requirement_snapshot`` resolves that identity through
``requirement_profile.PROFILE_ENGINES`` and then calls
``validate_execution_authority``. Registering a new Requirement generation means
changing ``scripts/vnext/requirement_profile.py``, which is inside
``issue_28_v13``'s 360-file execution authority; that would break every current
ordinary Run. Reusing ``issue_28_v13`` instead is not possible either, because
its ``replay_case`` re-prepares the latest period and would reject a historical
binding. So the Run identity question is raised on Issue #47 rather than
answered by quietly widening a frozen contract.

Until then the historical package still proves the properties a Run would: an
external data root, an installed source checkpoint, byte-identical rebuilding
inside that root, and a cold replay from a new process that reproduces the same
input identity, source identity, period and values.
"""
from pathlib import Path

from .canonical import content_hash, sha256_file
from .historical_results import prepare_historical_run_input
from .normal_run_v3 import REQUIREMENT_ID, _external, _install_case_inputs
from .normal_source_authority import ROOT
from .requirements import load_requirement_snapshot


BINDING_DIRECTORY = "historical_period_bindings"
BINDING_RECORD_TYPE = "HISTORICAL_PERIOD_INPUT_BINDING"
RECEIPT_RECORD_TYPE = "HISTORICAL_PERIOD_INSTALL_RECEIPT"


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def historical_binding(*, prepared, requirement):
    """Identity of one installed historical input, including its period."""
    body = {"record_type": BINDING_RECORD_TYPE, "schema_version": 1,
            "kind": prepared["kind"], "primary_metric_id": prepared["primary_metric_id"],
            "company_id": prepared["company_id"],
            "period_selection_id": prepared["period_selection"]["selection_id"],
            "target_report_end": prepared["period_selection"]["target_report_end"],
            "input_id": prepared["input_id"],
            "source_admission": prepared["source_admission"],
            "spec_paths": prepared["spec_paths"],
            "spec_closure_hashes": {key: value["spec_closure_hash"]
                                    for key, value in prepared["compiled_specs"].items()},
            "target_period": prepared["target_period"],
            "requirement_id": requirement["requirement_id"],
            "requirement_closure_hash": requirement["requirement_closure_hash"],
            "native_run_created": False, "production_authorized": False}
    return {**body, "binding_id": content_hash(value=body)}


def install_historical_inputs(*, data_root, company_id, metric_id, period_selection,
                              source_root=None):
    """Install one historical period's inputs into a separate data root.

    The input is prepared from the source root, installed immutably, and then
    rebuilt from the data root alone. The two bindings must be equal, which is
    what proves the installation carried the period, the sources and the rules
    rather than a summary of them.
    """
    data_root = _external(Path(data_root))
    source_root = ROOT if source_root is None else _external(Path(source_root))
    _need(source_root != data_root and source_root not in data_root.parents
          and data_root not in source_root.parents,
          "HISTORICAL_SOURCE_AND_OUTPUT_OVERLAP")
    prepared = prepare_historical_run_input(repo_root=source_root, company_id=company_id,
                                            metric_id=metric_id,
                                            period_selection=period_selection)
    requirement = load_requirement_snapshot(snapshot_dir=ROOT / "requirements" / REQUIREMENT_ID)
    case = {"source_proofs": prepared["source_proofs"], "primary_metric_id": metric_id}
    _install_case_inputs(data_root=data_root, source_root=source_root, company_id=company_id,
                         case=case, requirement=requirement)
    rebuilt = prepare_historical_run_input(repo_root=data_root, company_id=company_id,
                                           metric_id=metric_id,
                                           period_selection=period_selection)
    binding = historical_binding(prepared=prepared, requirement=requirement)
    _need(historical_binding(prepared=rebuilt, requirement=requirement) == binding,
          "HISTORICAL_IMPORTED_INPUT_CHANGED")
    from sec_http import write_immutable_bytes
    from .normal_run_v3 import _bytes
    write_immutable_bytes(path=data_root / BINDING_DIRECTORY / (binding["binding_id"][7:] + ".json"),
                          content=_bytes(binding))
    receipt = {"record_type": RECEIPT_RECORD_TYPE, "schema_version": 1,
               "company_id": company_id, "primary_metric_id": metric_id,
               "binding_id": binding["binding_id"],
               "period_selection_id": period_selection["selection_id"],
               "installed_requirement_id": requirement["requirement_id"],
               "installer_sha256": sha256_file(path=Path(__file__)),
               "native_run_created": False,
               "calls": {"provider": 0, "paid": 0, "sec": 0},
               "production_authorized": False}
    return {"binding": binding, "prepared": prepared, "installed": rebuilt,
            "receipt": {**receipt, "receipt_id": content_hash(value=receipt)},
            "data_root": str(data_root)}


def replay_historical_inputs(*, data_root, company_id, metric_id, binding_id):
    """Rebuild an installed historical input from the data root alone.

    The saved binding is read back, the period selection it names is re-derived
    from the installed sources, and the rebuilt binding must hash to the same
    identity. Nothing in the saved record is trusted as an answer.
    """
    from .canonical import strict_json_file
    from .sources import resolve_repository_file
    data_root = _external(Path(data_root))
    saved = strict_json_file(path=resolve_repository_file(
        repo_root=data_root,
        repo_relative_path=BINDING_DIRECTORY + "/" + binding_id[7:] + ".json"))
    _need(saved["record_type"] == BINDING_RECORD_TYPE and saved["binding_id"] == binding_id
          and saved["company_id"] == company_id and saved["primary_metric_id"] == metric_id,
          "HISTORICAL_BINDING_IDENTITY_REQUIRED")
    from .normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=data_root, company_id=company_id,
                                         report_end=saved["target_report_end"])
    _need(selection["selection_id"] == saved["period_selection_id"],
          "HISTORICAL_PERIOD_SELECTION_CHANGED")
    requirement = load_requirement_snapshot(snapshot_dir=data_root / "requirements" / REQUIREMENT_ID)
    rebuilt = prepare_historical_run_input(repo_root=data_root, company_id=company_id,
                                           metric_id=metric_id, period_selection=selection)
    binding = historical_binding(prepared=rebuilt, requirement=requirement)
    _need(binding == saved, "HISTORICAL_INSTALLED_INPUT_CHANGED")
    return {"binding": binding, "input": rebuilt, "period_selection": selection,
            "result": rebuilt["primary_result"],
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}
