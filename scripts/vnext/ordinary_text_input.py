"""Current input ownership with frozen text scope and source-selection rules."""
from pathlib import Path
from sec_urls import submissions_url,companyfacts_url
from .normal_text_input_v2 import (_need,_current_metadata_context,_source_plan,
    _check_selected_metadata_scope,_part_iii_proof)
from .canonical import content_hash,sha256_file
from .normal_annual_input import prepare_saved_annual_input
from .normal_governance_input import _Sources
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import raw_blob_record,source_reference_record
from .text_results_v2 import SCOPES


def prepare_current_business_text_input(*, repo_root: Path, company_id: str, metric_id: str):
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
    admission=verify_ordinary_source_proofs(data_root=root,proofs=proofs)
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


def current_text_sources(*, repo_root, company_id):
    """Rebuild the complete input set from pinned discovery, not the candidate."""
    prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id)
    admission = verify_ordinary_source_proofs(data_root=repo_root,
                                          proofs=prepared["source_proofs"])
    records, references = [], []
    for role, proof in zip(["submissions", "target_primary", "companyfacts"],
                           prepared["source_proofs"]):
        blob = raw_blob_record(repo_root=repo_root,
            repo_relative_path=proof["request_repo_relative_path"],
            media_type="text/html" if role == "target_primary" else "application/json")
        ref = source_reference_record(raw_blob=blob, company_id=company_id,
            source_url=proof["source_url"], accession=prepared["filing"]["accessionNumber"],
            document_name=proof["document_name"], source_role=role,
            request_attempt_id=proof["request_attempt_id"])
        records.extend([blob, ref])
        references.append(ref)
    return prepared, admission, records, references
