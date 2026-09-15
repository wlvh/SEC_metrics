"""Current source ownership around the unchanged early B06 equity guard."""
from decimal import Decimal
from pathlib import Path
from .b06_guarded_result_v3 import (SPEC_PATH,RESOLVER,_need,_installed_spec,
    _rebuild_equity,_terminal_records)
from .canonical import content_hash,sha256_bytes,canonical_json_bytes,strict_json_loads
from .deterministic_router import parse_accession_xbrl_source
from .normal_annual_input import _registry_rows
from .normal_candidates import _prepare_b06
from .ordinary_source_authority import verify_ordinary_source_proofs
from .observations import scope_key


def prepare_current_guarded_b06_result(*, repo_root: Path, company_id: str):
    """Return NOT_MEANINGFUL native records, or CONTINUE_DEBT_PATH; never a Run."""
    spec, trait_hashes = _installed_spec(repo_root)
    preparation = _prepare_b06(repo_root=repo_root, company_id=company_id)
    prepared = preparation["input_binding"]["prepared_annual_input"]
    proofs = list(preparation["input_binding"]["source_proofs"]) + list(prepared["source_proofs"])
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    period = prepared["table_input"]["target_period"]
    scope = {"entity_scope": "consolidated"}
    target = {"company_id": company_id, "entity": prepared["entity"], "accession": prepared["filing"]["accessionNumber"],
              "period_start": period["period_end"], "period_end": period["period_end"],
              "scope": scope, "scope_key": scope_key(scope=scope)}
    for key in ("primary", "xml", "facts"):
        item = preparation[key]
        _need(item["source_reference"]["raw_asset_id"] == "sha256:" + sha256_bytes(content=item["raw_bytes"]),
              "B06_GUARD_SOURCE_CHANGED_AFTER_ADMISSION")
    proof = _rebuild_equity(primary=preparation["primary"]["raw_bytes"], xml=preparation["xml"]["raw_bytes"],
        facts_raw=preparation["facts"]["raw_bytes"], facts_source=preparation["facts"]["source_reference"],
        target=target, period=period, filing=prepared["filing"])
    company = next(c for c in _registry_rows(repo_root=repo_root) if c["company_id"] == company_id)
    parsed = parse_accession_xbrl_source(raw_bytes=preparation["xml"]["raw_bytes"])
    industrial = set(spec["compiled"]["quality_rule"]["scope_review_dimension_members"])
    restricted = company["industry_profile"] == "financial_institution" or any(
        any(str(member).split(":")[-1] in industrial for member in c["dimensions"].values())
        for c in parsed.contexts.values() if c["period_end"] == target["period_end"]
        and str(int(c["entity_identifier"])) == target["entity"])
    nonpositive = Decimal(proof["value"]) <= 0
    terminal = nonpositive and not restricted
    observations, result, trace = [], None, None
    status = "NOT_MEANINGFUL" if terminal else "CONTINUE_DEBT_PATH"
    reason = "DENOMINATOR_NONPOSITIVE" if terminal else (
        "EXISTING_SPECIAL_SCOPE_REQUIRED" if restricted else "DENOMINATOR_POSITIVE")
    if terminal:
        result, trace, observations = _terminal_records(spec=spec, target=target, proof=proof,
            source=preparation[proof["observation_source_kind"]]["source_reference"],
            filed=prepared["filing"]["filingDate"], form=prepared["filing"]["form"])
    body = {"record_type": "B06_GUARDED_RESULT_COMPONENT", "resolver": RESOLVER, "company_id": company_id,
        "status": status, "reason_code": reason, "spec_path": SPEC_PATH, "spec_closure_hash": spec["spec_closure_hash"],
        "input_binding": preparation["input_binding"], "source_admission": admission, "trait_file_hashes": trait_hashes,
        "target": target, "filing_period": period, "equity_proof": proof, "debt_completeness": "NOT_EVALUATED",
        "source_records": preparation["records"],
        "source_references": [r for r in preparation["records"] if r["record_type"] == "SOURCE_REFERENCE"],
        "observations": observations, "trace": trace, "result": result, "native_run_status": "NOT_CREATED",
        "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}
    # QName measures originate as Python tuples. The public component contract
    # is JSON, so return the same list shapes that a cold reader receives.
    body = strict_json_loads(text=canonical_json_bytes(value=body).decode("utf-8"))
    return {**body, "component_id": content_hash(value=body)}
