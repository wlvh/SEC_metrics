"""A03, A04, A09, A11, A12 and A13 for a pinned annual period, where the gate is open.

These six are gated on the ``financial`` trait. The structural route answers
the closed side - a retailer has no liquidity coverage ratio - and until this
module the open side had no historical route at all, which the frame counted
as "structural only": a metric whose only implemented answer is that it does
not apply, at the one company it does apply to.

The ordinary route (``ordinary_financial_results.resolve_current_financial_metric``)
reads the filing's own bytes through frozen inspectors - the disclosed LCR
average, the managed NIM relationship, the nonperforming-loan fact, the AUM
balance, the firmwide VaR total, international net revenue - and hands the
fact to the frozen Calculator. Its one period dependency is
``prepare_saved_annual_input``, which means the newest annual report.
Everything after that call is a function of the preparation it returns, so
this module restates the two functions with the preparation handed in and
changes nothing else: the Spec check, the inspectors, the measurement-period
rule, the failure classification and every record shape are the frozen ones,
imported rather than copied.

Two deliberate differences, both about what the pinned preparation carries:

* The ordinary preparation holds exactly three proofs (the submissions
  inventory, the primary document and the company facts). A pinned one also
  carries the proofs of a period's amendments and, for a predecessor's year,
  the primary registrant's catalog blocks, because the installed data root has
  to be able to replay the selection. Those travel with the Run; the three the
  inspectors read are identified by their URLs rather than by position, so an
  extra proof can never be read as the primary document.
* The ordinary route is handed its preparation's fiscal-year label as
  ``normal_annual_input`` computes it. The pinned preparation relabels the
  period from the issuer's own DEI and keeps the unrelabelled body as
  ``original_input``; that body is what this passes on, because it is the shape
  the ordinary route reads. For a calendar-year registrant - the only financial
  one in this frame - the two are the same.

Amendments and a successor subject are answered exactly as the ordinary route
answers them: any ``update_status`` other than ``ORIGINAL_INPUT_READY`` gives
the ordinary route's own withheld result. The approved amendment policy is not
consulted here, because the ordinary wiring of that policy does not reach this
family; widening which inputs a metric accepts is not a port's decision. (The
lodging port did consult it, and that divergence is recorded.)

What no position exercises today, measured rather than assumed:

* JPMorgan is the frame's only financial registrant and every one of its target
  periods fails period selection on the saved catalog
  (``ORDINARY_PERIOD_SELECTION_SAVED_HISTORY_INCOHERENT``), so no JPMorgan
  position reaches this module. The route is checked against the ordinary one on
  JPMorgan's latest saved filing instead, with the ordinary preparation handed
  to both.
* The source set is discovered from the registrant's main submissions
  document, as in the ordinary route and the pinned accession route. JPMorgan's
  main document lists only filings from 2025-08-15 to 2026-08-17 - its FY2024
  10-K row sits in history block 004 - so once its catalog is repaired, four of
  its five target years would still fail discovery here with
  ``Source-set references differ from submissions discovery``. That is a named
  cross-route limit, not a disclosure gap.
"""
from pathlib import Path

from sec_urls import accession_document_url, companyfacts_url, submissions_url

from .calculator import (calculate_metric, calculate_observation_metric,
                         metric_is_applicable, withheld_metric_result)
from .canonical import content_hash, sha256_bytes, sha256_file
from .deterministic_router import source_set_manifest
from .financial_results import (RESOLVER, SPEC_PATHS, _ROLES, FinancialResultError,
                                _actual_period, _fact, _failure_classification,
                                _installed_rule, _need)
from .historical_annual_input import prepare_historical_annual_input
from .historical_filing_inventory import filing_inventory
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT, NormalSourceAuthorityError
from .observations import scope_key, structured_observation
from .ordinary_source_authority import (OrdinarySourceAuthorityError,
                                        verify_ordinary_source_proofs)
from .sources import raw_blob_record, resolve_repository_file, source_reference_record
from .traits import repository_company_traits

RECORD_TYPE = "HISTORICAL_FINANCIAL_COMPONENT"
SUPPORTED_METRICS = tuple(sorted(SPEC_PATHS))
_READ_ROLES = ("sec_submissions_inventory", "target_primary", "companyfacts")


