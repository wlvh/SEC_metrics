"""Build the body of Issue #47's SEC allowance extension and check the gates would accept it.

The owner decided on one further approval after the first was spent to its cap.
This builds what the owner posts - the ledger state it continues, the grants,
which already-requested URLs may be requested once more, and the cap - from
data, and runs it through the real verifier in a temporary tree, so what is
proposed is a thing the gate accepts rather than a thing that looks like one.

Where each part comes from:

* the ledger state: the committed export's index and its state archive (the
  claim log's digest, size and line count, and the resume chain's reserve);
* the need declarable today: the planner and the frame's declaration on a root
  restored from that export, every due row asked of the proposed scope exactly
  as the gate asks it;
* the need the declaration cannot name yet: a company whose saved history
  block disagrees with its index has periods the catalog does not reach, or
  reaches with rows missing. For those the cap carries bounds computed from the
  saved submissions, each term named: re-fetching the index and every block it
  lists plus one (SEC re-partitions a company's history as its recent filings
  roll: the saved index and blocks show the block boundaries moved between
  fetches, so a new index means new blocks); the annual chain, proxy and 8-K
  events of a target the catalog misses; 8-Ks a stale block hides inside a
  visible target's window; a proxy for every target whose governance plan does
  not exist yet; rows refused today only because they also serve an
  out-of-frame target. The 8-K estimator is calibrated first: on every window
  the declaration already names with none of it saved, twice its 8-K count must
  equal the due rows the planner reports, or nothing is written.

Nothing here grants anything. The body is written to the extension's
directory; the policy file the gate reads is written only by
``tools/vnext_historical_sec.py register-extension`` from the owner's posted
comment. Zero SEC or provider calls.

Usage (from a tree whose journal registered SOURCE_ROOT):
    SOURCE_ROOT=<restored root>/source-inputs python3 tools/propose_historical_extension.py
"""
import io
import json
import os
import socket
import sys
import tarfile
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from vnext.annual_update import saved_source  # noqa: E402
from vnext.canonical import sha256_bytes  # noqa: E402
from vnext.historical_event_sources import EVENT_FORMS  # noqa: E402
from vnext.historical_sec_extension import (EXTENSION_BODY_PATH, EXTENSION_DIRECTORY,  # noqa: E402
                                            EXTENSION_ORDINAL, EXTENSION_POLICY_PATH,
                                            EXTENSION_RECORD_PATH, EXTENSION_TYPE,
                                            REQUIRED_EXTENSION_FIELDS,
                                            HistoricalExtensionError, acquisition_extension,
                                            extended_allowance, reclaim_ordinal)
from vnext.historical_source_acquisition import (APPROVAL_RECORD_PATH, POLICY_PATH,  # noqa: E402
                                                 REQUIREMENT_ID, TRUSTED_APPROVER,
                                                 TRUSTED_REPOSITORY, HistoricalAcquisitionError,
                                                 acquisition_allowance, declared_frame,
                                                 request_is_in_scope)
from vnext import historical_sec_session as SESSION_MODULE  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once, plan_historical_sources  # noqa: E402
from vnext.projector import _load_registry  # noqa: E402

EXPORT = REPO / "evidence/issue47_acquired"
OUT = REPO / EXTENSION_DIRECTORY / "proposed-extension.json"
YEARS = 5
METADATA = ("SUBMISSIONS_INDEX", "SUBMISSIONS_HISTORY")
SUBMISSIONS = "https://data.sec.gov/submissions/"


def _stop(reason):
    raise SystemExit(reason)


