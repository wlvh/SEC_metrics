"""C04 for a pinned annual period, composed from routes that already exist.

C04 asks whether the registrant changed auditor. ``resolve_c04`` answers it by
comparing the auditor named in the target annual report with the one named in
the prior period's, and by reading the fiscal window's 8-K item index
independently - so that two equal names are not turned into a confirmed
no-change flag without the events that would have reported one.

Both halves already have a historical form. The annual chain comes from
``prepare_historical_annual_input``, which owns which filing a pinned period
means; the blocks the event window needs are loaded by the same cutoff the
ordinary route uses, which is already driven by the period rather than by the
newest filing. What was missing was the selection in between:
``select_governance_metadata`` decides which annual report is current by taking
the maximum report date across the loaded rows, which is right only for the
newest year. ``historical_governance_input`` replaces that one rule.

So this module is assembly, not arithmetic. It reads no filing itself and
computes no comparison: ``resolve_c04`` does both, unchanged, and returns the
Result and ExecutionTrace this hands to the Run factory.

What it does not do: reach a value where the material is not saved. The
accession index and instance the auditor comparison needs are class A of the
acquisition plan for every period but the most recent, so an earlier year
produces a named source gap rather than a flag. That is the correct answer for
a period whose material is missing, and it is why wiring this route is not the
same thing as delivering C04 for five years.
"""
from pathlib import Path

from sec_urls import companyfacts_url, submissions_file_url, submissions_url

from .calculator import withheld_metric_result
from .canonical import content_hash, sha256_file, strict_json_loads
from .governance_compensation_table import (SPEC_PATH as SCT_SPEC_PATH,
                                            CompensationTableError,
                                            resolve_compensation_table)
from .governance_signals import (C03_SPEC_PATH, C04_V2_SPEC_PATH, GovernanceSignalError,
                                 resolve_c03, resolve_c04)
from .historical_annual_input import prepare_historical_annual_input
from .historical_governance_input import (HistoricalGovernanceError,
                                          select_historical_governance_metadata)
from .normal_annual_input import _registry_rows
from .normal_companyfacts_results import _SOURCE_ERRORS
from .normal_governance_input import (_EVENT_FORMS, _Sources, _filings, _history_index,
                                      history_body_alignment)
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .deterministic_router import source_set_manifest
from .specs import compile_spec_file

RECORD_TYPE = "HISTORICAL_GOVERNANCE_COMPONENT"
# C03's path is the stage that answered, not a constant: the ordinary route
# tries the proxy's ECD facts first and the annual report's compensation table
# second, and it returns whichever one produced the value. Four of this
# repository's ten companies would get a different answer from a route that
# only carried one of the two - measured, not assumed.
SPEC_PATHS = {"C03": C03_SPEC_PATH, "C04": C04_V2_SPEC_PATH}
SUPPORTED_METRICS = tuple(sorted(SPEC_PATHS))


def _need(condition, reason, category=None):
    if not condition:
        error = HistoricalGovernanceError(reason)
        if category is not None:
            error.category = category
        raise error


def _blocks(*, reader, cik, payload, period, current):
    """The submissions blocks this pinned period and its prior year can need.

    The cutoff is the ordinary route's own: stop once no unread block can hold
    a filing dated on or after the earlier of the period start and the prior
    annual report end. That rule was already written in terms of the period it
    was given rather than the newest filing, so it needs no successor - only
    the selection that follows it did.
    """
    files = _history_index(payload, cik)
    inventories = [{"name": current["source_reference"]["document_name"],
                    "payload": payload, "source": current}]
    rows = _filings(payload, inventory_name=inventories[0]["name"])
    conflicts = []
    for shard in files:
        prior_end = max((row["reportDate"] for row in rows if row["form"] == "10-K"
                         and row["reportDate"] < period["period_end"]), default="")
        cutoff = min(prior_end, period["period_start"]) if prior_end else "0001-01-01"
        if shard["filingTo"] < cutoff:
            break
        source = reader.read(submissions_file_url(file_name=shard["name"]),
                             role="sec_submissions_history", media_type="application/json")
        data = strict_json_loads(text=source["raw_bytes"].decode("utf-8"))
        if "cik" in data:
            _need(str(data["cik"]).isdigit() and int(data["cik"]) == int(cik),
                  "HISTORICAL_GOVERNANCE_HISTORY_BODY_ENTITY_CONFLICT")
        shard_rows = _filings(data, inventory_name=shard["name"])
        conflict = history_body_alignment(shard=shard, rows=shard_rows)
        if conflict:
            conflicts.append(conflict)
        rows.extend(shard_rows)
        inventories.append({"name": shard["name"], "payload": data, "source": source})
    _need(not conflicts, "HISTORICAL_GOVERNANCE_HISTORY_SNAPSHOT_COVERAGE_CONFLICT",
          "SOURCE_COVERAGE_CONFLICT")
    accessions = [row["accessionNumber"] for row in rows]
    _need(len(accessions) == len(set(accessions)),
          "HISTORICAL_GOVERNANCE_INVENTORY_ACCESSIONS_OVERLAP")
    return inventories, rows, files