class _ProofReader:
    """The preparation's own request-proved documents, served by URL.

    The inspectors read proofs rather than a reader, so the question of which
    submissions document lists the filing is asked of the same proofs they
    will read - admitted by ``_pinned_sources`` before a byte is used.
    """

    def __init__(self, *, repo_root, prepared):
        self.repo_root, self.proofs = Path(repo_root), prepared["source_proofs"]

    def read(self, url, *, role, media_type, accession=""):
        matches = [proof for proof in self.proofs if proof["source_url"] == url]
        _need(len(matches) == 1, "NORMAL_FINANCIAL_SOURCE_SET_INCOMPLETE")
        raw = resolve_repository_file(
            repo_root=self.repo_root,
            repo_relative_path=matches[0]["request_repo_relative_path"]).read_bytes()
        return {"raw_bytes": raw, "proof": matches[0],
                "source_reference": {"document_name": matches[0]["document_name"],
                                     "source_role": role}}


def _read_proofs(*, repo_root, prepared, period_selection=None):
    """The three proofs the inspectors read, found by what they are.

    The submissions proof is the document that lists the filing: the main
    index when its recent block does, else the history block the pinned
    selection loaded that does. Without a selection - the ordinary
    preparation handed in by the regression - only the main index is asked,
    which is what the ordinary route reads.
    """
    cik = int(prepared["entity"])
    filing = prepared["filing"]
    reader = _ProofReader(repo_root=repo_root, prepared=prepared)
    main = reader.read(submissions_url(cik=cik), role="sec_submissions_inventory",
                       media_type="application/json")
    selection = period_selection or {"loaded_inventories": [main["proof"]["document_name"]]}
    listed_in = filing_inventory(reader=reader, inventory=main, period_selection=selection,
                                 cik=prepared["entity"], accession=filing["accessionNumber"])
    wanted = (listed_in["proof"]["source_url"],
              accession_document_url(cik=cik, accession=filing["accessionNumber"],
                                     document_name=filing["primaryDocument"]),
              companyfacts_url(cik=cik))
    found = []
    for url in wanted:
        matches = [proof for proof in prepared["source_proofs"] if proof["source_url"] == url]
        _need(len(matches) == 1, "NORMAL_FINANCIAL_SOURCE_SET_INCOMPLETE")
        found.append(matches[0])
    return found


def _pinned_sources(*, repo_root, company_id, prepared, period_selection=None):
    """``ordinary_financial_results._ordinary_sources`` with the preparation handed in."""
    read = _read_proofs(repo_root=repo_root, prepared=prepared,
                        period_selection=period_selection)
    try:
        admission = verify_ordinary_source_proofs(data_root=repo_root,
                                                  proofs=prepared["source_proofs"])
    except (NormalSourceAuthorityError, OrdinarySourceAuthorityError) as error:
        raise FinancialResultError("NORMAL_FINANCIAL_SOURCE_ADMISSION_FAILED:" + str(error)) from error
    records, references, raw = [], [], []
    for role, proof in zip(_READ_ROLES, read):
        media = "text/html" if role == "target_primary" else "application/json"
        blob = raw_blob_record(repo_root=repo_root,
                               repo_relative_path=proof["request_repo_relative_path"],
                               media_type=media)
        content = resolve_repository_file(
            repo_root=repo_root, repo_relative_path=proof["request_repo_relative_path"]).read_bytes()
        _need(blob["raw_asset_id"] == "sha256:" + proof["content_sha256"]
              and sha256_bytes(content=content) == proof["content_sha256"],
              "ORDINARY_SOURCE_CHANGED_AFTER_ADMISSION")
        dataset = ("SEC_SUBMISSIONS_INVENTORY" if role == "sec_submissions_inventory"
                   else "SEC_COMPANYFACTS_INVENTORY")
        reference = source_reference_record(
            raw_blob=blob, company_id=company_id, source_url=proof["source_url"],
            accession=proof["accession"] or dataset, document_name=proof["document_name"],
            source_role=role, request_attempt_id=proof["request_attempt_id"])
        records.extend([blob, reference])
        references.append(reference)
        raw.append(content)
    _need(len(references) == 3
          and references[1]["accession"] == prepared["filing"]["accessionNumber"],
          "NORMAL_FINANCIAL_SOURCE_SET_INCOMPLETE")
    filing_day = prepared["filing"]["filingDate"]
    manifest = source_set_manifest(
        company_id=company_id, source_role="target_primary", form_types=["10-K"],
        fiscal_or_date_window={"period_start": filing_day, "period_end": filing_day},
        discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1",
        inventory_source_reference=references[0], inventory_bytes=raw[0],
        ordered_source_references=[references[1]],
        cutoff_timestamp_or_pinned_submissions_attempt=references[0]["request_attempt_id"])
    bundle = {"source_bytes": raw[1], "source_reference": references[1],
              "source_set_manifest": manifest, "inventory_source_reference": references[0],
              "inventory_bytes": raw[0], "expected_cik": prepared["entity"],
              "target_period": prepared["table_input"]["target_period"]}
    return admission, records, references, bundle


