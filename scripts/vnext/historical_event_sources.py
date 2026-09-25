"""The 8-K bodies and headers the event metrics read, declared beside the plan.

Purpose: ``plan_historical_sources`` declares four dependency classes - the
submissions index, its history shards, Company Facts and the per-accession
annual documents - and no event class at all. The acquisition plan measured
485 filings and 970 request attempts of fiscal-year 8-K bodies and headers
that the zero-AI route reads for C01 and E01-E05 and that nothing declares,
so the gate admitting a URL refuses every one of them by name. A grant cannot
unblock those coordinates while that is true.

Why this is not an edit to the planner: ``normal_history_plan.py`` is a
``NEW_RULE_FILE`` of ``issue_47_v1``. Changing its bytes moves the Requirement
closure, and the previous batch's 343 frozen Runs are evidence about the
version that produced them. The declaration is made here instead and
``historical_source_acquisition.declared_frame`` takes the union. Being
outside the closure is not being outside the checks: these rows carry the
planner's fields, are classified by the planner's own ``_saved_state``, pass
through the same scope gate, and a case requires this declaration to be
exactly the set of URLs the route reads.

What it does not restate: which filings are in the window, which registrants
count, or how wide a successor's window is. All three come from the frozen
route - ``event_measurement_window``, ``repository_company_ciks``, and the
same form and date filter ``_event_sources`` applies - because a declaration
written from a second reading of the same rules is a declaration that can
drift from what is consumed.

Call relationships: ``historical_source_acquisition`` calls this. It reads
saved submissions metadata only; it fetches nothing and executes no metric.
"""
from pathlib import Path

from sec_urls import (accession_document_url, hdr_sgml_url, submissions_file_url,
                      submissions_url)
from .canonical import strict_json_loads
from .historical_source_acquisition import HistoricalAcquisitionError
from .normal_governance_input import _Sources, _filings, _history_index
from .normal_history_catalog import frame_period_candidates
from .normal_history_plan import _saved_state

# The six the zero-AI event route answers. Named rather than derived, because
# what makes a source an event dependency is that one of these consumes it.
EVENT_METRICS = ("C01", "E01", "E02", "E03", "E04", "E05")
EVENT_FORMS = frozenset({"8-K", "8-K/A"})
DEPENDENCY_CLASS = "FISCAL_EVENT_FILING"
BODY_ROLE = "fy_8k_primary"
HEADER_ROLE = "fy_8k_header"
# Every event accession costs two requests, and this is measured rather than
# assumed: normal_zero_ai_results reads the primary document and the
# accession's hdr.sgml for each filing, and of 186 saved accession directories
# 151 hold both while none holds a header alone.
REQUESTS_PER_ACCESSION = 2


class HistoricalEventSourceError(HistoricalAcquisitionError):
    """The event declaration could not be built for this company."""


def _need(condition, reason):
    if not condition:
        raise HistoricalEventSourceError(reason)


def _registry_row(*, repo_root, company_id):
    from .normal_annual_input import _registry_rows
    rows = [row for row in _registry_rows(repo_root=repo_root)
            if row["company_id"] == company_id]
    _need(len(rows) == 1, "HISTORICAL_EVENT_COMPANY_NOT_UNIQUE:" + company_id)
    return rows[0]


def _pinned_period(*, repo_root, cik, candidate):
    """The target year's own period, read from the filing that reports it.

    The window is derived from this, so a period whose primary is not saved
    has no derivable window. That is an ordering fact worth stating rather
    than papering over: the event dependencies of a past year only become
    listable after that year's annual primary is on disk, because the year's
    start date comes from the document's own DEI context and not from the
    submissions row's report date.
    """
    from .annual_update import saved_source
    from .normal_annual_input import annual_period
    filing = candidate["current_filing"]
    if filing is None:
        return None, "NO_ORIGINAL_ANNUAL_IN_SAVED_SUBMISSIONS"
    accession = filing["accessionNumber"]
    url = accession_document_url(cik=int(cik), accession=accession,
                                 document_name=filing["primaryDocument"])
    item = saved_source(repo_root=repo_root, url=url, accession=accession)
    if item is None:
        return None, "SAVED_SOURCE_MISSING:" + url
    return annual_period(raw=item["raw"], cik=int(cik), filing=filing), None


