"""B10/B11 for an explicitly selected historical filing and DEI annual period.

The ordinary and historical consumers use lodging_table_source's same
read_selected_lodging_source function. Source preparation owns issuer, filing,
period and amendment decisions; the table reader receives that selection and
an explicit policy, and verifies table year, scope, currency, footnotes and
raw cell positions. No lodging function namespace or bytecode is rewritten.

Older filings retain the approved plural introduction and optional comma
policy, tried only when the standard introduction is unproven. Other failures
remain failures. This adaptation does not acquire missing originals, create
new calls or change saved Runs; upstream historical DEI preparation is a
separate consumer still being simplified.
"""
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url

from .annual_sources import saved_source
from .calculator import metric_is_applicable, withheld_metric_result
from .canonical import content_hash, sha256_file
from .historical_amendment_admission import AmendmentAdmissionError, amendment_admission
from .historical_annual_input import prepare_historical_annual_input
from . import lodging_table_source as frozen_lodging
from .lodging_table_source import POLICY_PATH, LodgingSourceError
from .normal_lodging_results import (
    SPEC_PATHS as ORDINARY_SPEC_PATHS, _spec as _ordinary_spec,
    calculate_selected_lodging_metric, SelectedLodgingCalculationError)
from .normal_annual_input_v2 import exact_json_value
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import raw_blob_record, resolve_repository_file
from .specs import compile_spec_file
from .traits import repository_company_traits

INTRODUCTION_REFUSAL = "LODGING_TABLE_PERIOD_AND_OPERATING_INTRODUCTION_UNPROVEN"
# The two forms older reports print, as two replacements in the frozen pattern;
# each must hit exactly once, so a changed frozen pattern stops this rather
# than being widened by accident.
INTRODUCTION_FORMS = (
    ("The following table presents ", "The following (?:table presents|tables present) "),
    ("(?P<year>[0-9]{4}), and (?P=year)", "(?P<year>[0-9]{4}),? and (?P=year)"))


def _older_introduction(pattern):
    for old, new in INTRODUCTION_FORMS:
        if pattern.count(old) != 1:
            raise ValueError("HISTORICAL_LODGING_INTRODUCTION_FORM_NOT_IN_THE_FROZEN_PATTERN:" + old)
        pattern = pattern.replace(old, new)
    return pattern


OLDER_INTRODUCTION_POLICY = {
    **frozen_lodging.POLICY,
    "table_introduction_pattern": _older_introduction(frozen_lodging.POLICY["table_introduction_pattern"])}
def _inspect_selected(*, policy, raw, blob, reference, filing, company_id, cik, period):
    # Historical preparation already checked the filing's DEI interval and issuer.
    # CIK remains in this adapter signature for its existing consumers; table
    # reading receives the resulting explicit selection, period and policy.
    specs = {metric: compile_spec_file(path=ROOT / path, dependency_specs={})
             for metric, path in policy["metric_specs"].items()}
    return frozen_lodging.read_selected_lodging_source(
        raw=raw, blob=blob, reference=reference, filing=filing, company_id=company_id,
        period=period, policy=policy, specs=specs)


def inspect_lodging_table_source(**arguments):
    return _inspect_selected(policy=frozen_lodging.POLICY, **arguments)


def inspect_older_introduction(**arguments):
    return _inspect_selected(policy=OLDER_INTRODUCTION_POLICY, **arguments)


def inspect_with_older_introduction(**arguments):
    """The shared inspection; older forms only when the standard introduction is unproven.

    The frozen inspector refuses with ``LODGING_MATCHING_TABLE_NOT_UNIQUE`` and
    lists why each table with the metric headers failed. The older forms are
    tried only when the introduction is among those reasons; any other refusal
    is the frozen one, raised unchanged. The retry is the whole frozen
    inspection with only the pattern replaced, so every other table's reason,
    the one-candidate rule and the competing-target rule still apply.
    """
    try:
        return inspect_lodging_table_source(**arguments)
    except LodgingSourceError as error:
        message = str(error)
        if not message.startswith("LODGING_MATCHING_TABLE_NOT_UNIQUE:") \
                or INTRODUCTION_REFUSAL not in message:
            raise
    return inspect_older_introduction(**arguments)

RECORD_TYPE = "HISTORICAL_LODGING_COMPONENT"
# The deterministic Specs the ordinary route uses, not the historical AI ones
# the policy also names: a route that compiled a different Spec would produce a
# Result under a different identity while reading the same table.
SPEC_PATHS = dict(ORDINARY_SPEC_PATHS)
SUPPORTED_METRICS = tuple(sorted(SPEC_PATHS))
# Mutable historical selection/period helpers used by the selected-year case.
# The public updater separately tracks its shared parser/calculator and lodging
# paths. These explicit additions avoid installing or hashing a historical tree.
HISTORICAL_LODGING_PROCESSING_FILES = (
    'scripts/vnext/normal_period_selection.py',
    'scripts/vnext/normal_history_catalog.py',
    'scripts/vnext/historical_annual_input.py',
    'scripts/vnext/historical_dei.py',
    'scripts/vnext/historical_fiscal_labels.py',
    'scripts/vnext/fiscal_year_labels.py',
    'scripts/vnext/normal_annual_input_v2.py',
    'scripts/vnext/normal_governance_input.py',
    'scripts/vnext/historical_amendment_admission.py',
    'scripts/vnext/annual_amendment_scope.py',
    'config/normal_period_selection_v1.json',
    'config/normal_fiscal_year_labels_v1.json',
    'config/annual_amendment_scope_v1.json',
)