def resolve_prepared_financial_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                      prepared, period_selection=None) -> dict:
    """``resolve_current_financial_metric`` with the annual preparation handed in.

    The body is the ordinary one line for line; the regression hands both the
    same preparation and requires every returned field to be equal.
    """
    path, spec, trait_hashes = _installed_rule(repo_root=repo_root, metric_id=metric_id)
    admission, source_records, references, bundle = _pinned_sources(
        repo_root=repo_root, company_id=company_id, prepared=prepared,
        period_selection=period_selection)
    traits = repository_company_traits(repo_root=ROOT, company_id=company_id)
    applicable = metric_is_applicable(applicability=spec["compiled"]["applicability"],
                                      traits=traits)
    fact, passed, value, reason = None, False, None, "TRAIT_NOT_APPLICABLE"
    if applicable:
        if prepared["update_status"] != "ORIGINAL_INPUT_READY":
            reason = "FINANCIAL_NORMAL_INPUT_REQUIRES_AMENDMENT_OR_SUBJECT_PROCESSING"
        else:
            fact, passed, value = _fact(metric_id=metric_id, bundle=bundle)
            reason = "PASS" if passed else "FINANCIAL_SOURCE_SEMANTICS_UNRESOLVED"
    annual = prepared["table_input"]["target_period"]
    actual, time_basis = _actual_period(metric_id=metric_id, annual=annual, fact=fact,
                                        applicable=applicable, passed=passed)
    scope = dict(spec["compiled"]["required_claims"])
    target = {"company_id": company_id, "period_start": actual["period_start"],
              "period_end": actual["period_end"], "scope": scope,
              "scope_key": scope_key(scope=scope)}
    input_body = {"record_type": "ORDINARY_FINANCIAL_INPUT_BINDING", "resolver": RESOLVER,
                  "metric_id": metric_id, "company_id": company_id, "prepared_input": prepared,
                  "source_proofs": prepared["source_proofs"], "source_admission": admission,
                  "source_set_manifest": bundle["source_set_manifest"],
                  "source_reference_ids": [r["source_reference_id"] for r in references],
                  "trait_authority_sha256": trait_hashes, "company_traits": traits,
                  "spec_path": path, "spec_closure_hash": spec["spec_closure_hash"],
                  "spec_file_sha256": sha256_file(path=repo_root / path),
                  "filing_period": annual, "actual_target": target,
                  "actual_target_period": actual, "measurement_time_basis": time_basis,
                  "source_fact_hash": content_hash(value=fact) if fact is not None else None,
                  "source_semantics_passed": passed, "reason_code": reason,
                  "production_authorized": False}
    binding = {**input_body, "input_binding_id": content_hash(value=input_body)}
    observations = []
    if not applicable:
        result, trace, observations = calculate_metric(
            compiled_spec=spec,
            target={**target, "accession": prepared["filing"]["accessionNumber"],
                    "entity": prepared["entity"]},
            company_traits=traits, structured_facts=[], verified_observations=[])
    elif not passed:
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code=reason)
    else:
        primary = bundle["source_reference"]
        observation = structured_observation(
            metric_id=metric_id, semantic_role=_ROLES[metric_id], company_id=company_id,
            period_start=actual["period_start"], period_end=actual["period_end"],
            scope=scope, value=value, unit=spec["compiled"]["canonical_unit"], quality="EXACT",
            source_binding={"raw_asset_id": primary["raw_asset_id"],
                            "source_reference_id": primary["source_reference_id"],
                            "accession": primary["accession"],
                            "document_name": primary["document_name"],
                            "source_role": primary["source_role"], "entity": prepared["entity"],
                            "resolver": RESOLVER, "input_binding_id": binding["input_binding_id"],
                            "source_set_manifest_id":
                                bundle["source_set_manifest"]["source_set_manifest_id"],
                            "source_fact_hash": binding["source_fact_hash"],
                            "measurement_time_basis": time_basis, "filing_period": annual,
                            "actual_measurement_period": actual})
        result, trace = calculate_observation_metric(compiled_spec=spec, target=target,
                                                    company_traits=traits,
                                                    observation=observation)
        observations = [observation]
    return {"record_type": "ORDINARY_FINANCIAL_RESOLUTION", "resolver": RESOLVER,
            "metric_id": metric_id, "company_id": company_id, "spec_path": path,
            "compiled_spec": spec, "prepared_input": prepared, "source_records": source_records,
            "source_references": references, "source_proofs": prepared["source_proofs"],
            "source_admission": admission, "input_binding": binding, "source_fact": fact,
            "company_traits": traits, "filing_period": dict(annual), "target_period": actual,
            "target": target, "observations": observations, "result": result, "trace": trace,
            "records": [*source_records, *observations, trace, result],
            "selection": {"reason_code": reason, "source_semantics_passed": passed,
                          "classification": ("STRUCTURAL" if not applicable
                                             else "VERIFIED_SOURCE_FACT" if passed
                                             else _failure_classification(fact))},
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "native_run_status": "NOT_CREATED",
            "qualification_credit": "NONE", "formal_publication_authorized": False}


