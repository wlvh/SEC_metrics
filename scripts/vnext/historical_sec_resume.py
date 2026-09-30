"""Resume Issue #47's SEC ledger from the branch's export after the host that held it was lost.

Purpose: The acquisition runs in the executor's cloud container (plan revision
6). That container was once restored from an older snapshot while a company's
acquisition was running: the ledger root, its start record and every request
made after the last pushed export went with it. The design refused both ways
forward, as it was built to - a new start, because the branch carries this
approval's export, and the live path, because the local start record the
earliest marker names is gone - and left resuming to the owner. This module is
how a resume the owner decides on keeps the cumulative count bounding what was
spent (the loss and the decision: docs/evidence/issue47_history/
acquisition-wiring/ledger-lost-*/).

What a resume does, in order:

- It restores the ledger exactly as the branch's export carries it - slots,
  claim log, binding, attribution and data root - through the same
  ``restore_acquisition`` that checks every archive, replays the frozen
  checkpoint and registers it in this checkout's journal.
- It charges the lost segment. Requests the lost host made after its last
  export are recorded nowhere, so they are charged at their bound: every
  due row, inside a grant and not yet claimed, of the companies the lost host
  could have been acquiring (``lost_segment_reserve``). That count is the most
  one acquisition invocation for those companies could claim from the
  exported state, because a URL is claimed at most once, nothing is retried,
  and the rows it counts are of classes whose capture makes nothing new
  declarable. Where a due row is of a class whose capture can - an annual
  primary makes its event window and proxy declarable, an index or a shard
  decides which periods exist - the reserve is refused rather than
  understated, and the bound becomes the owner's to set.
- It writes a resume record beside the root, with a random number that stays
  local, and returns the marker comment to post on issue 47; the marker shows
  the record without the number and a digest of the whole, as a start marker
  does, and it carries the owner's decision as the executor transcribed it.

The reserve is counted by the ledger itself: ``HistoricalCallLedger.snapshot``
adds every resume's reserve to the SEC count, so a claim is refused as soon as
the slots plus the reserves reach the cap. The requests the lost segment may
have made will likely be made again, since the restored ledger has not claimed
them; the reserve pays for the first time, so the approved cap still bounds
what reached the SEC.

What the live path then requires (``require_published_resume``): no start
record beside the root (a host that kept it did not lose its ledger); the
approval's earliest start marker, unedited, is the start every resume in the
chain names; the resume markers on the issue, unedited and in order, are
exactly the local chain's public views - one more on the issue is a resume
made elsewhere, one fewer is a resume not yet published; every resume's
restored claim log is a prefix of the local one; and the ledger is not behind
the branch's export of it, claims and resume chain alike.

What this does not guard, and says so: the reserve rests on the executor's
record of which companies the lost host could have been acquiring (the
acquisition goes company by company and pushes an export after each, so it is
the companies after the last pushed export up to the one in flight); a
marker comment can be deleted by the account the executor acts as; and none of
it is a boundary against the executor itself. It keeps what was spent
auditable on the branch and on the issue, as the start does.

Call relationships: ``tools/vnext_historical_sec.py resume`` calls
``resume_ledger``; ``historical_sec_session.require_published_start`` calls
``require_published_resume`` when a resume chain is beside the root. Zero SEC
or provider calls.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import os
import secrets
import shutil

from .canonical import canonical_json_bytes, sha256_bytes, sha256_file, strict_json_file, strict_json_loads
from .historical_ledger_start import (LedgerKind, _host_facts, exported_here,
                                      require_not_behind_export, start_markers,
                                      start_record_path)
from .historical_sec_session import (RESUME_TYPE, HistoricalCallLedger, HistoricalSessionError,
                                     _allowance_ledger, _sec_start, resume_chain_path,
                                     resume_view)
from .historical_source_acquisition import (HistoricalAcquisitionError, declared_frame,
                                            request_is_in_scope)
from .invocation_control import _exclusive_write_bytes, _exclusive_write_json
from .normal_source_authority import ROOT

# The classes whose capture makes nothing new declarable: an 8-K body or header
# and a proxy are read by the routes, never by the planner's declarations. A
# due row of any other class can open more rows in a later pass - an annual
# primary its event window and proxy, an index or a shard the periods and
# filings themselves - so a reserve that counted only the rows due now would
# understate what one acquisition invocation could have claimed.
TERMINAL_CLASSES = ("FISCAL_EVENT_FILING", "GOVERNANCE_DISCLOSURE_FILING")
# Files the planner reads to declare what is due. The resume record carries
# their digests, so a reserve can be checked against the code that computed it.
PLANNER_FILES = ("scripts/vnext/historical_source_acquisition.py",
                 "scripts/vnext/normal_history_plan.py",
                 "scripts/vnext/historical_event_sources.py",
                 "scripts/vnext/historical_governance_sources.py")


def _need(condition, reason):
    if not condition:
        raise HistoricalSessionError("ISSUE_47_SEC_LEDGER_" + reason)


def _resume_kind():
    """The start kind with the resume record type: the same issue, account and approval checks."""
    start = _sec_start()
    return LedgerKind(record_type=RESUME_TYPE, prefix="ISSUE_47_SEC_LEDGER_RESUME",
                      title=start.title, error=start.error, ledger_paths=start.ledger_paths,
                      export_index=start.export_index, export_claims=start.export_claims,
                      repository=start.repository, issue_number=start.issue_number,
                      requirement_id=start.requirement_id, owner_id=start.owner_id)


MARKER_TITLE = "Issue #47 SEC ledger resume marker, posted by the executor."


def resume_markers(*, allowance, reader):
    """This approval's resume markers on issue 47, oldest first, by the owner's account only.

    A marker is a comment that begins with the marker's title: a status comment
    quoting one is not another resume. The same record posted twice - a retried
    POST GitHub had in fact accepted - is one resume, the earliest copy.
    """
    seen, markers = set(), []
    for item in start_markers(_resume_kind(), allowance=allowance, reader=reader):
        if not str(item["comment"].get("body") or "").startswith(MARKER_TITLE):
            continue
        digest = item["record"].get("resume_record_sha256")
        if digest in seen:
            continue
        seen.add(digest)
        markers.append(item)
    return markers


def _unedited(comment):
    created = comment.get("created_at")
    return type(created) is str and bool(created) and created == comment.get("updated_at")


def _expected_approval(allowance):
    """The approval block an export of this allowance's ledger carries."""
    return {key: allowance[key] for key in ("delegation_url", "delegation_body_sha256",
                                            "delegation_record_path", "budget_root",
                                            "maximum_additional_provider_paid_sec_calls")}


