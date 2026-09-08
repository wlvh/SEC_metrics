"""Bounded filing discovery and source preparation; never execute a metric.

The retained annual_input and annual_candidate bytes are execution-bound by
PR36. Discovery therefore checks metadata before calling the unchanged input
entrypoint. It does not change their selection, Reader or authorization rules.
"""

from datetime import date, datetime, timezone
from pathlib import Path
import re
from uuid import uuid4

from sec_http import SecHttpClient, request_log_attempt_id
from sec_urls import accession_document_url, companyfacts_url, submissions_url

from . import annual_input
from .batch_workflow import BatchWorkflowError
from .canonical import sha256_bytes, strict_json_file, strict_json_loads
from .publication import PublicationView
from .records import validate_record
from .sources import resolve_repository_file


class AnnualUpdateError(ValueError):
    """An unsuccessful check is never a no-change observation."""


def _require(condition, reason):
    if not condition:
        raise AnnualUpdateError(reason)


def _date(value, reason):
    try:
        _require(type(value) is str and date.fromisoformat(value).isoformat() == value, reason)
    except (ValueError, TypeError) as error:
        raise AnnualUpdateError(reason) from error
    return value


def _utc(value):
    _require(type(value) is str, "SOURCE_SAVED_TIME_UNKNOWN")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.utcoffset() is not None, "SOURCE_SAVED_TIME_UNKNOWN")
    return value


def supported_company(*, repo_root):
    """Reuse the existing ordinary-candidate company scope and registry."""
    policy = strict_json_file(path=repo_root / "docs/evidence/issue_28_annual_candidate_policy.json")
    company_id = policy["choice"]["company_id"]
    companies = [r for r in annual_input._registry_rows(repo_root=repo_root)
                 if r["company_id"] == company_id]
    _require(len(companies) == 1, "COMPANY_NOT_UNIQUE")
    company = companies[0]
    _require(company["entity_continuity_status"] == "continuous"
             and not company["related_ciks"] and company["fiscal_year_end"] == "1231",
             "ONLY_CONTINUOUS_CALENDAR_YEAR_SUPPORTED")
    return company


def _rows(repo_root):
    path = repo_root / "evidence/requests_log.csv"
    annual_input.validate_request_log_manifest(log_path=path)
    return annual_input.parse_request_log_rows(text=path.read_text(encoding="utf-8"))


def saved_source(*, repo_root, url, accession=""):
    """Retain the normal proof, but never hide a later failed observation."""
    rows = _rows(repo_root)
    matching = [(i, r) for i, r in enumerate(rows) if r["source_url"] == url and r["method"] == "GET"]
    if not matching:
        return None
    index, latest = matching[-1]
    _require(latest["status_code"] == "200" and not latest["error"], "LATEST_SOURCE_REQUEST_FAILED: " + url)
    proof, raw = annual_input._saved_source(repo_root=repo_root, rows=rows, url=url, accession=accession)
    _require(proof["request_attempt_id"] == request_log_attempt_id(row_index=index, row=latest),
             "SOURCE_ATTEMPT_SELECTION_CONFLICT")
    headers = strict_json_file(path=resolve_repository_file(repo_root=repo_root,
        repo_relative_path=proof["request_headers_repo_relative_path"]))
    return {"proof": proof, "saved_at_utc": _utc(headers.get("saved_at_utc")), "raw": raw}