def _window(*, repo_root, company_id, candidate, subject_policy):
    """The window and registrants one period's event enumeration reads.

    A registered predecessor's period is that registrant's own year: the route
    reads it under the period's subject policy - one CIK, its own fiscal-year
    window - not the company's successor-only policy, so this does the same.
    """
    from .historical_zero_ai_results import event_measurement_window
    registrant = candidate.get("reporting_cik", candidate["primary_cik"])
    pinned, reason = _pinned_period(repo_root=repo_root, cik=registrant, candidate=candidate)
    if pinned is None:
        return None, None, reason
    registered = (subject_policy["mode"] == "SUCCESSOR_REGISTRANT_ONLY"
                  and candidate.get("registrant_role", "PRIMARY") == "PRIMARY")
    window, scope = event_measurement_window(repo_root=repo_root, company_id=company_id,
                                             pinned=pinned, registered_event=registered)
    if registered:
        ciks = list(scope["registered_ciks"])
    else:
        ciks = [str(registrant)]
    return window, ciks, None


def _inventory_rows(*, cik, name, window, consumers):
    """The submissions documents an event enumeration for this CIK reads."""
    if name is None:
        return {"source_url": submissions_url(cik=int(cik)),
                "media_type": "application/json", "accession": "",
                "document_name": "CIK%010d.json" % int(cik),
                "dependency_class": "SUBMISSIONS_INDEX",
                "source_roles": ["sec_submissions_inventory"],
                "consumers": list(consumers)}
    return {"source_url": submissions_file_url(file_name=name),
            "media_type": "application/json", "accession": "",
            "document_name": name, "dependency_class": "SUBMISSIONS_HISTORY",
            "source_roles": ["sec_submissions_history"],
            "consumers": list(consumers)}


def _filing_rows(*, cik, filing, consumers):
    """The two documents the route reads for one event filing."""
    accession = filing["accessionNumber"]
    return [
        {"source_url": accession_document_url(cik=int(cik), accession=accession,
                                              document_name=filing["primaryDocument"]),
         "media_type": "text/html", "accession": accession,
         "document_name": filing["primaryDocument"],
         "dependency_class": DEPENDENCY_CLASS,
         "source_roles": [BODY_ROLE], "consumers": list(consumers)},
        {"source_url": hdr_sgml_url(cik=int(cik), accession=accession),
         "media_type": "text/plain", "accession": accession,
         "document_name": accession + ".hdr.sgml",
         "dependency_class": DEPENDENCY_CLASS,
         "source_roles": [HEADER_ROLE], "consumers": list(consumers)},
    ]


def _read_saved(*, repo_root, url):
    from .annual_update import saved_source
    return saved_source(repo_root=repo_root, url=url, accession="")


def event_filings(*, repo_root, cik, window):
    """Every 8-K the saved metadata places in this window, for this registrant.

    Returns the filings and the inventory documents they were found in, plus
    any block that had to be read and was not saved. An unsaved block is not
    "no filings there": it is a hole, and reporting it as an empty stretch is
    how a declaration silently shrinks.
    """
    index = _read_saved(repo_root=repo_root, url=submissions_url(cik=int(cik)))
    if index is None:
        return {"filings": [], "inventory_names": [], "unreadable": [
            {"name": None, "reason": "SAVED_SOURCE_MISSING",
             "source_url": submissions_url(cik=int(cik))}]}
    payload = strict_json_loads(text=index["raw"].decode("utf-8"))
    found, names, unreadable = [], [None], []
    sources = [(None, payload)]
    for shard in _history_index(payload, str(cik)):
        if shard["filingFrom"] > window["period_end"] or shard["filingTo"] < window["period_start"]:
            continue
        item = _read_saved(repo_root=repo_root,
                           url=submissions_file_url(file_name=shard["name"]))
        if item is None:
            unreadable.append({"name": shard["name"], "reason": "SAVED_SOURCE_MISSING",
                               "source_url": submissions_file_url(file_name=shard["name"])})
            continue
        sources.append((shard["name"], strict_json_loads(text=item["raw"].decode("utf-8"))))
        names.append(shard["name"])
    for name, data in sources:
        inventory_name = name if name is not None else "CIK%010d.json" % int(cik)
        for filing in _filings(data, inventory_name=inventory_name):
            if (filing["form"] in EVENT_FORMS
                    and window["period_start"] <= filing["filingDate"] <= window["period_end"]):
                found.append({**filing, "inventory_name": name})
    return {"filings": sorted(found, key=lambda f: (f["filingDate"], f["accessionNumber"])),
            "inventory_names": names, "unreadable": unreadable}