def _chain_lines(data):
    """Parse a chain's bytes: one canonical record per line, nothing else."""
    records = []
    for line in data.decode("utf-8").splitlines():
        record = strict_json_loads(text=line)
        _need(type(record) is dict and record.get("record_type") == RESUME_TYPE,
              "RESUME_CHAIN_RECORD_INVALID")
        _need(canonical_json_bytes(value=record).rstrip(b"\n") == line.encode("utf-8"),
              "RESUME_CHAIN_NOT_CANONICAL")
        records.append(record)
    return records


def _chain_bytes(records):
    return b"".join(canonical_json_bytes(value=record).rstrip(b"\n") + b"\n"
                    for record in records)


def local_chain(root):
    """The resume chain beside ``root``: public views, then this host's own full record last."""
    path = resume_chain_path(root)
    _need(path.is_file() and not path.is_symlink(), "RESUME_CHAIN_UNSAFE:" + str(path))
    records = _chain_lines(path.read_bytes())
    _need(records, "RESUME_CHAIN_EMPTY")
    _need("instance_nonce" in records[-1]
          and all("instance_nonce" not in record and "resume_record_sha256" in record
                  for record in records[:-1]),
          "RESUME_CHAIN_SHAPE:only the last record is this host's own")
    return records


def _check_links(views, *, start_sha):
    _need(views[0].get("resumes_start_record_sha256") == start_sha,
          "RESUME_IS_OF_ANOTHER_START")
    previous = None
    for view in views:
        _need(view.get("resumes_start_record_sha256") == start_sha
              and view.get("previous_resume_sha256") == previous,
              "RESUME_CHAIN_LINK_BROKEN")
        previous = view["resume_record_sha256"]


def _prefix(data, binding):
    return (type(binding) is dict and type(binding.get("size")) is int
            and len(data) >= binding["size"]
            and sha256_bytes(content=data[:binding["size"]]) == binding.get("sha256"))


def _export_member(index, name):
    return index.get("state_archive", {}).get("members", {}).get(name)