def _event_input(*, reader, cik, company_id, period, selection, inventories, files):
    """The fiscal window's 8-K documents, per block, in the shape C04 reads.

    ``resolve_c04`` checks that the blocks supplied cover every block whose
    declared range overlaps the period, so the set is built from the same
    declaration rather than from whichever blocks happened to be loaded.
    """
    from sec_urls import accession_document_url, hdr_sgml_url
    needed = {shard["name"] for shard in files
              if shard["filingFrom"] <= period["period_end"]
              and shard["filingTo"] >= period["period_start"]}
    inputs, manifests = [], []
    for inventory in inventories:
        if inventory is not inventories[0] and inventory["name"] not in needed:
            continue
        documents, references = [], []
        events = [row for row in selection["events"]
                  if row["metadata_origin"]["inventory_name"] == inventory["name"]]
        for filing in events:
            primary = reader.read(
                accession_document_url(cik=int(cik), accession=filing["accessionNumber"],
                                       document_name=filing["primaryDocument"]),
                accession=filing["accessionNumber"], role="fy_8k_primary",
                media_type="text/html")
            header = reader.read(hdr_sgml_url(cik=int(cik),
                                              accession=filing["accessionNumber"]),
                                 accession=filing["accessionNumber"], role="fy_8k_header",
                                 media_type="text/plain")
            documents.append({"hdr_bytes": header["raw_bytes"],
                              "hdr_source_reference": header["source_reference"],
                              "primary_document_bytes": primary["raw_bytes"],
                              "primary_source_reference": primary["source_reference"]})
            references.extend([header["source_reference"], primary["source_reference"]])
        source = inventory["source"]
        manifest = source_set_manifest(
            company_id=company_id, source_role="fy_8k_item_inventory",
            form_types=_EVENT_FORMS,
            fiscal_or_date_window={"period_start": period["period_start"],
                                   "period_end": period["period_end"]},
            discovery_policy="PINNED_SUBMISSIONS",
            inventory_source_reference=source["source_reference"],
            inventory_bytes=source["raw_bytes"], ordered_source_references=references,
            cutoff_timestamp_or_pinned_submissions_attempt=
            source["source_reference"]["request_attempt_id"])
        manifests.append(manifest)
        inputs.append({"filing_documents": documents, "source_set_manifest": manifest,
                       "inventory_source_reference": source["source_reference"],
                       "inventory_bytes": source["raw_bytes"]})
    return {**inputs[0], "history_inputs": inputs[1:]}, manifests


def _component(*, root, company_id, metric_id, period_selection, prepared, reader,
               selection, period, target, spec, spec_path, resolution, limitation,
               manifests, ledger):
    """The component shape both governance routes return.

    Shared rather than copied: the proof closure, the admission, the record
    ordering and the ledger check are properties of this route, not of one
    metric, and two copies would drift the moment one of them gained a check.
    """
    proofs_by_id = {}
    for proof in [*prepared["source_proofs"],
                  *(value["proof"] for value in reader.proofs.values())]:
        key = proof["request_attempt_id"]
        _need(key not in proofs_by_id or proofs_by_id[key] == proof,
              "HISTORICAL_GOVERNANCE_REQUEST_PROOF_COLLISION")
        proofs_by_id[key] = proof
    proofs = list(proofs_by_id.values())
    admission = verify_ordinary_source_proofs(data_root=root, proofs=proofs)
    source_records = list(reader.records.values())
    references = [record for record in source_records
                  if record["record_type"] == "SOURCE_REFERENCE"]
    # SourceSetManifests are not Run records - the event route carries them in
    # their own slot for the same reason - so they are exposed beside the
    # records rather than appended to them. The observation references them by
    # id, and a reader that wants the manifest a reference names finds it here.
    records = list(source_records)
    if resolution["observation"] is not None:
        records.append(resolution["observation"])
    records.extend([resolution["trace"], resolution["result"]])
    _need(sha256_file(path=root / "evidence/requests_log.csv") == ledger,
          "HISTORICAL_GOVERNANCE_LEDGER_CHANGED_DURING_PREPARATION")
    return {"record_type": RECORD_TYPE, "schema_version": 1, "company_id": company_id,
            "metric_id": metric_id, "spec_path": spec_path, "compiled_spec": spec,
            "selection": selection["selected_by"], "limitation": limitation,
            "resolution_selection_id": resolution["selection"]["selection_id"],
            "records": records, "source_records": source_records,
            "source_references": references, "source_proofs": proofs,
            "source_admission": admission, "source_set_manifests": manifests,
            "result": resolution["result"],
            "trace": resolution["trace"], "observation": resolution["observation"],
            "target_period": period, "loaded_blocks": selection["loaded_blocks"],
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}