def declare_event_sources(*, repo_root: Path, company_id: str, count: int = 5,
                          history=None):
    """Declare the event dependencies of every target period in the frame.

    Returns ``requirements`` in the planner's row shape and ``limitations``
    naming each period whose window could not be derived and each submissions
    block that had to be read and was not saved. A period that cannot be
    enumerated declares nothing rather than declaring an empty set, because
    the two read the same way in a plan and mean opposite things.
    """
    repo_root = Path(repo_root)
    row = _registry_row(repo_root=repo_root, company_id=company_id)
    from .normal_annual_input import _subject_policy
    subject_policy = _subject_policy(row)
    candidates, history, _ = frame_period_candidates(repo_root=repo_root,
                                                     company_id=company_id, count=count,
                                                     history=history)
    declared, limitations, readers = {}, [], {}

    def declare(entry):
        existing = declared.get(entry["source_url"])
        if existing is None:
            declared[entry["source_url"]] = {**entry, "source_roles": list(entry["source_roles"]),
                                             "consumers": list(entry["consumers"])}
            return
        for role in entry["source_roles"]:
            if role not in existing["source_roles"]:
                existing["source_roles"].append(role)
        for consumer in entry["consumers"]:
            if consumer not in existing["consumers"]:
                existing["consumers"].append(consumer)

    for candidate in candidates:
        label = candidate["report_date"]
        consumers = ["period:" + label + ":" + metric for metric in EVENT_METRICS]
        window, ciks, reason = _window(repo_root=repo_root, company_id=company_id,
                                       candidate=candidate, subject_policy=subject_policy)
        if window is None:
            limitations.append({"report_date": label, "kind": "EVENT_WINDOW_NOT_DERIVABLE",
                                "reason": reason,
                                "blocks_declaration_for_metrics": list(EVENT_METRICS)})
            continue
        for cik in ciks:
            found = event_filings(repo_root=repo_root, cik=cik, window=window)
            for name in found["inventory_names"]:
                declare({**_inventory_rows(cik=cik, name=name, window=window,
                                           consumers=consumers), "cik": str(cik)})
            for item in found["unreadable"]:
                declare({**_inventory_rows(cik=cik, name=item["name"], window=window,
                                           consumers=consumers), "cik": str(cik)})
                limitations.append({"report_date": label, "cik": str(cik),
                                    "kind": "EVENT_SUBMISSIONS_BLOCK_NOT_SAVED",
                                    "source_url": item["source_url"],
                                    "history_name": item["name"]})
            for filing in found["filings"]:
                for entry in _filing_rows(cik=cik, filing=filing, consumers=consumers):
                    declare({**entry, "cik": str(cik)})
    requirements = []
    for url in sorted(declared):
        item = declared[url]
        cik = item.pop("cik")
        if cik not in readers:
            readers[cik] = _Sources(repo_root, company_id, cik)
        requirements.append({**item, "source_roles": sorted(item["source_roles"]),
                             "consumers": sorted(item["consumers"]),
                             "primary_cik": str(candidates[0]["primary_cik"]) if candidates
                             else str(row["primary_cik"]),
                             "declared_by": "historical_event_sources",
                             "registrant_cik": cik,
                             **_saved_state(readers[cik], repo_root, item),
                             "new_acquisition_required": False,
                             "acquisition_kind": None,
                             "source_acquisition_credit": False})
    for item in requirements:
        item["new_acquisition_required"] = item["saved_status"] != "VERIFIED_SAVED_SOURCE"
        if item["saved_status"] == "MISSING_SAVED_SOURCE":
            item["acquisition_kind"] = "FIRST_ACQUISITION"
        elif item["saved_status"] == "SAVED_SOURCE_BLOCKED":
            item["acquisition_kind"] = "REPLACEMENT_ACQUISITION"
    return {"company_id": company_id, "requirements": requirements,
            "limitations": limitations,
            "subject_policy_mode": subject_policy["mode"],
            "requests_per_accession": REQUESTS_PER_ACCESSION,
            "production_authorized": False}