def lost_segment_reserve(*, data_root, claimed_urls, allowance, company_ids, years=5):
    """The most requests the named companies' acquisition could have sent from this state.

    Computed exactly as a pass computes what to claim: the frame's rows that
    need a new acquisition, minus URLs this ledger has claimed, each asked of
    ``request_is_in_scope``. A URL is claimed at most once and nothing is
    retried, so these rows are the most one invocation could claim - provided
    capturing them makes nothing new declarable, which is why a due row of any
    class outside ``TERMINAL_CLASSES`` is a refusal rather than a smaller bound.
    """
    from .historical_sec_extension import reclaim_ordinal
    purpose = allowance["scope"]["purposes"][0]
    # A mapping from URL to the ordinals of the slots that claimed it lets a row
    # the owner's extension allows to be requested once more count as one the
    # lost host could have claimed; a plain set of URLs (no ordinals) cannot say
    # that, and counts every claimed URL as done.
    claimed = (claimed_urls if isinstance(claimed_urls, dict)
               else {url: None for url in claimed_urls})
    by_company = {}
    for company_id in company_ids:
        _need(company_id in allowance["scope"]["company_ids"],
              "RESUME_COMPANY_NOT_IN_SCOPE:" + company_id)
        frame = declared_frame(repo_root=Path(data_root), company_id=company_id, years=years)
        admitted, outside = [], 0
        for row in frame["requirements"]:
            if not row["new_acquisition_required"]:
                continue
            if row["source_url"] in claimed and (
                    claimed[row["source_url"]] is None
                    or reclaim_ordinal(allowance=allowance, dependency=row,
                                       claimed_ordinals=claimed[row["source_url"]]) is None):
                continue
            try:
                request_is_in_scope(allowance=allowance, company_id=company_id, dependency=row,
                                    purpose=purpose,
                                    frame_report_dates=frame["target_report_dates"])
            except HistoricalSessionError:
                raise
            except HistoricalAcquisitionError:
                outside += 1
                continue
            admitted.append(row)
        opening = sorted({row["dependency_class"] for row in admitted
                          if row["dependency_class"] not in TERMINAL_CLASSES})
        _need(not opening, "RESUME_RESERVE_UNBOUNDED:" + company_id + ":" + ",".join(opening)
              + ": capturing these can make rows declarable that this count does not see; "
                "the bound is the owner's to set")
        by_company[company_id] = {
            "admitted_due_rows": len(admitted),
            "by_class": dict(sorted(Counter(row["dependency_class"]
                                            for row in admitted).items())),
            "due_outside_every_grant": outside}
    return {"reserve_sec_calls": sum(item["admitted_due_rows"] for item in by_company.values()),
            "by_company": by_company}


def marker_comment_body(record, *, decision_text):
    """The comment the executor posts on issue 47; its first json block is the resume's public view."""
    import json
    view = resume_view(record)
    reserve = record["lost_segment"]["reserve_sec_calls"]
    return (MARKER_TITLE + "\n\n"
            "The container that held the ledger was lost after the export "
            + record["restored_export"]["export_id"] + " was pushed. The owner's decision, "
            "transcribed by the executor (not posted by the owner): \"" + decision_text + "\". "
            "The ledger is restored exactly as that export carries it, and the requests the "
            "lost host may have made after it are charged at their bound, "
            + str(reserve) + " SEC calls, so the approved cap still bounds what was spent. "
            "The live path reads this issue's comments and refuses unless the resume markers "
            "for this approval are exactly the local resume chain, whose random number is not "
            "published here.\n\n```json\n"
            + json.dumps(view, indent=1, sort_keys=True, ensure_ascii=False) + "\n```\n")


_EXTENSION_NAMING = ("extension_ordinal", "delegation_url", "delegation_body_sha256",
                     "maximum_additional_provider_paid_sec_calls")


def _extension_named(extension):
    """The fields that name an extension, as a resume record and an export index carry them."""
    return {field: extension[field] for field in _EXTENSION_NAMING}


def _same_extension(exported, held):
    return held is not None and all(exported.get(field) == held.get(field)
                                    for field in _EXTENSION_NAMING)


