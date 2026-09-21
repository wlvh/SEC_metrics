"""Metrics a company's own registry traits make structurally non-applicable.

A liquidity coverage ratio at a retailer is not an implementation gap and not
a disclosure gap - it is a metric that does not apply. Eighty-two positions of
the five-year frame were reported as HISTORICAL_ROUTE_NOT_WIRED for exactly
that reason, which reads as "we have not built this yet" for a question the
Spec's own applicability and the registry's own traits already answer. Six
metrics are gated on ``financial`` and none of the companies whose periods are
reachable is a bank; two are gated on ``lodging`` and eight of the ten are not
hotels.

This route decides nothing. ``calculate_metric`` refuses to consume a single
fact for a metric whose traits do not match and returns the N_A_STRUCTURAL
result itself; what this supplies is the pinned period, the company and the
admitted source set the Run has to be bound to. When the metric *is*
applicable it refuses, by name - because then a real route is what is missing,
and answering "not applicable" would be a false statement about the issuer
rather than a missing implementation.

The Run still carries the period's own admitted sources. A structural result
takes no value from any of them, which is why no amendment question arises
here: an amendment is evidence about whether an original filing's *inputs*
still stand, and this reads no input. What the sources do is bind the Run to
the year that was asked for, so the record is a statement about that period
rather than a free-floating assertion.
"""
from pathlib import Path

from .calculator import calculate_metric, metric_is_applicable
from .canonical import content_hash, sha256_file
from .historical_annual_input import prepare_historical_annual_input
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import raw_blob_record, source_reference_record
from .specs import compile_spec_file
from .traits import repository_company_traits

RECORD_TYPE = "HISTORICAL_STRUCTURAL_RESULT"
# Every catalog/metrics Spec whose applicability is gated on a company trait.
# Declared rather than discovered so that a Spec losing its gate is a loud
# failure here instead of a metric quietly becoming eligible for this route.
SPEC_PATHS = {
    "A03": "catalog/metrics/A03_liquidity_coverage_ratio.md",
    "A04": "catalog/metrics/A04_net_interest_margin.md",
    "A09": "catalog/metrics/A09_nonperforming_loan_ratio.md",
    "A11": "catalog/metrics/A11_assets_under_management.md",
    "A12": "catalog/metrics/A12_trading_exposure.md",
    "A13": "catalog/metrics/A13_geographic_exposure.md",
    "B10": "catalog/metrics/B10_occupancy.md",
    "B11": "catalog/metrics/B11_revpar.md",
}
SUPPORTED_METRICS = tuple(sorted(SPEC_PATHS))


class HistoricalStructuralError(ValueError):
    """A structural applicability limitation, never a disclosure conclusion."""

    def __init__(self, reason, category="IMPLEMENTATION_GAP"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="IMPLEMENTATION_GAP"):
    if not condition:
        raise HistoricalStructuralError(reason, category)


def structurally_not_applicable(*, repo_root: Path, company_id: str, metric_id: str):
    """Whether this company's traits put this metric outside its own gate.

    Returns False for a metric this route does not carry, so a caller asking
    "is there a route here" gets one answer rather than an exception it has to
    interpret.
    """
    if metric_id not in SPEC_PATHS:
        return False
    spec = compile_spec_file(path=Path(repo_root) / SPEC_PATHS[metric_id],
                             dependency_specs={})["compiled"]
    traits = list(repository_company_traits(repo_root=Path(repo_root), company_id=company_id))
    return not metric_is_applicable(applicability=spec["applicability"], traits=traits)


