"""Render the public row for one native historical Run.

Not a second projector. The presentation policy, the row and evidence field
sets, ``projector._project_result``, the evidence builders and the period label
are the ordinary ones, imported unchanged. What differs is one thing, and it is
the reason a successor file exists at all: the ordinary renderer re-prepares
the company's *latest* annual input and requires the Run's fiscal label to
equal it, which is exactly what a past year cannot satisfy. Here the annual
input comes from the Run's own pinned selection.

Structured routes only. A historical text or capacity route is not wired, and
this refuses those explicitly rather than rendering something it cannot
validate.
"""
import json
from pathlib import Path

from . import projector, publication
from .canonical import content_hash, sha256_file, strict_json_file
from .historical_annual_input import prepare_historical_annual_input
from .historical_run import REQUIREMENT_ID, replay_case
from .normal_numeric_projection import (_period_label, _objects, _filings,
                                        _selected_financial_locators)
from .normal_source_authority import ROOT
from .ordinary_projection import POLICY_PATH, _claim_evidence
from .run_store import _mechanically_replay_open_run, load_frozen_run


class HistoricalProjectionError(ValueError):
    """A rendering limitation; never a financial or disclosure conclusion."""


def _need(condition, reason):
    if not condition:
        raise HistoricalProjectionError(reason)


def _claims(prepared):
    claims = {}
    for value in _objects(prepared):
        if value.get("record_type") == "DETERMINISTIC_VERIFIED_CLAIM":
            key = value["verified_claim_id"]
            _need(key not in claims or claims[key] == value,
                  "HISTORICAL_PROJECTION_CLAIM_CONFLICT")
            claims[key] = value
    return claims


