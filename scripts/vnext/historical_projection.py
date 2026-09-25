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
                                        _selected_financial_locators, _raw_value)
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


ROW_BUNDLE_NAME = "row_receipt.json"
ROW_BUNDLE_RECORD_TYPE = "HISTORICAL_PERIOD_ROW_BUNDLE"


def row_bundle_path(*, run_dir):
    """Where a Run's persisted row bundle lives: beside the Run, never in it.

    One expression, because the writer and the reader disagreeing about it is
    silent in both directions - a reader that looks in the wrong place reports
    no row where there is one, and a writer that puts it in the wrong place
    makes the Run itself unreadable.

    Args:
        run_dir: The run directory.

    Returns:
        The bundle path, a sibling of ``run_dir`` rather than a child.
    """
    run_dir = Path(run_dir)
    return run_dir.parent / (run_dir.name + "." + ROW_BUNDLE_NAME)


def render_historical_run(*, data_root: Path, run_dir: Path, frozen=False, persist=False):
    """Build one public row and its evidence from a historical Run.

    The Run is loaded through the same store, its whole case is re-derived from
    the data root, and the row's fiscal label comes from the selected filing's
    own annual input rather than from whatever the company filed most recently.

    Args:
        data_root: The installed data root the Run was created against.
        run_dir: The run directory.
        frozen: Load a frozen Run rather than mechanically replaying an open one.
        persist: Also write the row, its evidence and the receipt beside the Run
            as ``row_receipt.json``. Without this the row exists only in the
            caller's memory, so a later reader has no way to say whether a
            position reached a public row at all - and a summary that re-renders
            it to find out is no longer reading, it is recomputing.

    Returns:
        The row, its evidence and the receipt. The receipt carries the row and
        evidence hashes, so a persisted bundle can be checked rather than
        trusted.
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
    _need(case["kind"] in {"STRUCTURED", "TEXT"},
          "HISTORICAL_PROJECTION_ROUTE_NOT_WIRED:" + str(case["kind"]))
    text_route = case["kind"] == "TEXT"
    results = [r for r in records
               if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == metric]
    _need(len(results) == 1, "HISTORICAL_PROJECTION_PRIMARY_RESULT_NOT_UNIQUE")
    result = results[0]
    # B13 outside the company scope its approved definition names. The route is
    # STRUCTURED - it reads no filing - but the result is built under B13's text
    # Spec, so it is TEXT_V1 with no payload. It is the one such case, named by
    # its component rather than inferred from the result's shape, and it renders
    # as the ordinary route renders it: no evidence row and no value.
    scope_answer = (case["kind"] == "STRUCTURED"
                    and prepared.get("component", {}).get("record_type")
                    == "HISTORICAL_CAPACITY_SCOPE_RESULT"
                    and result["applicability"] == "N_A_STRUCTURAL"
                    and result["value"] is None and result.get("text_payload") is None)
    _need((result.get("value_kind") == "TEXT_V1") == (text_route or scope_answer),
          "HISTORICAL_PROJECTION_VALUE_KIND_DISAGREES_WITH_ROUTE")
    spec = case["compiled_specs"][metric]
    policy = strict_json_file(path=ROOT / POLICY_PATH)
    _need(policy["record_type"] == "ORDINARY_INTEGRATED_PRESENTATION_POLICY"
          and policy["schema_version"] == 1 and policy["production_authorized"] is False
          and policy["confidence_inferred"] is False,
          "HISTORICAL_PRESENTATION_POLICY_CHANGED")
    item = policy["metrics"][metric]
    projection = {**item["projection"],
                  **item["spec_overrides"].get(prepared["spec_paths"][metric], {})}
    # A text metric has no canonical numeric unit for the projection to agree with.
    same_unit = text_route or scope_answer or (
        projection["unit"] == spec["compiled"].get("canonical_unit")
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
    # The CIK of the registrant that filed this period: the primary's for its
    # own years, a registered predecessor's for a year that registrant filed.
    # The shared projector writes company["primary_cik"] into every published
    # row and evidence row, so it is handed the period's registrant under that
    # key. Setting only the baseline left a published predecessor-year row
    # naming the successor's CIK beside the predecessor's accession, while the
    # withheld rows of the same year named the predecessor.
    company = {**company, "primary_cik": annual["entity"]}
    baseline.update(company=company["display_name"], cik=annual["entity"],
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
    if text_route:
        # The row and its evidence come from the shared projector, exactly as on
        # the current route: a disclosed item is its own evidence row, so there
        # is no claim to look up and no source cell to quote. The invariant to
        # assert is ordinary_projection's - every published item reaches the row.
        _need(len(evidence) == len(result["text_payload"]["items"]),
              "HISTORICAL_TEXT_EVIDENCE_SET_CHANGED")
    elif scope_answer:
        # The ordinary renderer's B13 structural arm, with its assertion: the
        # shared projector made no evidence row out of a result with no value.
        _need(not evidence, "HISTORICAL_B13_SCOPE_ANSWER_HAS_EVIDENCE")
        row["notes"] = ("Outside the company scope the approved B13 definition names. "
                        "No disclosure-absence or utilization claim is made.")
    else:
        evidence = []
        claims = _claims(prepared)
        # A structured Company Facts observation is bound to an XBRL fact, not to a
        # verified claim, so it carries no claim identifiers at all. The ordinary
        # projector has always had two branches here and this one had only the first,
        # which made every revenue-route metric fail to render a row its own Run had
        # already resolved as EXACT. The B13 quantity_statement branch is not ported:
        # that is a text route, and case["kind"] == "STRUCTURED" is required above.
        selection = case["results"][metric].get("selection")
        financial_locators = _selected_financial_locators(metric, selection)
        for observation in ordered:
            binding = observation["source_binding"]
            identifiers = binding.get("verified_claim_ids",
                                      binding.get("matched_verified_claim_ids", []))
            if identifiers:
                for identity in identifiers:
                    _need(identity in claims, "HISTORICAL_PROJECTION_SELECTED_CLAIM_MISSING")
                    evidence.append(_claim_evidence(claims[identity], observation, result, company,
                                                    projection, indexes, str(period["fiscal_year"])))
                continue
            entry = projector._evidence_row(observation=observation, result=result, company=company,
                                            projection=projection, source_index=indexes["sources"],
                                            raw_index=indexes["raw"],
                                            fiscal_year=str(period["fiscal_year"]))
            entry.update(value_raw=_raw_value(observation, financial_locators, selection),
                         context_or_dimension=json.dumps(
                             {"source_binding": binding, "source_cells": financial_locators},
                             ensure_ascii=False, sort_keys=True),
                         evidence_quote="Normalized source-derived observation: "
                                        + entry["evidence_quote"])
            if "table_locator" in binding:
                entry.update(value_raw=binding["reported_raw_text"],
                             context_or_dimension=json.dumps(
                                 {"source_binding": binding,
                                  "source_cells": binding["source_witnesses"]},
                                 ensure_ascii=False, sort_keys=True),
                             evidence_quote="Source table cell: " + binding["reported_raw_text"])
            evidence.append(entry)
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
    admission = prepared["source_admission"]
    recorded = admission["source_credit"] == "RECORDED_TEST_ONLY"
    # Same two arms the ordinary renderer has. Only the first was ported, which
    # is harmless while every historical package is built from already-saved
    # bytes and becomes wrong the first time one is not: a row whose inputs
    # include newly acquired SEC records would not say so.
    if recorded:
        row["notes"] += (" Recorded source refresh test using preexisting SEC content; "
                         "no new SEC acquisition.")
    elif admission.get("real_sec_credit") is True:
        row["notes"] += (" Selected source inputs include new SEC acquisition records; "
                         "each input retains its own acquisition identity.")
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
    # And the receipt carries the acquisition identity for the same reason the
    # ordinary one does: a row that cost requests must be readable as such.
    if recorded:
        receipt.update(source_credit="RECORDED_TEST_ONLY",
                       source_checkpoint_id=admission["checkpoint_id"],
                       real_sec_credit=False)
    elif "checkpoint_id" in admission:
        receipt.update(source_credit=admission["source_credit"],
                       source_checkpoint_id=admission["checkpoint_id"],
                       real_sec_credit=admission["real_sec_credit"],
                       selected_new_request_attempt_ids=admission[
                           "selected_new_request_attempt_ids"])
    bundle = {"row": row, "evidence": evidence,
              "receipt": {**receipt, "receipt_id": content_hash(value=receipt)}}
    if persist:
        # Written beside the run directory, not inside it. Not changing the
        # manifest's three hashed files is necessary and was already true; it is
        # not sufficient. A frozen Run's directory has to hold exactly the
        # artifacts its records name - that check is what stops an unhashed file
        # from sitting there unaccounted for - and this receipt is deliberately
        # unhashed by the manifest, so inside is precisely where it must not be.
        # Measured: with the receipt in the directory, `load_frozen_run` refuses
        # every historical Run whose row was persisted, with "Run validation
        # artifact exact set differs". It is still its own checkable object: the
        # receipt holds the hashes of the row and the evidence it was written
        # with.
        path = row_bundle_path(run_dir=run_dir)
        path.write_text(json.dumps({"record_type": ROW_BUNDLE_RECORD_TYPE,
                                    "schema_version": 1, **bundle},
                                   ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
    return bundle