def ledger_state():
    """The state the extension continues: the claim log and the reserve, as the export carries them."""
    index = json.loads((EXPORT / "export.json").read_text(encoding="utf-8"))
    archive = index["state_archive"]
    raw = (EXPORT / archive["name"]).read_bytes()
    if sha256_bytes(content=raw) != archive["sha256"]:
        _stop("EXTENSION_PROPOSAL_STATE_ARCHIVE_CHANGED")
    members = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for name in ("ledger/claims.jsonl", "ledger/resumes.jsonl"):
            data = tar.extractfile(name).read()
            listed = archive["members"][name]
            if sha256_bytes(content=data) != listed["sha256"] or len(data) != listed["size"]:
                _stop("EXTENSION_PROPOSAL_MEMBER_DIFFERS_FROM_ITS_INDEX:" + name)
            members[name] = data
    claims, resumes = members["ledger/claims.jsonl"], members["ledger/resumes.jsonl"]
    reserve = sum(json.loads(line)["lost_segment"]["reserve_sec_calls"]
                  for line in resumes.decode("utf-8").splitlines())
    spent = [0, 0, 0]
    for line in claims.decode("utf-8").splitlines():
        spent[{"PROVIDER": 0, "PAID": 1, "SEC": 2}[json.loads(line)["channel"]]] += 1
    spent[2] += reserve
    return index, {"export_id": index["export_id"],
                   "claims": {"sha256": sha256_bytes(content=claims), "size": len(claims)},
                   "claim_count": claims.count(b"\n"),
                   "resumes": {"sha256": sha256_bytes(content=resumes), "size": len(resumes)},
                   "cumulative": spent}, claims


def claimed_urls(source_root):
    """URL -> ordinals, from the plans the restored ledger's slots wrote before their sockets."""
    claimed = {}
    for slot in sorted((Path(source_root).parent / "ledger" / "calls").iterdir()):
        plan = json.loads((slot / "sec-plan.json").read_text(encoding="utf-8"))
        claimed.setdefault(plan["request"]["url"], []).append(int(slot.name))
    return claimed


def _saved_json(source_root, url):
    got = saved_source(repo_root=source_root, url=url)
    return json.loads(got["raw"]) if got else None


def submissions(source_root, cik, untrusted):
    """The saved index, its block list, and the filings the trusted tables list, once each."""
    index = _saved_json(source_root, SUBMISSIONS + "CIK%010d.json" % int(cik))
    tables = [index["filings"]["recent"]]
    for item in index["filings"]["files"]:
        if item["name"] in untrusted:
            continue
        body = _saved_json(source_root, SUBMISSIONS + item["name"])
        if body is None:
            _stop("EXTENSION_PROPOSAL_TRUSTED_BLOCK_NOT_SAVED:" + item["name"])
        tables.append(body)
    seen, filings = set(), []
    for table in tables:
        for form, day, accession in zip(table["form"], table["filingDate"],
                                        table["accessionNumber"]):
            if accession not in seen:
                seen.add(accession)
                filings.append((form, day))
    return index, filings


def _year_before(report_end):
    day = date.fromisoformat(report_end)
    return day.replace(year=day.year - 1, day=min(day.day, 28) if day.month == 2 else day.day)


def event_window(report_end):
    """A fiscal year's filing window, for a target whose annual document is not read yet."""
    return (_year_before(report_end) + timedelta(days=1)).isoformat(), report_end


def events_in(filings, start, end):
    return sum(1 for form, day in filings if form in EVENT_FORMS and start <= day <= end)


def measure(source_root, company):
    """One company's plan and frame on the restored root, and what the saved submissions show."""
    plan = plan_historical_sources(repo_root=source_root, company_id=company["company_id"],
                                   count=YEARS)
    frame = declared_frame(repo_root=source_root, company_id=company["company_id"],
                           years=YEARS)
    limitations = list(plan["catalog_limitations"])
    for item in plan.get("predecessor_catalogs", []):
        limitations.extend(item["limitations"])
    untrusted = {item["history_name"]: item for item in limitations
                 if item["kind"] == "HISTORY_SHARD_SNAPSHOT_CONFLICT"}
    return plan, frame, untrusted


def _periods(row):
    return sorted({consumer.split(":")[1] for consumer in row.get("consumers", [])
                   if str(consumer).startswith("period:")})