def resolve_historical_financial_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                        period_selection):
    """Resolve one financial metric for the period the selection pins.

    Args:
        repo_root: Data root holding the saved originals.
        company_id: Logical company; its traits must open the ``financial`` gate.
        metric_id: One of ``SUPPORTED_METRICS``.
        period_selection: The pinned period, from ``resolve_period_selection``.

    Returns:
        The component shape ``historical_results._historical_component_run_input``
        consumes.

    Raises:
        FinancialResultError: When the metric is not one of the six, when the
            company's traits close the gate (the structural route owns that
            answer, so a second one under another record type is refused), or
            when the ledger moves during preparation.
    """
    _need(metric_id in SUPPORTED_METRICS,
          "HISTORICAL_FINANCIAL_METRIC_NOT_WIRED:" + str(metric_id), "IMPLEMENTATION_GAP")
    root = Path(repo_root)
    ledger = sha256_file(path=root / "evidence/requests_log.csv")
    _, spec, _ = _installed_rule(repo_root=root, metric_id=metric_id)
    traits = repository_company_traits(repo_root=ROOT, company_id=company_id)
    _need(metric_is_applicable(applicability=spec["compiled"]["applicability"], traits=traits),
          "HISTORICAL_FINANCIAL_METRIC_NOT_APPLICABLE:" + company_id, "IMPLEMENTATION_GAP")
    prepared = prepare_historical_annual_input(repo_root=root, company_id=company_id,
                                               period_selection=period_selection)
    resolution = resolve_prepared_financial_metric(repo_root=root, company_id=company_id,
                                                   metric_id=metric_id,
                                                   prepared=prepared["original_input"],
                                                   period_selection=period_selection)
    _need(sha256_file(path=root / "evidence/requests_log.csv") == ledger,
          "HISTORICAL_FINANCIAL_LEDGER_CHANGED_DURING_PREPARATION")
    body = {"record_type": RECORD_TYPE, "schema_version": 1, "company_id": company_id,
            "metric_id": metric_id, "period_selection": period_selection,
            "spec_path": resolution["spec_path"], "compiled_spec": resolution["compiled_spec"],
            "prepared_input": prepared, "selection": resolution["selection"],
            "source_fact": resolution["source_fact"], "input_binding": resolution["input_binding"],
            "records": resolution["records"], "source_records": resolution["source_records"],
            "source_references": resolution["source_references"],
            "source_proofs": prepared["source_proofs"],
            "source_admission": resolution["source_admission"],
            "source_set_manifests": [resolution["input_binding"]["source_set_manifest"]],
            "observations": resolution["observations"], "result": resolution["result"],
            "trace": resolution["trace"], "target_period": prepared["table_input"]["target_period"],
            "measurement_period": resolution["target_period"],
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "component_id": content_hash(value=body)}
