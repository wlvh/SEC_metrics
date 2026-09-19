"""Turn the saved annual catalog into a deduplicated acquisition plan.

Separate from ``normal_history_catalog`` on purpose. The catalog reads saved
submissions metadata and its identity is bound to its own bytes, so an
installed historical package replays only while that reader is unchanged. A
plan is a different kind of statement: it says which documents are still
missing, which saved bytes are stale, and what an acquisition would cost, and
those rules are expected to keep improving. Holding both in one file meant
every planning fix changed the catalog's identity and invalidated packages
whose sources and reading had not changed at all.

Nothing here fetches anything. Producing a plan spends no SEC or model business
call and authorizes none.
"""
from pathlib import Path

from sec_urls import (accession_directory_url, accession_document_url,
                      companyfacts_url, submissions_file_url, submissions_url)

from .canonical import content_hash, sha256_file
from .normal_annual_input import _registry_rows
from .normal_history_catalog import (HistoryCatalogError, _need, load_annual_history,
                                     target_period_candidates)
from .sources import resolve_repository_file


PLAN_RECORD_TYPE = "ORDINARY_HISTORICAL_SOURCE_PLAN"


def _document_requirements(*, cik, filing, roles, consumer):
    accession = filing["accessionNumber"]
    return [
        {"source_url": accession_document_url(cik=int(cik), accession=accession,
                                              document_name=filing["primaryDocument"]),
         "media_type": "text/html", "accession": accession,
         "document_name": filing["primaryDocument"],
         "dependency_class": "ANNUAL_PERIOD_IDENTITY",
         "source_roles": list(roles), "consumers": list(consumer)},
        {"source_url": accession_directory_url(cik=int(cik), accession=accession),
         "media_type": "application/json", "accession": accession,
         "document_name": "index.json",
         "dependency_class": "ACCESSION_INSTANCE_DISCOVERY",
         "source_roles": [role + "_accession_index" for role in roles],
         "consumers": list(consumer)},
    ]


def _native_instance_alternative(reader, repo_root, filing, cik):
    """Is this filing's own authenticated instance saved instead of its HTML?

    The existing prior-annual route already establishes an annual period from
    the accession's own XBRL instance, authenticated through the saved
    accession index, with the same DEI identity checks. Recording that here
    keeps the plan honest about what still needs acquiring; it does not by
    itself authorize any consumer to substitute an instance for HTML text.
    """
    from .annual_update import AnnualUpdateError
    from .batch_workflow import BatchWorkflowError
    from .normal_governance_input import NormalGovernanceInputError
    from .sources import SourceError
    try:
        sources = reader.auditor_filing(filing)
    except (AnnualUpdateError, BatchWorkflowError, NormalGovernanceInputError,
            SourceError, HistoryCatalogError) as error:
        return {"status": "NOT_ESTABLISHED", "reason": str(error),
                "error_type": type(error).__name__}
    file_set = reader.file_sets[-1]
    if file_set["primary_saved"] or not file_set["expected_xml_documents"]:
        return {"status": "NOT_APPLICABLE"}
    from .normal_annual_input import annual_period
    try:
        periods = [annual_period(raw=item["raw_bytes"], cik=cik, filing=filing)
                   for item in sources]
    except (AnnualUpdateError, SourceError, ValueError) as error:
        return {"status": "NOT_ESTABLISHED", "reason": str(error),
                "error_type": type(error).__name__}
    if not periods or any(period != periods[0] for period in periods):
        return {"status": "NOT_ESTABLISHED", "reason": "NATIVE_INSTANCE_PERIOD_CONFLICT"}
    return {"status": "VERIFIED_ACCESSION_NATIVE_INSTANCE",
            "annual_period": periods[0],
            "instance_documents": file_set["expected_xml_documents"],
            "satisfies_source_roles": ["prior_annual_primary"],
            "establishes_issuer_fiscal_label": False,
            "substitutes_html_text_range": False,
            "source_acquisition_credit": False}