def _select_filing(*, company, payload):
    """Metadata-only preflight with PR35's calendar/current-block refusals.

    Unknown annual dates block selection even for otherwise irrelevant years.
    Actual primary DEI periods are still owned by annual_input, after discovery.
    """
    cik = int(company["primary_cik"])
    _require(int(payload["cik"]) == cik, "SUBMISSIONS_CIK_MISMATCH")
    filings = annual_input.filing_rows_from_submission_payloads(
        company=company["display_name"], cik=cik, entity_role="primary", payloads=[payload])
    annual = [f for f in filings if f["form"] in {"10-K", "10-K/A"}]
    _require(bool(annual), "ANNUAL_FILING_MISSING_IN_SAVED_BLOCK")
    for filing in annual:
        _date(filing["reportDate"], "ANNUAL_REPORT_DATE_INVALID")
        _date(filing["filingDate"], "ANNUAL_FILING_DATE_INVALID")
        _require(filing["filingDate"] >= filing["reportDate"], "ANNUAL_FILING_DATE_CONFLICT")
        _require(type(filing["accessionNumber"]) is str
                 and re.fullmatch(r"\d{10}-\d{2}-\d{6}", filing["accessionNumber"]), "ACCESSION_INVALID")
    year = max(date.fromisoformat(f["reportDate"]).year for f in annual)
    files = payload["filings"]["files"]
    _require(type(files) is list, "SUPPLEMENTAL_HISTORY_INVALID")
    for shard in files:
        start = _date(shard["filingFrom"], "SUPPLEMENTAL_HISTORY_DATE_UNKNOWN")
        end = _date(shard["filingTo"], "SUPPLEMENTAL_HISTORY_DATE_UNKNOWN")
        _require(start <= end, "SUPPLEMENTAL_HISTORY_DATE_CONFLICT")
        _require(end < str(year) + "-01-01", "SUPPLEMENTAL_HISTORY_REQUIRED")
    selected = [f for f in annual if date.fromisoformat(f["reportDate"]).year == year]
    _require(not any(f["form"] == "10-K/A" for f in selected), "AMENDED_ANNUAL_UNSUPPORTED")
    _require(len(selected) == 1, "ANNUAL_FILING_AMBIGUOUS")
    filing = selected[0]
    document = filing["primaryDocument"]
    _require(type(document) is str and bool(re.fullmatch(r"[A-Za-z0-9_.-]+", document))
             and document not in {".", ".."}, "PRIMARY_DOCUMENT_INVALID")
    _require(filing["reportDate"] == str(year) + "-12-31", "ANNUAL_IDENTITY_OR_PERIOD_UNSUPPORTED")
    # Revisions appearing alongside a newer annual cannot silently disappear.
    amendments = [f for f in annual if f["form"] == "10-K/A"]
    return filing, amendments


def _identity(*, company, filing):
    return {"company_id": company["company_id"], "cik": str(int(company["primary_cik"])),
            "accession": filing["accessionNumber"], "form": filing["form"],
            "period_start": filing["reportDate"][:4] + "-01-01", "period_end": filing["reportDate"],
            "primary_document": filing["primaryDocument"]}