def company_need(*, source_root, company, plan, frame, untrusted, scope):
    """Due rows the scope admits today, and the named bounds for what it cannot name yet."""
    admitted, refused_serving_window, serving_only_outside = [], [], []
    due = [row for row in frame["requirements"] if row["new_acquisition_required"]]
    for row in due:
        try:
            request_is_in_scope(allowance={"scope": scope}, company_id=company["company_id"],
                                dependency=row, purpose=scope["purposes"][0],
                                frame_report_dates=frame["target_report_dates"])
            admitted.append(row)
        except HistoricalAcquisitionError as error:
            inside = [period for period in _periods(row)
                      if scope["earliest_report_end"] <= period <= scope["latest_report_end"]]
            if str(error).startswith("ISSUE_47_TARGET_PERIOD_NOT_IN_SCOPE") and inside:
                refused_serving_window.append(row)
            elif str(error).startswith("ISSUE_47_TARGET_PERIOD_NOT_IN_SCOPE"):
                # Serves only a target outside the five years: once the
                # catalog is right it is no target, and nothing asks for it.
                serving_only_outside.append(row)
            else:
                _stop("EXTENSION_PROPOSAL_REFUSES_A_DUE_ROW:" + company["company_id"] + ":"
                      + row["source_url"] + ":" + str(error)[:120])
    terms = {"declarable_today": len(admitted),
             "refused_today_only_for_an_out_of_frame_consumer": len(refused_serving_window)}
    notes = {"due_rows_serving_only_a_target_outside_the_window": len(serving_only_outside)}
    if untrusted:
        index, filings = submissions(source_root, company["primary_cik"], set(untrusted))
        blocks = len(index["filings"]["files"])
        metadata_rows = sum(1 for row in admitted if row["dependency_class"] in METADATA)
        terms["metadata_refresh_beyond_the_declared_rows"] = (1 + blocks + 1) - metadata_rows
        notes["metadata"] = ("the index and every one of its %d blocks plus one, less the %d "
                             "refresh rows already declared" % (blocks, metadata_rows))
        targets = sorted(frame["target_report_dates"])
        latest = date.fromisoformat(targets[-1])
        expected = {latest.year - step for step in range(YEARS)}
        hidden = sorted(year for year in expected
                        if year not in {date.fromisoformat(t).year for t in targets})
        # The estimator must agree with the planner where both can be read.
        declared_windows = {}
        for row in due:
            if row["dependency_class"] == "FISCAL_EVENT_FILING":
                for period in _periods(row):
                    declared_windows[period] = declared_windows.get(period, 0) + 1
        saved_event_windows = {period for row in frame["requirements"]
                               if row["dependency_class"] == "FISCAL_EVENT_FILING"
                               and not row["new_acquisition_required"]
                               for period in _periods(row)}
        calibration = {}
        for period, rows in sorted(declared_windows.items()):
            if period in saved_event_windows:
                continue
            start, end = event_window(period)
            calibration[period] = {"due_rows": rows, "estimate": 2 * events_in(filings, start, end)}
            if calibration[period]["due_rows"] != calibration[period]["estimate"]:
                _stop("EXTENSION_PROPOSAL_ESTIMATOR_DISAGREES_WITH_THE_PLANNER:"
                      + company["company_id"] + ":" + json.dumps(calibration[period]))
        notes["event_estimator_calibration"] = calibration
        uses_estimator = bool(hidden) or any(
            item.get("saved_filing_count", 0) >= item["declared_filing_count"]
            for item in untrusted.values())
        if uses_estimator and not calibration:
            _stop("EXTENSION_PROPOSAL_ESTIMATOR_USED_WITHOUT_A_CALIBRATION_WINDOW:"
                  + company["company_id"])
        hidden_events = {}
        for year in hidden:
            report_end = latest.replace(year=year).isoformat()
            start, end = event_window(report_end)
            hidden_events[report_end] = 2 * events_in(filings, start, end)
        terms["a_missed_target_s_events"] = sum(hidden_events.values())
        terms["a_missed_target_s_annual_chain"] = 2 * len(hidden)
        terms["a_missed_target_s_proxy"] = len(hidden)
        notes["missed_targets"] = hidden_events
        # 8-Ks a stale block hides inside a target's window.
        hidden_by_block = {}
        for name, item in sorted(untrusted.items()):
            declared = next(f for f in index["filings"]["files"] if f["name"] == name)
            if item.get("saved_filing_count", 0) < item["declared_filing_count"]:
                missing = item["declared_filing_count"] - item["saved_filing_count"]
                basis = "the block lists %d filings its saved copy lacks" % missing
            else:
                # The saved copy is another partition: bound by the same span
                # in the years before, read from the trusted tables.
                start, end = declared["filingFrom"], declared["filingTo"]
                spans = []
                for back in range(1, YEARS):
                    shifted = [date.fromisoformat(day) for day in (start, end)]
                    shifted = [d.replace(year=d.year - back, day=min(d.day, 28)
                                         if d.month == 2 else d.day) for d in shifted]
                    spans.append(events_in(filings, shifted[0].isoformat(),
                                           shifted[1].isoformat()))
                missing = max(spans)
                basis = ("the saved copy is another partition; the most 8-Ks in the same "
                         "span of the %d years before: %s" % (YEARS - 1, spans))
            overlapping = [t for t in targets
                           if event_window(t)[0] <= declared["filingTo"]
                           and declared["filingFrom"] <= event_window(t)[1]]
            hidden_by_block[name] = {"filings": missing if overlapping else 0,
                                     "windows": overlapping, "basis": basis}
        terms["events_a_stale_block_hides"] = sum(2 * item["filings"]
                                                  for item in hidden_by_block.values())
        notes["stale_blocks"] = hidden_by_block
    governance = [item for item in frame["governance_declaration_limitations"]
                  if scope["earliest_report_end"] <= item["report_end"]
                  <= scope["latest_report_end"]]
    terms["proxies_of_targets_without_a_governance_plan"] = len(governance)
    return {"terms": terms, "notes": notes, "admitted": admitted,
            "classes": sorted({row["dependency_class"] for row in due}
                              | (set(METADATA) | {"ACCESSION_INSTANCE_DISCOVERY",
                                                  "ANNUAL_PERIOD_IDENTITY",
                                                  "FISCAL_EVENT_FILING",
                                                  "GOVERNANCE_DISCLOSURE_FILING"}
                                 if untrusted else set())
                              | ({"GOVERNANCE_DISCLOSURE_FILING"} if governance else set()))}


