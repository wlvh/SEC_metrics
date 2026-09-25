"""Issue #47's own SEC acquisition: its allowance, its count, its execution.

``tools/vnext_historical_sec.py capture`` refused with
``ISSUE_47_SEC_EXECUTION_NOT_WIRED`` even when an allowance existed, because
the execution path did not exist. It was also the plainest counter-example to
a sentence this issue had written and withdrawn - "no wiring work left that is
not blocked on material or allowance". Connecting an allowance check, a
cumulative count, a request, an immutable save and a source installation is
offline engineering that needs no grant, and this is it.

Why not reuse ``SecAcquisitionSession``. Its ``_check`` asserts
``requirement_id == issue_28_v14``, ``limits == [240, 240, 80]``, Issue #28's
budget root and Issue #28's own offline wiring receipt; its ledger's
``live_ledger`` calls ``load_delegation``, which refuses any other requirement
by name. Running Issue #47's fetches through it would draw on Issue #28's
allowance, which this issue's text forbids. ``continuous_call_ledger.py``,
``continuous_sec_acquisition.py`` and ``continuous_call_policy.py`` are all in
the approved call policy's ``rule_paths``, so none of them can be widened
either. **Capability is reusable, authorization is not** - so the transport,
the attempt primitives, the source installation shape and the provenance
validator are all the existing ones, and the allowance and the count are new.

What guarantees the sources this produces. The checkpoint written here is
validated by ``continuous_sec_acquisition.validate_acquisition_checkpoint``,
which is frozen under ``issue_28_v14`` and cannot be edited from this issue.
It replays the ledger prefix, every capture's row binding and every successful
capture's immutable attempt. So the provenance claim does not rest on this
module's bytes - it rests on code this issue cannot change, which is why this
module does not need to be a rule file.

What that validator does **not** say is which issue's allowance paid for a
row: its record carries mode and captures, not an issue. That attribution is
provable from this ledger's own slots, which name ``issue_47_v1``, and from
the attribution record written beside them. Stating that separation is the
point; a checkpoint in the shared journal must not be read as Issue #47
credit, nor as Issue #28's.

Execution modes. ``recorded_historical_session`` takes an explicit response
and is test-only: it refuses any configured budget root, writes
``RECORDED_TEST_ONLY`` through every record, and its checkpoint carries
``real_sec_credit: False``. ``live_historical_session`` requires Issue #47's
own allowance record, which does not exist, so it refuses today by naming the
path and fields rather than by failing vaguely. A recorded run cannot be
relabelled live: the mode is fixed by the factory and re-checked by the frozen
validator.
"""
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
import fcntl
import os

from sec_http import (SecHttpClient, parse_request_log_rows, request_log_attempt_id,
                      validate_official_sec_url, validate_request_log_manifest)
from .batch_workflow import validate_request_attempt_binding
from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file
from .historical_source_acquisition import (POLICY_PATH, REQUIREMENT_ID,
                                            HistoricalAcquisitionError,
                                            acquisition_allowance, declared_frame,
                                            historical_dependency, request_is_in_scope)
from .invocation_control import _exclusive_write_bytes, _exclusive_write_json
from .normal_source_authority import MANIFEST_PATH, ROOT, _baseline_file
from .sources import resolve_repository_file

_FACTORY = object()
MANIFEST = "requirements/issue_47_v1/baseline_manifest.json"
PARENT_ID = "issue_28_v13"
PARENT_REGISTER = "decision_register.json"
# The frozen validator's own record type. Conforming to its contract is what
# makes it able to check this issue's output; a private type would mean a
# private validator, which is exactly the weaker claim.
CHECKPOINT_TYPE = "ORDINARY_SEC_ACQUISITION_CHECKPOINT"
ATTRIBUTION_TYPE = "ISSUE_47_HISTORICAL_ACQUISITION_ATTRIBUTION"
LIVE_PURPOSE = "ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"
RECORDED_PURPOSE = "ISSUE47_RECORDED_SOURCE_TEST"
LEDGER_TYPE = "ISSUE_47_HISTORICAL_CALL_ALLOWANCE"
SEC = "SEC"
# One declared dependency, taken from the planner's own output: the prior
# annual accession index that B02 reads for Marriott's 2021 target.
WIRING_COMPANY = "marriott_international"
WIRING_URL = ("https://www.sec.gov/Archives/edgar/data/1048286/"
              "000162828021002433/index.json")


class HistoricalSessionError(HistoricalAcquisitionError):
    """This session's own refusal: allowance, count, mode or observed ledger.

    The dependency gate raises the base ``HistoricalAcquisitionError`` instead,
    and deliberately so: an undeclared URL is the same refusal whether it is
    reached through the planning CLI or through a capture, and giving it two
    names would suggest two rules. A caller that wants both catches the base.
    """


def _need(condition, reason):
    if not condition:
        raise HistoricalSessionError(reason)


def _sealed(body, field):
    return {**body, field: content_hash(value=body)}


def _check_seal(value, field):
    _need(value.get(field) == content_hash(
        value={k: v for k, v in value.items() if k != field}),
        "ISSUE_47_ACQUISITION_RECORD_CHANGED:" + field)