def _recorded_baseline(*, company, manifest_raw, records_raw, reviews_raw, provenance):
    """Read the persisted B10 result/trace/source links, without rerunning it.

    An OPEN result is historical candidate evidence, not FROZEN qualification
    or a publication. This metadata comparison does not recertify old content.
    """
    manifest = validate_record(record=strict_json_loads(text=manifest_raw.decode()))
    records = [validate_record(record=strict_json_loads(text=line))
               for line in records_raw.decode().splitlines() if line.strip()]
    reviews = [validate_record(record=strict_json_loads(text=line))
               for line in reviews_raw.decode().splitlines() if line.strip()]
    _require(manifest["company_id"] == company["company_id"], "BASELINE_COMPANY_MISMATCH")
    _require(manifest["status"] in {"OPEN", "FROZEN"}, "BASELINE_RUN_NOT_SUCCESSFUL")
    if manifest["status"] == "FROZEN":
        _require(manifest["records_file_hash"] == sha256_bytes(content=records_raw)
                 and manifest["review_decisions_file_hash"] == sha256_bytes(content=reviews_raw),
                 "BASELINE_FROZEN_BYTES_CHANGED")
    results = [r for r in records if r["record_type"] == "METRIC_RESULT" and r["metric_id"] == "B10"]
    _require(len(results) == 1, "BASELINE_SUCCESSFUL_RESULT_MISSING")
    result = results[0]
    _require(result["publication"] == "PUBLISHED" and result["reason_code"] == "PASS"
             and result["company_id"] == company["company_id"], "BASELINE_RESULT_NOT_SUCCESSFUL")
    traces = [r for r in records if r["record_type"] == "EXECUTION_TRACE" and r["trace_id"] == result["trace_id"]]
    _require(len(traces) == 1, "BASELINE_TRACE_MISSING")
    observations = [r for r in records if r["record_type"] == "VERIFIED_OBSERVATION"
                    and r["observation_id"] in traces[0]["input_observation_ids"]]
    _require(len(observations) == 1, "BASELINE_SOURCE_AMBIGUOUS")
    observation = observations[0]
    attempts = [r for r in records if r["record_type"] == "AI_EXTRACTION_ATTEMPT"]
    _require(len(attempts) == 1 and attempts[0]["status"] == "SUCCEEDED"
             and not attempts[0]["error_class"], "BASELINE_ATTEMPT_NOT_SUCCESSFUL")
    candidates = [r for r in records if r["record_type"] == "OBSERVATION_CANDIDATE"
                  and r["attempt_id"] == attempts[0]["attempt_id"]
                  and r["assistant_output_sha256"] == attempts[0]["assistant_output_sha256"]]
    _require(len(candidates) == 1, "BASELINE_CANDIDATE_MISSING")
    checks = [r for r in records if r["record_type"] == "EVIDENCE_CHECK"
              and r["candidate_hash"] == candidates[0]["candidate_hash"]]
    _require(len(checks) == 1 and checks[0]["status"] == "PASS", "BASELINE_EVIDENCE_NOT_PASS")
    decisions = [r for r in reviews if r["decision"] == "APPROVE"
                 and r["approval_effect_hash"] == observation["approval_effect_hash"]]
    _require(len(decisions) == 1, "BASELINE_APPROVAL_MISSING")
    source_ids = {observation["source_binding"]["source_reference_id"]}
    sources = [r for r in records if r["record_type"] == "SOURCE_REFERENCE" and r["source_reference_id"] in source_ids]
    _require(len(sources) == 1, "BASELINE_SOURCE_MISSING")
    source = sources[0]
    period = manifest["target_period"]
    for field in ("period_start", "period_end"):
        _date(period[field], "BASELINE_PERIOD_INVALID")
        _require(result[field] == observation[field] == period[field], "BASELINE_PERIOD_CONFLICT")
    _require(period["period_start"] == str(period["fiscal_year"]) + "-01-01"
             and period["period_end"] == str(period["fiscal_year"]) + "-12-31", "BASELINE_PERIOD_UNSUPPORTED")
    _require(source in manifest["source_references"] and source["company_id"] == company["company_id"]
             and source["raw_asset_id"] == observation["source_binding"]["raw_asset_id"]
             and source in decisions[0]["reviewed_source_bindings"]
             and source["source_reference_id"] in candidates[0]["source_reference_ids"], "BASELINE_SOURCE_CONFLICT")
    _require(observation["company_id"] == result["company_id"]
             and observation["metric_id"] == traces[0]["metric_id"] == result["metric_id"]
             and observation["value"] == traces[0]["result"] == result["value"]
             and observation["unit"] == result["unit"]
             and observation["scope_key"] == result["scope_key"], "BASELINE_RESULT_LINK_CONFLICT")
    _require(source["source_url"] == accession_document_url(cik=int(company["primary_cik"]),
        accession=source["accession"], document_name=source["document_name"]), "BASELINE_SOURCE_URL_CONFLICT")
    identity = {"company_id": company["company_id"], "cik": str(int(company["primary_cik"])),
        "accession": source["accession"], "form": "10-K", "period_start": period["period_start"],
        "period_end": period["period_end"], "primary_document": source["document_name"]}
    return {"filing": identity, "primary_sha256": source["raw_asset_id"].removeprefix("sha256:"),
        "metric_id": "B10", "result_id": result["result_id"], "run_id": manifest["run_id"],
        "run_status": manifest["status"], "provenance": provenance,
        "verification_scope": "PERSISTED_RESULT_LINKS_NOT_CONTENT_RECERTIFICATION",
        "manifest_sha256": sha256_bytes(content=manifest_raw), "records_sha256": sha256_bytes(content=records_raw),
        "reviews_sha256": sha256_bytes(content=reviews_raw)}


def candidate_baseline(*, company, run_dir):
    manifest = resolve_repository_file(repo_root=run_dir, repo_relative_path="manifest.json").read_bytes()
    records = resolve_repository_file(repo_root=run_dir, repo_relative_path="records.jsonl").read_bytes()
    reviews = resolve_repository_file(repo_root=run_dir, repo_relative_path="review_decisions.jsonl").read_bytes()
    return _recorded_baseline(company=company, manifest_raw=manifest, records_raw=records, reviews_raw=reviews,
        provenance={"kind": "RECORDED_CANDIDATE_RESULT_LINKS", "run_directory": str(run_dir.resolve()),
                    "qualification_credit": "NONE", "publication_credit": "NONE"})


