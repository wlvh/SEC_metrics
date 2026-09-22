"""B10 and B11 for a pinned annual period, from the filing's own statistics table.

Occupancy and RevPAR are the two metrics this repository answers from a table
in the annual report itself rather than from XBRL. The ordinary route already
does that deterministically - ``lodging_table_source`` rebuilds the whole table
set, matches the scope contract against the table's own headers and geometry,
and reads the reported figure - so this route is the same arithmetic on a
different filing.

One rule is replaced and it is the only one: the ordinary source preparation
calls ``prepare_saved_annual_input``, which means the newest annual report.
Everything downstream of that already takes the filing and the period as
arguments - ``inspect_lodging_table_source`` re-derives the source's own annual
period from its bytes and refuses if it disagrees with the period it was given
- so pointing it at a pinned filing is a substitution, not a reimplementation.

What was measured before writing it: the ordinary chain's answer for the one
lodging company in this repository. Marriott's FY2025 gives B10 = 0.693 and
B11 = 128.8 USD, both EXACT and PUBLISHED, both from ``table_000011``, with
``ai_response_used`` false. A historical route that produced a different value,
or the same value from a different table, would be a different route wearing
this one's name, and the regression asserts the whole tuple rather than the
number.

Amendments go through the approved policy like every other historical route:
B10 and B11 are statement-class inputs and are not among the nine metric IDs
the policy does not cover, so a period carrying an amendment is decided rather
than refused on sight.

What this does not do: reach a value where the target filing's own original is
not saved. B10 and B11 read only the target filing - no prior period, no
accession index - so they are the cheapest historical metrics in the set, but
a period whose primary document is missing still produces a named source gap.
"""
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url

from .annual_update import saved_source
from .calculator import (calculate_observation_metric, metric_is_applicable,
                         withheld_metric_result)
from .canonical import content_hash, sha256_file
from .historical_amendment_admission import AmendmentAdmissionError, amendment_admission
from .historical_annual_input import prepare_historical_annual_input
from .lodging_table_source import (POLICY_PATH, LodgingSourceError,
                                   inspect_lodging_table_source)
from .normal_lodging_results import SPEC_PATHS as ORDINARY_SPEC_PATHS, _spec as _ordinary_spec
from .normal_annual_input_v2 import exact_json_value
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .observations import scope_key, structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import raw_blob_record, resolve_repository_file
from .specs import compile_spec_file
from .traits import repository_company_traits

RECORD_TYPE = "HISTORICAL_LODGING_COMPONENT"
# The deterministic Specs the ordinary route uses, not the historical AI ones
# the policy also names: a route that compiled a different Spec would produce a
# Result under a different identity while reading the same table.
SPEC_PATHS = dict(ORDINARY_SPEC_PATHS)
SUPPORTED_METRICS = tuple(sorted(SPEC_PATHS))


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
        component = inspect_lodging_table_source(
            raw=saved["raw"], blob=blob, reference=reference, filing=prepared["filing"],
            company_id=company_id, cik=prepared["entity"], period=period)
        fact = component["selection"]["facts"][metric_id]
        _need(fact["scope"] == scope and fact["period"] == period,
              "HISTORICAL_LODGING_SCOPE_OR_PERIOD_CHANGED")
        amount = fact["source_witnesses"]["amount"]
        binding = {"raw_asset_id": reference["raw_asset_id"],
                   "source_reference_id": reference["source_reference_id"],
                   "source_role": reference["source_role"],
                   "document_name": reference["document_name"],
                   "accession": reference["accession"], "entity": prepared["entity"],
                   "form": prepared["filing"]["form"],
                   "filed": prepared["filing"]["filingDate"],
                   "derived_asset_id": component["derived_asset"]["derived_asset_id"],
                   "table_locator": amount["locator"], "reported_raw_text": amount["raw_text"],
                   "reported_value": fact["reported_value"],
                   "reported_unit": fact["reported_unit"],
                   "source_witnesses": fact["source_witnesses"],
                   "source_component_id": component["component_id"],
                   "period_basis": fact["period_basis"],
                   "ordinary_source_policy_hash": component["policy_hash"]}
        observation = structured_observation(
            metric_id=metric_id, semantic_role=fact["semantic_role"], company_id=company_id,
            period_start=period["period_start"], period_end=period["period_end"], scope=scope,
            value=fact["value"], unit=fact["unit"], quality="EXACT", source_binding=binding)
        result, trace = calculate_observation_metric(compiled_spec=spec, target=target,
                                                    company_traits=traits,
                                                    observation=observation)
        asset = component["derived_asset"]
        selection = {"classification": "DETERMINISTIC_REPORTED_TABLE",
                     "reason_code": result["reason_code"],
                     "table_id": component["selection"]["table_id"],
                     "source_component_id": component["component_id"],
                     "period_basis": fact["period_basis"], "ai_response_used": False,
                     "qualification_credit": False}
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
    return {**body, "component_id": content_hash(value=body)}