def _presentation_paths():
    """The parent's presentation paths, reached through this issue's manifest.

    ``initialize_source_inputs`` excludes these because presentation is
    installed from current bound code rather than as a source dependency, and
    one of them is under ``config/``, so the exclusion cannot be skipped by
    only copying data directories.

    The value is read from the parent's committed decision register, whose
    bytes this issue's own manifest records - so the chain is manifest to
    snapshot-file hash to value, not a constant copied into this file.
    """
    manifest = strict_json_file(path=ROOT / MANIFEST)
    parent = manifest["parent"]
    _need(parent["requirement_id"] == PARENT_ID,
          "ISSUE_47_PARENT_CHANGED:" + str(parent["requirement_id"]))
    recorded = parent["snapshot_files"][PARENT_REGISTER]
    path = resolve_repository_file(
        repo_root=ROOT, repo_relative_path="requirements/" + PARENT_ID + "/" + PARENT_REGISTER)
    raw = path.read_bytes()
    _need({"sha256": sha256_bytes(content=raw), "size": len(raw)} == recorded,
          "ISSUE_47_PARENT_REGISTER_CHANGED")
    register = strict_json_file(path=path)
    found = _find_presentation(register)
    _need(found is not None, "ISSUE_47_PARENT_PRESENTATION_PATHS_MISSING")
    return set(found), manifest


def _find_presentation(value):
    if isinstance(value, dict):
        if "presentation_paths" in value:
            return value["presentation_paths"]
        for item in value.values():
            found = _find_presentation(item)
            if found is not None:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_presentation(item)
            if found is not None:
                return found
    return None


def install_historical_source_inputs(*, root: Path):
    """Copy the finite existing source corpus and this issue's rule inputs once.

    Same shape as ``initialize_source_inputs``: the baseline corpus is copied
    on first use and thereafter only checked, so a session never re-fetches
    what the repository already holds, and the installed root is owned rather
    than adopted. The rule inputs come from Issue #47's own manifest and are
    verified byte for byte, so an installation cannot quietly run against
    different configuration from the one the manifest records.
    """
    root = Path(root)
    baseline = strict_json_file(path=ROOT / MANIFEST_PATH)
    stamp = {"baseline_manifest_sha256": sha256_file(path=ROOT / MANIFEST_PATH)}
    if root.exists():
        _need((root / "source-baseline.json").is_file(),
              "ISSUE_47_SOURCE_ROOT_UNOWNED")
        _need(strict_json_file(path=root / "source-baseline.json") == stamp,
              "ISSUE_47_SOURCE_BASELINE_CHANGED")
    else:
        root.mkdir(parents=True)
        for relative in baseline["files"]:
            _baseline_file(ROOT, relative, baseline)
            raw = resolve_repository_file(repo_root=ROOT,
                                          repo_relative_path=relative).read_bytes()
            _exclusive_write_bytes(path=root / relative, content=raw)
        _exclusive_write_json(path=root / "source-baseline.json", value=stamp)
    from .normal_annual_input_v2 import POLICY_PATH as fiscal_policy
    # Written unconditionally on every call, never skipped when the file is
    # already there. ``_exclusive_write_bytes`` accepts a second write of
    # identical bytes and rejects different ones, so calling it again is what
    # re-checks an existing root rather than trusting it; skipping the write
    # would also skip the hash comparison below.
    _exclusive_write_bytes(path=root / fiscal_policy,
                           content=(ROOT / fiscal_policy).read_bytes())
    # Every rule input, chosen by the kind of file rather than by where it
    # lives. The parent's installer copies config/ and catalog/, and this one
    # did the same until a recorded bank run over an installed root stopped
    # with "No such file" at 02_指标定义_SEC_10公司单年指标.md: B13's scope is
    # read from the approved definition, the definition sits at the repository
    # root, and the route reads it from the data root. A directory list is a
    # proxy for "rule input", and the proxy was short. Code is the one kind
    # left out, because it runs from the bound code tree and nothing imports
    # it from here; presentation is left out as before.
    presentation, manifest = _presentation_paths()
    for relative, binding in manifest["execution_authority"]["files"].items():
        if relative in presentation or relative.endswith(".py"):
            continue
        raw = resolve_repository_file(repo_root=ROOT,
                                      repo_relative_path=relative).read_bytes()
        _need({"sha256": sha256_bytes(content=raw), "size": len(raw)} == binding,
              "ISSUE_47_PROCESSING_RULE_CHANGED:" + relative)
        _exclusive_write_bytes(path=root / relative, content=raw)


RESOLVED = {"SUCCEEDED", "FAILED_TERMINAL"}


def _terminal_block_reason(*, slot, intent, mode):
    """Why this slot still blocks the channel, or None when it is resolved.

    The previous version asked only whether ``terminal.json`` existed. Measured
    against that: a terminal whose whole content was ``{}``, and a properly
    sealed terminal whose status was ``UNKNOWN_REMOTE_OUTCOME``, both stopped
    blocking - and the second is exactly the case the rule exists for, because
    ``capture`` writes a terminal for an unknown outcome too. A file is not an
    outcome.

    Four distinct states, because collapsing them is what hid the defect:
    absent, unreadable or unsealed, bound to another intent, and a terminal
    that records that nobody knows what happened. Only a well-formed terminal
    for this intent, recording a known outcome, resolves the slot. A known
    failure resolves it - failures count and the run continues - and an
    unknown one does not, because continuing past an unknown makes the
    cumulative count untrustworthy, which is the one thing a ceiling cannot
    survive.
    """
    path = slot / "terminal.json"
    if not path.is_file():
        return "TERMINAL_ABSENT"
    try:
        terminal = strict_json_file(path=path)
        _check_seal(terminal, "terminal_id")
    except Exception:
        return "TERMINAL_RECORD_DAMAGED"
    if terminal.get("intent_id") != intent["intent_id"]:
        return "TERMINAL_BOUND_TO_ANOTHER_INTENT"
    if terminal.get("execution_mode") != mode:
        return "TERMINAL_MODE_DIFFERS"
    status = terminal.get("status")
    if status not in RESOLVED:
        return "OUTCOME_NOT_KNOWN:" + str(status)
    # A terminal names a receipt; until this read it, a terminal could name a
    # receipt that was missing or belonged to another request and still resolve
    # the slot. Measured against that: both cases left blocked empty and the
    # next claim succeeded. The frozen source validator would refuse such a
    # ledger later, but "later" is after the next request has gone out, and
    # this check exists to run before it.
    receipt_path = slot / "sec-receipt.json"
    if not receipt_path.is_file():
        return "RECEIPT_ABSENT"
    try:
        receipt = strict_json_file(path=receipt_path)
        _check_seal(receipt, "receipt_id")
    except Exception:
        return "RECEIPT_RECORD_DAMAGED"
    if receipt.get("receipt_id") != terminal.get("sec_receipt_id"):
        return "TERMINAL_NAMES_ANOTHER_RECEIPT"
    if receipt.get("intent_id") != intent["intent_id"]:
        return "RECEIPT_BOUND_TO_ANOTHER_INTENT"
    if receipt.get("status") != status:
        return "RECEIPT_AND_TERMINAL_DISAGREE:" + str(receipt.get("status"))
    if receipt.get("execution_mode") != mode:
        return "RECEIPT_MODE_DIFFERS"
    return None