def published_baseline(*, company, publication_root):
    view = PublicationView.open(publication_root=publication_root)
    batch = strict_json_loads(text=view.read_bytes(relative_path="internal/batch/batch_manifest.json").decode())
    found = []
    for run in batch["runs"]:
        if run["company_id"] != company["company_id"]:
            continue
        prefix = "internal/batch/" + run["run_path"]
        raw = view.read_bytes(relative_path=prefix + "/records.jsonl")
        records = [strict_json_loads(text=line) for line in raw.decode().splitlines() if line.strip()]
        if not any(r["record_type"] == "METRIC_RESULT" and r["metric_id"] == "B10" for r in records):
            continue
        baseline = _recorded_baseline(company=company, records_raw=raw,
            manifest_raw=view.read_bytes(relative_path=prefix + "/manifest.json"),
            reviews_raw=view.read_bytes(relative_path=prefix + "/review_decisions.jsonl"),
            provenance={"kind": "PINNED_PUBLICATION", "publication_id": view.publication_id,
                        "bundle_directory": str(view.bundle_dir), "run_path": prefix})
        _require(baseline["result_id"] in run["result_ids"] and baseline["run_id"] == run["run_id"],
                 "PUBLISHED_BASELINE_BATCH_CONFLICT")
        found.append(baseline)
    _require(len(found) == 1, "PUBLISHED_BASELINE_NOT_UNIQUE")
    return found[0]


def _compare(filing, baseline):
    if filing == baseline["filing"]:
        return "UNCHANGED"
    old = baseline["filing"]
    _require(filing["company_id"] == old["company_id"] and filing["cik"] == old["cik"], "BASELINE_COMPANY_MISMATCH")
    _require(filing["accession"] != old["accession"], "ACCESSION_METADATA_CONFLICT")
    _require(filing["period_end"] > old["period_end"], "ANNUAL_PERIOD_REGRESSION_OR_REPLACEMENT")
    return "NEW_ANNUAL_FILING"


def _facts_cover(*, raw, cik, filing):
    payload = annual_input._json(raw=raw)
    _require(int(payload["cik"]) == cik, "COMPANYFACTS_CIK_MISMATCH")
    # Source readiness only: do not select a concept, value or B01 answer.
    for namespace in payload["facts"].values():
        for concept in namespace.values():
            for facts in concept["units"].values():
                for fact in facts:
                    if (fact.get("accn") == filing["accession"] and fact.get("form") == "10-K"
                            and fact.get("start") == filing["period_start"] and fact.get("end") == filing["period_end"]):
                        return True
    return False


