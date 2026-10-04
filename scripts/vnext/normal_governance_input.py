"""Discover C03/C04 inputs from saved SEC metadata and real request proofs.

No derived filing inventory, legacy result, sample answer or fabricated request
identity is read. This is an input adapter: it neither invokes a resolver nor
creates/freezes Runs, obtains sources, or changes a publication.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import re

from sec_urls import accession_directory_url, accession_document_url, hdr_sgml_url
from sec_urls import companyfacts_url, submissions_url, submissions_file_url
from sec_http import request_log_attempt_id

from .annual_update import AnnualUpdateError, saved_source, _rows, _utc
from .batch_workflow import BatchWorkflowError, validate_request_attempt_binding
from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_loads, strict_json_file
from .deterministic_router import source_set_manifest
from .governance_signals import C03_SPEC_PATH, C04_V2_SPEC_PATH
from .governance_compensation_table import SPEC_PATH as SCT_SPEC_PATH
from .normal_annual_input import prepare_saved_annual_input, _registry_rows
from .observations import scope_key
from .sources import raw_blob_record, source_reference_record, resolve_repository_file, SourceError


_IDENTITY_FIELDS = ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument")
_FORMS = {"10-K", "10-K/A", "DEF 14A", "DEF 14A/A", "8-K", "8-K/A"}
_EVENT_FORMS = ["8-K", "8-K/A"]
_CODE_ROOT = Path(__file__).resolve().parents[2]


class NormalGovernanceInputError(ValueError):
    """An input failure with a category that does not imply non-disclosure."""

    def __init__(self, reason, category="SOURCE_INTEGRITY_ERROR"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise NormalGovernanceInputError(reason, category)


def _date(value):
    try:
        _need(type(value) is str and date.fromisoformat(value).isoformat() == value, "GOVERNANCE_METADATA_DATE_INVALID")
    except ValueError as error:
        raise NormalGovernanceInputError("GOVERNANCE_METADATA_DATE_INVALID") from error
    return value


def _filings(payload, *, inventory_name):
    """Validate source arrays, then retain exact relevant filing metadata."""
    block = payload["filings"]["recent"] if "filings" in payload else payload
    _need(type(block) is dict and set(_IDENTITY_FIELDS) <= set(block)
          and all(type(v) is list for v in block.values())
          and len({len(v) for v in block.values()}) == 1, "GOVERNANCE_METADATA_COLUMNS_CONFLICT")
    rows, seen = [], set()
    for index, form in enumerate(block["form"]):
        _need(type(form) is str and form and form.strip() == form, "GOVERNANCE_METADATA_FORM_INVALID")
        if form not in _FORMS:
            continue
        row = {k: v[index] for k, v in block.items()}
        accession, document = row["accessionNumber"], row["primaryDocument"]
        _need(type(accession) is str and re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession)
              and accession not in seen, "GOVERNANCE_METADATA_ACCESSION_INVALID_OR_DUPLICATE")
        seen.add(accession)
        _need(type(document) is str and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:htm|html)", document, re.I),
              "GOVERNANCE_PRIMARY_DOCUMENT_INVALID")
        _date(row["filingDate"])
        if form in {"10-K", "10-K/A"}:
            _need(_date(row["reportDate"]) <= row["filingDate"], "GOVERNANCE_ANNUAL_METADATA_DATE_CONFLICT")
        row["metadata_origin"] = {"inventory_name": inventory_name, "row_index": index}
        rows.append(row)
    return rows


def _history_index(payload, cik):
    _need(type(payload.get("cik")) in (int, str) and str(payload["cik"]).isdigit()
          and int(payload["cik"]) == int(cik), "GOVERNANCE_SUBMISSIONS_CIK_CONFLICT")
    files = payload["filings"]["files"]
    _need(type(files) is list, "GOVERNANCE_HISTORY_INDEX_INVALID")
    seen = set()
    for row in files:
        _need(type(row) is dict and {"name", "filingFrom", "filingTo"} <= set(row), "GOVERNANCE_HISTORY_INDEX_INVALID")
        name = row["name"]
        _need(type(name) is str and re.fullmatch("CIK" + str(int(cik)).zfill(10) + r"-submissions-\d+\.json", name)
              and name not in seen, "GOVERNANCE_HISTORY_NAME_INVALID_OR_DUPLICATE")
        seen.add(name)
        _need(_date(row["filingFrom"]) <= _date(row["filingTo"]), "GOVERNANCE_HISTORY_RANGE_INVALID")
    return sorted(files, key=lambda r: (r["filingTo"], r["filingFrom"], r["name"]), reverse=True)


def _order(filings):
    """Use SEC acceptance time for same-date filings; never accession rank."""
    def key(filing):
        timestamp = filing.get("acceptanceDateTime", "")
        if timestamp:
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                _need(parsed.utcoffset() is not None, "GOVERNANCE_ACCEPTANCE_TIME_INVALID")
                timestamp = parsed.astimezone(timezone.utc).isoformat()
            except (ValueError, TypeError) as error:
                raise NormalGovernanceInputError("GOVERNANCE_ACCEPTANCE_TIME_INVALID") from error
        return (filing["filingDate"], timestamp)
    for day in {f["filingDate"] for f in filings}:
        same_day = [f for f in filings if f["filingDate"] == day]
        _need(len(same_day) < 2 or all(f.get("acceptanceDateTime") for f in same_day),
              "GOVERNANCE_SAME_DAY_ORDER_NOT_PROVEN")
    values = sorted(filings, key=key, reverse=True)
    _need(len({key(f) for f in values}) == len(values), "GOVERNANCE_SAME_TIME_FILINGS_AMBIGUOUS")
    return values


def history_body_alignment(*, shard, rows):
    """Keep an inconsistent saved index/shard snapshot as an explicit gap."""
    outside = [r for r in rows if not shard["filingFrom"] <= r["filingDate"] <= shard["filingTo"]]
    return None if not outside else {"history_name": shard["name"],
        "declared_filing_from": shard["filingFrom"], "declared_filing_to": shard["filingTo"],
        "out_of_range_filings": [{k: row[k] for k in _IDENTITY_FIELDS} for row in outside],
        "reason": "SAVED_HISTORY_INDEX_AND_BODY_ARE_NOT_A_COHERENT_SNAPSHOT"}


def select_governance_metadata(*, company, prepared_input, inventories):
    """Select filing identities from the complete loaded metadata projection.

    Inventories contain decoded saved bodies and their names; this pure
    function does not confer authenticity on a caller-created dictionary.
    ``prepare_saved_governance_input`` supplies their actual request proofs.
    """
    period = prepared_input["table_input"]["target_period"]
    primary = inventories[0]
    files = _history_index(primary["payload"], company["primary_cik"])
    rows = []
    for inventory in inventories:
        rows.extend(_filings(inventory["payload"], inventory_name=inventory["name"]))
    accessions = [r["accessionNumber"] for r in rows]
    _need(len(accessions) == len(set(accessions)), "GOVERNANCE_INVENTORY_ACCESSIONS_OVERLAP")
    ordinary = [r for r in rows if r["form"] == "10-K"]
    current_end = max((r["reportDate"] for r in rows if r["form"] in {"10-K", "10-K/A"}), default="")
    current = [r for r in ordinary if r["reportDate"] == current_end]
    _need(len(current) == 1 and current_end == period["period_end"], "GOVERNANCE_CURRENT_ORDINARY_MISSING_OR_CHANGED")
    _need(all(current[0][k] == prepared_input["filing"][k] for k in _IDENTITY_FIELDS), "GOVERNANCE_PREPARED_ANNUAL_INPUT_DIVERGED")
    prior_end = max((r["reportDate"] for r in ordinary if r["reportDate"] < current_end), default="")
    priors = [r for r in ordinary if r["reportDate"] == prior_end]
    _need(len(priors) <= 1, "GOVERNANCE_PRIOR_ORDINARY_AMBIGUOUS")
    cutoff = min(period["period_start"], prior_end) if prior_end else "0001-01-01"
    loaded_names = {i["name"] for i in inventories[1:]}
    _need({r["name"] for r in files if r["filingTo"] >= cutoff} <= loaded_names,
          "GOVERNANCE_RELEVANT_HISTORY_NOT_LOADED", "SOURCE_UNAVAILABLE")
    amendments = _order([r for r in rows if r["form"] == "10-K/A" and r["reportDate"] == current_end])
    prior_amendments = _order([r for r in rows if r["form"] == "10-K/A" and r["reportDate"] == prior_end]) if prior_end else []
    proxies = _order([r for r in rows if r["form"] == "DEF 14A"])
    latest_proxy = proxies[0] if proxies else None
    proxy_amendments = _order([r for r in rows if r["form"] == "DEF 14A/A"
                              and (latest_proxy is None or r["filingDate"] >= latest_proxy["filingDate"])])
    events = [r for r in rows if r["form"] in _EVENT_FORMS and period["period_start"] <= r["filingDate"] <= period["period_end"]]
    return {"ordinary": current[0], "amendments": amendments, "current_filing_chain": amendments + current,
            "prior_ordinary": priors[0] if priors else None, "prior_amendments": prior_amendments,
            "prior_filing_chain": prior_amendments + priors,
            "prior_status": "SAME_CIK_PRIOR_DISCOVERED" if priors else "NO_SAME_CIK_PRIOR_IN_COMPLETE_SAVED_SUBMISSIONS",
            "latest_def14a": latest_proxy, "def14a_amendments": proxy_amendments,
            "def14a_status": "LATEST_SAME_CIK_DEF14A_DISCOVERED" if latest_proxy else "NO_SAME_CIK_DEF14A_IN_COMPLETE_RELEVANT_SUBMISSIONS",
            "events": sorted(events, key=lambda f: (f["filingDate"], f["accessionNumber"])),
            "history_loaded": sorted(loaded_names), "history_not_needed": [r for r in files if r["name"] not in loaded_names]}


class _Sources:
    def __init__(self, root, company_id, cik):
        self.root, self.company_id, self.cik = root, company_id, str(cik)
        self.cache, self.proofs, self.records = {}, {}, {}
        self.file_sets = []
        self.failed_attempts = {}

    def read(self, url, *, accession="", role, media_type, required=True):
        key = (url, accession, role, media_type)
        if key in self.cache:
            return self.cache[key]
        try:
            item = saved_source(repo_root=self.root, url=url, accession=accession)
        except AnnualUpdateError as error:
            if str(error).startswith("LATEST_SOURCE_REQUEST_FAILED"):
                matches = [(i, r) for i, r in enumerate(_rows(self.root)) if r["source_url"] == url and r["method"] == "GET"]
                if matches:
                    index, row = matches[-1]
                    attempt_id = request_log_attempt_id(row_index=index, row=row)
                    self.failed_attempts[attempt_id] = {"request_attempt_id": attempt_id,
                        **{k: row[k] for k in ("timestamp_utc", "source_url", "status_code", "error", "retry_attempt")}}
            raise
        except BatchWorkflowError as error:
            # The old convenience selector refuses repeated legacy attempts.
            # Pin the actual final GET row with the existing explicit verifier;
            # do not invent an attempt, change the ledger, or upgrade its tier.
            if str(error) != "Exact SEC response has ambiguous legacy ledger attempts":
                raise
            matches = [(i, r) for i, r in enumerate(_rows(self.root)) if r["source_url"] == url and r["method"] == "GET"]
            _need(bool(matches), "GOVERNANCE_PINNED_REQUEST_MISSING")
            index, row = matches[-1]
            _need(row["status_code"] == "200" and not row["error"], "GOVERNANCE_LATEST_SOURCE_REQUEST_FAILED", "SOURCE_ACCESS_FAILED")
            proof = validate_request_attempt_binding(repo_root=self.root, source_url=url, content_sha256=row["content_sha256"],
                accession=accession, document_name=row["document_name"], request_attempt_id=request_log_attempt_id(row_index=index, row=row), require_immutable=False)
            headers = strict_json_file(path=resolve_repository_file(repo_root=self.root, repo_relative_path=proof["request_headers_repo_relative_path"]))
            item = {"proof": {"source_url": url, "accession": accession, "document_name": row["document_name"],
                              "content_sha256": row["content_sha256"], **proof},
                    "saved_at_utc": _utc(headers.get("saved_at_utc")),
                    "raw": resolve_repository_file(repo_root=self.root, repo_relative_path=proof["request_repo_relative_path"]).read_bytes()}
        if item is None:
            _need(not required, "SAVED_SOURCE_MISSING:" + url, "SOURCE_UNAVAILABLE")
            return None
        proof = item["proof"]
        blob = raw_blob_record(repo_root=self.root, repo_relative_path=proof["request_repo_relative_path"], media_type=media_type)
        _need(blob["raw_asset_id"] == "sha256:" + sha256_bytes(content=item["raw"])
              and proof["request_body_sha256"] == proof["content_sha256"] == blob["raw_asset_id"][7:], "GOVERNANCE_SOURCE_CHANGED_DURING_READ")
        reference = source_reference_record(raw_blob=blob, company_id=self.company_id, source_url=url,
            accession=accession or "SUBMISSIONS-" + self.cik, document_name=proof["document_name"],
            source_role=role, request_attempt_id=proof["request_attempt_id"])
        result = {"raw_bytes": item["raw"], "raw_blob": blob, "source_reference": reference}
        self.cache[key] = result
        self.records[blob["raw_asset_id"]] = blob
        self.records[reference["source_reference_id"]] = reference
        self.proofs[reference["source_reference_id"]] = {"source_reference_id": reference["source_reference_id"],
            "raw_asset_id": blob["raw_asset_id"], "proof": proof, "saved_at_utc": item["saved_at_utc"]}
        return result

    def primary(self, filing, *, required=True):
        return self.read(accession_document_url(cik=int(self.cik), accession=filing["accessionNumber"], document_name=filing["primaryDocument"]),
            accession=filing["accessionNumber"], role="governance_proxy" if filing["form"].startswith("DEF 14A") else "target_primary",
            media_type="text/html", required=required)

    def auditor_filing(self, filing):
        accession = filing["accessionNumber"]
        index = self.read(accession_directory_url(cik=int(self.cik), accession=accession), accession=accession,
                          role="accession_index", media_type="application/json")
        payload = strict_json_loads(text=index["raw_bytes"].decode("utf-8"))
        directory = payload["directory"]
        _need(directory["name"] == "/Archives/edgar/data/" + self.cik + "/" + accession.replace("-", ""), "GOVERNANCE_ACCESSION_INDEX_IDENTITY_CONFLICT")
        items = directory["item"]
        _need(type(items) is list and all(type(x) is dict and type(x.get("name")) is str
              and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", x["name"]) for x in items), "GOVERNANCE_ACCESSION_INDEX_ITEMS_INVALID")
        names = [x["name"] for x in items]
        _need(len(names) == len(set(names)) and filing["primaryDocument"] in names, "GOVERNANCE_PRIMARY_NOT_IN_INDEX_OR_DUPLICATE")
        xml_names = sorted(n for n in names if n.lower().endswith(".xml") and n.lower() != "filingsummary.xml"
                           and not n.lower().endswith(("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml"))
                           and re.match(r"r\d", n, re.I) is None)
        primary = self.primary(filing, required=False)
        sources = [primary] if primary else []
        for name in xml_names:
            sources.append(self.read(accession_document_url(cik=int(self.cik), accession=accession, document_name=name),
                accession=accession, role="auditor_facts", media_type="application/xml"))
        _need(bool(sources), "GOVERNANCE_AUDITOR_SOURCE_NOT_SAVED:" + accession, "SOURCE_UNAVAILABLE")
        self.file_sets.append({"filing": filing, "index_source_reference_id": index["source_reference"]["source_reference_id"],
            "expected_xml_documents": xml_names, "primary_saved": primary is not None,
            "missing_primary_treatment": None if primary else "AUDITOR_INSTANCE_ROUTE_DOES_NOT_REQUIRE_UNSAVED_HTML",
            "source_reference_ids": [s["source_reference"]["source_reference_id"] for s in sources]})
        return sources


def prepare_saved_governance_input(*, repo_root: Path, company_id: str):
    """Prepare resolver inputs and portable records without executing metrics."""
    ledger_path = repo_root / "evidence/requests_log.csv"
    ledger_sha = sha256_file(path=ledger_path)
    registry_sha = sha256_file(path=repo_root / "config/company_registry.csv")
    _need(registry_sha == sha256_file(path=_CODE_ROOT / "config/company_registry.csv"),
          "GOVERNANCE_COMPANY_REGISTRY_DIFFERS_FROM_INSTALLED_SCOPE")
    prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id)
    company = next(c for c in _registry_rows(repo_root=repo_root) if c["company_id"] == company_id)
    cik = prepared["subject_policy"]["selected_cik"]
    _need(cik == prepared["entity"] == company["primary_cik"] and prepared["subject_policy"]["cross_entity_combination_authorized"] is False,
          "GOVERNANCE_SUBJECT_POLICY_CONFLICT")
    reader = _Sources(repo_root, company_id, cik)
    current_inventory = reader.read(submissions_url(cik=int(cik)), role="sec_submissions_inventory", media_type="application/json")
    payload = strict_json_loads(text=current_inventory["raw_bytes"].decode("utf-8"))
    files = _history_index(payload, cik)
    inventories = [{"name": current_inventory["source_reference"]["document_name"], "payload": payload, "source": current_inventory}]
    rows = _filings(payload, inventory_name=inventories[0]["name"])
    period = prepared["table_input"]["target_period"]
    history_conflicts = []
    for shard in files:
        prior_end = max((r["reportDate"] for r in rows if r["form"] == "10-K" and r["reportDate"] < period["period_end"]), default="")
        cutoff = min(prior_end, period["period_start"]) if prior_end else "0001-01-01"
        if shard["filingTo"] < cutoff:
            break
        source = reader.read(submissions_file_url(file_name=shard["name"]), role="sec_submissions_history", media_type="application/json")
        data = strict_json_loads(text=source["raw_bytes"].decode("utf-8"))
        if "cik" in data:
            _need(str(data["cik"]).isdigit() and int(data["cik"]) == int(cik), "GOVERNANCE_HISTORY_BODY_ENTITY_CONFLICT")
        shard_rows = _filings(data, inventory_name=shard["name"])
        conflict = history_body_alignment(shard=shard, rows=shard_rows)
        if conflict:
            history_conflicts.append(conflict)
        rows.extend(shard_rows)
        inventories.append({"name": shard["name"], "payload": data, "source": source})
    selection = select_governance_metadata(company=company, prepared_input=prepared, inventories=inventories)
    # Include normal annual preparation's Company Facts proof in its portable
    # closure even though it is not the source of compensation/auditor values.
    reader.read(companyfacts_url(cik=int(cik)), accession=selection["ordinary"]["accessionNumber"], role="companyfacts", media_type="application/json")
    scope = {"entity_scope": "registrant"}
    target = {"company_id": company_id, "period_start": period["period_start"], "period_end": period["period_end"], "scope": scope, "scope_key": scope_key(scope=scope)}
    resolvers, limitations, manifests = {}, [], []
    proxy = selection["latest_def14a"]
    try:
        if proxy is not None:
            source = reader.primary(proxy)
            resolvers["c03_ecd"] = {"spec_path": C03_SPEC_PATH, "arguments": {**source, "target": target, "expected_cik": cik}}
        else:
            limitations.append({"metric_id": "C03", "category": "SOURCE_ROUTE_UNAVAILABLE", "reason": selection["def14a_status"]})
        if selection["def14a_amendments"]:
            for filing in selection["def14a_amendments"]:
                reader.primary(filing)
            resolvers.pop("c03_ecd", None)
            limitations.append({"metric_id": "C03", "category": "IMPLEMENTATION_GAP", "reason": "DEF14A_AMENDMENT_CHAIN_REQUIRES_SEMANTIC_REPLAY"})
    except (NormalGovernanceInputError, AnnualUpdateError, BatchWorkflowError, SourceError) as error:
        limitations.append({"metric_id": "C03", "category": getattr(error, "category", "SOURCE_ACCESS_FAILED"), "reason": str(error)})
    sct = []
    for filing in selection["current_filing_chain"]:
        try:
            source = reader.primary(filing)
            sct.append({"spec_path": SCT_SPEC_PATH, "filing": filing, "arguments": {**source,
                "expected_company_id": company_id, "expected_cik": cik, "report_period_start": period["period_start"],
                "report_period_end": period["period_end"], "fiscal_year": period["fiscal_year"]}})
        except (NormalGovernanceInputError, AnnualUpdateError, BatchWorkflowError, SourceError) as error:
            limitations.append({"metric_id": "C03", "category": getattr(error, "category", "SOURCE_ACCESS_FAILED"), "reason": str(error)})
    resolvers["c03_sct_candidates"] = sct
    try:
        _need(not history_conflicts, "GOVERNANCE_HISTORY_SNAPSHOT_COVERAGE_CONFLICT", "SOURCE_COVERAGE_CONFLICT")
        current = [reader.auditor_filing(f) for f in selection["current_filing_chain"]]
        prior = [reader.auditor_filing(f) for f in selection["prior_filing_chain"]]
        event_inputs = []
        needed_history = {s["name"] for s in files if s["filingFrom"] <= period["period_end"] and s["filingTo"] >= period["period_start"]}
        for inventory in inventories:
            if inventory is not inventories[0] and inventory["name"] not in needed_history:
                continue
            documents, references = [], []
            events = [r for r in selection["events"] if r["metadata_origin"]["inventory_name"] == inventory["name"]]
            for filing in events:
                primary = reader.read(accession_document_url(cik=int(cik), accession=filing["accessionNumber"], document_name=filing["primaryDocument"]),
                    accession=filing["accessionNumber"], role="fy_8k_primary", media_type="text/html")
                hdr = reader.read(hdr_sgml_url(cik=int(cik), accession=filing["accessionNumber"]), accession=filing["accessionNumber"], role="fy_8k_header", media_type="text/plain")
                documents.append({"hdr_bytes": hdr["raw_bytes"], "hdr_source_reference": hdr["source_reference"],
                    "primary_document_bytes": primary["raw_bytes"], "primary_source_reference": primary["source_reference"]})
                references.extend([hdr["source_reference"], primary["source_reference"]])
            source = inventory["source"]
            manifest = source_set_manifest(company_id=company_id, source_role="fy_8k_item_inventory", form_types=_EVENT_FORMS,
                fiscal_or_date_window={"period_start": period["period_start"], "period_end": period["period_end"]},
                discovery_policy="PINNED_SUBMISSIONS", inventory_source_reference=source["source_reference"], inventory_bytes=source["raw_bytes"],
                ordered_source_references=references, cutoff_timestamp_or_pinned_submissions_attempt=source["source_reference"]["request_attempt_id"])
            manifests.append(manifest)
            event_inputs.append({"filing_documents": documents, "source_set_manifest": manifest,
                "inventory_source_reference": source["source_reference"], "inventory_bytes": source["raw_bytes"]})
        event_input = {**event_inputs[0], "history_inputs": event_inputs[1:]}
        resolvers["c04"] = {"spec_path": C04_V2_SPEC_PATH, "arguments": {"current_filings": current, "prior_filings": prior,
            "prior_sources": [], "target_accession": selection["current_filing_chain"][0]["accessionNumber"],
            "prior_period_end": selection["prior_ordinary"]["reportDate"] if selection["prior_ordinary"] else "",
            "target": target, "expected_cik": cik, "event_input": event_input}}
    except (NormalGovernanceInputError, AnnualUpdateError, BatchWorkflowError, SourceError) as error:
        limitations.append({"metric_id": "C04", "category": getattr(error, "category", "SOURCE_ACCESS_FAILED"), "reason": str(error)})
    _need(sha256_file(path=ledger_path) == ledger_sha, "GOVERNANCE_LEDGER_CHANGED_DURING_PREPARATION")
    body = {"record_type": "NORMAL_GOVERNANCE_INPUT_BINDING", "company_id": company_id,
            "company_registry_sha256": registry_sha, "subject_policy": prepared["subject_policy"],
            "prepared_annual_input": prepared, "selection": selection, "accession_source_sets": reader.file_sets,
            "source_proofs": [row["proof"] for row in reader.proofs.values()],
            "source_bindings": list(reader.proofs.values()), "source_set_manifests": manifests, "limitations": limitations,
            "failed_source_attempts": list(reader.failed_attempts.values()),
            "history_alignment_conflicts": history_conflicts,
            "metric_input_status": {"C03": "BLOCKED" if any(x["metric_id"] == "C03" and x["category"] != "SOURCE_ROUTE_UNAVAILABLE" for x in limitations)
                                    else "PREPARED" if "c03_ecd" in resolvers or sct else "BLOCKED",
                                    "C04": "PREPARED" if "c04" in resolvers else "BLOCKED"},
            "source_evidence": "REAL_SAVED_REQUEST_PROOFS", "execution": "NOT_EXECUTED", "production_authorized": False}
    binding = {**body, "input_binding_id": content_hash(value=body)}
    return {"input_binding": binding, "records": list(reader.records.values()), "resolver_inputs": resolvers,
            "business_calls": [0, 0, 0]}


def verify_current_governance_preparation(*, repo_root: Path, company_id: str, input_binding):
    """Re-discover current inputs; historical Run replay instead pins old proofs."""
    rebuilt = prepare_saved_governance_input(repo_root=repo_root, company_id=company_id)
    _need(rebuilt["input_binding"] == input_binding, "GOVERNANCE_CURRENT_PREPARATION_CHANGED")
    return rebuilt