def _compensation_resolution(*, root, reader, selection, target, company_id, cik,
                             period, spec):
    """C03 for the pinned period: the proxy's ECD facts, then the report's table.

    The same two stages the ordinary route runs and in the same order, because
    a route carrying one of them gives the other stage's companies an answer
    that is confident and wrong. The proxy is the one pinned to this period
    rather than the latest one; the compensation-table candidates come from
    this period's own annual chain.

    Returns the spec path that answered, the resolution, and a limitation
    record when neither stage did - a missing proxy is a source gap and keeps
    that name.
    """
    def blocked(reason, details):
        withheld, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                                 reason_code=reason)
        return (C03_SPEC_PATH,
                {"selection": {"selection_id": None, "reason_code": reason,
                               "details": details},
                 "observation": None, "result": withheld, "trace": trace},
                {"reason": reason, "details": details,
                 "category": "SOURCE_OR_IMPLEMENTATION_UNRESOLVED"})

    proxy, failures = selection["pinned_def14a"], []
    if selection["def14a_amendments"]:
        # The frozen route stops here too: an amended proxy needs a semantic
        # replay this deterministic path does not do, and choosing the
        # unamended one would be answering from a superseded document.
        for filing in selection["def14a_amendments"]:
            failures.append({"filing": filing["accessionNumber"],
                             "reason": "DEF14A_AMENDMENT_CHAIN_REQUIRES_SEMANTIC_REPLAY"})
    elif proxy is not None:
        try:
            source = reader.primary(proxy)
            resolved = resolve_c03(compiled_spec=spec, **source, target=target,
                                   expected_cik=cik)
            if resolved["selection"]["reason_code"] not in {"C03_PEO_FACT_NOT_FOUND",
                                                            "C03_TARGET_PERIOD_NOT_FOUND"}:
                return C03_SPEC_PATH, resolved, None
            failures.append(resolved["selection"])
        except (*_SOURCE_ERRORS, GovernanceSignalError) as error:
            failures.append({"filing": proxy["accessionNumber"], "reason": str(error)})
    else:
        failures.append({"reason": selection["def14a_status"]})
    table_spec = compile_spec_file(path=root / SCT_SPEC_PATH, dependency_specs={})
    for filing in selection["current_filing_chain"]:
        try:
            source = reader.primary(filing)
            resolved = resolve_compensation_table(
                compiled_spec=table_spec, **source, expected_company_id=company_id,
                expected_cik=cik, report_period_start=period["period_start"],
                report_period_end=period["period_end"],
                fiscal_year=period["fiscal_year"])
            if resolved["result"]["value"] is not None:
                return SCT_SPEC_PATH, resolved, None
            failures.append(resolved["selection"])
            if resolved["selection"]["reason_code"] != "SCT_SUPPORTED_TABLE_NOT_FOUND":
                return blocked("C03_REPORTED_TABLE_UNRESOLVED", failures)
        except CompensationTableError as error:
            failures.append({"filing": filing["accessionNumber"], "reason": str(error)})
            # An absent table may continue to the next filing in the chain. A
            # found but conflicting table cannot be repaired by reading an
            # older one.
            if "SCT_TABLE_NOT_FOUND" not in str(error) and "SCT_TABLE_TITLE" not in str(error):
                return blocked("C03_REPORTED_TABLE_UNRESOLVED", failures)
        except _SOURCE_ERRORS as error:
            failures.append({"filing": filing["accessionNumber"], "reason": str(error)})
    return blocked("C03_SUPPORTED_CURRENT_SOURCE_NOT_FOUND", failures)