def inspect_annual_update(*, repo_root, company, successful_candidate=None, published=None):
    """Read saved sources and explicit result baselines; no writes or sockets."""
    report = {"status": "CHECK_FAILED", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "check_scope": "ANNUAL_FILING_IDENTITY_ONLY", "submissions": None, "discovered_filing": None,
        "latest_successful_candidate": successful_candidate, "current_published": published,
        "candidate_baseline_status": "SUPPLIED" if successful_candidate else "NOT_SUPPLIED",
        "comparison_baseline": None, "filing_change": "UNKNOWN", "missing_sources": [],
        "source_availability": "NOT_CHECKED", "candidate_plan": {"status": "NOT_REQUESTED"},
        "prepared_input": None, "execution": "NOT_EXECUTED", "qualification_credit": "NONE",
        "publication_credit": "NONE", "provider_paid_sec_calls": [0, 0, 0]}
    try:
        baselines = [b for b in (successful_candidate, published) if b is not None]
        _require(bool(baselines), "SUCCESSFUL_OR_PUBLISHED_BASELINE_REQUIRED")
        baseline = max(baselines, key=lambda b: b["filing"]["period_end"])
        if len(baselines) == 2 and baselines[0]["filing"]["period_end"] == baselines[1]["filing"]["period_end"]:
            _require(baselines[0]["filing"] == baselines[1]["filing"]
                     and baselines[0]["primary_sha256"] == baselines[1]["primary_sha256"], "BASELINE_SOURCE_CONFLICT")
        report["comparison_baseline"] = baseline
        cik = int(company["primary_cik"])
        inventory = saved_source(repo_root=repo_root, url=submissions_url(cik=cik))
        _require(inventory is not None, "SUBMISSIONS_SOURCE_MISSING")
        report["submissions"] = {"source_proof": inventory["proof"], "saved_at_utc": inventory["saved_at_utc"]}
        selected, amendments = _select_filing(company=company, payload=annual_input._json(raw=inventory["raw"]))
        filing = _identity(company=company, filing=selected)
        report["discovered_filing"] = {**filing, "filing_date": selected["filingDate"], "period_basis": "SUBMISSIONS_REPORT_DATE"}
        oldest_baseline_period = min(b["filing"]["period_end"] for b in baselines)
        _require(not any(f["reportDate"] >= oldest_baseline_period for f in amendments), "AMENDED_ANNUAL_UNSUPPORTED")
        change = _compare(filing, baseline)
        report["filing_change"] = change
        primary_url = accession_document_url(cik=cik, accession=filing["accession"], document_name=filing["primary_document"])
        primary = saved_source(repo_root=repo_root, url=primary_url, accession=filing["accession"])
        hashes = {r["content_sha256"] for r in _rows(repo_root) if r["source_url"] == primary_url
                  and r["status_code"] == "200" and not r["error"]}
        _require(len(hashes) <= 1, "PRIMARY_SOURCE_CONTENT_CONFLICT")
        if primary and filing["accession"] == baseline["filing"]["accession"]:
            _require(primary["proof"]["content_sha256"] == baseline["primary_sha256"], "PRIMARY_SOURCE_CONTENT_CONFLICT")
        if change == "UNCHANGED":
            report.update(status="NO_NEW_ANNUAL_FILING", input_status="NOT_PREPARED_NO_NEW_FILING",
                source_availability={"primary_document_saved": primary is not None,
                                     "companyfacts": "NOT_CHECKED_NO_NEW_FILING"})
            return report
        needed = []
        if primary is None:
            needed.append({"kind": "PRIMARY_DOCUMENT", "url": primary_url, "document_name": filing["primary_document"], "reason": "SAVED_SOURCE_MISSING"})
        else:
            actual = annual_input._annual_period(raw=primary["raw"], cik=cik, filing=selected)
            _require(actual["period_end"] == filing["period_end"], "ANNUAL_PERIOD_CONFLICT")
            report["discovered_filing"]["period_basis"] = "PRIMARY_DEI_AND_CONTEXT"
        facts_url = companyfacts_url(cik=cik)
        facts = saved_source(repo_root=repo_root, url=facts_url, accession=filing["accession"])
        if facts is None or not _facts_cover(raw=facts["raw"], cik=cik, filing=filing):
            needed.append({"kind": "COMPANYFACTS", "url": facts_url, "document_name": facts_url.rsplit("/", 1)[1],
                           "reason": "SAVED_SOURCE_MISSING" if facts is None else "TARGET_ANNUAL_FACTS_MISSING"})
        report["missing_sources"] = needed
        report["source_availability"] = {"primary_document_saved": primary is not None,
            "companyfacts": "MISSING_OR_TARGET_ABSENT" if any(n["kind"] == "COMPANYFACTS" for n in needed) else "TARGET_ANNUAL_FACTS_PRESENT"}
        if needed:
            report.update(status="INPUTS_MISSING", input_status="NOT_PREPARED")
            return report
        prepared = annual_input.prepare_annual_input(repo_root=repo_root, company_id=company["company_id"],
                                                     fiscal_year=int(filing["period_end"][:4]))
        _require(prepared["table_input"]["accession"] == filing["accession"]
                 and prepared["source_proofs"] == [inventory["proof"], primary["proof"], facts["proof"]], "INPUT_CHANGED_DURING_CHECK")
        report.update(status="INPUT_READY", input_status="PREPARED_AWAITING_EXECUTION", prepared_input=prepared)
    except (ValueError, KeyError, TypeError, OSError, IndexError, BatchWorkflowError) as error:
        report.update(status="CHECK_FAILED", input_status="NOT_PREPARED", prepared_input=None,
                      error=str(error), error_type=type(error).__name__)
    return report


