"""Normal saved-source preparation for C02/D02, with no execution or fetching.

The unchanged annual adapter proves the period and complete current-metadata
scope. Only the selected governance source is added for C02. C04 event/auditor
preparation is never executed or made into a dependency of these text tasks.
"""
from __future__ import annotations

from pathlib import Path
import re

from sec_urls import submissions_url, companyfacts_url
from .canonical import content_hash, sha256_file, strict_json_loads
from .normal_annual_input import prepare_saved_annual_input
from .normal_governance_input import _Sources, _filings, _history_index, _order
from .normal_source_authority import verify_saved_source_proofs
from .text_business_candidates import governance_source_document
from .text_coverage import build_text_document, _heading
from .text_results_v2 import SCOPES


class NormalTextInputV2Error(ValueError):
    """A source/implementation limitation, not a business absence finding."""

    def __init__(self, reason, category="SOURCE_INTEGRITY_ERROR"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise NormalTextInputV2Error(reason, category)


def _source_plan(*, governance_binding, metric_id):
    """Pure metadata choice; the public entry supplies authenticated discovery."""
    prepared = governance_binding["prepared_annual_input"]
    selected = governance_binding["selection"]
    period = prepared["table_input"]["target_period"]
    ordinary = selected["ordinary"]
    _need(ordinary["accessionNumber"] == prepared["filing"]["accessionNumber"]
          and ordinary["reportDate"] == period["period_end"], "TEXT_INPUT_ANNUAL_SELECTION_CHANGED")
    amendments = selected["amendments"]
    base = {"ordinary": ordinary, "annual_amendments": amendments,
            "annual_update_status": prepared["update_status"], "current_latest_verified": False}
    if metric_id == "D02":
        return {**base, "text_filings": [ordinary], "basis": "ORDINARY_ANNUAL_DISCLOSURE_SOURCE",
                "requires_part_iii_proof": False,
                "amendment_status": "AMENDMENT_PROCESSING_REQUIRED" if amendments else "NO_CURRENT_ANNUAL_AMENDMENTS"}
    latest = selected["latest_def14a"]
    current = latest if latest and latest["filingDate"] >= period["period_end"] else None
    pending_proxy = [f for f in selected["def14a_amendments"] if f["filingDate"] >= period["period_end"]]
    _need(not pending_proxy, "TEXT_INPUT_GOVERNANCE_PROXY_AMENDMENT_REPLAY_REQUIRED", "IMPLEMENTATION_GAP")
    if current:
        later = []
        for amendment in amendments:
            ordered = _order([current, amendment])
            if ordered[0]["accessionNumber"] == amendment["accessionNumber"]:
                later.append(amendment)
        _need(not later, "TEXT_INPUT_LATER_ANNUAL_AMENDMENT_GOVERNANCE_SCOPE_UNRESOLVED", "IMPLEMENTATION_GAP")
        return {**base, "text_filings": [ordinary, current], "basis": "CURRENT_SAME_CIK_DEF14A",
                "requires_part_iii_proof": False,
                "amendment_status": "EARLIER_ANNUAL_AMENDMENTS_RETAINED" if amendments else "NO_CURRENT_ANNUAL_AMENDMENTS",
                "prior_proxy_not_used": None}
    _need(bool(amendments), "TEXT_INPUT_CURRENT_GOVERNANCE_SOURCE_NOT_SAVED", "SOURCE_UNAVAILABLE")
    _need(len(amendments) == 1, "TEXT_INPUT_MULTIPLE_GOVERNANCE_AMENDMENTS_REQUIRE_REPLAY", "IMPLEMENTATION_GAP")
    _need(amendments[0]["reportDate"] == period["period_end"], "TEXT_INPUT_GOVERNANCE_AMENDMENT_PERIOD_CHANGED")
    return {**base, "text_filings": [ordinary, amendments[0]], "basis": "SAME_PERIOD_PART_III_ANNUAL_AMENDMENT",
            "requires_part_iii_proof": True, "amendment_status": "SELECTED_PART_III_SOURCE_REQUIRES_RAW_PROOF",
            "prior_proxy_not_used": latest}


def _check_selected_metadata_scope(*, plan, references):
    # The inherited annual selector proves relevant filings are in the
    # current block. An inconsistent history body cannot become a newer
    # governance source merely by carrying an out-of-range filing date.
    current=[s for s in references if s["source_role"]=="sec_submissions_inventory"]
    _need(len(current)==1,"TEXT_INPUT_CURRENT_METADATA_SOURCE_NOT_UNIQUE")
    _need(all(f.get("metadata_origin",{}).get("inventory_name")==current[0]["document_name"]
              for f in plan["text_filings"]),"TEXT_INPUT_SELECTED_FILING_OUTSIDE_CURRENT_METADATA_BLOCK","SOURCE_COVERAGE_CONFLICT")


def _part_iii_proof(*, source, blob, raw, filing, company_id, cik, period_end):
    """Prove a full same-year amendment has a real Part III/Item body structure."""
    build_text_document(raw_bytes=raw, raw_blob=blob, source_reference=source,
        expected_company_id=company_id, expected_cik=cik, expected_period_end=period_end)
    doc = governance_source_document(raw_bytes=raw, raw_blob=blob, source_reference=source,
        company_id=company_id, cik=cik, filing=filing)
    _need(doc["source_state"] == "COMPLETE_LOCAL_DOCUMENT", "TEXT_INPUT_PART_III_DOCUMENT_INCOMPLETE", "IMPLEMENTATION_GAP")
    blocks = doc["blocks"]
    parts = [i for i,b in enumerate(blocks) if b.get("emphasized") and not b["linked"]
             and re.fullmatch(r"PART\s+III", b["text"].strip(), re.I)]
    items = [h for i in range(len(blocks)) if (h := _heading(blocks,i)) is not None]
    candidates = []
    for part in parts:
        next_parts = [i for i,b in enumerate(blocks) if i > part and b.get("emphasized") and not b["linked"]
                      and re.fullmatch(r"PART\s+IV",b["text"].strip(),re.I)]
        end = min(next_parts) if next_parts else len(blocks)
        headings = [h for h in items if part < h["block_index"] < end and h["item"] in {"10","11","12","13","14"}]
        if headings and sum(len(b["text"]) for b in blocks[headings[0]["heading_end_index"] + 1:end]) >= 120:
            candidates.append({"start_block": part, "end_block_exclusive": end, "item_headings": headings,
                "part_heading_locator": {k:blocks[part][k] for k in ("block_index","text","raw_start_byte","raw_end_byte","raw_span_sha256")}})
    _need(len(candidates) == 1, "TEXT_INPUT_PART_III_STRUCTURE_NOT_UNIQUE_OR_UNSUPPORTED", "IMPLEMENTATION_GAP")
    body = {"record_type":"NORMAL_PART_III_SOURCE_PROOF", "source_reference_id":source["source_reference_id"],
            "raw_asset_id":source["raw_asset_id"],"document_id":doc["text_document_id"],"source_filing":filing,
            "range":candidates[0],"claim":"PART_III_SOURCE_STRUCTURE_ONLY_NOT_BOARD_ASOF_OR_COUNT"}
    return {**body,"proof_id":content_hash(value=body)}


def _current_metadata_context(*, prepared, inventory, metric_id):
    """Rebuild a scoped metadata view from a complete authenticated JSON body.

    The entire raw JSON remains the source. Rows for unrelated event forms are
    not validated as documents or fetched. Original row indices are retained,
    so this view cannot replace the source or change filing identities.
    """
    payload = strict_json_loads(text=inventory["raw_bytes"].decode("utf-8"))
    shards = _history_index(payload, prepared["entity"])
    period = prepared["table_input"]["target_period"]
    _need(all(s["filingTo"] < period["period_end"] for s in shards),
          "TEXT_INPUT_CURRENT_METADATA_SCOPE_REQUIRES_HISTORY", "SOURCE_UNAVAILABLE")
    block = payload["filings"]["recent"]
    forms = {"10-K", "10-K/A", "DEF 14A", "DEF 14A/A"} if metric_id == "C02" else {"10-K", "10-K/A"}
    indices = [i for i,f in enumerate(block["form"]) if f in forms]
    scoped = {key:[values[i] for i in indices] for key,values in block.items()}
    rows = _filings(scoped, inventory_name=inventory["source_reference"]["document_name"])
    for row in rows:
        row["metadata_origin"]["row_index"] = indices[row["metadata_origin"]["row_index"]]
    ordinary = [f for f in rows if f["form"] == "10-K" and f["reportDate"] == period["period_end"]]
    _need(len(ordinary) == 1 and all(ordinary[0][k] == prepared["filing"][k]
              for k in ("form","reportDate","filingDate","accessionNumber","primaryDocument")),
          "TEXT_INPUT_ANNUAL_SELECTION_CHANGED")
    amendments = _order([f for f in rows if f["form"] == "10-K/A" and f["reportDate"] == period["period_end"]])
    proxies = _order([f for f in rows if f["form"] == "DEF 14A" and f["filingDate"] >= period["period_end"]])
    latest = proxies[0] if proxies else None
    proxy_amendments = _order([f for f in rows if f["form"] == "DEF 14A/A"
        and f["filingDate"] >= (latest["filingDate"] if latest else period["period_end"])])
    selection = {"ordinary":ordinary[0],"amendments":amendments,"latest_def14a":latest,
                 "def14a_amendments":proxy_amendments}
    scope = {"record_type":"CURRENT_TEXT_METADATA_SCOPE", "company_id":prepared["company_id"],
             "cik":prepared["entity"],"source_reference_id":inventory["source_reference"]["source_reference_id"],
             "raw_asset_id":inventory["raw_blob"]["raw_asset_id"],"source_recent_row_count":len(block["form"]),
             "considered_forms":sorted(forms),"considered_source_row_indices":indices,
             "complete_history_declarations":shards,"current_interval_lower_bound":period["period_end"],
             "history_rule":"ALL_DECLARED_SHARDS_END_BEFORE_CURRENT_ANNUAL_END_ELSE_REJECT",
             "selection":selection}
    return {"prepared_annual_input":prepared,"selection":selection,"scope":{**scope,"scope_id":content_hash(value=scope)}}


def prepare_normal_business_text_input(*, repo_root: Path, company_id: str, metric_id: str):
    """Discover/admit the minimal complete source set for the v2 primitives."""
    _need(metric_id in {"C02","D02"},"TEXT_INPUT_METRIC_NOT_SUPPORTED","IMPLEMENTATION_GAP")
    root=Path(repo_root)
    ledger_sha=sha256_file(path=root/"evidence/requests_log.csv")
    prepared=prepare_saved_annual_input(repo_root=root,company_id=company_id)
    _need(prepared["company_id"]==company_id
          and prepared["entity"]==prepared["subject_policy"]["selected_cik"]
          and prepared["subject_policy"]["cross_entity_combination_authorized"] is False,
          "TEXT_INPUT_SUBJECT_POLICY_CHANGED")
    cik=prepared["entity"]
    reader=_Sources(root,company_id,cik)
    inventory=reader.read(submissions_url(cik=int(cik)),role="sec_submissions_inventory",media_type="application/json")
    metadata=_current_metadata_context(prepared=prepared,inventory=inventory,metric_id=metric_id)
    ordinary=metadata["selection"]["ordinary"]
    annual=reader.primary(ordinary)
    reader.read(companyfacts_url(cik=int(cik)),accession=ordinary["accessionNumber"],role="companyfacts",media_type="application/json")
    plan=None;part_proof=None;text_sources=[];filings={};limitations=[]
    period=prepared["table_input"]["target_period"]
    scope=dict(SCOPES[metric_id])
    target={"company_id":company_id,"entity":cik,"accession":ordinary["accessionNumber"],
            "period_start":period["period_start"],"period_end":period["period_end"],"scope":scope,"scope_key":content_hash(value=scope)}
    try:
        plan=_source_plan(governance_binding=metadata,metric_id=metric_id)
        _check_selected_metadata_scope(plan=plan,references=[inventory["source_reference"]])
        text_sources=[annual["source_reference"]]
        filings[text_sources[0]["source_reference_id"]]=ordinary
        if metric_id=="C02":
            filing=plan["text_filings"][1]
            selected=reader.primary(filing)
            text_sources.append(selected["source_reference"])
            filings[text_sources[-1]["source_reference_id"]]=filing
            if plan["requires_part_iii_proof"]:
                part_proof=_part_iii_proof(source=selected["source_reference"],blob=selected["raw_blob"],raw=selected["raw_bytes"],
                    filing=filing,company_id=company_id,cik=cik,period_end=period["period_end"])
    except ValueError as error:
        category=getattr(error,"category",None) or (
            "SOURCE_ACCESS_FAILED" if str(error).startswith("LATEST_SOURCE_REQUEST_FAILED") else "SOURCE_INTEGRITY_ERROR")
        limitations.append({"metric_id":metric_id,"category":category,"reason":str(error)})
    proofs_by_id={}
    for proof in [*prepared["source_proofs"],*(v["proof"] for v in reader.proofs.values())]:
        key=proof["request_attempt_id"]
        _need(key not in proofs_by_id or proofs_by_id[key]==proof,"TEXT_INPUT_REQUEST_PROOF_COLLISION")
        proofs_by_id[key]=proof
    proofs=list(proofs_by_id.values())
    admission=verify_saved_source_proofs(data_root=root,proofs=proofs)
    records=list(reader.records.values())
    references=[r for r in records if r["record_type"]=="SOURCE_REFERENCE"]
    blobs={r["raw_asset_id"]:r for r in records if r["record_type"]=="RAW_BLOB"}
    raw={v["raw_blob"]["raw_asset_id"]:v["raw_bytes"] for v in reader.cache.values()}
    text_args=None if limitations else {"target":target,"source_references":text_sources,
        "raw_blobs":blobs,"raw_bytes_by_id":raw,"source_filings":filings}
    _need(sha256_file(path=root/"evidence/requests_log.csv")==ledger_sha,"TEXT_INPUT_LEDGER_CHANGED_DURING_PREPARATION")
    status="BLOCKED" if limitations else "PREPARED_ORIGINAL_WITH_AMENDMENTS" if metric_id=="D02" and prepared["amendments"] else "PREPARED"
    body={"record_type":"NORMAL_BUSINESS_TEXT_INPUT_V2_BINDING","metric_id":metric_id,"company_id":company_id,
          "prepared_input":prepared,"current_metadata_scope":metadata["scope"],"source_proofs":proofs,"source_admission":admission,
          "source_references":references,"source_set_manifests":[],
          "text_source_reference_ids":[] if text_args is None else [s["source_reference_id"] for s in text_sources],
          "source_filings":{} if text_args is None else filings,"target":target,"source_plan":plan,
          "part_iii_source_proof":part_proof,"input_status":status,"limitations":limitations,
          "failed_source_attempts":list(reader.failed_attempts.values()),"current_latest_verified":False,
          "execution":"NOT_EXECUTED","production_authorized":False,"business_calls":[0,0,0]}
    binding={**body,"input_binding_id":content_hash(value=body)}
    return {"prepared_input":prepared,"input_binding":binding,"input_status":status,"records":records,
            "source_references":references,"source_set_manifests":[],"source_proofs":proofs,"admission":admission,
            "text_arguments":text_args,"business_calls":[0,0,0]}