class HistoricalCallLedger:
    """Issue #47's own cumulative count, with a process lock over its root.

    Counting is by claimed slot rather than by outcome, which is what makes a
    failure count: the slot is written before the request and never removed.
    A slot with no terminal blocks the channel, because a claim with no
    terminal means the request may have gone out and nobody knows - continuing
    past that is what would make the cumulative number untrustworthy, and the
    number is the only thing a ceiling can rest on.
    """

    def __init__(self, *, factory, root, binding, live):
        _need(factory is _FACTORY, "ISSUE_47_LEDGER_FACTORY_REQUIRED")
        self._factory = factory
        self.root = Path(root)
        self.binding = binding
        self.live = live
        self._locked = False

    @contextmanager
    def locked(self):
        """Hold the root's lock for one capture, so two processes cannot claim."""
        self.root.mkdir(parents=True, exist_ok=True)
        handle = os.open(str(self.root / ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self._locked = True
            yield self
        finally:
            self._locked = False
            fcntl.flock(handle, fcntl.LOCK_UN)
            os.close(handle)

    def snapshot(self):
        """Counts consumed so far and any channel a lost terminal blocks."""
        calls = self.root / "calls"
        counts = [0, 0, 0]
        blocked = []
        slots = sorted(calls.iterdir()) if calls.is_dir() else []
        for slot in slots:
            intent = strict_json_file(path=slot / "intent.json")
            _check_seal(intent, "intent_id")
            _need(intent["requirement_id"] == REQUIREMENT_ID,
                  "ISSUE_47_LEDGER_SLOT_IS_FOR_ANOTHER_REQUIREMENT:" + slot.name)
            _need(intent["execution_mode"] == self.mode,
                  "ISSUE_47_LEDGER_MODE_CHANGED:" + slot.name)
            index = {"PROVIDER": 0, "PAID": 1, SEC: 2}[intent["channel"]]
            counts[index] += 1
            reason = _terminal_block_reason(slot=slot, intent=intent, mode=self.mode)
            if reason is not None:
                blocked.append({"slot": slot.name, "channel": intent["channel"],
                                "reason": reason})
        return {"counts": counts, "limits": list(self.binding["limits"]),
                "blocked": blocked, "slot_count": len(slots)}

    @property
    def mode(self):
        return "LIVE" if self.live else "RECORDED_TEST_ONLY"

    def require_unblocked(self):
        """Refuse while any claim lacks a terminal, and return the state.

        Checked before a capture does anything, not only before it claims. An
        unresolved terminal means the count cannot be accounted for, and a
        session that answered other questions against such a ledger would be
        handing back results it cannot stand behind - including the "already
        saved, no call needed" answer, which is exactly the one that looks
        harmless. Reconciling the slot is the only way forward.
        """
        state = self.snapshot()
        _need(not state["blocked"],
              "ISSUE_47_UNRESOLVED_TERMINAL_BLOCKS_THE_CHANNEL:"
              + ",".join(item["slot"] + "=" + item["reason"]
                         for item in state["blocked"]))
        return state

    def claim(self, *, channel, request_digest, plan_id, purpose):
        """Consume one call of ``channel`` and return its slot and intent."""
        _need(self._locked, "ISSUE_47_LEDGER_LOCK_REQUIRED")
        _need(purpose in self.binding["purposes"],
              "ISSUE_47_PURPOSE_NOT_IN_ALLOWANCE:" + purpose)
        state = self.require_unblocked()
        index = {"PROVIDER": 0, "PAID": 1, SEC: 2}[channel]
        delta = [0, 0, 0]
        delta[index] = 1
        _need(all(a + b <= c for a, b, c in
                  zip(state["counts"], delta, self.binding["limits"])),
              "ISSUE_47_CUMULATIVE_LIMIT_REACHED:" + channel + ":"
              + str(state["counts"]) + " of " + str(self.binding["limits"]))
        ordinal = state["slot_count"] + 1
        path = self.root / "calls" / ("%04d" % ordinal)
        intent = _sealed({"record_type": "ISSUE_47_HISTORICAL_CALL_INTENT",
                          "requirement_id": REQUIREMENT_ID, "channel": channel,
                          "ordinal": ordinal, "execution_mode": self.mode,
                          "allowance_binding_id": self.binding["binding_id"],
                          "request_digest": request_digest, "plan_id": plan_id,
                          "purpose": purpose, "automatic_retry_count": 0,
                          "counts_before": state["counts"],
                          "production_authorized": False}, "intent_id")
        _exclusive_write_json(path=path / "intent.json", value=intent)
        return path, intent

    def finish(self, *, path, intent, receipt):
        """Close the slot. Only a written terminal unblocks the channel."""
        _need(self._locked, "ISSUE_47_LEDGER_LOCK_REQUIRED")
        counts = [0, 0, 0]
        counts[{"PROVIDER": 0, "PAID": 1, SEC: 2}[intent["channel"]]] = 1
        terminal = _sealed({"record_type": "ISSUE_47_HISTORICAL_CALL_TERMINAL",
                            "intent_id": intent["intent_id"],
                            "sec_receipt_id": receipt["receipt_id"],
                            "status": receipt["status"],
                            "stop_reason": receipt["stop_reason"],
                            "execution_mode": self.mode, "counts": counts,
                            "counts_kind": ("ACTUAL_OR_UNKNOWN_CHARGED" if self.live
                                            else "RECORDED_TEST_SIMULATION"),
                            "production_authorized": False}, "terminal_id")
        _exclusive_write_json(path=path / "terminal.json", value=terminal)
        return terminal


class HistoricalSecSession:
    """One declared Issue #47 dependency per capture; no loop, no retry."""

    def __init__(self, *, factory, ledger, allowance, recorded_response=None,
                 recorded_status=200):
        _need(factory is _FACTORY, "ISSUE_47_SESSION_FACTORY_REQUIRED")
        # bytes answers every URL with the same body, which is all a
        # single-document chain needs. A dict answers each URL with its own,
        # which is what a chain over several documents needs - a refresh of a
        # submissions index and its shards is not one document, and the index
        # and each shard have to disagree for the check under test to mean
        # anything. Nothing else is accepted, so a live session still carries
        # no recorded body at all.
        _need((ledger.live and recorded_response is None)
              or (not ledger.live and type(recorded_response) in (bytes, dict)),
              "ISSUE_47_TRANSPORT_MODE_CHANGED")
        if type(recorded_response) is dict:
            _need(recorded_response and all(type(key) is str and type(value) is bytes
                                            for key, value in recorded_response.items()),
                  "ISSUE_47_RECORDED_RESPONSE_MAP_INVALID")
        self._factory = factory
        self.ledger = ledger
        self.allowance = allowance
        self.response = recorded_response
        self.response_status = recorded_status
        self.data_root = ledger.root / "source-inputs"
        # What this session claimed, so a caller never has to infer it from the
        # shared ledger's total. Two snapshots around a capture are not taken
        # under the same lock, so another process finishing a request between
        # them makes the difference read as this invocation's - attributing
        # somebody else's call to us.
        self.claimed_slots = []

    def _check(self):
        _need(self._factory is _FACTORY, "ISSUE_47_SESSION_FACTORY_REQUIRED")
        _need(self.allowance["requirement_id"] == REQUIREMENT_ID,
              "ISSUE_47_ALLOWANCE_IS_FOR_ANOTHER_REQUIREMENT")
        _need(self.ledger.binding["limits"]
              == list(self.allowance["maximum_additional_provider_paid_sec_calls"]),
              "ISSUE_47_LEDGER_LIMITS_DIFFER_FROM_ALLOWANCE")
        _need(self.allowance["scope"].get("company_ids")
              and self.allowance["scope"].get("dependency_classes"),
              "ISSUE_47_ALLOWANCE_SCOPE_IS_NOT_ENFORCEABLE")
        if self.ledger.live:
            _need(self.ledger.root == Path(self.allowance["budget_root"])
                  and self.response is None,
                  "ISSUE_47_LIVE_SESSION_MUST_USE_THE_GRANTED_ROOT")

    def _recorded_body(self, *, url):
        """The body this session answers one URL with, or a named refusal.

        A missing entry is a refusal rather than a fallback to some other
        document: answering a URL with another URL's bytes is the failure a
        multi-document chain is meant to expose, and it would look like a pass.
        """
        if type(self.response) is bytes:
            return self.response
        _need(url in self.response,
              "ISSUE_47_RECORDED_RESPONSE_NOT_PROVIDED:" + url)
        return self.response[url]

    def capture(self, *, company_id, url, years=5):
        """Fetch one declared dependency and prove what the ledger then holds."""
        self._check()
        validate_official_sec_url(url=url)
        with self.ledger.locked():
            self.ledger.require_unblocked()
            install_historical_source_inputs(root=self.data_root)
            frame = declared_frame(repo_root=self.data_root, company_id=company_id,
                                   years=years)
            matches = [row for row in frame["requirements"] if row["source_url"] == url]
            _need(matches, "HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY:" + url)
            _need(len(matches) == 1, "HISTORICAL_URL_IS_DECLARED_MORE_THAN_ONCE:" + url)
            dependency = matches[0]
            # The planner, not the saved flag, decides whether a fetch is due.
            # A SNAPSHOT_REFRESH row carries VERIFIED_SAVED_SOURCE *and*
            # new_acquisition_required: its bytes are intact but disagree with
            # the index it was declared under, so reading only the first field
            # answered "already saved" about a source that needs refreshing.
            if not dependency["new_acquisition_required"]:
                return {"status": "EXISTING_VERIFIED_SOURCE_REUSED",
                        "source": dependency, "calls": [0, 0, 0],
                        "acquisition_kind": dependency.get("acquisition_kind")}
            log = self.data_root / "evidence/requests_log.csv"
            validate_request_log_manifest(log_path=log)
            before = log.read_bytes()
            old_rows = parse_request_log_rows(text=before.decode("utf-8"))
            client = SecHttpClient(workdir=self.data_root,
                                   config_path=ROOT / "config/sec_config.json",
                                   log_path=log)
            client.config = {**client.config, "max_retries": 0}
            request = {"url": url, "method": "GET", "automatic_retry_count": 0,
                       "sec_configuration_sha256": sha256_file(
                           path=ROOT / "config/sec_config.json")}
            plan = {"company_id": company_id, "requirement_id": REQUIREMENT_ID,
                    "source_dependency": dependency, "request": request,
                    "source_ledger_before_sha256": sha256_bytes(content=before),
                    "source_row_count_before": len(old_rows)}
            # Both halves, and in both modes. A URL being a real dependency is
            # not the same as this grant allowing it to be fetched; and a scope
            # check only the live path runs is a check nothing ever exercises,
            # so the recorded session carries a scope too and is held to it.
            purpose = self.allowance["scope"]["purposes"][0]
            admitted = request_is_in_scope(allowance=self.allowance,
                                           company_id=company_id,
                                           dependency=dependency, purpose=purpose,
                                           frame_report_dates=frame["target_report_dates"])
            plan["scope_admission"] = admitted
            path, intent = self.ledger.claim(
                channel=SEC, request_digest=content_hash(value=request),
                plan_id=content_hash(value=plan), purpose=purpose)
            self.claimed_slots.append({"intent_id": intent["intent_id"],
                                       "ordinal": intent["ordinal"],
                                       "channel": intent["channel"]})
            _exclusive_write_json(path=path / "sec-plan.json", value=plan)
            document_name = Path(urlsplit(url).path).name
            _need(bool(document_name), "ISSUE_47_DOCUMENT_NAME_MISSING")
            target = (self.data_root / "evidence/issue47-historical"
                      / ("%04d" % intent["ordinal"]) / document_name)
            if self.ledger.live:
                # Re-checked immediately before the only socket in this module.
                self._check()
                result = client.fetch(url=url, purpose=LIVE_PURPOSE, local_path=target)
            else:
                result = client._persist_result(
                    url=url, status_code=self.response_status,
                    body=self._recorded_body(url=url),
                    headers={"Content-Type": dependency["media_type"]},
                    local_path=target,
                    error="" if self.response_status == 200 else "RECORDED_HTTP_FAILURE")
                client._append_log_row(result=result, purpose=RECORDED_PURPOSE, attempt=0)
            receipt = self._receipt(intent=intent, path=path, log=log, before=before,
                                    old_rows=old_rows, url=url, result=result,
                                    dependency=dependency, company_id=company_id)
            terminal = self.ledger.finish(path=path, intent=intent, receipt=receipt)
            checkpoint = self.register_checkpoint()
            return {"status": receipt["status"], "receipt": receipt, "terminal": terminal,
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "calls": [0, 0, int(self.ledger.live)],
                    "production_authorized": False}

    def calls_this_session(self):
        """What this session actually claimed, by channel.

        Derived from the slots this object claimed, not from the ledger's
        running total. The ledger is shared, and the total moving between two
        reads says only that somebody made a request - not that we did.
        """
        counts = [0, 0, 0]
        for slot in self.claimed_slots:
            counts[{"PROVIDER": 0, "PAID": 1, SEC: 2}[slot["channel"]]] += 1
        return counts if self.ledger.live else [0, 0, 0]

    def _receipt(self, *, intent, path, log, before, old_rows, url, result, dependency,
                 company_id):
        """Prove this session appended exactly its own row, then seal it."""
        validate_request_log_manifest(log_path=log)
        after = log.read_bytes()
        new_rows = parse_request_log_rows(text=after.decode("utf-8"))
        _need(after.startswith(before) and len(new_rows) == len(old_rows) + 1,
              "ISSUE_47_UNOWNED_APPEND_OR_PREFIX_CHANGE")
        row = new_rows[-1]
        _need(row["source_url"] == url and row["method"] == "GET"
              and row["retry_attempt"] == "0", "ISSUE_47_NATIVE_REQUEST_CHANGED")
        wire = {}
        for name, location in [("body", result.local_path), ("headers", result.headers_path)]:
            if location:
                relative = Path(location).relative_to(self.data_root).as_posix()
                data = resolve_repository_file(repo_root=self.data_root,
                                               repo_relative_path=relative).read_bytes()
                _exclusive_write_bytes(path=path / "sec-wire" / (name + ".bin"), content=data)
                wire[name] = {"source_path": relative, "sha256": sha256_bytes(content=data),
                              "size": len(data)}
        success = row["status_code"] == "200" and not row["error"]
        proof = None
        if success:
            binding = validate_request_attempt_binding(
                repo_root=self.data_root, source_url=url,
                content_sha256=row["content_sha256"], accession=dependency["accession"],
                document_name=row["document_name"],
                request_attempt_id=request_log_attempt_id(row_index=len(old_rows), row=row),
                require_immutable=True)
            proof = {"source_url": url, "accession": dependency["accession"],
                     "document_name": row["document_name"],
                     "content_sha256": row["content_sha256"], **binding}
        body = {"record_type": "ISSUE_47_HISTORICAL_SEC_RECEIPT",
                "intent_id": intent["intent_id"], "execution_mode": self.ledger.mode,
                "actual_sec_egress_count": int(self.ledger.live),
                "automatic_retry_count": 0,
                "status": ("SUCCEEDED" if success else "FAILED_TERMINAL"
                           if row["status_code"] != "0" else "UNKNOWN_REMOTE_OUTCOME"),
                "stop_reason": ("UNKNOWN_REMOTE_OUTCOME" if row["status_code"] == "0"
                                else "HTTP_402" if row["status_code"] == "402" else ""),
                "ledger_before_sha256": sha256_bytes(content=before),
                "ledger_after_sha256": sha256_bytes(content=after),
                "ledger_row_index": len(old_rows), "ledger_row": row, "proof": proof,
                "wire": wire, "company_id": company_id,
                "requirement_id": REQUIREMENT_ID, "production_authorized": False}
        receipt = _sealed(body, "receipt_id")
        _exclusive_write_json(path=path / "sec-receipt.json", value=receipt)
        return receipt

    def register_checkpoint(self):
        """Enroll the observed ledger, validated by the frozen replay.

        The checkpoint conforms to ``ORDINARY_SEC_ACQUISITION_CHECKPOINT`` so
        that ``validate_acquisition_checkpoint`` - frozen under
        ``issue_28_v14`` and unreachable from this issue - performs the
        provenance replay. Because that record carries a mode and captures but
        not an issue, the attribution record written beside it in this issue's
        own ledger root is what names ``issue_47_v1``.
        """
        from .continuous_sec_acquisition import (_journal, validate_acquisition_checkpoint)
        from .ordinary_source_authority import _immutable
        _need(self._factory is _FACTORY and self.ledger._locked,
              "ISSUE_47_ACQUISITION_CREATOR_REQUIRED")
        captures = []
        for slot in sorted((self.ledger.root / "calls").iterdir()):
            intent = strict_json_file(path=slot / "intent.json")
            if intent["channel"] != SEC:
                continue
            _need((slot / "terminal.json").is_file(),
                  "ISSUE_47_UNKNOWN_SLOT_NOT_ADMISSIBLE:" + slot.name)
            captures.append({"intent": intent,
                             "receipt": strict_json_file(path=slot / "sec-receipt.json"),
                             "terminal": strict_json_file(path=slot / "terminal.json")})
        body = {"record_type": CHECKPOINT_TYPE, "schema_version": 1,
                "baseline_manifest_sha256": sha256_file(path=ROOT / MANIFEST_PATH),
                "ledger_sha256": sha256_file(
                    path=self.data_root / "evidence/requests_log.csv"),
                "execution_mode": self.ledger.mode,
                "source_credit": ("VERIFIED_SEC_ACQUISITION" if self.ledger.live
                                  else "RECORDED_TEST_ONLY"),
                "real_sec_credit": self.ledger.live, "captures": captures,
                "production_authorized": False}
        checkpoint = _sealed(body, "checkpoint_id")
        validate_acquisition_checkpoint(self.data_root, checkpoint,
                                        strict_json_file(path=ROOT / MANIFEST_PATH))
        _immutable(_journal() / (body["ledger_sha256"] + ".json"), checkpoint)
        attribution = _sealed(
            {"record_type": ATTRIBUTION_TYPE, "schema_version": 1,
             "requirement_id": REQUIREMENT_ID,
             "checkpoint_id": checkpoint["checkpoint_id"],
             "ledger_sha256": body["ledger_sha256"],
             "allowance_binding_id": self.ledger.binding["binding_id"],
             "execution_mode": self.ledger.mode,
             "what_the_shared_checkpoint_does_not_say": (
                 "which issue's allowance paid for these rows. The shared journal "
                 "record carries mode and captures, not an issue, so a checkpoint "
                 "found there is not Issue #47 credit by itself."),
             "production_authorized": False}, "attribution_id")
        _exclusive_write_json(
            path=self.ledger.root / "acquisition-attribution" / (body["ledger_sha256"] + ".json"),
            value=attribution)
        return checkpoint


WIRING_TYPE = "ISSUE_47_SEC_ACQUISITION_OFFLINE_WIRING"
# Fixed and required, not whatever the receipt happens to list. Measured
# against an earlier version: a receipt carrying ``evidence: {}`` passed,
# because the loop that re-hashes each named file simply ran zero times. A
# check that switches off when its inputs are deleted is not a check. The
# builder is in the set for the same reason the suite is: it decides which
# cases run, so a builder weakened to run fewer of them must invalidate the
# receipt it produced rather than silently keep conferring the grant.
REQUIRED_WIRING_EVIDENCE = (
    "scripts/vnext/historical_sec_session.py",
    "scripts/vnext/historical_source_acquisition.py",
    # The event declaration. It lives outside the Requirement closure because
    # the planner it extends is a rule file, and that is exactly why its bytes
    # belong here: a declaration the gate admits from must be pinned by the
    # same receipt as the gate.
    "scripts/vnext/historical_event_sources.py",
    # The governance declaration, here for the same reason: C02's second source
    # is a proxy or a Part III amendment, the planner declares neither, and a
    # declaration the gate admits from has to be pinned by the same receipt as
    # the gate.
    "scripts/vnext/historical_governance_sources.py",
    "tests/vnext/test_historical_sec_session.py",
    "tools/vnext_historical_sec.py",
    "tools/vnext_historical_wiring.py",
    "docs/evidence/issue47_history/acquisition-wiring/fault-injections.json",
)


def execute_recorded_chain(*, root, response):
    """Drive the acquisition chain offline once and report what happened.

    Gate, scope, claim, save, verified append, immutable proof, receipt,
    terminal, frozen checkpoint replay and installation, in a single pass over
    a recorded response. This is the business half of the wiring evidence and
    it is all of that evidence this module owns.

    Choosing, running and counting test cases used to live here too: two
    hand-maintained selector lists, a coverage check over them and a
    ``unittest`` subprocess, 200 lines that made this module unloadable
    wherever the test package is absent and made every ordinary new test an
    edit to business code. That work is now in
    ``tools/vnext_historical_wiring.py``, which reads the suite rather than
    listing it.
    """
    from .ordinary_source_authority import checkpoint_installation
    session = recorded_historical_session(root=Path(root), response=response)
    captured = session.capture(company_id=WIRING_COMPANY, url=WIRING_URL)
    _need(captured["status"] == "SUCCEEDED", "ISSUE_47_OFFLINE_WIRING_CAPTURE_FAILED")
    checkpoint, paths = checkpoint_installation(source_root=session.data_root)
    _need(checkpoint["checkpoint_id"] == captured["checkpoint_id"] and bool(paths),
          "ISSUE_47_OFFLINE_WIRING_INSTALLATION_FAILED")
    return {"capture_status": captured["status"],
            "execution_mode": session.ledger.mode,
            "checkpoint_id": checkpoint["checkpoint_id"],
            "installed_source_paths": len(paths),
            "calls": session.calls_this_session()}


def seal_wiring_receipt(*, chain, verification_run):
    """Seal a measured chain and a measured test run into one record.

    Neither half is decided here: ``chain`` is what the pass above returned
    and ``verification_run`` is what the builder observed a separate process
    do. An earlier version wrote ``frozen_validator_routing_verified: true``
    and ``fault_injections_caught: true`` having run neither, which is the
    reason both are now outcomes rather than fields. Fault injections are
    still not claimed in this record at all - an injection edits the source
    and re-runs, so no single process can perform one - they are recorded in
    the file this receipt hashes.
    """
    _need(chain["capture_status"] == "SUCCEEDED" and chain["calls"] == [0, 0, 0],
          "ISSUE_47_OFFLINE_WIRING_CHAIN_DID_NOT_SUCCEED")
    evidence = {relative: sha256_file(path=ROOT / relative)
                for relative in REQUIRED_WIRING_EVIDENCE}
    return _sealed({"record_type": WIRING_TYPE, "schema_version": 2,
                    "requirement_id": REQUIREMENT_ID, "calls": [0, 0, 0],
                    "chain_executed_over_recorded_responses": True,
                    "execution_mode": chain["execution_mode"],
                    "capture_status": chain["capture_status"],
                    "installed_source_paths": chain["installed_source_paths"],
                    "verification_run": verification_run,
                    "fault_injections_recorded_in": (
                        "docs/evidence/issue47_history/acquisition-wiring/"
                        "fault-injections.json, hashed by this receipt"),
                    "checkpoint_validated_by": (
                        "continuous_sec_acquisition.validate_acquisition_checkpoint, "
                        "frozen under issue_28_v14 and not editable from this issue"),
                    "what_that_validator_does_not_prove": (
                        "that the grant is valid, that the request is in scope, that "
                        "the cumulative count is intact, that an unknown outcome stops "
                        "the channel, or that a stale snapshot is refreshed - those are "
                        "this module's own checks"),
                    "downstream_reader_accepted": True,
                    "real_sec_credit": False, "production_authorized": False,
                    "evidence": evidence}, "receipt_id")


def verify_offline_wiring(*, receipt_path):
    """Refuse a live session unless the chain was exercised offline first.

    Same guarantee Issue #28's policy carries through
    ``sec_wiring_receipt_path``. Three things an earlier version did not do:
    the evidence set must be exactly ``REQUIRED_WIRING_EVIDENCE``, so dropping
    a file from the receipt drops the grant rather than the check; the
    acceptance claim must be a recorded test outcome rather than a boolean the
    builder wrote about itself; and the run must account for every case the
    suite declared, so a run that quietly covered a subset is refused.

    What it deliberately does not do is name the cases. Comparing against a
    literal list here is what made an ordinary new test an edit to this file,
    and it is unavailable anyway in a runtime that has no test package. The
    accounting is checked as a property of the record - run and excluded
    partition declared, with no overlap - and the builder that produced those
    three sets is itself one of the hashed files, so a builder weakened to
    declare less changes its own bytes and the grant falls.
    """
    _need(type(receipt_path) is str and receipt_path,
          "ISSUE_47_OFFLINE_WIRING_PATH_REQUIRED")
    receipt = strict_json_file(path=resolve_repository_file(
        repo_root=ROOT, repo_relative_path=receipt_path))
    _check_seal(receipt, "receipt_id")
    _need(receipt["record_type"] == WIRING_TYPE
          and receipt["requirement_id"] == REQUIREMENT_ID
          and receipt["calls"] == [0, 0, 0]
          and receipt["chain_executed_over_recorded_responses"] is True
          and receipt["real_sec_credit"] is False,
          "ISSUE_47_OFFLINE_WIRING_CHANGED")
    named = set(receipt["evidence"])
    _need(named == set(REQUIRED_WIRING_EVIDENCE),
          "ISSUE_47_OFFLINE_WIRING_EVIDENCE_SET_CHANGED:missing="
          + ",".join(sorted(set(REQUIRED_WIRING_EVIDENCE) - named)) + ";extra="
          + ",".join(sorted(named - set(REQUIRED_WIRING_EVIDENCE))))
    for relative, digest in receipt["evidence"].items():
        _need(sha256_file(path=resolve_repository_file(
            repo_root=ROOT, repo_relative_path=relative)) == digest,
            "ISSUE_47_OFFLINE_WIRING_EVIDENCE_CHANGED:" + relative)
    _verify_case_accounting(run=receipt["verification_run"])
    return receipt


def _verify_case_accounting(*, run):
    """The run must have covered everything the suite declared, and passed.

    Both halves matter and they fail differently. A run that passed but
    covered nine of twenty-six classes is the defect this repository already
    had once: the receipt attested a green run that excluded every regression
    the round had just added. A run that covered everything and failed is the
    ordinary case.
    """
    declared = run.get("classes_declared")
    executed = run.get("classes_run")
    excluded = run.get("classes_excluded")
    _need(all(type(value) is list and all(type(name) is str for name in value)
              for value in (declared, executed, excluded)),
          "ISSUE_47_OFFLINE_WIRING_CASE_ACCOUNTING_MALFORMED")
    _need(len(set(executed)) == len(executed)
          and len(set(excluded)) == len(excluded)
          and not set(executed) & set(excluded)
          and set(executed) | set(excluded) == set(declared)
          and bool(executed),
          "ISSUE_47_OFFLINE_WIRING_CASES_NOT_ACCOUNTED_FOR:unrun="
          + ",".join(sorted(set(declared) - set(executed) - set(excluded)))
          + ";unknown="
          + ",".join(sorted((set(executed) | set(excluded)) - set(declared)))
          + ";both=" + ",".join(sorted(set(executed) & set(excluded))))
    _need(run["passed"] is True and run["failures"] == 0 and run["errors"] == 0
          and run["tests_run"] >= len(executed) and run.get("return_code") == 0,
          "ISSUE_47_OFFLINE_WIRING_VERIFICATION_RUN_DID_NOT_PASS:" + str(run)[:200])


def _allowance_ledger(*, allowance, root, live):
    body = {"record_type": LEDGER_TYPE, "requirement_id": REQUIREMENT_ID,
            "root": str(root), "limits": list(
                allowance["maximum_additional_provider_paid_sec_calls"]),
            "purposes": list(allowance["scope"]["purposes"]),
            "execution_mode": "LIVE" if live else "RECORDED_TEST_ONLY"}
    return HistoricalCallLedger(factory=_FACTORY, root=root,
                                binding=_sealed(body, "binding_id"), live=live)


def live_historical_session():
    """Issue #47's granted session, or a refusal naming what is missing.

    ``acquisition_allowance`` never falls back to Issue #28's record, so while
    ``config/issue47_historical_calls_v1.json`` does not exist this raises and
    no transport is constructed. The rest of the chain is built and exercised
    regardless, because an execution path that first appears alongside its
    grant is a path nobody has run.
    """
    # The live path always supplies the reader, so a grant is verified against
    # the comment on GitHub rather than against a second local file.
    from .historical_source_acquisition import github_comment_reader
    allowance = acquisition_allowance(repo_root=ROOT,
                                      delegation_reader=github_comment_reader)
    _need(allowance["delegation_body_sha256"] and allowance["delegation_url"],
          "ISSUE_47_ALLOWANCE_DELEGATION_INCOMPLETE:" + POLICY_PATH)
    verify_offline_wiring(receipt_path=allowance["sec_wiring_receipt_path"])
    root = Path(allowance["budget_root"])
    return HistoricalSecSession(factory=_FACTORY, allowance=allowance,
                                ledger=_allowance_ledger(allowance=allowance, root=root,
                                                         live=True))


def recorded_historical_session(*, root, response, status=200, limits=(0, 0, 80),
                                purposes=("historical_five_year_source_acquisition",),
                                company_ids=("marriott_international",),
                                # Every class the declaration emits, so the
                                # recorded path can exercise all of them. The
                                # first version listed four and omitted
                                # SUBMISSIONS_HISTORY, so a recorded capture of
                                # a history shard was impossible and nothing
                                # said so; adding the event class found it.
                                dependency_classes=("ACCESSION_INSTANCE_DISCOVERY",
                                                    "ANNUAL_PERIOD_IDENTITY",
                                                    "COMPANYFACTS", "FISCAL_EVENT_FILING",
                                                    "GOVERNANCE_DISCLOSURE_FILING",
                                                    "SUBMISSIONS_HISTORY",
                                                    "SUBMISSIONS_INDEX"),
                                earliest_report_end="2000-01-01",
                                latest_report_end="2099-12-31",
                                allowance_root=None):
    """Offline tests only; no conversion of this session into production.

    The root must not be any configured budget root - neither Issue #28's nor
    Issue #47's - so a recorded run can never write into the place a granted
    count is kept.

    ``allowance_root`` points at a tree holding a real allowance record, so the
    whole legal path - reading the approved body, re-hashing it against the
    declared digest, and holding every request to the approved scope - runs
    over recorded transport. Without it the session carries a test allowance
    with the same shape. Testing only that a missing allowance is refused
    leaves the branch that matters unexercised.
    """
    root = Path(root).resolve()
    from .continuous_call_policy import POLICY_PATH as continuous_policy
    live_roots = {str(Path(strict_json_file(path=ROOT / continuous_policy)["budget_root"]))}
    if (ROOT / POLICY_PATH).is_file():
        live_roots.add(str(Path(strict_json_file(path=ROOT / POLICY_PATH)["budget_root"])))
    _need(str(root) not in live_roots, "ISSUE_47_TEST_CANNOT_USE_A_GRANTED_LEDGER")
    if allowance_root is not None:
        allowance = acquisition_allowance(repo_root=Path(allowance_root))
        allowance = {**allowance, "verified_from": str(allowance_root)}
    else:
        allowance = {"requirement_id": REQUIREMENT_ID, "budget_root": str(root),
                     "maximum_additional_provider_paid_sec_calls": list(limits),
                     "scope": {"purposes": list(purposes),
                               "company_ids": list(company_ids),
                               "dependency_classes": list(dependency_classes),
                               "earliest_report_end": earliest_report_end,
                               "latest_report_end": latest_report_end},
                     "delegation_url": None, "delegation_body_sha256": None,
                     "recorded_test_allowance": True}
    return HistoricalSecSession(
        factory=_FACTORY, allowance=allowance,
        ledger=_allowance_ledger(allowance={
            **allowance,
            "maximum_additional_provider_paid_sec_calls":
                allowance["maximum_additional_provider_paid_sec_calls"]},
            root=root, live=False),
        recorded_response=response, recorded_status=status)