def resume_ledger(*, allowance, reader, checkout, in_flight_company_ids, decision,
                  branch_export_index, branch_tip_commit, now=None):
    """Rebuild this approval's lost SEC ledger from the branch's export; return the marker to post.

    ``in_flight_company_ids`` are the companies the lost host could have been
    acquiring after its last pushed export; ``decision`` is the owner's
    decision as the executor transcribed it (``text`` and ``received_at``).
    ``branch_export_index`` is the export index as the branch's remote tip
    carries it, read by the caller after fetching, and ``branch_tip_commit``
    that tip, which the checkout's HEAD must contain: the checkout's export
    must be that one. A loss can take the checkout back with it - the one this was
    written for reset it to a commit hours old - and a checkout behind the
    branch would restore an older export and charge only what came after it.
    Everything that can be checked from the export's index and state archive
    is checked before the data root is rebuilt, which is the slow part.
    Nothing here is requested: the live path refuses until the marker is on
    GitHub.
    """
    from .historical_source_export import (EXPORT_DIRECTORY, INDEX_NAME, RESUME_MEMBER,
                                           STATE_ARCHIVE, _check_seal, _read_archive,
                                           restore_acquisition)
    kind = _sec_start()
    checkout = Path(checkout)
    root = Path(allowance["budget_root"])
    _need(root.is_absolute()
          and not any(path.is_symlink() for path in [root, *root.parents]),
          "RESUME_ROOT_UNSAFE:" + str(root))
    start_path, chain_path = start_record_path(root), resume_chain_path(root)
    _need(not start_path.exists() and not start_path.is_symlink(),
          "RESUME_BESIDE_A_START_RECORD:this host kept its start; it did not lose its ledger")
    _need(not chain_path.exists() and not chain_path.is_symlink(),
          "ALREADY_RESUMED_HERE:" + str(chain_path))
    _need(not (root.exists() and any(root.iterdir()))
          and not any(Path(other).exists() or Path(other).is_symlink()
                      for other in kind.ledger_paths(root)),
          "RESUME_ROOT_NOT_EMPTY:" + str(root))
    _need(type(decision) is dict and type(decision.get("text")) is str
          and bool(decision["text"].strip())
          and type(decision.get("received_at")) is str and bool(decision["received_at"]),
          "RESUME_DECISION_MISSING")
    companies = list(in_flight_company_ids)
    _need(companies and len(companies) == len(set(companies)), "RESUME_IN_FLIGHT_COMPANIES_INVALID")
    _need(exported_here(kind, allowance=allowance, checkout=checkout),
          "NOTHING_TO_RESUME:the checkout carries no export of this approval's ledger")
    export_dir = checkout / EXPORT_DIRECTORY
    _need(type(branch_export_index) is bytes
          and (export_dir / INDEX_NAME).read_bytes() == branch_export_index
          and type(branch_tip_commit) is str and len(branch_tip_commit) == 40,
          "RESUME_CHECKOUT_IS_NOT_THE_BRANCH_S_EXPORT:bring the checkout to the branch's tip")
    index = strict_json_file(path=export_dir / INDEX_NAME)
    _check_seal(index, "export_id")
    _need(index.get("execution_mode") == "LIVE"
          and index.get("approval") == _expected_approval(allowance),
          "RESUME_EXPORT_IS_FOR_ANOTHER_APPROVAL")
    # An export made under an extension says so; the reserve for what the lost
    # host could have spent after it must be computed under that extension's
    # grants and re-request rule, or the charge leaves out exactly the rows only
    # the extension admits. An allowance holding an extension the export does
    # not name is the other, conservative way round and is allowed.
    _need(index.get("extension") is None
          or _same_extension(index["extension"], allowance.get("extension")),
          "RESUME_EXPORT_WAS_SPENT_UNDER_AN_EXTENSION_THIS_ALLOWANCE_LACKS")
    state = _read_archive(export_dir / STATE_ARCHIVE, index["state_archive"])
    binding = strict_json_loads(text=state["ledger/binding.json"].decode("utf-8"))
    expected = _allowance_ledger(allowance=allowance, root=root, live=True).binding
    _need(binding == expected, "RESUME_BINDING_DIFFERS_FROM_THE_ALLOWANCE")
    exported_chain = _chain_lines(state[RESUME_MEMBER]) if RESUME_MEMBER in state else []
    markers = start_markers(kind, allowance=allowance, reader=reader)
    _need(markers, "RESUME_WITHOUT_A_PUBLISHED_START")
    _need(_unedited(markers[0]["comment"]),
          "START_MARKER_EDITED:" + str(markers[0]["comment"].get("html_url")))
    start_sha = markers[0]["record"].get("start_record_sha256")
    _need(type(start_sha) is str and bool(start_sha), "RESUME_START_MARKER_HAS_NO_DIGEST")
    published = resume_markers(allowance=allowance, reader=reader)
    _need(all(_unedited(item["comment"]) for item in published), "RESUME_MARKER_EDITED")
    # A resume marker on the issue that the export does not carry is a resume
    # whose own host was lost before it exported: what it spent after resuming
    # is not in this export either, and which companies it reached is not
    # something this host can know. The owner decides.
    _need([item["record"] for item in published] == exported_chain,
          "RESUMED_SINCE_THE_EXPORT:the issue shows " + str(len(published))
          + " resume markers and the export carries " + str(len(exported_chain))
          + "; ask the owner")
    if exported_chain:
        _check_links(exported_chain, start_sha=start_sha)
    claims = state["ledger/claims.jsonl"]
    staging = root.parent / ("." + root.name + ".resuming")
    sentinel = root.parent / ("." + root.name + ".resuming.lock")
    root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Held exclusively for the whole resume, so a second resume on this host is
    # refused rather than racing this one, and only the holder removes the
    # staging directory: a refused resume never deletes another's work.
    try:
        os.close(os.open(str(sentinel), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600))
    except FileExistsError:
        _need(False, "RESUME_IN_PROGRESS_OR_LEFT_OVER:" + str(sentinel) + ": a resume that "
              "stopped part way leaves this, its staging directory and possibly a partial "
              "root; see the ledger-lost evidence under "
              "docs/evidence/issue47_history/acquisition-wiring/")
    try:
        _need(not staging.exists() and not staging.is_symlink(),
              "RESUME_STAGING_LEFT_OVER:" + str(staging))
        restore_acquisition(export_dir=export_dir, out_root=staging)
        restored = staging / "ledger"
        _need((restored / "claims.jsonl").read_bytes() == claims
              and strict_json_file(path=restored / "binding.json") == binding,
              "RESUME_RESTORE_DIFFERS_FROM_THE_EXPORT")
        claimed = {}
        for slot in sorted((restored / "calls").iterdir()):
            claimed.setdefault(strict_json_file(path=slot / "sec-plan.json")["request"]["url"],
                               []).append(int(slot.name))
        reserve = lost_segment_reserve(data_root=staging / "source-inputs", claimed_urls=claimed,
                                       allowance=allowance, company_ids=companies)
        record = {"record_type": RESUME_TYPE, "schema_version": 1,
                  "requirement_id": kind.requirement_id,
                  "delegation_url": allowance["delegation_url"],
                  "delegation_body_sha256": allowance["delegation_body_sha256"],
                  "budget_root": allowance["budget_root"],
                  "resumes_start_record_sha256": start_sha,
                  "previous_resume_sha256": (exported_chain[-1]["resume_record_sha256"]
                                             if exported_chain else None),
                  "restored_export": {
                      "export_id": index["export_id"], "ledger_sha256": index["ledger_sha256"],
                      "exported_row_count": index["exported_row_count"],
                      "exported_from_commit": index["exported_from_commit"],
                      "branch_tip_commit": branch_tip_commit,
                      "claims": {"sha256": sha256_bytes(content=claims), "size": len(claims)}},
                  "lost_segment": {
                      "in_flight_company_ids": companies,
                      "reserve_sec_calls": reserve["reserve_sec_calls"],
                      "by_company": reserve["by_company"],
                      "basis": ("every due row inside a grant and not yet claimed of the "
                                "companies the lost host could have been acquiring, computed "
                                "from the restored export as a pass computes what to claim"),
                      "years": 5,
                      "planner_files_sha256": {relative: sha256_file(path=ROOT / relative)
                                               for relative in PLANNER_FILES}},
                  **({"extension": _extension_named(allowance["extension"])}
                     if allowance.get("extension") is not None else {}),
                  "decision": {"text": decision["text"], "received_at": decision["received_at"],
                               "recorded_as": "the owner's decision in the session, transcribed "
                                              "by the executor; not posted by the owner"},
                  "instance_nonce": secrets.token_hex(16),
                  "created_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "host": _host_facts(reader)}
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        # The data root last: a root holding only source-inputs reads to the
        # ledger's lock as a new ledger, while one holding a binding without
        # its anchor, or slots without a binding, is refused.
        for name in ("calls", "acquisition-attribution", "claims.jsonl", "binding.json"):
            os.replace(restored / name, root / name)
        os.replace(staging / "source-inputs", root / "source-inputs")
        _exclusive_write_json(path=HistoricalCallLedger.anchor_path(root), value=binding)
        _exclusive_write_bytes(path=HistoricalCallLedger.mirror_path(root), content=claims)
        # Last, so a resume cut short leaves no chain: the live path then
        # refuses the root, and it is plain that nothing was spent past the
        # export.
        _exclusive_write_bytes(path=chain_path, content=_chain_bytes([*exported_chain, record]))
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        sentinel.unlink()
    return {"status": "LEDGER_RESUMED", "resume_record": str(chain_path),
            "record": resume_view(record), "reserve": reserve,
            "marker_comment_body": marker_comment_body(record, decision_text=decision["text"]),
            "calls": [0, 0, 0]}


def require_published_resume(*, allowance, reader, checkout):
    """This host resumed the ledger, every resume is on GitHub, and it is not behind its export."""
    from .historical_source_export import EXPORT_DIRECTORY, INDEX_NAME
    kind = _sec_start()
    root = Path(allowance["budget_root"])
    start_path = start_record_path(root)
    _need(not start_path.exists() and not start_path.is_symlink(),
          "RESUME_BESIDE_A_START_RECORD:" + str(start_path))
    chain = local_chain(root)
    views = [resume_view(record) if "instance_nonce" in record else record for record in chain]
    for view in views:
        _need(view.get("requirement_id") == kind.requirement_id
              and all(view.get(key) == allowance[key]
                      for key in ("delegation_url", "delegation_body_sha256", "budget_root")),
              "RESUME_RECORD_IS_FOR_ANOTHER_APPROVAL")
        # A resume charged under an extension holds only while that extension
        # is the one in force: under another, or none, its reserve was not
        # computed against the grants now being spent.
        _need("extension" not in view or view["extension"]
              == (_extension_named(allowance["extension"])
                  if allowance.get("extension") is not None else None),
              "RESUME_WAS_CHARGED_UNDER_ANOTHER_EXTENSION")
    markers = start_markers(kind, allowance=allowance, reader=reader)
    _need(markers, "RESUME_WITHOUT_A_PUBLISHED_START")
    _need(_unedited(markers[0]["comment"]),
          "START_MARKER_EDITED:" + str(markers[0]["comment"].get("html_url")))
    _check_links(views, start_sha=markers[0]["record"].get("start_record_sha256"))
    published = resume_markers(allowance=allowance, reader=reader)
    _need(all(_unedited(item["comment"]) for item in published), "RESUME_MARKER_EDITED")
    shown = [item["record"] for item in published]
    _need(len(shown) >= len(views), "RESUME_NOT_PUBLISHED:post the resume marker on issue "
          + str(kind.issue_number))
    _need(shown == views, "RESUMED_ELSEWHERE:the issue's resume markers are not this "
          "host's chain")
    log = root / "claims.jsonl"
    held = log.read_bytes() if log.is_file() and not log.is_symlink() else b""
    for view in views:
        _need(_prefix(held, view["restored_export"]["claims"]),
              "RESUMED_LEDGER_IS_NOT_WHAT_WAS_RESTORED")
    require_not_behind_export(kind, allowance=allowance, checkout=checkout)
    index_path = Path(checkout) / EXPORT_DIRECTORY / INDEX_NAME
    exported = (_export_member(strict_json_file(path=index_path), "ledger/resumes.jsonl")
                if exported_here(kind, allowance=allowance, checkout=checkout) else None)
    own = _chain_bytes(views)
    # Until an export carrying the whole chain is on the branch, a second loss
    # would find the resume only on the issue - a deleted marker would take it
    # with it - so nothing is claimed before that export.
    _need(exported is not None and _prefix(own, exported) and exported["size"] == len(own),
          "RESUME_NOT_EXPORTED:export the resumed ledger and push it before acquiring")
    return {"resume_record": chain[-1], "marker_url": published[-1]["comment"].get("html_url"),
            "reserve_sec_calls": sum(view["lost_segment"]["reserve_sec_calls"] for view in views)}