def main():
    source_root = Path(os.environ["SOURCE_ROOT"])
    first = acquisition_allowance(repo_root=REPO)
    export, state, claims = ledger_state()
    if export["approval"]["delegation_body_sha256"] != first["delegation_body_sha256"]:
        _stop("EXTENSION_PROPOSAL_EXPORT_IS_OF_ANOTHER_APPROVAL")
    if (Path(source_root).parent / "ledger" / "claims.jsonl").read_bytes() != claims:
        _stop("EXTENSION_PROPOSAL_SOURCE_ROOT_IS_NOT_THE_EXPORTED_LEDGER")
    first_scope = first["scope"]
    window = {"earliest_report_end": first_scope["earliest_report_end"],
              "latest_report_end": first_scope["latest_report_end"]}
    measured, frames = {}, {}
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")), \
            checkpoint_replayed_once():
        for company in _load_registry(repo_root=REPO):
            plan, frame, untrusted = measure(source_root, company)
            frames[company["company_id"]] = frame
            due = [row for row in frame["requirements"] if row["new_acquisition_required"]]
            if not due and not untrusted:
                continue
            measured[company["company_id"]] = (company, plan, frame, untrusted)
            print(company["company_id"], len(due), sorted(untrusted), flush=True)
        # The scope first asks every class a company could need, then is cut to
        # the classes the measurement named for it.
        wide = {"purposes": list(first_scope["purposes"]), "company_ids": sorted(measured),
                "dependency_classes": sorted(set(METADATA) | {
                    "ACCESSION_INSTANCE_DISCOVERY", "ANNUAL_PERIOD_IDENTITY",
                    "FISCAL_EVENT_FILING", "GOVERNANCE_DISCLOSURE_FILING"}),
                **window}
        wide["grants"] = [{"grant": "PROBE", "company_ids": wide["company_ids"],
                           "dependency_classes": wide["dependency_classes"], **window}]
        need = {company_id: company_need(source_root=source_root, company=company, plan=plan,
                                         frame=frame, untrusted=untrusted, scope=wide)
                for company_id, (company, plan, frame, untrusted) in measured.items()}
    classes = sorted({name for item in need.values() for name in item["classes"]})
    grants = [{"grant": "X_" + name,
               "company_ids": sorted(c for c, item in need.items() if name in item["classes"]),
               "dependency_classes": [name], **window} for name in classes]
    scope = {"purposes": list(first_scope["purposes"]), "company_ids": sorted(need),
             "dependency_classes": sorted({name for grant in grants
                                           for name in grant["dependency_classes"]}),
             "earliest_report_end": min(grant["earliest_report_end"] for grant in grants),
             "latest_report_end": max(grant["latest_report_end"] for grant in grants),
             "grants": grants}
    claimed = claimed_urls(source_root)
    reclaim_kinds = {}
    for company_id, (company, plan, frame, untrusted) in measured.items():
        for row in need[company_id]["admitted"]:
            if row["source_url"] in claimed:
                reclaim_kinds.setdefault(row["acquisition_kind"], set()).add(
                    row["dependency_class"])
        if untrusted and any(SUBMISSIONS + "CIK%010d" % int(company["primary_cik"]) in url
                             for url in claimed):
            # A new index means every block is asked for again.
            reclaim_kinds.setdefault("SNAPSHOT_REFRESH", set()).update(METADATA)
    reclaim = [{"acquisition_kind": kind, "dependency_classes": sorted(names)}
               for kind, names in sorted(reclaim_kinds.items())]
    if not set(reclaim_kinds) <= {"SNAPSHOT_REFRESH", "REPLACEMENT_ACQUISITION"}:
        _stop("EXTENSION_PROPOSAL_A_CLAIMED_ROW_IS_NOT_A_REFRESH_OR_REPLACEMENT:"
              + ",".join(sorted(reclaim_kinds)))
    cap = sum(sum(item["terms"].values()) for item in need.values())
    body = {"record_type": EXTENSION_TYPE, "requirement_id": REQUIREMENT_ID,
            "extension_ordinal": EXTENSION_ORDINAL,
            "extends": {"delegation_url": first["delegation_url"],
                        "delegation_body_sha256": first["delegation_body_sha256"],
                        "ledger_state": state},
            "budget_root": first["budget_root"],
            "maximum_additional_provider_paid_sec_calls": [0, 0, cap],
            "scope": scope, "reclaim": reclaim,
            "cap_arithmetic": {company_id: item["terms"] for company_id, item in sorted(need.items())},
            "execution": ("the same ledger, root, container, start marker and export as the "
                          "approval it extends; every gate that approval passes through "
                          "applies to this one, and they bind the executor's code path, not "
                          "the executor"),
            "production_authorized": False}
    text = json.dumps(body, indent=1, sort_keys=True)
    digest = sha256_bytes(content=text.encode("utf-8"))
    checks = verify(first=first, body=body, text=text, digest=digest, claimed=claimed,
                    frames=frames, need=need)
    out = {"record_type": "ISSUE_47_PROPOSED_SEC_ALLOWANCE_EXTENSION",
           "this_is_a_proposal_not_a_grant": {
               "where_a_grant_would_live": EXTENSION_POLICY_PATH,
               "what_is_still_missing": ["the owner posts the body below on issue 47",
                                         "register-extension reads it back from GitHub and "
                                         "writes the policy and the record"]},
           "the_comment_body_to_post": body, "the_comment_body_as_text": text,
           "digest_of_the_body": digest,
           "need_notes": {company_id: item["notes"] for company_id, item in sorted(need.items())},
           "verified": checks, "calls": {"provider": 0, "paid": 0, "sec": 0},
           "production_authorized": False}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (REPO / EXTENSION_BODY_PATH).write_bytes(text.encode("utf-8"))
    print(json.dumps({"cap": cap, "digest_of_the_body": digest, "verified": checks}, indent=1))


