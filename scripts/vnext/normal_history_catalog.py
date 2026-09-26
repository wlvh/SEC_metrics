"""Read the saved annual submissions metadata for one company.

This module is the reader, and only the reader. It loads the declared
submissions shards a bounded window can need, groups the annual filings by
report end, and reports what the saved bytes do not support as an explicit
limitation. It never chooses a fiscal-year label: a report end is SEC metadata
and an issuer label belongs to that filing's own DEI contexts.

``catalog_identity`` binds this module's own bytes, because a replay has to
prove the same reading logic produced the same catalog. That is exactly why the
acquisition planning that used to live here now lives in
``normal_history_plan.py``: a plan describes what is still missing and changes
whenever the plan's own rules improve, and while it shared this file every such
change altered ``catalog_module_sha256`` and invalidated every installed
historical package that had read nothing different at all.
"""
from datetime import date
from pathlib import Path

from sec_urls import submissions_file_url, submissions_url

from .canonical import content_hash, sha256_file, strict_json_loads
from .normal_annual_input import _cik, _registry_rows, _subject_policy
from .normal_governance_input import (_Sources, _filings, _history_index,
                                      history_body_alignment, NormalGovernanceInputError)
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


ANNUAL_FORMS = ("10-K", "10-K/A")
CATALOG_RECORD_TYPE = "ORDINARY_ANNUAL_HISTORY_CATALOG"