def render_historical_run(*, data_root: Path, run_dir: Path, frozen=False):
    """Build one public row and its evidence from a historical Run.

    The Run is loaded through the same store, its whole case is re-derived from
    the data root, and the row's fiscal label comes from the selected filing's
    own annual input rather than from whatever the company filed most recently.
    """
    if frozen:
        manifest, records, _ = load_frozen_run(run_dir=run_dir, repo_root=data_root)
    else:
        manifest, records, _ = _mechanically_replay_open_run(
            run_dir=run_dir, repo_root=data_root, require_complete_results=True)
    _need(manifest["requirement_id"] == REQUIREMENT_ID,
          "HISTORICAL_PROJECTION_REQUIREMENT_CHANGED")
    case = replay_case(data_root=data_root, manifest=manifest)
    prepared = case["input"]
    metric = case["primary_metric_id"]
    _need(case["kind"] == "STRUCTURED", "HISTORICAL_PROJECTION_TEXT_ROUTE_NOT_WIRED")
    results = [r for r in records
               if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == metric]
    _need(len(results) == 1, "HISTORICAL_PROJECTION_PRIMARY_RESULT_NOT_UNIQUE")
    result = results[0]
    _need(result.get("value_kind") != "TEXT_V1", "HISTORICAL_PROJECTION_TEXT_ROUTE_NOT_WIRED")
    spec = case["compiled_specs"][metric]
    policy = strict_json_file(path=ROOT / POLICY_PATH)
    _need(policy["record_type"] == "ORDINARY_INTEGRATED_PRESENTATION_POLICY"
          and policy["schema_version"] == 1 and policy["production_authorized"] is False
          and policy["confidence_inferred"] is False,
          "HISTORICAL_PRESENTATION_POLICY_CHANGED")
    item = policy["metrics"][metric]
    projection = {**item["projection"],
                  **item["spec_overrides"].get(prepared["spec_paths"][metric], {})}
    same_unit = (projection["unit"] == spec["compiled"]["canonical_unit"]
                 and projection["value_multiplier"] == "1")
    percent_unit = (spec["compiled"]["canonical_unit"] == "ratio"
                    and projection["unit"] == "percent"
                    and projection["value_multiplier"] == "100"
                    and spec["compiled"]["legacy_projection"].get("unit") == "percent"
                    and spec["compiled"]["legacy_projection"].get("value_multiplier") == "100")
    _need(same_unit or percent_unit, "HISTORICAL_PROJECTION_UNIT_CHANGED")
    company = next(c for c in projector._load_registry(repo_root=data_root)
                   if c["company_id"] == manifest["company_id"])
    # The pinned period's own annual input, not the company's latest one.
    annual = prepare_historical_annual_input(repo_root=data_root,
                                             company_id=manifest["company_id"],
                                             period_selection=case["period_selection"])
    period = annual["table_input"]["target_period"]
    _need(period["fiscal_year"] == manifest["target_period"]["fiscal_year"]
          and period["period_end"] == manifest["target_period"]["period_end"],
          "HISTORICAL_PROJECTION_PERIOD_CHANGED")
    indexes = projector._record_indexes(runs=[(manifest, records)])
    trace = indexes["traces"][result["trace_id"]]
    ordered, _ = projector._ordered_observations(trace=trace, observations=indexes["observations"],
                                                 projection=projection)
    view = {"compiled": {"name": item["name"] or spec["compiled"]["name"],
                         "reported_unit": spec["compiled"]["reported_unit"],
                         "legacy_projection": projection}}
    baseline = {key: "" for key in publication.METRIC_FIELDS}
    baseline.update(company=company["display_name"], cik=company["primary_cik"],
                    metric_id=metric, metric_name=view["compiled"]["name"],
                    unit=projection["unit"], status=result["quality"],
                    source_class=projection["source_class"],
                    formula=projection.get("formula", ""),
                    period_start=result["period_start"], period_end=result["period_end"],
                    fiscal_year=str(period["fiscal_year"]), notes=projection.get("notes", ""),
                    form=annual["filing"]["form"], filed_date=annual["filing"]["filingDate"])
    if result["publication"] == "WITHHELD":
        row, evidence = dict(baseline), []
        row.update(status="WITHHELD")
    else:
        row, evidence, _ = projector._project_result(
            result=result, trace=trace, company=company, spec=view, baseline_row=baseline,
            indexes=indexes, fiscal_year=str(period["fiscal_year"]),
            metric_fields=publication.METRIC_FIELDS)
    evidence = []
    claims = _claims(prepared)
    financial_locators = _selected_financial_locators(metric, None)
    for observation in ordered:
        binding = observation["source_binding"]
        identifiers = binding.get("verified_claim_ids",
                                  binding.get("matched_verified_claim_ids", []))
        _need(bool(identifiers), "HISTORICAL_PROJECTION_OBSERVATION_WITHOUT_CLAIMS")
        for identity in identifiers:
            _need(identity in claims, "HISTORICAL_PROJECTION_SELECTED_CLAIM_MISSING")
            evidence.append(_claim_evidence(claims[identity], observation, result, company,
                                            projection, indexes, str(period["fiscal_year"])))
    label, note = _period_label(result, period)
    row["fiscal_period"] = label
    row["notes"] = " ".join([row.get("notes", ""), note,
                             "Native state: " + result["publication"]
                             + "; reason: " + result["reason_code"] + ".",
                             "Pinned historical period; the current value comes from the "
                             "selected filing and the prior value from the prior selected "
                             "filing. No latest-restated view is applied."])
    row["context_or_dimension"] = json.dumps(
        {"scope": trace["calculation_target"]["scope"], "measurement_kind": label,
         "annual_filing_period": period,
         "period_selection_id": case["period_selection"]["selection_id"],
         "target_report_end": case["period_selection"]["target_report_end"],
         "requested_fiscal_year": case["period_selection"]["requested_fiscal_year"],
         "source_reference_ids": [r["source_reference_id"]
                                  for r in prepared["source_references"]]},
        ensure_ascii=False, sort_keys=True)
    filings = _filings(prepared)
    accessions = list(dict.fromkeys(e["accession"] for e in evidence))
    known = [filings[a] for a in accessions if a in filings]
    row.update(accession=";".join(accessions), confidence="")
    if known:
        row.update(form=";".join(dict.fromkeys(f["form"] for f in known)),
                   filed_date=";".join(dict.fromkeys(f["filingDate"] for f in known)))
    if annual["fiscal_year_label_resolution"]["metadata_conflict_retained"]:
        row["notes"] += (" Fiscal label follows the explicit issuer definition; original "
                         "DEI/Company Facts labels remain in the source binding.")
    if prepared["source_admission"]["source_credit"] == "RECORDED_TEST_ONLY":
        row["notes"] += (" Recorded source refresh test using preexisting SEC content; "
                         "no new SEC acquisition.")
    _need(set(row) == set(publication.METRIC_FIELDS)
          and all(set(e) == set(publication.EVIDENCE_FIELDS) for e in evidence),
          "HISTORICAL_PUBLIC_ROW_SCHEMA_CHANGED")
    receipt = {"record_type": "HISTORICAL_PERIOD_ROW_RECEIPT",
               "status": "FROZEN_CANDIDATE" if frozen else "VERIFIED_OPEN_PREVIEW",
               "run_id": manifest["run_id"], "run_status": manifest["status"],
               "requirement_id": manifest["requirement_id"],
               "result_id": result["result_id"], "primary_metric_id": metric,
               "period_selection_id": case["period_selection"]["selection_id"],
               "source_required_metric_ids": sorted(case["compiled_specs"]),
               "presentation_policy_sha256": sha256_file(path=ROOT / POLICY_PATH),
               "renderer_sha256": sha256_file(path=Path(__file__)),
               "row_hash": content_hash(value=row),
               "evidence_hash": content_hash(value=evidence),
               "evidence_count": len(evidence),
               "source_validation": "FULL_NATIVE_HISTORICAL_RUN_REPLAY",
               "calls": {"provider": 0, "paid": 0, "sec": 0},
               "production_authorized": False}
    return {"row": row, "evidence": evidence,
            "receipt": {**receipt, "receipt_id": content_hash(value=receipt)}}