def _saved_state(reader, repo_root, item):
    """Classify one declared dependency against the saved request ledger."""
    from .annual_update import AnnualUpdateError
    from .batch_workflow import BatchWorkflowError
    from .sources import SourceError
    try:
        source = reader.read(item["source_url"], accession=item["accession"],
                             role=item["source_roles"][0], media_type=item["media_type"],
                             required=False)
    except (AnnualUpdateError, BatchWorkflowError, SourceError, HistoryCatalogError) as error:
        return {"saved_status": "SAVED_SOURCE_BLOCKED", "reason": str(error),
                "error_type": type(error).__name__}
    if source is None:
        return {"saved_status": "MISSING_SAVED_SOURCE"}
    from .ordinary_source_authority import verify_ordinary_source_proofs
    proof = next(v["proof"] for v in reader.proofs.values()
                 if v["source_reference_id"] == source["source_reference"]["source_reference_id"])
    verify_ordinary_source_proofs(data_root=repo_root, proofs=[proof])
    return {"saved_status": "VERIFIED_SAVED_SOURCE",
            "content_sha256": proof["content_sha256"],
            "request_attempt_id": proof["request_attempt_id"],
            "request_repo_relative_path": proof["request_repo_relative_path"]}


def plan_historical_sources(*, repo_root: Path, company_id: str, count=5):
    """Produce the deduplicated, machine-readable historical source gap plan.

    Every entry names its company, target report end, dependency roles, CIK,
    accession, URL, media type, saved state and consumers. Deduplication is by
    actual URL; all consumer relations are retained. Nothing is fetched and no
    total is estimated: what index discovery has not yet revealed is reported
    as not yet known, not as a count.
    """
    history = load_annual_history(repo_root=repo_root, company_id=company_id,
                                  required_annual_count=count + 1)
    reader = history["reader"]
    cik = history["primary_cik"]
    candidates = target_period_candidates(repo_root=repo_root, company_id=company_id,
                                          count=count, history=history)
    declared = {}

    def declare(entries):
        for entry in entries:
            existing = declared.get(entry["source_url"])
            if existing is None:
                declared[entry["source_url"]] = dict(entry)
                continue
            for role in entry["source_roles"]:
                if role not in existing["source_roles"]:
                    existing["source_roles"].append(role)
            for consumer in entry["consumers"]:
                if consumer not in existing["consumers"]:
                    existing["consumers"].append(consumer)

    declare([{"source_url": submissions_url(cik=int(cik)), "media_type": "application/json",
              "accession": "", "document_name": "CIK%010d.json" % int(cik),
              "dependency_class": "SUBMISSIONS_INDEX",
              "source_roles": ["sec_submissions_inventory"], "consumers": ["historical_catalog"]}])
    for name in history["loaded_inventories"][1:]:
        declare([{"source_url": submissions_file_url(file_name=name),
                  "media_type": "application/json", "accession": "", "document_name": name,
                  "dependency_class": "SUBMISSIONS_HISTORY",
                  "source_roles": ["sec_submissions_history"], "consumers": ["historical_catalog"]}])
    for item in history["limitations"]:
        if item["kind"] in {"HISTORY_SHARD_NOT_SAVED", "HISTORY_SHARD_METADATA_REJECTED"}:
            declare([{"source_url": item["source_url"], "media_type": "application/json",
                      "accession": "", "document_name": item["history_name"],
                      "dependency_class": "SUBMISSIONS_HISTORY",
                      "source_roles": ["sec_submissions_history"],
                      "consumers": ["historical_catalog"]}])
    declare([{"source_url": companyfacts_url(cik=int(cik)), "media_type": "application/json",
              "accession": "", "document_name": "CIK%010d.json" % int(cik),
              "dependency_class": "COMPANYFACTS",
              "source_roles": ["companyfacts"],
              "consumers": ["B02", "B04", "B05", "A05", "A06", "A07", "A08", "A10", "B07", "B08", "B09"]}])
    filings_by_accession = {}
    for candidate in candidates:
        label = candidate["report_date"]
        for filing, roles in ((candidate["current_filing"], ["target_primary"]),
                              *[(a, ["target_amendment_primary"]) for a in candidate["current_amendments"]]):
            if filing is not None:
                filings_by_accession[filing["accessionNumber"]] = filing
                declare(_document_requirements(cik=cik, filing=filing, roles=roles,
                                               consumer=["period:" + label]))
        if candidate["prior_filing"] is not None:
            filings_by_accession[candidate["prior_filing"]["accessionNumber"]] = candidate["prior_filing"]
            declare(_document_requirements(cik=cik, filing=candidate["prior_filing"],
                                           roles=["prior_annual_primary"],
                                           consumer=["period:" + label + ":B02"]))
        for amendment in candidate["prior_amendments"]:
            filings_by_accession[amendment["accessionNumber"]] = amendment
            declare(_document_requirements(cik=cik, filing=amendment,
                                           roles=["prior_amendment_primary"],
                                           consumer=["period:" + label + ":B02"]))
    requirements = []
    for url in sorted(declared):
        item = declared[url]
        requirements.append({**item, "source_roles": sorted(item["source_roles"]),
                             "consumers": sorted(item["consumers"]),
                             "primary_cik": cik,
                             **_saved_state(reader, repo_root, item),
                             "new_acquisition_required": False,
                             "acquisition_kind": None,
                             "source_acquisition_credit": False})
    for item in requirements:
        item["new_acquisition_required"] = item["saved_status"] != "VERIFIED_SAVED_SOURCE"
        if item["saved_status"] == "MISSING_SAVED_SOURCE":
            item["acquisition_kind"] = "FIRST_ACQUISITION"
        elif item["saved_status"] == "SAVED_SOURCE_BLOCKED":
            # Bytes exist but do not verify, so the saved copy has to be
            # replaced rather than merely obtained.
            item["acquisition_kind"] = "REPLACEMENT_ACQUISITION"
        if (item["dependency_class"] == "ANNUAL_PERIOD_IDENTITY"
                and item["saved_status"] == "MISSING_SAVED_SOURCE"):
            alternative = _native_instance_alternative(
                reader, repo_root, filings_by_accession[item["accession"]], cik)
            item["alternative_dependency"] = alternative
            # The alternative closes only the prior-annual role, so a document
            # this plan also needs as a target primary still has to be acquired.
            if (alternative["status"] == "VERIFIED_ACCESSION_NATIVE_INSTANCE"
                    and item["source_roles"] == ["prior_annual_primary"]):
                item["new_acquisition_required"] = False
                item["acquisition_kind"] = None
    # A shard whose saved body does not sit inside the range the saved index
    # declares for it is a stale snapshot, not a missing one: its bytes are
    # present and they verify, which is exactly why marking acquisition by
    # saved status alone left these out of the plan and made the budget look
    # smaller than it is. Coherence is a property of the index and the shard
    # together, so the pair is refreshed together and re-checked afterwards;
    # refreshing one of them proves nothing about the other.
    conflicts = {item["history_name"]: item for item in history["limitations"]
                 if item["kind"] == "HISTORY_SHARD_SNAPSHOT_CONFLICT"}
    refreshed = []
    if conflicts:
        for item in requirements:
            if (item["dependency_class"] == "SUBMISSIONS_HISTORY"
                    and item["document_name"] in conflicts):
                conflict = conflicts[item["document_name"]]
                item["snapshot_conflict"] = {
                    "reason": conflict["reason"],
                    "declared_filing_from": conflict["declared_filing_from"],
                    "declared_filing_to": conflict["declared_filing_to"],
                    "out_of_range_filing_count": len(conflict["out_of_range_filings"])}
            elif item["dependency_class"] == "SUBMISSIONS_INDEX":
                item["snapshot_conflict"] = {
                    "reason": "DECLARES_THE_RANGES_THE_CONFLICTING_SHARDS_CONTRADICT",
                    "conflicting_history_names": sorted(conflicts)}
            else:
                continue
            item["new_acquisition_required"] = True
            item["acquisition_kind"] = "SNAPSHOT_REFRESH"
            refreshed.append(item["source_url"])
    pending_index = [item for item in requirements
                     if item["dependency_class"] == "ACCESSION_INSTANCE_DISCOVERY"
                     and item["saved_status"] != "VERIFIED_SAVED_SOURCE"]
    classes = sorted({item["dependency_class"] for item in requirements})
    by_class = {name: {"declared": 0, "verified_saved": 0, "new_acquisition_required": 0}
                for name in classes}
    by_kind = {}
    for item in requirements:
        entry = by_class[item["dependency_class"]]
        entry["declared"] += 1
        entry["verified_saved"] += int(item["saved_status"] == "VERIFIED_SAVED_SOURCE")
        entry["new_acquisition_required"] += int(item["new_acquisition_required"])
        _need(bool(item["acquisition_kind"]) == item["new_acquisition_required"],
              "HISTORY_PLAN_ACQUISITION_KIND_INCONSISTENT")
        if item["acquisition_kind"]:
            by_kind[item["acquisition_kind"]] = by_kind.get(item["acquisition_kind"], 0) + 1
    identity_ready = [candidate for candidate in candidates
                      if _identity_ready(candidate, requirements, cik)]
    body = {"record_type": PLAN_RECORD_TYPE, "schema_version": 1,
            "company_id": company_id, "primary_cik": cik,
            "requested_target_count": count,
            "target_candidates": candidates,
            "declared_shards": history["declared_shards"],
            "loaded_inventories": history["loaded_inventories"],
            "catalog_limitations": history["limitations"],
            "requirements": requirements,
            "deduplicated_known_get_count": len(requirements),
            "requirements_by_dependency_class": by_class,
            "new_acquisition_urls": sorted(item["source_url"] for item in requirements
                                           if item["new_acquisition_required"]),
            "new_acquisition_count": sum(1 for item in requirements if item["new_acquisition_required"]),
            "new_acquisition_by_kind": by_kind,
            "snapshot_refresh_urls": sorted(refreshed),
            "snapshot_refresh_is_one_coherent_pass": bool(refreshed),
            "annual_identity_ready_report_dates": [c["report_date"] for c in identity_ready],
            "accession_indexes_not_yet_discovered": sorted(item["accession"] for item in pending_index),
            "further_requests_pending_index_discovery": bool(pending_index),
            "complete_plan_proven": (not history["limitations"] and not pending_index
                                     and all(c["metadata_status"] == "METADATA_CANDIDATE_READY"
                                             for c in candidates)),
            "plan_status": "PLAN_READY",
            "sources_ready": False,
            "fetch_authorized": False, "metric_executed": False,
            "production_authorized": False,
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "module_sha256": sha256_file(path=Path(__file__)),
            "registry_sha256": sha256_file(
                path=resolve_repository_file(repo_root=repo_root,
                                             repo_relative_path="config/company_registry.csv"))}
    return {**body, "plan_id": content_hash(value=body)}