class HistoricalLodgingError(ValueError):
    """A pinned lodging period that cannot be resolved from saved bytes."""


def _need(condition, reason, category=None):
    if not condition:
        error = HistoricalLodgingError(reason)
        if category is not None:
            error.category = category
        raise error


def _spec(repo_root, metric_id):
    """The ordinary route's own Spec check, reused rather than restated.

    It checks four things beyond compiling: that the installed copy equals the
    repository's, that the quality rule still names this source policy and its
    bytes, that the original AI Spec it derives from is unchanged, and that
    thirteen economic fields still agree with that original. None of those is
    about which period is being resolved, so a second copy here could only
    drift from the first.
    """
    return _ordinary_spec(repo_root, metric_id)


def resolve_historical_lodging_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                      period_selection):
    """Retain the existing component interface for historical consumers."""
    component, _ = _resolve_historical_lodging_metric(
        repo_root=repo_root, company_id=company_id, metric_id=metric_id,
        period_selection=period_selection)
    return component


def prepare_historical_lodging_case(*, repo_root: Path, company_id: str, metric_id: str,
                                    period_selection):
    """Adapt the same calculation to the shared saved-case writer, without a Run."""
    component, prepared = _resolve_historical_lodging_metric(
        repo_root=repo_root, company_id=company_id, metric_id=metric_id,
        period_selection=period_selection)
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id,
        'input_binding': {'record_type': 'HISTORICAL_SELECTED_LODGING_INPUT',
                          'prepared_input': prepared, 'component_id': component['component_id']},
        'source_records': component['source_records'], 'references': component['source_references'],
        'source_proofs': component['source_proofs'], 'admission': component['source_admission'],
        'spec_paths': {metric_id: component['spec_path']},
        'compiled_specs': {metric_id: component['compiled_spec']},
        'target_period': component['target_period'], 'expected_records': component['records'],
        'results': {metric_id: component['result']}, 'traces': {metric_id: component['trace']},
        'observations': [component['observation']] if component['observation'] is not None else [],
        'selection': component['selection']}


def prepare_historical_lodging_year_case(*, repo_root: Path, company_id: str,
                                         metric_id: str, fiscal_year: int):
    """Existing fiscal-year selection and calculation for the public updater.

    The updater owns storage, recovery and unchanged-input reuse. This adapter
    selects the requested issuer year from saved originals and returns the
    same lodging case; it never chooses the latest filing or acquires a source.
    """
    from .normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=repo_root, company_id=company_id,
                                         fiscal_year=fiscal_year)
    return prepare_historical_lodging_case(repo_root=repo_root, company_id=company_id,
        metric_id=metric_id, period_selection=selection)