def verify(*, first, body, text, digest, claimed, frames, need):
    """The gate on the proposal, in a temporary tree, and the measured rows under it."""
    checks = {}
    record = json.loads((REPO / APPROVAL_RECORD_PATH).read_text(encoding="utf-8"))
    comment_id = int(record["id"]) + 1
    policy = {"requirement_id": REQUIREMENT_ID, "repository": TRUSTED_REPOSITORY,
              "approver_login": TRUSTED_APPROVER, "extension_ordinal": EXTENSION_ORDINAL,
              "delegation_url": record["html_url"].rsplit("-", 1)[0] + "-" + str(comment_id),
              "delegation_body_sha256": digest, "delegation_record_path": EXTENSION_RECORD_PATH,
              **{field: body[field] for field in ("extends", "budget_root",
                                                  "maximum_additional_provider_paid_sec_calls",
                                                  "scope", "reclaim")}}
    if set(policy) != set(REQUIRED_EXTENSION_FIELDS):
        _stop("EXTENSION_PROPOSAL_POLICY_FIELDS_DIFFER_FROM_THE_GATE_S")
    stand_in = {**record, "id": comment_id, "html_url": policy["delegation_url"], "body": text}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for relative in (POLICY_PATH, APPROVAL_RECORD_PATH):
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_bytes((REPO / relative).read_bytes())
        (root / EXTENSION_POLICY_PATH).write_text(json.dumps(policy, indent=1, sort_keys=True))
        (root / EXTENSION_RECORD_PATH).parent.mkdir(parents=True, exist_ok=True)
        (root / EXTENSION_RECORD_PATH).write_text(json.dumps(stand_in, indent=1))
        allowance = acquisition_allowance(repo_root=root)
        extension = acquisition_extension(repo_root=root, allowance=allowance)
        checks["accepted_offline"] = extension is not None
        effective = extended_allowance(allowance=allowance, extension=extension)
        widened = {**policy, "maximum_additional_provider_paid_sec_calls":
                   [0, 0, body["maximum_additional_provider_paid_sec_calls"][2] + 1]}
        (root / EXTENSION_POLICY_PATH).write_text(json.dumps(widened, indent=1, sort_keys=True))
        try:
            acquisition_extension(repo_root=root, allowance=allowance)
            _stop("EXTENSION_PROPOSAL_A_WIDER_POLICY_WAS_ACCEPTED")
        except HistoricalExtensionError as error:
            if not str(error).startswith("ISSUE_47_EXTENSION_WIDENS_THE_APPROVED_GRANT"):
                _stop("EXTENSION_PROPOSAL_WIDER_POLICY_REFUSED_FOR_ANOTHER_REASON:" + str(error))
            checks["a_policy_wider_than_the_comment"] = str(error)
    # Every due row the scope admits, asked of the effective allowance with
    # the re-request rule, as the session will ask it.
    census = {"admitted": 0, "admitted_as_a_request_again": 0, "refused": {}}
    for company_id, item in need.items():
        frame = frames[company_id]
        for row in item["admitted"]:
            request_is_in_scope(allowance=effective, company_id=company_id, dependency=row,
                                purpose=effective["scope"]["purposes"][0],
                                frame_report_dates=frame["target_report_dates"])
            if row["source_url"] in claimed:
                if reclaim_ordinal(allowance=effective, dependency=row,
                                   claimed_ordinals=claimed[row["source_url"]]) is None:
                    key = company_id + ":" + row["dependency_class"] + ":" + row["acquisition_kind"]
                    census["refused"][key] = census["refused"].get(key, 0) + 1
                    continue
                census["admitted_as_a_request_again"] += 1
            census["admitted"] += 1
    if census["refused"]:
        _stop("EXTENSION_PROPOSAL_A_DECLARED_ROW_WOULD_STILL_BE_REFUSED:"
              + json.dumps(census["refused"]))
    checks["declared_rows_under_the_extension"] = census
    # What pin_extension will check on the live root, checked now with the
    # ledger's own reserve reader: the claim log begins with the stated bytes,
    # holds the stated count, and the stated spending is what it had spent.
    root = Path(first["budget_root"])
    state = body["extends"]["ledger_state"]
    live = root / "claims.jsonl"
    if not live.is_file():
        _stop("EXTENSION_PROPOSAL_LIVE_LEDGER_NOT_HERE:" + str(live))
    held = live.read_bytes()[:state["claims"]["size"]]
    spent = [0, 0, 0]
    for line in held.decode("utf-8").splitlines():
        spent[{"PROVIDER": 0, "PAID": 1, "SEC": 2}[json.loads(line)["channel"]]] += 1
    spent[2] += SESSION_MODULE.resume_reserve_at_state(root, claims_size=state["claims"]["size"],
                                                       resumes=state["resumes"])
    if (sha256_bytes(content=held) != state["claims"]["sha256"]
            or held.count(b"\n") != state["claim_count"] or spent != state["cumulative"]):
        _stop("EXTENSION_PROPOSAL_LIVE_LEDGER_IS_NOT_THE_STATED_ONE:" + json.dumps(
            {"stated": state, "spent_at_that_log": spent}))
    checks["the_live_ledger_is_the_stated_one"] = {"claim_count": state["claim_count"],
                                                   "spent_at_that_log": spent}
    return checks


if __name__ == "__main__":
    main()