class HistoryCatalogError(ValueError):
    """An inventory limitation, never a financial or disclosure conclusion."""

    def __init__(self, reason, category="SOURCE_INTEGRITY_ERROR"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise HistoryCatalogError(reason, category)


def _identity(row):
    return {key: row[key] for key in
            ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument")}


def _company(repo_root, company_id):
    companies = [c for c in _registry_rows(repo_root=repo_root)
                 if c["company_id"] == company_id]
    _need(len(companies) == 1, "HISTORY_COMPANY_NOT_UNIQUE", "IMPLEMENTATION_GAP")
    return companies[0]


def _reading_cik(company, cik):
    """Which registrant's own saved catalog to read: the primary or a predecessor.

    A registered predecessor's periods are that registrant's own filings, read
    from its own saved submissions - never merged into the successor's catalog,
    and never read for a company whose registry row does not name it. The
    primary keeps the registry's exact value, so a primary catalog reads and
    hashes exactly as it did before predecessors could be read at all.
    """
    if cik is None or _cik(cik) == _cik(company["primary_cik"]):
        return company["primary_cik"], "PRIMARY"
    policy = _subject_policy(company)
    _need(str(_cik(cik)) in policy.get("related_predecessor_ciks", ()),
          "HISTORY_CIK_NOT_REGISTERED_FOR_COMPANY", "IMPLEMENTATION_GAP")
    return str(_cik(cik)), "PREDECESSOR"


def registered_predecessor_ciks(*, repo_root: Path, company_id: str):
    """The predecessor CIKs the registry records for this company, in its order."""
    return list(_subject_policy(_company(repo_root, company_id)).get(
        "related_predecessor_ciks", ()))


def _annual_ends(rows):
    return sorted({row["reportDate"] for row in rows if row["form"] == "10-K"}, reverse=True)


def load_annual_history(*, repo_root: Path, company_id: str, reader=None, required_annual_count=6,
                        cik=None):
    """Load exactly the saved submissions blocks a bounded window can need.

    Shards are loaded newest first and only while the window is not yet proven:
    either not enough distinct annual report ends are known, or a declared shard
    could still hold an amendment filed on or after the oldest needed report
    end. Loading stops there, so an unrelated 1990s shard is never pulled in and
    never turned into a spurious limitation.

    A needed shard that is not saved, whose body contradicts its declared range,
    or whose rows the frozen metadata parser rejects, is kept as an explicit
    limitation. It is never skipped silently and never treated as "no filing".
    """
    _need(type(required_annual_count) is int and 0 < required_annual_count <= 60,
          "HISTORY_REQUIRED_ANNUAL_COUNT_INVALID", "IMPLEMENTATION_GAP")
    company = _company(repo_root, company_id)
    _subject_policy(company)
    cik, role = _reading_cik(company, cik)
    reader = reader if reader is not None else _Sources(repo_root, company_id, cik)
    inventory = reader.read(submissions_url(cik=int(cik)),
                            role="sec_submissions_inventory", media_type="application/json")
    payload = strict_json_loads(text=inventory["raw_bytes"].decode("utf-8"))
    shards = _history_index(payload, cik)
    names = [inventory["source_reference"]["document_name"]]
    rows = _filings(payload, inventory_name=names[0])
    limitations = []
    considered = []

    def window_end():
        ends = _annual_ends(rows)
        return ends[required_annual_count - 1] if len(ends) >= required_annual_count else None

    for shard in shards:
        boundary = window_end()
        if boundary is not None and shard["filingTo"] < boundary:
            break
        considered.append(shard["name"])
        url = submissions_file_url(file_name=shard["name"])
        source = reader.read(url, role="sec_submissions_history",
                             media_type="application/json", required=False)
        if source is None:
            limitations.append({"kind": "HISTORY_SHARD_NOT_SAVED",
                                "history_name": shard["name"], "source_url": url,
                                "declared_filing_from": shard["filingFrom"],
                                "declared_filing_to": shard["filingTo"]})
            continue
        body = strict_json_loads(text=source["raw_bytes"].decode("utf-8"))
        _need("cik" not in body or str(body["cik"]).isdigit() and int(body["cik"]) == int(cik),
              "HISTORY_SHARD_ENTITY_CONFLICT")
        try:
            shard_rows = _filings(body, inventory_name=shard["name"])
        except NormalGovernanceInputError as error:
            limitations.append({"kind": "HISTORY_SHARD_METADATA_REJECTED",
                                "history_name": shard["name"], "source_url": url,
                                "declared_filing_from": shard["filingFrom"],
                                "declared_filing_to": shard["filingTo"],
                                "reason": str(error), "error_category": error.category})
            continue
        problem = history_body_alignment(shard=shard, rows=shard_rows)
        if problem:
            limitations.append({"kind": "HISTORY_SHARD_SNAPSHOT_CONFLICT", **problem})
        rows.extend(shard_rows)
        names.append(shard["name"])
    accessions = [row["accessionNumber"] for row in rows]
    _need(len(accessions) == len(set(accessions)), "HISTORY_INVENTORY_ACCESSIONS_OVERLAP")
    annual = sorted((row for row in rows if row["form"] in ANNUAL_FORMS),
                    key=lambda row: (row["reportDate"], row["filingDate"], row["accessionNumber"]))
    boundary = window_end()
    return {"company_id": company_id, "primary_cik": company["primary_cik"],
            "reporting_cik": cik, "registrant_role": role, "reader": reader,
            "inventory": inventory, "declared_shards": shards, "loaded_inventories": names,
            "considered_shards": considered, "required_annual_count": required_annual_count,
            "window_oldest_report_end": boundary,
            "window_proven": boundary is not None and not limitations,
            "annual_rows": annual, "all_rows": rows, "limitations": limitations}


def load_history_for_period(*, repo_root: Path, company_id: str, report_end: str, reader=None,
                            cik=None):
    """Load exactly the blocks one target period and its prior year can need.

    Loading is newest first and stops as soon as three facts hold, so the set of
    read blocks depends only on the company and the requested report end:

    * no unloaded shard can hold a filing dated on or after the target period
      end, which is where an amendment of that period would appear;
    * the immediately preceding annual report end is known, or the declared
      history is exhausted;
    * no unloaded shard can hold a filing dated on or after that prior end.

    The unchanged latest-period selector enforces the first condition by
    refusing to select while such a shard exists. Here the same invariant is
    met by reading those blocks instead.
    """
    company = _company(repo_root, company_id)
    _subject_policy(company)
    cik, role = _reading_cik(company, cik)
    reader = reader if reader is not None else _Sources(repo_root, company_id, cik)
    inventory = reader.read(submissions_url(cik=int(cik)),
                            role="sec_submissions_inventory", media_type="application/json")
    payload = strict_json_loads(text=inventory["raw_bytes"].decode("utf-8"))
    shards = _history_index(payload, cik)
    names = [inventory["source_reference"]["document_name"]]
    rows = _filings(payload, inventory_name=names[0])
    limitations = []
    considered = []

    def cutoff():
        prior = max((row["reportDate"] for row in rows
                     if row["form"] == "10-K" and row["reportDate"] < report_end), default="")
        return prior or None

    for shard in shards:
        prior_end = cutoff()
        if prior_end is not None and shard["filingTo"] < prior_end and shard["filingTo"] < report_end:
            break
        considered.append(shard["name"])
        url = submissions_file_url(file_name=shard["name"])
        source = reader.read(url, role="sec_submissions_history",
                             media_type="application/json", required=False)
        if source is None:
            limitations.append({"kind": "HISTORY_SHARD_NOT_SAVED",
                                "history_name": shard["name"], "source_url": url,
                                "declared_filing_from": shard["filingFrom"],
                                "declared_filing_to": shard["filingTo"]})
            continue
        body = strict_json_loads(text=source["raw_bytes"].decode("utf-8"))
        _need("cik" not in body or str(body["cik"]).isdigit() and int(body["cik"]) == int(cik),
              "HISTORY_SHARD_ENTITY_CONFLICT")
        try:
            shard_rows = _filings(body, inventory_name=shard["name"])
        except NormalGovernanceInputError as error:
            limitations.append({"kind": "HISTORY_SHARD_METADATA_REJECTED",
                                "history_name": shard["name"], "source_url": url,
                                "declared_filing_from": shard["filingFrom"],
                                "declared_filing_to": shard["filingTo"],
                                "reason": str(error), "error_category": error.category})
            continue
        problem = history_body_alignment(shard=shard, rows=shard_rows)
        if problem:
            limitations.append({"kind": "HISTORY_SHARD_SNAPSHOT_CONFLICT", **problem})
        rows.extend(shard_rows)
        names.append(shard["name"])
    accessions = [row["accessionNumber"] for row in rows]
    _need(len(accessions) == len(set(accessions)), "HISTORY_INVENTORY_ACCESSIONS_OVERLAP")
    annual = sorted((row for row in rows if row["form"] in ANNUAL_FORMS),
                    key=lambda row: (row["reportDate"], row["filingDate"], row["accessionNumber"]))
    unloaded = sorted(shard["name"] for shard in shards
                      if shard["name"] not in names and shard["filingTo"] >= report_end)
    return {"company_id": company_id, "primary_cik": company["primary_cik"],
            "reporting_cik": cik, "registrant_role": role, "reader": reader,
            "inventory": inventory, "declared_shards": shards, "loaded_inventories": names,
            "considered_shards": considered, "required_annual_count": None,
            "target_report_end": report_end, "prior_report_end": cutoff(),
            "unloaded_history_reaching_period": unloaded,
            "window_oldest_report_end": cutoff() or report_end,
            "window_proven": not limitations and not unloaded,
            "annual_rows": annual, "all_rows": rows, "limitations": limitations}


def annual_periods(*, history):
    """Group the saved annual metadata by report end date, newest first.

    An original and its amendments share one report end. This grouping is
    metadata only: ``fiscal_year`` is deliberately absent because a report end
    date is not an issuer fiscal-year label.
    """
    grouped = {}
    for row in history["annual_rows"]:
        grouped.setdefault(row["reportDate"], []).append(row)
    periods = []
    for report_date in sorted(grouped, reverse=True):
        members = grouped[report_date]
        originals = [r for r in members if r["form"] == "10-K"]
        amendments = sorted((r for r in members if r["form"] == "10-K/A"),
                            key=lambda r: (r["filingDate"], r["accessionNumber"]))
        periods.append({"report_date": report_date,
                        "original": _identity(originals[0]) if len(originals) == 1 else None,
                        "original_status": ("SINGLE_ORIGINAL_ANNUAL" if len(originals) == 1
                                            else "NO_ORIGINAL_ANNUAL" if not originals
                                            else "AMBIGUOUS_ORIGINAL_ANNUAL"),
                        "amendments": [_identity(r) for r in amendments],
                        "amendment_count": len(amendments)})
    return periods


def _unsaved_shard_reaches(history, report_date):
    """Name every declared shard that could still hide a relevant amendment."""
    unsaved = {item["history_name"] for item in history["limitations"]
               if item["kind"] == "HISTORY_SHARD_NOT_SAVED"}
    return sorted(shard["name"] for shard in history["declared_shards"]
                  if shard["name"] in unsaved and shard["filingTo"] >= report_date)


def target_period_candidates(*, repo_root: Path, company_id: str, count=5, history=None):
    """Return the newest ``count`` annual report ends with their dependencies.

    The first year's prior dependency is resolved as well; it is an input of
    that year, not an additional output year.
    """
    _need(type(count) is int and 0 < count <= 40, "HISTORY_TARGET_COUNT_INVALID",
          "IMPLEMENTATION_GAP")
    history = history if history is not None else load_annual_history(
        repo_root=repo_root, company_id=company_id, required_annual_count=count + 1)
    periods = annual_periods(history=history)
    return [_candidate(company_id=company_id, history=history, periods=periods, index=index,
                       ordinal=index + 1)
            for index in range(min(count, len(periods)))]


def _candidate(*, company_id, history, periods, index, ordinal):
    """One target candidate; its prior is the next period in the same catalog."""
    period = periods[index]
    following = periods[index + 1] if index + 1 < len(periods) else None
    blocking = _unsaved_shard_reaches(history, period["report_date"])
    reasons = []
    if period["original_status"] != "SINGLE_ORIGINAL_ANNUAL":
        reasons.append(period["original_status"])
    if blocking:
        reasons.append("RELEVANT_HISTORY_NOT_LOADED")
    if any(item["kind"] == "HISTORY_SHARD_SNAPSHOT_CONFLICT"
           for item in history["limitations"]):
        reasons.append("HISTORY_SNAPSHOT_CONFLICT")
    candidate = {
        "company_id": company_id, "primary_cik": history["primary_cik"],
        "report_date": period["report_date"], "target_ordinal": ordinal,
        "current_filing": period["original"], "current_amendments": period["amendments"],
        "prior_report_date": following["report_date"] if following else None,
        "prior_filing": following["original"] if following else None,
        "prior_amendments": following["amendments"] if following else [],
        "prior_status": ("SAME_CIK_PRIOR_DISCOVERED" if following and following["original"]
                         else "NO_SAME_CIK_PRIOR_IN_SAVED_SUBMISSIONS"),
        "unloaded_history_reaching_period": blocking,
        "metadata_status": "METADATA_CANDIDATE_READY" if not reasons else "METADATA_BLOCKED",
        "metadata_blocking_reasons": sorted(set(reasons)),
        "fiscal_year": None,
        "fiscal_label_status": "ISSUER_LABEL_REQUIRES_ORIGINAL_DOCUMENT"}
    if history.get("registrant_role", "PRIMARY") != "PRIMARY":
        candidate.update(reporting_cik=history["reporting_cik"],
                         registrant_role=history["registrant_role"])
    return candidate


def predecessor_period_candidates(*, repo_root: Path, company_id: str, count, before,
                                  first_ordinal):
    """Target candidates a registered predecessor filed, older than ``before``.

    ``before`` is the oldest annual report end in the primary's own catalog, or
    None when the primary has none: a predecessor's period is taken only where
    the successor reports no annual period of its own, so the two registrants'
    periods never overlap and no period the successor reports is answered from
    the predecessor. Each candidate's prior is the next period in that same
    predecessor's catalog - a prior is never taken across the registrant
    boundary. Returns ``(candidates, histories)``; the histories are the
    predecessors' catalogs the candidates came from.

    More than one predecessor contributing periods would need an order between
    them that the registry does not record, so that case stops by name rather
    than guessing one.
    """
    _need(type(count) is int and count >= 0, "HISTORY_TARGET_COUNT_INVALID",
          "IMPLEMENTATION_GAP")
    candidates, histories = [], []
    if count == 0:
        return candidates, histories
    for cik in registered_predecessor_ciks(repo_root=repo_root, company_id=company_id):
        skipped, history, periods = 0, None, []
        for _attempt in range(2):
            history = load_annual_history(repo_root=repo_root, company_id=company_id,
                                          required_annual_count=count + 1 + skipped, cik=cik)
            periods = annual_periods(history=history)
            newer = sum(1 for period in periods
                        if before is not None and period["report_date"] >= before)
            if newer == skipped:
                break
            skipped = newer
        offset = skipped
        kept = [_candidate(company_id=company_id, history=history, periods=periods,
                           index=offset + index, ordinal=first_ordinal + index)
                for index in range(min(count, len(periods) - offset))]
        if kept:
            _need(not candidates, "HISTORY_MULTIPLE_PREDECESSOR_CATALOGS_NOT_IMPLEMENTED",
                  "IMPLEMENTATION_GAP")
            candidates.extend(kept)
            histories.append(history)
    return candidates, histories


def frame_period_candidates(*, repo_root: Path, company_id: str, count=5, history=None):
    """The window's target candidates: the primary's, then a predecessor's.

    A registered predecessor's years join only where the primary's complete
    catalog runs out, and only from a complete primary catalog - an incomplete
    one cannot show that the successor filed nothing older. Returns
    ``(candidates, history, predecessor_histories)`` so a caller declaring
    dependencies can name each registrant's own catalog.
    """
    history = history if history is not None else load_annual_history(
        repo_root=repo_root, company_id=company_id, required_annual_count=count + 1)
    candidates = target_period_candidates(repo_root=repo_root, company_id=company_id,
                                          count=count, history=history)
    predecessor_histories = []
    if len(candidates) < count and not history["limitations"]:
        periods = annual_periods(history=history)
        earlier, predecessor_histories = predecessor_period_candidates(
            repo_root=repo_root, company_id=company_id, count=count - len(candidates),
            before=periods[-1]["report_date"] if periods else None,
            first_ordinal=len(candidates) + 1)
        candidates = candidates + earlier
    return candidates, history, predecessor_histories


def _check_report_end(value):
    _need(type(value) is str and len(value) == 10, "HISTORY_REPORT_END_INVALID")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise HistoryCatalogError("HISTORY_REPORT_END_INVALID") from error
    _need(parsed.isoformat() == value, "HISTORY_REPORT_END_INVALID")
    return parsed


def catalog_identity(*, history):
    """A content identity for the exact saved metadata this catalog read."""
    body = {"record_type": CATALOG_RECORD_TYPE, "schema_version": 1,
            "company_id": history["company_id"], "primary_cik": history["primary_cik"],
            "loaded_inventories": history["loaded_inventories"],
            "annual_rows": [_identity(row) for row in history["annual_rows"]],
            "limitations": history["limitations"],
            "inventory_source_reference_id":
                history["inventory"]["source_reference"]["source_reference_id"],
            "catalog_module_sha256": sha256_file(path=Path(__file__))}
    # Named only for a predecessor's catalog, so a primary catalog's identity is
    # exactly what it was before a predecessor's could be read.
    if history.get("registrant_role", "PRIMARY") != "PRIMARY":
        body.update(reporting_cik=history["reporting_cik"],
                    registrant_role=history["registrant_role"])
    return {**body, "catalog_id": content_hash(value=body)}


def _installed_registry_matches(repo_root):
    return (sha256_file(path=resolve_repository_file(
        repo_root=repo_root, repo_relative_path="config/company_registry.csv"))
        == sha256_file(path=ROOT / "config/company_registry.csv"))