def _identity_ready(candidate, requirements, cik):
    """Can this target period's own annual identity be read from saved bytes?

    A target period needs its own primary document. The accession's own XBRL
    instance closes the *prior* year's dependency, because that role only needs
    dates and adjacency, but it cannot establish an issuer fiscal-year label:
    the frozen label policy reads the issuer's explicit definition from the full
    document and refuses an extracted instance outright. So the alternative is
    deliberately not accepted here.

    This answers the period-identity question only. A metric still needs its
    own inputs, and a prior-year dependency is a different target's question.
    """
    if candidate["metadata_status"] != "METADATA_CANDIDATE_READY":
        return False
    filing = candidate["current_filing"]
    url = accession_document_url(cik=int(cik), accession=filing["accessionNumber"],
                                 document_name=filing["primaryDocument"])
    item = next((r for r in requirements if r["source_url"] == url), None)
    return item is not None and item["saved_status"] == "VERIFIED_SAVED_SOURCE"


def inspect_historical_plans(*, repo_root: Path, company_ids=None, count=5):
    """Keep every configured company and isolate per-company failures."""
    configured = [c["company_id"] for c in _registry_rows(repo_root=repo_root)]
    selected = configured if company_ids is None else list(company_ids)
    _need(bool(selected) and len(selected) == len(set(selected)) and set(selected) <= set(configured),
          "HISTORY_PLAN_COMPANY_SET_INVALID", "IMPLEMENTATION_GAP")
    reports = []
    for company_id in selected:
        try:
            reports.append(plan_historical_sources(repo_root=repo_root, company_id=company_id,
                                                   count=count))
        except (ValueError, KeyError, TypeError, OSError) as error:
            reports.append({"company_id": company_id, "plan_status": "PLAN_FAILED",
                            "reason": str(error), "error_type": type(error).__name__,
                            "category": getattr(error, "category", "IMPLEMENTATION_ERROR")})
    return {"record_type": "ORDINARY_HISTORICAL_SOURCE_PLAN_REPORT", "companies": reports,
            "requested_target_count": count,
            "execution": "NOT_EXECUTED", "fetch_authorized": False,
            "production_authorized": False,
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
