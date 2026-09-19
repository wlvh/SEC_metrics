"""Prepare the D02 text input for an explicitly selected historical period.

A source adapter, not a second reader. ``_current_metadata_context``,
``_source_plan``, ``_check_selected_metadata_scope`` and the ``text_results_v2``
scopes are imported unchanged from the frozen modules, and the candidate
functions this feeds read only the target filing's own bytes. What this module
owns is which filing the text roles mean when the period is pinned.

It exists as a successor file because ``scripts/vnext/ordinary_text_input.py`` is
byte-bound by the ``issue_28_v13`` rule set; changing it would stop every
existing ordinary Run from loading its own Requirement.

Only D02 is wired. C02 is refused, and not for want of code: its source plan
needs the annual meeting's DEF 14A, and of the 82 proxies this repository's
saved submissions indexes list, ten have their accession material saved and all
ten were filed in 2026. A historical C02 would resolve the most recent period
and name a source gap for every earlier one, so the missing proxies are the ask
rather than the route.
"""
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url

from .canonical import content_hash, sha256_file
from .historical_annual_input import prepare_historical_annual_input
from .normal_governance_input import _Sources
from .normal_text_input_v2 import (_check_selected_metadata_scope, _current_metadata_context,
                                   _need, _source_plan)
from .ordinary_source_authority import verify_ordinary_source_proofs
from .text_results_v2 import SCOPES

RECORD_TYPE = "HISTORICAL_BUSINESS_TEXT_INPUT_BINDING"
SUPPORTED_METRICS = ("D02",)


def prepare_historical_business_text_input(*, repo_root: Path, company_id: str, metric_id: str,
                                           period_selection):
    """Admit the target filing's own text for a pinned annual period.

    The 10-K is chosen by ``_current_metadata_context`` on the pinned period's
    own end date and checked against the selection's filing, so the text comes
    from the year that was asked for rather than from whatever was filed last.
    """
    _need(metric_id in SUPPORTED_METRICS,
          "HISTORICAL_TEXT_INPUT_METRIC_NOT_WIRED:" + metric_id, "IMPLEMENTATION_GAP")
    root = Path(repo_root)
    ledger_sha = sha256_file(path=root / "evidence/requests_log.csv")
    prepared = prepare_historical_annual_input(repo_root=root, company_id=company_id,
                                               period_selection=period_selection)
    cik = prepared["entity"]
    reader = _Sources(root, company_id, cik)
    inventory = reader.read(submissions_url(cik=int(cik)), role="sec_submissions_inventory",
                            media_type="application/json")
    metadata = _current_metadata_context(prepared=prepared, inventory=inventory,
                                         metric_id=metric_id)
    ordinary = metadata["selection"]["ordinary"]
    annual = reader.primary(ordinary)
    reader.read(companyfacts_url(cik=int(cik)), accession=ordinary["accessionNumber"],
                role="companyfacts", media_type="application/json")
    period = prepared["table_input"]["target_period"]
    scope = dict(SCOPES[metric_id])
    target = {"company_id": company_id, "entity": cik,
              "accession": ordinary["accessionNumber"],
              "period_start": period["period_start"], "period_end": period["period_end"],
              "scope": scope, "scope_key": content_hash(value=scope)}
    plan, text_sources, filings, limitations = None, [], {}, []
    try:
        plan = _source_plan(governance_binding=metadata, metric_id=metric_id)
        _check_selected_metadata_scope(plan=plan, references=[inventory["source_reference"]])
        text_sources = [annual["source_reference"]]
        filings[text_sources[0]["source_reference_id"]] = ordinary
    except ValueError as error:
        limitations.append({"metric_id": metric_id,
                            "category": getattr(error, "category", None)
                            or ("SOURCE_ACCESS_FAILED"
                                if str(error).startswith("LATEST_SOURCE_REQUEST_FAILED")
                                else "SOURCE_INTEGRITY_ERROR"),
                            "reason": str(error)})
    proofs_by_id = {}
    for proof in [*prepared["source_proofs"], *(v["proof"] for v in reader.proofs.values())]:
        key = proof["request_attempt_id"]
        _need(key not in proofs_by_id or proofs_by_id[key] == proof,
              "HISTORICAL_TEXT_INPUT_REQUEST_PROOF_COLLISION")
        proofs_by_id[key] = proof
    proofs = list(proofs_by_id.values())
    admission = verify_ordinary_source_proofs(data_root=root, proofs=proofs)
    records = list(reader.records.values())
    references = [r for r in records if r["record_type"] == "SOURCE_REFERENCE"]
    blobs = {r["raw_asset_id"]: r for r in records if r["record_type"] == "RAW_BLOB"}
    raw = {v["raw_blob"]["raw_asset_id"]: v["raw_bytes"] for v in reader.cache.values()}
    text_args = None if limitations else {
        "target": target, "source_references": text_sources, "raw_blobs": blobs,
        "raw_bytes_by_id": raw, "source_filings": filings}
    _need(sha256_file(path=root / "evidence/requests_log.csv") == ledger_sha,
          "HISTORICAL_TEXT_INPUT_LEDGER_CHANGED_DURING_PREPARATION")
    status = ("BLOCKED" if limitations
              else "PREPARED_ORIGINAL_WITH_AMENDMENTS" if prepared["amendments"] else "PREPARED")
    body = {"record_type": RECORD_TYPE, "metric_id": metric_id, "company_id": company_id,
            "period_selection": period_selection, "prepared_input": prepared,
            "current_metadata_scope": metadata["scope"], "source_proofs": proofs,
            "source_admission": admission, "source_references": references,
            "source_set_manifests": [],
            "text_source_reference_ids": ([] if text_args is None
                                          else [s["source_reference_id"] for s in text_sources]),
            "source_filings": {} if text_args is None else filings, "target": target,
            "source_plan": plan, "part_iii_source_proof": None, "input_status": status,
            "limitations": limitations,
            "failed_source_attempts": list(reader.failed_attempts.values()),
            "current_latest_verified": False, "latest_restated_values_used": False,
            "execution": "NOT_EXECUTED", "production_authorized": False,
            "business_calls": [0, 0, 0]}
    binding = {**body, "input_binding_id": content_hash(value=body)}
    return {"prepared_input": prepared, "input_binding": binding, "input_status": status,
            "records": records, "source_references": references, "source_set_manifests": [],
            "source_proofs": proofs, "admission": admission, "text_arguments": text_args,
            "target_period": period, "business_calls": [0, 0, 0]}