def check_annual_update(*, repo_root, candidate_run=None, refresh="none", sec_request_limit=0):
    """Load the explicit historical candidate and current published baseline."""
    company = supported_company(repo_root=repo_root)
    published = published_baseline(company=company, publication_root=repo_root)
    candidate = candidate_baseline(company=company, run_dir=candidate_run) if candidate_run else None
    return refresh_annual_update(repo_root=repo_root, company=company,
        successful_candidate=candidate, published=published, refresh=refresh, sec_request_limit=sec_request_limit)


def refresh_annual_update(*, repo_root, company, successful_candidate=None, published=None,
                         refresh="none", sec_request_limit=0):
    """Operator entry: optionally refresh one list, then only missing inputs.

    The explicit request limit is a per-command SEC request bound, not a new
    authorization authority. A caller must already have owner permission.
    """
    _require(refresh in {"none", "submissions", "missing"}, "REFRESH_SCOPE_INVALID")
    _require(type(sec_request_limit) is int and
             ((refresh == "none" and sec_request_limit == 0)
              or (refresh == "submissions" and sec_request_limit == 1)
              or (refresh == "missing" and 1 <= sec_request_limit <= 3)), "SEC_REQUEST_LIMIT_INVALID")
    candidate = successful_candidate
    calls, fetched = 0, []
    client = None
    uncertain_fetch = False

    def fetch(item):
        nonlocal calls, client, uncertain_fetch
        _require(calls < sec_request_limit, "SEC_REQUEST_LIMIT_REACHED")
        if client is None:
            client = SecHttpClient(workdir=repo_root, config_path=repo_root / "config/sec_config.json",
                                   log_path=repo_root / "evidence/requests_log.csv")
            # Narrow this instance only. Preserve the normal transport,
            # pacing, raw snapshots, ledger and global configuration bytes.
            client.config = {**client.config, "max_retries": 0}
        calls += 1
        try:
            result = client.fetch(url=item["url"], purpose="annual_update_" + item["kind"].lower(),
                local_path=repo_root / "evidence/annual_refresh" / uuid4().hex / item["document_name"])
        except (ValueError, OSError):
            # A local persistence failure can happen after the socket. Do not
            # manufacture an exact call count when fetch returned no receipt.
            uncertain_fetch = True
            raise
        fetched.append({"kind": item["kind"], **result.__dict__})
        _require(result.status_code == 200 and not result.error, "SEC_FETCH_FAILED: " + item["url"])

    report = None
    try:
        if refresh != "none":
            url = submissions_url(cik=int(company["primary_cik"]))
            fetch({"kind": "SUBMISSIONS", "url": url, "document_name": url.rsplit("/", 1)[1]})
        report = inspect_annual_update(repo_root=repo_root, company=company, successful_candidate=candidate, published=published)
        if refresh == "missing":
            # Reinspect after each fetch. A wrong primary must stop before
            # Company Facts; no URL is retried within this invocation.
            attempted = set()
            while report["status"] == "INPUTS_MISSING" and calls < sec_request_limit:
                item = report["missing_sources"][0]
                if item["url"] in attempted:
                    break
                attempted.add(item["url"])
                fetch(item)
                report = inspect_annual_update(repo_root=repo_root, company=company, successful_candidate=candidate, published=published)
    except (ValueError, KeyError, TypeError, OSError) as error:
        report = report or {"latest_successful_candidate": candidate, "current_published": published,
            "checked_at_utc": datetime.now(timezone.utc).isoformat(), "check_scope": "ANNUAL_FILING_IDENTITY_ONLY",
            "discovered_filing": None, "submissions": None, "filing_change": "UNKNOWN",
            "qualification_credit": "NONE", "publication_credit": "NONE"}
        report.update(status="CHECK_FAILED", error=str(error), input_status="NOT_PREPARED",
                      prepared_input=None, execution="NOT_EXECUTED")
    report.update(provider_paid_sec_calls=[0, 0, None if uncertain_fetch else calls],
                  sec_fetch_invocations=calls, refresh_scope=refresh, fetched_sources=fetched,
                  sec_request_limit=sec_request_limit, automatic_retry_count=0)
    return report