def resolve_historical_structural_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                         period_selection):
    """One pinned period's structural non-applicability, with its sources."""
    repo_root = Path(repo_root)
    _need(metric_id in SPEC_PATHS,
          "HISTORICAL_STRUCTURAL_METRIC_NOT_WIRED:" + str(metric_id))
    spec_path = SPEC_PATHS[metric_id]
    spec = compile_spec_file(path=repo_root / spec_path, dependency_specs={})
    compiled = spec["compiled"]
    _need(compiled["metric_id"] == metric_id,
          "HISTORICAL_STRUCTURAL_SPEC_METRIC_CHANGED:" + spec_path)
    # A Spec with no trait gate can never be structurally non-applicable, so
    # reaching this route with one means the declaration and the file disagree.
    _need(bool(compiled["applicability"]["all"]) or bool(compiled["applicability"]["none"]),
          "HISTORICAL_STRUCTURAL_SPEC_HAS_NO_TRAIT_GATE:" + metric_id)
    _need(not compiled["dependencies"],
          "HISTORICAL_STRUCTURAL_SPEC_HAS_DEPENDENCIES:" + metric_id)
    traits = list(repository_company_traits(repo_root=repo_root, company_id=company_id))
    _need(not metric_is_applicable(applicability=compiled["applicability"], traits=traits),
          "HISTORICAL_STRUCTURAL_METRIC_IS_APPLICABLE_HERE:" + company_id + ":" + metric_id)
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection)
    admission = verify_ordinary_source_proofs(data_root=repo_root,
                                              proofs=prepared["source_proofs"])
    period = prepared["table_input"]["target_period"]
    scope = compiled["required_claims"]
    target = {"company_id": company_id, "entity": prepared["entity"],
              "accession": prepared["filing"]["accessionNumber"],
              "period_start": period["period_start"], "period_end": period["period_end"],
              "scope": scope, "scope_key": scope_key(scope=scope)}
    result, trace, observations = calculate_metric(compiled_spec=spec, target=target,
                                                   company_traits=traits,
                                                   structured_facts=[],
                                                   verified_observations=[])
    # The calculator owns this decision; asserting what it returned is how a
    # future change that made this route produce a value instead of a
    # non-applicability becomes a failure rather than a surprise.
    _need(result["applicability"] == "N_A_STRUCTURAL" and result["value"] is None
          and result["reason_code"] == "TRAIT_NOT_APPLICABLE" and not observations,
          "HISTORICAL_STRUCTURAL_RESULT_IS_NOT_STRUCTURAL:" + metric_id)
    source_records, references = [], []
    for proof in prepared["source_proofs"]:
        blob = raw_blob_record(
            repo_root=repo_root, repo_relative_path=proof["request_repo_relative_path"],
            media_type=("application/json" if proof["document_name"].endswith(".json")
                        else "text/html"))
        reference = source_reference_record(
            raw_blob=blob, company_id=company_id, source_url=proof["source_url"],
            accession=proof["accession"] or "SUBMISSIONS-" + prepared["entity"],
            document_name=proof["document_name"], source_role="supporting_input",
            request_attempt_id=proof["request_attempt_id"])
        source_records.extend([blob, reference])
        references.append(reference)
    source_records = list({content_hash(value=r): r for r in source_records}.values())
    body = {"record_type": RECORD_TYPE, "company_id": company_id, "metric_id": metric_id,
            "period_selection": period_selection, "spec_path": spec_path,
            "spec_origin": {"spec_path": spec_path}, "compiled_spec": spec,
            "company_traits": traits, "applicability": compiled["applicability"],
            "prepared_input": prepared, "target_period": period, "target": target,
            "source_records": source_records,
            "source_references": [r for r in source_records
                                  if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": prepared["source_proofs"], "source_admission": admission,
            "source_set_manifests": [], "claims": [], "observations": [],
            "dependency_specs": {}, "dependency_records": [],
            "selection": {"status": "N_A_STRUCTURAL", "category": "SPEC_TRAIT_GATE",
                          "reason_code": result["reason_code"],
                          "disclosure_absence_asserted": False,
                          "value_taken_from_any_filing": False},
            "result": result, "trace": trace,
            "records": list({content_hash(value=r): r
                             for r in [*source_records, trace, result]}.values()),
            "resolver_sha256": sha256_file(path=Path(__file__)),
            "native_run_status": "NOT_CREATED", "current_latest_verified": False,
            "latest_restated_values_used": False,
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}
    return {**body, "component_id": content_hash(value=body)}