def resolve_historical_governance_metric(*, repo_root: Path, company_id: str,
                                         metric_id: str, period_selection):
    """One governance metric resolved against a pinned annual period.

    Args:
        repo_root: Installed data root holding the saved bytes.
        company_id: Configured company.
        metric_id: Currently C04 only.
        period_selection: The pinned period this Run is for.

    Returns:
        The component shape the historical Run factory consumes: the compiled
        Spec, the admitted source set, the records, and the Result and
        ExecutionTrace ``resolve_c04`` produced.

    Raises:
        HistoricalGovernanceError: When the metric is not wired here, when the
            blocks disagree with their declared ranges, or when the selection
            does not name this period's filing.
        GovernanceSignalError: When the material a comparison needs is not
            saved. That is a source gap rather than a route gap and keeps its
            own reason.
    """
    _need(metric_id in SPEC_PATHS,
          "HISTORICAL_GOVERNANCE_METRIC_NOT_WIRED:" + str(metric_id), "IMPLEMENTATION_GAP")
    root = Path(repo_root)
    ledger = sha256_file(path=root / "evidence/requests_log.csv")
    prepared = prepare_historical_annual_input(repo_root=root, company_id=company_id,
                                               period_selection=period_selection)
    company = next(row for row in _registry_rows(repo_root=root)
                   if row["company_id"] == company_id)
    cik = prepared["entity"]
    _need(cik == company["primary_cik"], "HISTORICAL_GOVERNANCE_SUBJECT_POLICY_CONFLICT")
    reader = _Sources(root, company_id, cik)
    current = reader.read(submissions_url(cik=int(cik)), role="sec_submissions_inventory",
                          media_type="application/json")
    payload = strict_json_loads(text=current["raw_bytes"].decode("utf-8"))
    period = prepared["table_input"]["target_period"]
    inventories, rows, files = _blocks(reader=reader, cik=cik, payload=payload,
                                       period=period, current=current)
    selection = select_historical_governance_metadata(
        prepared=prepared, history={"all_rows": rows,
                                    "loaded_inventories": [i["name"] for i in inventories]})
    reader.read(companyfacts_url(cik=int(cik)),
                accession=selection["ordinary"]["accessionNumber"], role="companyfacts",
                media_type="application/json")
    scope = {"entity_scope": "registrant"}
    target = {"company_id": company_id, "period_start": period["period_start"],
              "period_end": period["period_end"], "scope": scope,
              "scope_key": scope_key(scope=scope)}
    spec_path = SPEC_PATHS[metric_id]
    spec = compile_spec_file(path=root / spec_path, dependency_specs={})
    _need(spec["compiled"]["metric_id"] == metric_id,
          "HISTORICAL_GOVERNANCE_SPEC_METRIC_CHANGED:" + spec_path)
    if metric_id == "C03":
        spec_path, resolution, limitation = _compensation_resolution(
            root=root, reader=reader, selection=selection, target=target,
            company_id=company_id, cik=cik, period=period, spec=spec)
        spec = compile_spec_file(path=root / spec_path, dependency_specs={})
        return _component(root=root, company_id=company_id, metric_id=metric_id,
                          period_selection=period_selection, prepared=prepared,
                          reader=reader, selection=selection, period=period,
                          target=target, spec=spec, spec_path=spec_path,
                          resolution=resolution, limitation=limitation,
                          manifests=[], ledger=ledger)
    # A period whose accession material is not saved is a source gap, not a
    # route gap, and the frame has to be able to say which. So the reads and
    # the comparison are inside one boundary and a missing file becomes a
    # withheld Result carrying the reason - the same shape the Company Facts
    # route uses - rather than an exception that produces no Run at all.
    manifests, limitation = [], None
    try:
        chain = [reader.auditor_filing(filing)
                 for filing in selection["current_filing_chain"]]
        prior_chain = [reader.auditor_filing(filing)
                       for filing in selection["prior_filing_chain"]]
        event_input, manifests = _event_input(
            reader=reader, cik=cik, company_id=company_id, period=period,
            selection=selection, inventories=inventories, files=files)
        resolution = resolve_c04(
            current_filings=chain, prior_filings=prior_chain, prior_sources=[],
            target_accession=selection["ordinary"]["accessionNumber"],
            prior_period_end=(selection["prior_ordinary"]["reportDate"]
                              if selection["prior_ordinary"] else ""),
            target=target, expected_cik=cik, compiled_spec=spec, event_input=event_input)
    except (*_SOURCE_ERRORS, GovernanceSignalError) as error:
        limitation = {"reason": str(error), "error_type": type(error).__name__,
                      "category": getattr(error, "category", "SOURCE_OR_IMPLEMENTATION_UNRESOLVED")}
        withheld, trace = withheld_metric_result(
            compiled_spec=spec, target=target,
            reason_code="HISTORICAL_GOVERNANCE_SOURCE_ROUTE_UNRESOLVED")
        resolution = {"selection": {"selection_id": None}, "observation": None,
                      "result": withheld, "trace": trace}
    return _component(root=root, company_id=company_id, metric_id=metric_id,
                      period_selection=period_selection, prepared=prepared,
                      reader=reader, selection=selection, period=period,
                      target=target, spec=spec, spec_path=spec_path,
                      resolution=resolution, limitation=limitation,
                      manifests=manifests, ledger=ledger)