def _resolve_historical_lodging_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                       period_selection):
    """Resolve B10 or B11 for the period the selection pins.

    Args:
        repo_root: Data root holding the saved originals.
        company_id: Logical company.
        metric_id: ``B10`` or ``B11``.
        period_selection: The pinned period, from ``resolve_period_selection``.

    Returns:
        The component shape ``historical_results._historical_component_run_input``
        consumes: the Result, its trace, the records behind it and the admitted
        source set.

    Raises:
        HistoricalLodgingError: When the metric is not one of the two, when the
            installed Spec or policy differ from the repository's, or when the
            ledger moves during preparation.
    """
    _need(metric_id in SPEC_PATHS,
          "HISTORICAL_LODGING_METRIC_NOT_WIRED:" + metric_id, "IMPLEMENTATION_GAP")
    root = Path(repo_root)
    installed_policy = resolve_repository_file(repo_root=root, repo_relative_path=POLICY_PATH)
    _need(installed_policy.read_bytes() == (ROOT / POLICY_PATH).read_bytes(),
          "HISTORICAL_LODGING_INSTALLED_POLICY_CHANGED", "AUTHORITY_CONFLICT")
    ledger = sha256_file(path=root / "evidence/requests_log.csv")
    spec = _spec(root, metric_id)
    prepared = prepare_historical_annual_input(repo_root=root, company_id=company_id,
                                               period_selection=period_selection)
    table_input = prepared["table_input"]
    period = table_input["target_period"]
    traits = repository_company_traits(repo_root=root, company_id=company_id)
    # The same three reads the ordinary route makes, so the Run carries the
    # inventory and the company facts the selection rests on and not only the
    # one document the value came out of.
    reader = _Sources(root, company_id, prepared["entity"])
    reader.read(submissions_url(cik=int(prepared["entity"])),
                role="sec_submissions_inventory", media_type="application/json")
    primary = reader.primary(prepared["filing"])
    reader.read(companyfacts_url(cik=int(prepared["entity"])),
                accession=prepared["filing"]["accessionNumber"], role="companyfacts",
                media_type="application/json")
    scope = {key: value for key, value in spec["compiled"]["required_claims"].items()
             if key != "period_role"}
    target = {"company_id": company_id, "period_start": period["period_start"],
              "period_end": period["period_end"], "scope": scope,
              "scope_key": scope_key(scope=scope)}
    observation, asset, limitation = None, None, None
    selection = None
    if not metric_is_applicable(applicability=spec["compiled"]["applicability"], traits=traits):
        # Reached only when the dispatcher sends a non-lodging company here.
        # The structural route owns that answer, so this refuses rather than
        # producing a second one under a different record type.
        _need(False, "HISTORICAL_LODGING_METRIC_NOT_APPLICABLE:" + company_id,
              "IMPLEMENTATION_GAP")
    try:
        if prepared["amendments"]:
            amendment_admission(repo_root=root, company_id=company_id,
                                metric_ids=[metric_id], prepared=prepared)
        _need(prepared["subject_policy"]["mode"] == "CONTINUOUS_PRIMARY",
              "HISTORICAL_LODGING_SUCCESSOR_SCOPE_NOT_IMPLEMENTED", "IMPLEMENTATION_GAP")
        saved = saved_source(repo_root=root, url=table_input["source_url"],
                             accession=table_input["accession"])
        proof = saved["proof"]
        blob = raw_blob_record(repo_root=root,
                               repo_relative_path=proof["request_repo_relative_path"],
                               media_type="text/html")
        reference = primary["source_reference"]
        _need(reference["raw_asset_id"] == blob["raw_asset_id"],
              "HISTORICAL_LODGING_PRIMARY_SOURCE_CONFLICT")
        component = inspect_with_older_introduction(
            raw=saved["raw"], blob=blob, reference=reference, filing=prepared["filing"],
            company_id=company_id, cik=prepared["entity"], period=period)
        fact = component["selection"]["facts"][metric_id]
        _need(fact["scope"] == scope and fact["period"] == period,
              "HISTORICAL_LODGING_SCOPE_OR_PERIOD_CHANGED")
        try:
            calculated = calculate_selected_lodging_metric(
                prepared=prepared, component=component, reference=reference,
                metric_id=metric_id, spec=spec, traits=traits)
        except SelectedLodgingCalculationError as error:
            raise HistoricalLodgingError(str(error)) from error
        observation, result, trace = (calculated[key]
                                     for key in ("observation", "result", "trace"))
        asset = component["derived_asset"]
        selection = calculated["selection"]
    except (AmendmentAdmissionError, HistoricalLodgingError, LodgingSourceError) as error:
        decided = isinstance(error, AmendmentAdmissionError) and str(error).startswith(
            "HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED")
        reason_code = ("APPROVED_AMENDMENT_POLICY_REFUSAL" if decided
                       else "HISTORICAL_LODGING_SOURCE_ROUTE_UNRESOLVED")
        if isinstance(error, HistoricalLodgingError) and getattr(error, "category", None) \
                == "IMPLEMENTATION_GAP":
            raise
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code=reason_code)
        limitation = {"metric_id": metric_id, "reason": str(error),
                      "category": getattr(error, "category", None) or "SOURCE_UNAVAILABLE"}
        selection = {"classification": "SOURCE_OR_IMPLEMENTATION_UNRESOLVED",
                     "reason": str(error), "reason_code": result["reason_code"]}
    proofs_by_id = {}
    for entry in [*prepared["source_proofs"],
                  *(value["proof"] for value in reader.proofs.values())]:
        key = entry["request_attempt_id"]
        _need(key not in proofs_by_id or proofs_by_id[key] == entry,
              "HISTORICAL_LODGING_REQUEST_PROOF_COLLISION")
        proofs_by_id[key] = entry
    proofs = list(proofs_by_id.values())
    admission = verify_ordinary_source_proofs(data_root=root, proofs=proofs)
    source_records = list(reader.records.values())
    references = [record for record in source_records
                  if record["record_type"] == "SOURCE_REFERENCE"]
    records = [*source_records]
    if asset is not None:
        records.append(asset)
    if observation is not None:
        records.append(observation)
    records.extend([trace, result])
    _need(sha256_file(path=root / "evidence/requests_log.csv") == ledger,
          "HISTORICAL_LODGING_LEDGER_CHANGED_DURING_PREPARATION")
    body = {"record_type": RECORD_TYPE, "schema_version": 1, "company_id": company_id,
            "metric_id": metric_id, "spec_path": SPEC_PATHS[metric_id], "compiled_spec": spec,
            "selection": selection, "limitation": limitation,
            "records": records, "source_records": source_records,
            "source_references": references,
            "source_proofs": proofs, "source_admission": admission,
            "source_set_manifests": [], "result": result, "trace": trace,
            "observation": observation, "target_period": period,
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "component_id": content_hash(value=body)}, prepared
