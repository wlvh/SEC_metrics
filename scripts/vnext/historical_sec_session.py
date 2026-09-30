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
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
import fcntl
import os

from sec_http import (SecHttpClient, parse_request_log_rows, request_log_attempt_id,
                      validate_official_sec_url, validate_request_log_manifest)
from git_workspace import first_symlink_in_path
from .batch_workflow import validate_request_attempt_binding
from .canonical import (canonical_json_bytes, content_hash, sha256_bytes, sha256_file,
                        strict_json_file, strict_json_loads)
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
# One declared dependency, taken from the planner's own output when the chain
# runs: the prior annual accession index that B02 reads for the company's
# earliest target (_wiring_url). Spelling its URL here named a CIK and an
# accession in production Python, which the scalability audit rejects.
WIRING_COMPANY = "marriott_international"
WIRING_ROLE = "prior_annual_primary_accession_index"


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
    rule_inputs = {fiscal_policy: (ROOT / fiscal_policy).read_bytes()}
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
        rule_inputs[relative] = raw
    _install_rule_inputs(root=root, rule_inputs=rule_inputs,
                         baseline_files=set(baseline["files"]))


RULE_INPUT_STAMP = "source-rule-inputs.json"
RULE_INPUT_TRANSITIONS = "source-rule-inputs-transitions.jsonl"


def _install_rule_inputs(*, root: Path, rule_inputs, baseline_files):
    """Put the minted generation's rule inputs in the root; say when they change.

    Within one generation the installed bytes are re-checked on every call,
    never trusted: ``_exclusive_write_bytes`` accepts a second write of the same
    bytes and refuses different ones. A re-mint is a new generation - merging
    the base moved a configuration file the parent generation records - and
    then the root takes the new generation's inputs, each already checked
    against the manifest, and records the transition beside them. The first
    ledger root met exactly that before its second round: the installer refused
    the merged configuration, before any request, because it allowed no
    difference at all, and the one it met was the kind a re-mint is for. A rule
    input that is also a baseline file stays with the baseline stamp, which
    refuses any change to the corpus.
    """
    digests = {relative: sha256_bytes(content=raw) for relative, raw in sorted(rule_inputs.items())}
    stamp = {"rule_inputs_sha256": content_hash(value=digests)}
    stamp_path = root / RULE_INPUT_STAMP
    installed = strict_json_file(path=stamp_path) if stamp_path.exists() else None
    if installed == stamp:
        for relative, raw in sorted(rule_inputs.items()):
            _exclusive_write_bytes(path=root / relative, content=raw)
        return
    changed = []
    for relative, raw in sorted(rule_inputs.items()):
        path = root / relative
        if path.is_file() and not path.is_symlink() and path.read_bytes() == raw:
            continue
        _need(relative not in baseline_files or not path.exists(),
              "ISSUE_47_BASELINE_RULE_INPUT_CHANGED:" + relative)
        _replace_rule_input(path=path, content=raw)
        changed.append(relative)
    transition = {"from": installed, "to": stamp, "changed": changed,
                  "requirement_manifest_sha256": sha256_file(path=ROOT / MANIFEST)}
    with (root / RULE_INPUT_TRANSITIONS).open("a", encoding="utf-8") as handle:
        handle.write(canonical_json_bytes(value=transition).decode("utf-8").rstrip("\n") + "\n")
    _replace_rule_input(path=stamp_path, content=canonical_json_bytes(value=stamp))


def _replace_rule_input(*, path: Path, content: bytes):
    """Write ``content`` at ``path`` whole or not at all, never through a link."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _need(not path.parent.is_symlink() and path.parent.is_dir() and not path.is_symlink(),
          "ISSUE_47_RULE_INPUT_PATH_UNSAFE:" + str(path))
    temporary = path.with_name("." + path.name + ".installing")
    temporary.write_bytes(content)
    os.replace(temporary, path)


RESOLVED = {"SUCCEEDED", "FAILED_TERMINAL"}
# A capture of these can change what the frame declares: an index or a shard
# decides which periods exist and which filings serve them. A batch pass ends
# after one, so the next pass plans against what was actually fetched.
FRAME_CHANGING_CLASSES = ("SUBMISSIONS_INDEX", "SUBMISSIONS_HISTORY")
# The SEC's fair-access refusals. Sending more requests into one is not
# something a batch should do on its own; the pass stops and says so.
SEC_ACCESS_REFUSED = ("403", "429")
INDEX_TIER, SHARD_TIER, OTHER_TIER = "SUBMISSIONS_INDEX", "SUBMISSIONS_HISTORY", "OTHER"
PASS_TIERS = (INDEX_TIER, SHARD_TIER, OTHER_TIER)


def _tier(row):
    return row["dependency_class"] if row["dependency_class"] in FRAME_CHANGING_CLASSES \
        else OTHER_TIER


def _listed(row):
    """What a pass reports about a row: enough to find it, nothing it decided."""
    return {"source_url": row["source_url"], "dependency_class": row["dependency_class"],
            "consumers": list(row.get("consumers", []))}


def _row_outcome(row):
    """The status and stop a request log row itself records.

    Read from the row the SEC client appended, not from the slot's own
    records, which are self-sealed: an independent review showed a stop
    hidden by rewriting a terminal and its receipt together. The row is the
    one the frozen replay also binds every receipt to.
    """
    if row["status_code"] == "200" and not row["error"]:
        return "SUCCEEDED", ""
    if row["status_code"] == "0":
        return "UNKNOWN_REMOTE_OUTCOME", "UNKNOWN_REMOTE_OUTCOME"
    return "FAILED_TERMINAL", "HTTP_402" if row["status_code"] == "402" else ""


def _terminal_block_reason(*, slot, intent, mode, rows=None):
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
    if rows is not None:
        index = receipt.get("ledger_row_index")
        if type(index) is not int or not 0 <= index < len(rows) \
                or rows[index] != receipt.get("ledger_row"):
            return "RECEIPT_ROW_IS_NOT_THE_LOGGED_ROW"
        if _row_outcome(rows[index]) != (status, terminal.get("stop_reason")):
            return "TERMINAL_DISAGREES_WITH_THE_LOGGED_ROW:" + "/".join(_row_outcome(rows[index]))
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
        # The session's request log, whose rows every receipt names. Set by
        # the session; while it is None the rows are not compared.
        self.request_log = None
        # Slots found resolved while this process holds the lock. Every slot
        # file is written exclusively and never rewritten, and only a lock
        # holder writes at all, so a slot resolved under the lock stays
        # resolved until the lock is released. Without this a pass re-read
        # every earlier slot at every claim - quadratic in the ledger, about
        # half a second per claim by the end of a full allowance. Cleared on
        # every acquire and release, so nothing is carried across two holds.
        self._resolved = {}
        # The resume charge the live path verified against the issue before
        # this session existed (0 for a ledger started here). A snapshot that
        # reads another refuses: a chain deleted or cut after that check would
        # otherwise lower the count mid-session. None until the session pins
        # it; recorded sessions have no published start to pin from.
        self._pinned_reserve = None
        # The owner's extension of the approval this ledger was bound to, once
        # the live path has verified it (historical_sec_extension): its added
        # limits and the claim-log state it continues from. None without one.
        self._extension = None

    @staticmethod
    def anchor_path(root):
        """Where the initialization anchor of a ledger at ``root`` lives: beside it."""
        root = Path(root)
        return root.parent / ("." + root.name + ".initialized.json")

    @staticmethod
    def mirror_path(root):
        """Where the claim log's copy outside the root lives: beside it, with the anchor.

        An independent review of the model ledger, which has this ledger's
        shape, deleted the slots and the claim log together, kept the binding
        and the anchor, and the ledger read as unused. Every claim is appended
        here first, and the log inside the root must be this copy, so emptying
        the root - or truncating its last claim - no longer empties the ledger.
        """
        root = Path(root)
        return root.parent / ("." + root.name + ".claims.jsonl")

    @contextmanager
    def locked(self):
        """Hold the root's lock, and refuse a ledger that was reset or moved under us.

        What an independent review found against the previous version: every
        count was rebuilt from whichever slot directories still existed, so
        deleting a stopped slot released the stop, and deleting the root
        released the cap. Issue #28's ledger refuses both and this one now does
        the same: the lock is on the directory, not on a file inside it; the
        root and its parents may not be symlinks; a binding written on first
        use must still be there and unchanged, with a copy of it beside the
        root that a deleted root does not take with it; and every claim is
        also appended to a log that the slots must match.
        """
        _need(self.root.is_absolute()
              and not any(path.is_symlink() for path in [self.root, *self.root.parents]),
              "ISSUE_47_LEDGER_PATH_ALIAS:" + str(self.root))
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = os.open(str(self.root), os.O_RDONLY)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self._resolved = {}
            self._locked = True
            self._check_binding()
            yield self
        finally:
            self._locked = False
            self._resolved = {}
            fcntl.flock(handle, fcntl.LOCK_UN)
            os.close(handle)

    def _check_binding(self):
        binding_path, anchor = self.root / "binding.json", self.anchor_path(self.root)
        mirror = self.mirror_path(self.root)
        if not binding_path.exists():
            # A new ledger. Only the installed source root may already be
            # here, because a session can install before it first claims; a
            # slot, a claim log, an anchor or a mirror without a binding is a
            # ledger that was reset, and is refused rather than restarted.
            present = sorted(path.name for path in self.root.iterdir())
            _need(not anchor.exists() and not mirror.exists() and set(present) <= {"source-inputs"},
                  "ISSUE_47_LEDGER_BINDING_MISSING_OR_RESET:" + ",".join(present))
            _exclusive_write_json(path=anchor, value=self.binding)
            os.close(os.open(str(mirror), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))
            _exclusive_write_json(path=binding_path, value=self.binding)
        _need(anchor.is_file(), "ISSUE_47_LEDGER_INITIALIZATION_ANCHOR_MISSING:" + str(anchor))
        _need(mirror.is_file() and not mirror.is_symlink(),
              "ISSUE_47_LEDGER_CLAIM_MIRROR_MISSING:" + str(mirror))
        _need(strict_json_file(path=anchor) == self.binding,
              "ISSUE_47_LEDGER_INITIALIZATION_ANCHOR_CHANGED")
        _need(strict_json_file(path=binding_path) == self.binding,
              "ISSUE_47_LEDGER_BINDING_CHANGED")

    def _claims(self):
        """The claim log inside the root, which must be its copy beside the root line for line.

        A ledger nothing has initialized - no binding, no log and no copy - has
        no claims; any one of them present means it was initialized, and then
        the copy must be there. (Initializing, and refusing a ledger whose
        binding went while its anchor stayed, is the lock's.)
        """
        path = self.root / "claims.jsonl"
        mirror = self.mirror_path(self.root)
        if not ((self.root / "binding.json").exists() or path.exists() or mirror.exists()):
            return []
        claims = []
        if path.exists():
            _need(path.is_file() and not path.is_symlink(), "ISSUE_47_LEDGER_CLAIM_LOG_UNSAFE")
            claims = [strict_json_loads(text=line)
                      for line in path.read_text(encoding="utf-8").splitlines()]
        _need(mirror.is_file() and not mirror.is_symlink(),
              "ISSUE_47_LEDGER_CLAIM_MIRROR_MISSING:" + str(mirror))
        copy = [strict_json_loads(text=line) for line in mirror.read_text(encoding="utf-8").splitlines()]
        _need(copy == claims, "ISSUE_47_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR:"
              + str(len(claims)) + " in the root, " + str(len(copy)) + " beside it")
        return claims

    def _log_rows(self):
        """The request log's rows, or None when this ledger has no log to compare."""
        if self.request_log is None:
            return None
        _need(Path(self.request_log).is_file(), "ISSUE_47_LEDGER_REQUEST_LOG_MISSING")
        return parse_request_log_rows(text=Path(self.request_log).read_text(encoding="utf-8"))

    def snapshot(self):
        """Counts consumed so far and any channel a lost terminal blocks.

        The slots must be exactly the claim log: as many, in sequence, each
        equal to its logged claim, each naming the one before it and this
        ledger's binding. A missing slot, a missing claim or a slot in the
        wrong place is a refusal, not a smaller count.
        """
        calls = self.root / "calls"
        counts = [0, 0, 0]
        blocked = []
        slots = sorted(calls.iterdir()) if calls.is_dir() else []
        claims = self._claims()
        _need(len(slots) == len(claims), "ISSUE_47_LEDGER_CLAIM_SET_CHANGED:"
              + str(len(slots)) + " slots, " + str(len(claims)) + " claims")
        _need([slot.name for slot in slots] == ["%04d" % (i + 1) for i in range(len(slots))],
              "ISSUE_47_LEDGER_SEQUENCE_CHANGED")
        rows = self._log_rows() if slots else None
        previous, digests = None, set()
        for slot, claim in zip(slots, claims):
            if self._locked and slot.name in self._resolved:
                index, previous, digest = self._resolved[slot.name]
                counts[index] += 1
                digests.add(digest)
                continue
            _need(slot.is_dir() and not slot.is_symlink(), "ISSUE_47_LEDGER_SLOT_UNSAFE:" + slot.name)
            intent = strict_json_file(path=slot / "intent.json")
            _check_seal(intent, "intent_id")
            _need(intent == claim, "ISSUE_47_LEDGER_CLAIM_CHANGED:" + slot.name)
            _need(intent["requirement_id"] == REQUIREMENT_ID,
                  "ISSUE_47_LEDGER_SLOT_IS_FOR_ANOTHER_REQUIREMENT:" + slot.name)
            _need(intent["execution_mode"] == self.mode,
                  "ISSUE_47_LEDGER_MODE_CHANGED:" + slot.name)
            _need(intent["ordinal"] == int(slot.name)
                  and intent["previous_intent_id"] == previous
                  and intent["allowance_binding_id"] == self.binding["binding_id"],
                  "ISSUE_47_LEDGER_INTENT_BINDING_CHANGED:" + slot.name)
            _need(intent["request_digest"] not in digests,
                  "ISSUE_47_LEDGER_DUPLICATE_REQUEST:" + slot.name)
            digests.add(intent["request_digest"])
            previous = intent["intent_id"]
            index = {"PROVIDER": 0, "PAID": 1, SEC: 2}[intent["channel"]]
            counts[index] += 1
            reason = _terminal_block_reason(slot=slot, intent=intent, mode=self.mode, rows=rows)
            if reason is not None:
                blocked.append({"slot": slot.name, "channel": intent["channel"],
                                "reason": reason})
            elif self._locked:
                self._resolved[slot.name] = (index, previous, intent["request_digest"])
        # Requests a lost host made after its last export are in no slot; a
        # resume charges them at their bound (historical_sec_resume), and the
        # count carries that charge like any claimed slot.
        reserve = _resume_reserve(self.root)
        _need(self._pinned_reserve is None or reserve == self._pinned_reserve,
              "ISSUE_47_LEDGER_RESUME_RESERVE_CHANGED:" + str(reserve) + " now, "
              + str(self._pinned_reserve) + " when the live path checked it")
        counts[2] += reserve
        return {"counts": counts, "limits": self._limits(),
                "blocked": blocked, "slot_count": len(slots), "resume_reserve": reserve,
                "previous_intent_id": previous, "request_digests": digests}

    def _limits(self):
        """The binding's limits, plus what a pinned extension adds."""
        limits = list(self.binding["limits"])
        if self._extension is not None:
            limits = [a + b for a, b in zip(limits, self._extension["limits"])]
        return limits

    def pin_extension(self, extension):
        """Raise the cap by what the owner's extension adds, for as long as this ledger lives.

        Only for the ledger the extension names: its claim log must begin with
        exactly the bytes the extension's ledger state describes, and those
        bytes must hold the claim count it states. An extension of another
        ledger - or of this one reset or rewound - is refused rather than
        added to whatever is here.
        """
        _need(self._extension is None, "ISSUE_47_LEDGER_EXTENSION_ALREADY_PINNED")
        state = extension["ledger_state"]
        log = self.root / "claims.jsonl"
        _need(log.is_file() and not log.is_symlink(),
              "ISSUE_47_LEDGER_EXTENSION_WITHOUT_A_CLAIM_LOG")
        held = log.read_bytes()
        size = state["claims"]["size"]
        _need(len(held) >= size and sha256_bytes(content=held[:size]) == state["claims"]["sha256"]
              and held[:size].count(b"\n") == state["claim_count"],
              "ISSUE_47_LEDGER_IS_NOT_THE_ONE_THE_EXTENSION_EXTENDS")
        # What the owner read as already spent is what this ledger had spent at
        # that state: its claims by channel, plus every resume charge recorded
        # at or before that claim log. A stated count lower than the real one
        # would let the owner approve more than they meant.
        spent = [0, 0, 0]
        for line in held[:size].decode("utf-8").splitlines():
            spent[{"PROVIDER": 0, "PAID": 1, SEC: 2}[strict_json_loads(text=line)["channel"]]] += 1
        spent[2] += resume_reserve_at_state(self.root, claims_size=size,
                                            resumes=state["resumes"])
        _need(spent == list(state["cumulative"]),
              "ISSUE_47_EXTENSION_STATES_ANOTHER_SPENDING:" + str(state["cumulative"])
              + " stated, " + str(spent) + " at that claim log")
        # The first pin at this root writes what it pinned beside the root; a
        # later pin, in any process, must be the same extension. An extension
        # dict that was never the verified one cannot follow a real one here.
        # Written whole under a temporary name and linked into place, so a
        # crash or a second process never sees a partial anchor.
        anchor = extension_anchor_path(self.root, extension["extension_ordinal"])
        pinned = canonical_json_bytes(value={
            field: extension[field] for field in (
                "extension_ordinal", "delegation_url", "delegation_body_sha256",
                "maximum_additional_provider_paid_sec_calls", "ledger_state")})
        _need(first_symlink_in_path(path=anchor) is None, "ISSUE_47_EXTENSION_ANCHOR_UNSAFE")
        if not anchor.exists() and not anchor.is_symlink():
            staged = anchor.parent / (anchor.name + "." + os.urandom(8).hex() + ".tmp")
            try:
                with staged.open("xb") as handle:
                    handle.write(pinned)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(staged, anchor)
                except FileExistsError:
                    pass
            finally:
                staged.unlink(missing_ok=True)
        _need(anchor.is_file() and not anchor.is_symlink() and anchor.read_bytes() == pinned,
              "ISSUE_47_ANOTHER_EXTENSION_WAS_PINNED_HERE:" + anchor.name)
        self._extension = {"limits": list(extension["maximum_additional_provider_paid_sec_calls"]),
                           "claim_count": state["claim_count"],
                           "extension_ordinal": extension["extension_ordinal"]}

    def pin_resume_reserve(self, reserve):
        """Hold the ledger to the resume charge the live path verified, for as long as it lives."""
        _need(type(reserve) is int and reserve >= 0 and self._pinned_reserve is None,
              "ISSUE_47_LEDGER_RESUME_RESERVE_PIN_INVALID")
        _need(_resume_reserve(self.root) == reserve,
              "ISSUE_47_LEDGER_RESUME_RESERVE_CHANGED:the chain beside the root no longer "
              "charges what the live path verified")
        self._pinned_reserve = reserve

    @property
    def mode(self):
        return "LIVE" if self.live else "RECORDED_TEST_ONLY"

    def claimed_urls(self):
        """Every URL a slot in this ledger has claimed, whatever its outcome.

        Read from the plans the slots wrote before their sockets, not from this
        process's memory, so an earlier invocation's claims count too. A slot
        without a plan is one whose claim was interrupted before it; such a slot
        has no terminal either, so ``require_unblocked`` refuses before this is
        asked - and if it is asked anyway, the answer is a refusal rather than
        a set that silently omits it.
        """
        return set(self.claimed_url_ordinals())

    def claimed_url_ordinals(self):
        """Every URL a slot has claimed, with the ordinals of the slots that claimed it."""
        calls = self.root / "calls"
        urls = {}
        for slot in (sorted(calls.iterdir()) if calls.is_dir() else []):
            plan = slot / "sec-plan.json"
            _need(plan.is_file(), "ISSUE_47_SLOT_HAS_NO_PLAN:" + slot.name)
            urls.setdefault(strict_json_file(path=plan)["request"]["url"], []).append(
                int(slot.name))
        return urls

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
                  zip(state["counts"], delta, state["limits"])),
              "ISSUE_47_CUMULATIVE_LIMIT_REACHED:" + channel + ":"
              + str(state["counts"]) + " of " + str(state["limits"]))
        # The same request twice is a redraw, and zero retries forbids it.
        _need(request_digest not in state["request_digests"],
              "ISSUE_47_UNCHANGED_REQUEST_REDRAW_FORBIDDEN")
        ordinal = state["slot_count"] + 1
        path = self.root / "calls" / ("%04d" % ordinal)
        intent = _sealed({"record_type": "ISSUE_47_HISTORICAL_CALL_INTENT",
                          "requirement_id": REQUIREMENT_ID, "channel": channel,
                          "ordinal": ordinal, "execution_mode": self.mode,
                          "allowance_binding_id": self.binding["binding_id"],
                          "previous_intent_id": state["previous_intent_id"],
                          "request_digest": request_digest, "plan_id": plan_id,
                          "purpose": purpose, "automatic_retry_count": 0,
                          "counts_before": state["counts"],
                          "production_authorized": False}, "intent_id")
        # The claim is logged before its slot exists, append-only and synced -
        # beside the root first, then inside it - so a removed slot, the last
        # one included, disagrees with the log, an emptied root disagrees with
        # the copy beside it, and a crash between any two writes refuses
        # before the next socket.
        line = canonical_json_bytes(value=intent).rstrip(b"\n") + b"\n"
        for log in (self.mirror_path(self.root), self.root / "claims.jsonl"):
            handle = os.open(str(log), os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
            try:
                written = 0
                while written < len(line):
                    count = os.write(handle, line[written:])
                    _need(count > 0, "ISSUE_47_LEDGER_CLAIM_WRITE_FAILED")
                    written += count
                os.fsync(handle)
            finally:
                os.close(handle)
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
        ledger.request_log = self.data_root / "evidence/requests_log.csv"
        self._sec_client = None
        self._transport_facts = None
        # The live path's published check, run again before every pass: a
        # resume published elsewhere while this session runs means this
        # ledger was declared lost, and it must stop spending. None for a
        # recorded session, which has no issue to read.
        self.published_check = None
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
        # A ledger pinned to an extension raises the cap; the session holding
        # the grants and the re-request rule must be the same extension's, or
        # requests would be counted against one approval and admitted by another.
        extension, pinned = self.allowance.get("extension"), self.ledger._extension
        _need((extension is None and pinned is None)
              or (extension is not None and pinned is not None
                  and pinned["extension_ordinal"] == extension["extension_ordinal"]
                  and pinned["limits"]
                  == list(extension["maximum_additional_provider_paid_sec_calls"])),
              "ISSUE_47_LEDGER_AND_SESSION_DISAGREE_ON_THE_EXTENSION")

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

    def _published_still(self):
        """None while the live path's check still holds with the charge this ledger was pinned to.

        A refusal is returned as a stop, not raised: ``acquire`` goes on to the
        next company after an error, and this is about the whole ledger.
        """
        if self.published_check is None:
            return None
        try:
            published = self.published_check()
        except (HistoricalSessionError, HistoricalAcquisitionError) as refusal:
            return "LIVE_PATH_REFUSED:" + str(refusal)
        if published["reserve_sec_calls"] != self.ledger._pinned_reserve:
            return "LIVE_PATH_REFUSED:ISSUE_47_LEDGER_RESUME_RESERVE_CHANGED"
        return None

    def capture(self, *, company_id, url, years=5):
        """Fetch one declared dependency and prove what the ledger then holds."""
        self._check()
        validate_official_sec_url(url=url)
        with self.ledger.locked():
            self.ledger.require_unblocked()
            refused = self._published_still()
            _need(refused is None, "ISSUE_47_" + str(refused))
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
            reclaim = self._reclaim(dependency, self.ledger.claimed_url_ordinals())
            _need(reclaim is not False, "ISSUE_47_URL_ALREADY_CLAIMED_IN_THIS_LEDGER:" + url)
            purpose = self.allowance["scope"]["purposes"][0]
            admitted = request_is_in_scope(allowance=self.allowance,
                                           company_id=company_id,
                                           dependency=dependency, purpose=purpose,
                                           frame_report_dates=frame["target_report_dates"])
            receipt, terminal = self._capture_one(company_id=company_id, url=url,
                                                  dependency=dependency,
                                                  admitted=admitted, reclaim=reclaim)
            checkpoint = self.register_checkpoint()
            return {"status": receipt["status"], "receipt": receipt, "terminal": terminal,
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "calls": [0, 0, int(self.ledger.live)],
                    "production_authorized": False}

    def capture_pending(self, *, company_id, years=5, max_captures=None, register=True):
        """One pass over one company's due dependencies inside the grants.

        ``capture`` recomputes the whole frame and replays the whole checkpoint
        for every request. Measured on an installed root: 22 to 30 seconds per
        request, growing by two to three seconds with each capture, so the
        1,354 requests the allowance covers would take days. Every check that
        matters per request stays - an official SEC URL, declared by a frame
        this session computed itself under its own lock, due by the planner,
        never claimed before in this ledger, inside a grant, a slot claimed
        before the socket and closed by a terminal - but the frame is computed
        once per pass and the checkpoint is registered once at its end.

        A pass takes the first tier that has anything to fetch: the
        submissions index, then the history shards, then everything else. The
        first two decide which periods and filings exist, so a pass that
        captures from either ends there and the next pass plans against what
        was fetched; shards do not list other shards, so all the shards one
        index declares go in one pass. Capturing an annual primary can also
        make new event and proxy rows declarable, which is why the caller
        repeats passes until one captures nothing.

        Zero automatic retries means a URL this ledger has claimed is never
        claimed again by a pass, whatever the planner says about it next: a
        failed fetch stays failed and is reported, and a refresh whose new
        bytes still conflict is reported rather than fetched in a loop.

        A pass stops early, by name, when the cumulative cap refuses a claim
        (before any socket), when a receipt carries a stop reason or an
        unknown outcome (which also blocks the ledger), when the SEC refuses
        access (403 or 429 - a fair-access refusal is not something to keep
        sending into), or at ``max_captures``. Dependencies outside every
        grant are listed and never claimed.

        The ledger is registered at the end of every pass that captured, and
        at the start of a pass that finds it unregistered. Both are needed.
        The planner reads saved sources through the frozen reader, which
        trusts an extended ledger only through a registered checkpoint, so a
        pass that left its rows unregistered made the next pass's frame raise
        ``ORDINARY_SOURCE_UNREGISTERED_LEDGER`` - measured, when registration
        was deferred to the end of a company to save the replay's cost. And a
        process that died between its last capture and its registration left
        the same state for the next invocation, which could then never plan
        again; registering first is what lets it continue.

        ``register=False`` is for callers that register themselves.
        """
        self._check()
        result = {"company_id": company_id, "captured": [], "outside_grants": [],
                  "already_claimed": [], "stop": None, "tier": None,
                  "frame_may_have_changed": False, "checkpoint_id": None}
        with self.ledger.locked():
            self.ledger.require_unblocked()
            refused = self._published_still()
            if refused is not None:
                result["stop"] = refused
                result["calls"] = self.calls_this_session()
                return result
            install_historical_source_inputs(root=self.data_root)
            if register:
                result["registered_before_planning"] = self._register_if_unregistered()
            frame = declared_frame(repo_root=self.data_root, company_id=company_id,
                                   years=years)
            urls = [row["source_url"] for row in frame["requirements"]]
            duplicated = sorted({url for url in urls if urls.count(url) > 1})
            _need(not duplicated,
                  "HISTORICAL_URL_IS_DECLARED_MORE_THAN_ONCE:" + ",".join(duplicated))
            claimed = self.ledger.claimed_url_ordinals()
            due, reclaims = [], {}
            for row in frame["requirements"]:
                if not row["new_acquisition_required"]:
                    continue
                reclaim = self._reclaim(row, claimed)
                if reclaim is False:
                    result["already_claimed"].append(_listed(row))
                    continue
                reclaims[row["source_url"]] = reclaim
                due.append(row)
            purpose = self.allowance["scope"]["purposes"][0]
            for tier in PASS_TIERS:
                rows = sorted((row for row in due if _tier(row) == tier),
                              key=lambda row: row["source_url"])
                admitted_rows = []
                for dependency in rows:
                    try:
                        admitted = request_is_in_scope(
                            allowance=self.allowance, company_id=company_id,
                            dependency=dependency, purpose=purpose,
                            frame_report_dates=frame["target_report_dates"])
                    except HistoricalSessionError:
                        raise
                    except HistoricalAcquisitionError as refusal:
                        result["outside_grants"].append(
                            {**_listed(dependency), "reason": str(refusal)})
                        continue
                    admitted_rows.append((dependency, admitted))
                if not admitted_rows:
                    continue
                result["tier"] = tier
                for dependency, admitted in admitted_rows:
                    if max_captures is not None and len(result["captured"]) >= max_captures:
                        result["stop"] = "MAX_CAPTURES_FOR_THIS_INVOCATION"
                        break
                    try:
                        receipt, _ = self._capture_one(
                            company_id=company_id, url=dependency["source_url"],
                            dependency=dependency, admitted=admitted,
                            reclaim=reclaims[dependency["source_url"]])
                    except HistoricalSessionError as refusal:
                        if not str(refusal).startswith("ISSUE_47_CUMULATIVE_LIMIT_REACHED"):
                            raise
                        result["stop"] = str(refusal)
                        break
                    status_code = receipt["ledger_row"]["status_code"]
                    result["captured"].append({**_listed(dependency),
                                               "status": receipt["status"],
                                               "status_code": status_code,
                                               "grants": admitted["grants"]})
                    if receipt["status"] not in RESOLVED or receipt["stop_reason"]:
                        result["stop"] = receipt["stop_reason"] or receipt["status"]
                        break
                    if status_code in SEC_ACCESS_REFUSED:
                        result["stop"] = "SEC_ACCESS_REFUSED:" + status_code
                        break
                result["frame_may_have_changed"] = tier != OTHER_TIER
                break
            if result["captured"] and register:
                result["checkpoint_id"] = self.register_checkpoint()["checkpoint_id"]
        result["calls"] = self.calls_this_session()
        return result

    def _register_if_unregistered(self):
        """Register the ledger as it stands if nothing has; the lock is the caller's.

        Returns the checkpoint ID when it registered, else None - including
        for a ledger with no slots, whose rows are the trusted baseline and
        need no checkpoint.
        """
        from .continuous_sec_acquisition import _journal
        _need(self.ledger._locked, "ISSUE_47_LEDGER_LOCK_REQUIRED")
        if not (self.ledger.root / "calls").is_dir():
            return None
        ledger = sha256_file(path=self.data_root / "evidence/requests_log.csv")
        if (_journal() / (ledger + ".json")).is_file():
            return None
        return self.register_checkpoint()["checkpoint_id"]

    def acquire(self, *, company_ids, years=5, max_captures=None):
        """Passes over each company until one captures nothing, or a stop.

        A company's declaration grows as its sources arrive: the shards make
        periods discoverable, an annual primary makes its event window and its
        proxy declarable. So a company is done only when a pass over the frame
        its own captures produced has nothing left to take; that terminates
        because a pass that captures consumes at least one slot and no URL is
        claimed twice. A stop is global - the cap, an unknown outcome and a
        fair-access refusal are about the ledger and the SEC, not about one
        company - so it ends the whole acquisition, and the summary says where.

        A company whose frame cannot be computed is reported with the error
        and the next company goes ahead, but only while the ledger has no
        unresolved slot: a planner failure happens before any claim, and is a
        development gap for that company rather than a reason to stop the
        others. If the ledger is blocked, the acquisition stops, because
        nothing may be claimed past an unresolved slot.
        """
        summary = {"record_type": "ISSUE_47_HISTORICAL_ACQUISITION_SUMMARY",
                   "requirement_id": REQUIREMENT_ID, "execution_mode": self.ledger.mode,
                   "companies": {}, "stop": None, "checkpoints": [],
                   "production_authorized": False}
        remaining = max_captures
        for company_id in company_ids:
            passes, error = [], None
            while True:
                try:
                    result = self.capture_pending(company_id=company_id, years=years,
                                                  max_captures=remaining)
                except Exception as failure:  # noqa: BLE001 - reported, and the ledger decides
                    error = {"error_type": type(failure).__name__, "error": str(failure)[:2000]}
                    break
                passes.append(result)
                for key in ("registered_before_planning", "checkpoint_id"):
                    if result.get(key):
                        summary["checkpoints"].append({"company_id": company_id,
                                                       "when": key,
                                                       "checkpoint_id": result[key]})
                if remaining is not None:
                    remaining -= len(result["captured"])
                if result["stop"] is not None:
                    summary["stop"] = {"company_id": company_id, "reason": result["stop"]}
                    break
                if not result["captured"]:
                    break
            captured = [item for result in passes for item in result["captured"]]
            summary["companies"][company_id] = {
                "passes": len(passes), "captured": captured, "error": error,
                "outside_grants": passes[-1]["outside_grants"] if passes else [],
                "already_claimed": passes[-1]["already_claimed"] if passes else []}
            if error is not None and self.ledger.snapshot()["blocked"]:
                summary["stop"] = {"company_id": company_id,
                                   "reason": "LEDGER_BLOCKED_AFTER_ERROR"}
            if summary["stop"] is not None:
                break
        summary["calls_this_session"] = self.calls_this_session()
        summary["cumulative"] = self.ledger.snapshot()
        return summary

    def _reclaim(self, dependency, claimed):
        """None for a URL this ledger never claimed, an extension ordinal for one it may claim
        again, and False for one it may not.

        ``claimed`` maps each claimed URL to the ordinals of the slots that
        claimed it. Zero automatic retries means a claimed URL is never claimed
        again - unless the owner's extension says a refresh or a replacement of
        exactly this kind of row may be requested once more
        (``historical_sec_extension.reclaim_ordinal``).
        """
        ordinals = claimed.get(dependency["source_url"])
        if not ordinals:
            return None
        from .historical_sec_extension import reclaim_ordinal
        ordinal = reclaim_ordinal(allowance=self.allowance, dependency=dependency,
                                  claimed_ordinals=ordinals)
        return False if ordinal is None else ordinal

    def _capture_one(self, *, company_id, url, dependency, admitted, reclaim=None):
        """Claim, fetch, prove and close one request. The lock is the caller's.

        Everything from the claim to the terminal happens here and nowhere
        else, so ``capture`` and ``capture_pending`` cannot drift apart on the
        part that spends the allowance. The scope admission is the caller's
        because the caller holds the frame it was computed against; it is
        still bound into the plan the slot claims, so a slot never exists
        without the grant that let it be claimed.

        ``reclaim`` is the extension ordinal under which an already-claimed URL
        is requested again. It goes into the request, so the request's digest
        differs from the first one's and the ledger's rule against drawing the
        same request twice still holds within the extension.
        """
        _need(self.ledger._locked, "ISSUE_47_LEDGER_LOCK_REQUIRED")
        # A re-request is only the extension's to make: a marker naming an
        # extension this session does not hold is refused before anything else.
        _need(reclaim is None
              or (type(reclaim) is int and reclaim > 0
                  and (self.allowance.get("extension") or {}).get("extension_ordinal")
                  == reclaim), "ISSUE_47_RECLAIM_WITHOUT_ITS_EXTENSION")
        # And the marker must be the one this ledger's slots give, read now
        # under the lock: a caller's marker for a URL already requested under
        # the extension, or never requested, is refused.
        _need(self._reclaim(dependency, self.ledger.claimed_url_ordinals()) == reclaim,
              "ISSUE_47_RECLAIM_IS_NOT_WHAT_THE_LEDGER_ALLOWS:" + url)
        validate_official_sec_url(url=url)
        _need(admitted.get("company_id") == company_id
              and admitted.get("dependency_class") == dependency["dependency_class"]
              and admitted.get("grants"), "ISSUE_47_ADMISSION_IS_FOR_ANOTHER_REQUEST")
        log = self.data_root / "evidence/requests_log.csv"
        validate_request_log_manifest(log_path=log)
        before = log.read_bytes()
        old_rows = parse_request_log_rows(text=before.decode("utf-8"))
        # One client per session, so its pacing applies across requests. A new
        # client per request starts from a zero timestamp and never waits,
        # which turns the configured rate into no rate at all once requests
        # follow each other without a frame computation between them.
        if self._sec_client is None:
            self._sec_client = SecHttpClient(workdir=self.data_root,
                                             config_path=ROOT / "config/sec_config.json",
                                             log_path=log)
            self._sec_client.config = {**self._sec_client.config, "max_retries": 0}
        client = self._sec_client
        _need(client.config["max_retries"] == 0, "ISSUE_47_AUTOMATIC_RETRY_ENABLED")
        request = {"url": url, "method": "GET", "automatic_retry_count": 0,
                   "sec_configuration_sha256": sha256_file(
                       path=ROOT / "config/sec_config.json")}
        if reclaim is not None:
            request["reclaimed_under_extension"] = reclaim
        plan = {"company_id": company_id, "requirement_id": REQUIREMENT_ID,
                "source_dependency": dependency, "request": request,
                "source_ledger_before_sha256": sha256_bytes(content=before),
                "source_row_count_before": len(old_rows),
                # Both halves, and in both modes. A URL being a real dependency
                # is not the same as this grant allowing it to be fetched; and a
                # scope check only the live path runs is a check nothing ever
                # exercises, so the recorded session carries a scope too.
                "scope_admission": admitted}
        path, intent = self.ledger.claim(
            channel=SEC, request_digest=content_hash(value=request),
            plan_id=content_hash(value=plan), purpose=admitted["purpose"])
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
        return receipt, terminal

    def _transport(self):
        """Which way this session's HTTPS went: the proxy and the CA bundle, as facts.

        The owner accepted a run from the executor's container,
        whose egress proxy re-terminates TLS, so the client there verifies the
        proxy's certificate rather than SEC's. A receipt that did not say which
        path its bytes took would read as a direct fetch. Recorded, not judged:
        what a proxy does to TLS is stated in the approval the owner posted.
        """
        if not self.ledger.live:
            return {"network": "NONE_RECORDED_RESPONSE"}
        if self._transport_facts is None:
            from urllib.request import getproxies
            proxy = getproxies().get("https")
            if proxy:
                # Never a credential: only where the proxy is, not who logs in to it.
                parts = urlsplit(proxy)
                proxy = (parts.scheme + "://" + (parts.hostname or "")
                         + (":" + str(parts.port) if parts.port else ""))
            bundle = os.environ.get("SSL_CERT_FILE")
            self._transport_facts = {
                "https_proxy": proxy or None,
                "ca_bundle": ({"path": bundle, "sha256": sha256_file(path=Path(bundle))}
                              if bundle and Path(bundle).is_file() else None)}
        return self._transport_facts

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
                "wire": wire, "transport": self._transport(), "company_id": company_id,
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
    # The planner. It is a rule file, bound by the Requirement closure, but the
    # live path checks this receipt and not the closure, and the planner now
    # holds the block that answers checkpoint replays from a memo while a frame
    # is computed: a weakened memo would weaken every saved-source check the
    # frame makes, and nothing on the live path would notice. An independent
    # review found that gap; a declaration the gate admits from is pinned by
    # the same receipt as the gate, and so is what verifies what it declares.
    "scripts/vnext/normal_history_plan.py",
    # The catalog the planner reads. Whether a saved history block is the block
    # its index declares decides whether the planner asks for it again
    # (SNAPSHOT_REFRESH) and whether a period's filings can be listed at all,
    # so a weakened block check would change what the gate admits as due just
    # as a weakened planner would. It is a rule file too, and for the same
    # reason as the planner that is not enough on the live path.
    "scripts/vnext/normal_history_catalog.py",
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
    # The start that outlives the host, shared with the model ledger: a start
    # the gate refuses without is part of the path a grant is spent on.
    "scripts/vnext/historical_ledger_start.py",
    # What carries an acquisition from the host that ran it to a checkout, and
    # what rebuilds and registers it there. Both ends are part of the path a
    # grant is spent on, so the receipt pins them with the rest.
    "scripts/vnext/historical_source_export.py",
    # The resume after a lost host: it rebuilds the ledger a grant is spent on
    # and charges what the lost host may have spent, so it is on that path too.
    "scripts/vnext/historical_sec_resume.py",
    # The owner's extension of the approval: it raises the cap a grant is spent
    # against and decides which already-requested URLs may be requested again,
    # so it is on the path as much as the first approval's gate is.
    "scripts/vnext/historical_sec_extension.py",
    "tests/vnext/test_historical_sec_session.py",
    "tools/vnext_historical_sec.py",
    "tools/vnext_historical_wiring.py",
    "docs/evidence/issue47_history/acquisition-wiring/fault-injections.json",
)


def _wiring_url(*, repo_root):
    """The one dependency the recorded chain captures, read from the declaration.

    The prior annual accession index the planner declares for the wiring
    company's earliest target: exactly one row, still to be acquired.
    """
    from .historical_source_acquisition import declared_frame
    frame = declared_frame(repo_root=Path(repo_root), company_id=WIRING_COMPANY, years=5)
    earliest = frame["target_report_dates"][0]
    rows = [row for row in frame["requirements"] if WIRING_ROLE in row["source_roles"]
            and any(consumer.startswith("period:" + earliest + ":")
                    for consumer in row["consumers"])]
    _need(len(rows) == 1 and rows[0]["new_acquisition_required"],
          "ISSUE_47_OFFLINE_WIRING_DEPENDENCY_NOT_DECLARED_ONCE:" + str(len(rows)))
    return rows[0]["source_url"]


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
    # The declaration over the checkout's saved materials, which the session's
    # baseline copies; its own source root holds nothing before the first capture.
    captured = session.capture(company_id=WIRING_COMPANY, url=_wiring_url(repo_root=ROOT))
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


# ------------------------------------------------ a start that outlives the host
# The owner decided that Issue #47's acquisition runs in the executor's cloud
# container. Everything above keeps the count honest while the ledger exists,
# but a container is reclaimed with its disk, and a ledger that vanishes with it
# would let the same allowance be spent again from an empty one. The start that
# outlives the host - a record beside the root, a marker on issue 47, and a
# refusal once the branch carries this approval's export - is shared with the
# model ledger in historical_ledger_start; these are the SEC ledger's names for
# it, with its own record type, refusal prefix and export index.
def _sec_ledger_paths(root):
    return (HistoricalCallLedger.anchor_path(root), HistoricalCallLedger.mirror_path(root))


def _sec_export_claims(index):
    """The claim log an SEC export carries, as bound by its state archive."""
    return index["state_archive"]["members"]["ledger/claims.jsonl"]


def _sec_start():
    from .historical_ledger_start import LedgerKind
    from .historical_source_acquisition import (ISSUE_NUMBER, TRUSTED_APPROVER_ID,
                                                TRUSTED_REPOSITORY)
    from .historical_source_export import EXPORT_DIRECTORY, INDEX_NAME
    # One SEC approval, one export directory: the export refuses to replace
    # another approval's index (historical_source_export).
    return LedgerKind(record_type=START_TYPE, prefix="ISSUE_47_SEC_LEDGER",
                      title="Issue #47 SEC ledger", error=HistoricalSessionError,
                      ledger_paths=_sec_ledger_paths,
                      export_index=lambda allowance: EXPORT_DIRECTORY + "/" + INDEX_NAME,
                      export_claims=_sec_export_claims,
                      repository=TRUSTED_REPOSITORY, issue_number=ISSUE_NUMBER,
                      requirement_id=REQUIREMENT_ID, owner_id=TRUSTED_APPROVER_ID)


START_TYPE = "ISSUE_47_SEC_LEDGER_START"
RESUME_TYPE = "ISSUE_47_SEC_LEDGER_RESUME"


def resume_chain_path(root):
    """Where a resumed ledger's resume chain lives: beside the root, with the start record."""
    root = Path(root)
    return root.parent / ("." + root.name + ".resumes.jsonl")


def resume_view(record):
    """What a resume marker publishes: the record without its random number, and a digest of it."""
    view = {key: value for key, value in record.items() if key != "instance_nonce"}
    view["resume_record_sha256"] = sha256_bytes(content=canonical_json_bytes(value=record))
    return view


def extension_anchor_path(root, ordinal):
    """Where the first pin of an extension at ``root`` records it: beside the root, with the anchor."""
    root = Path(root)
    return root.parent / ("." + root.name + ".extension-" + str(int(ordinal)) + ".json")


def resume_reserve_at_state(root, *, claims_size, resumes):
    """The resume charge a ledger state carries, read from the chain beside ``root``.

    ``resumes`` is the chain as the state's export carried it (its public
    views' bytes: digest and size). The chain here must begin with exactly
    those bytes, their reserves are the charge at that state, and every resume
    after them must have restored a claim log at least as long as the state's -
    a resume made after the state cannot have restored an earlier one, and one
    restoring an earlier log that the stated chain leaves out would be a charge
    the state understates. Binding the prefix rather than the restored length
    lets a resume made after the state, restoring the stated export itself,
    stay outside the stated spending.
    """
    from .historical_sec_resume import local_chain
    path = resume_chain_path(root)
    records = (local_chain(root) if path.exists() or path.is_symlink() else [])
    lines = [canonical_json_bytes(value=resume_view(record) if "instance_nonce" in record
                                  else record).rstrip(b"\n") + b"\n" for record in records]
    offset, reserve, stated = 0, 0, resumes["size"]
    for record, line in zip(records, lines):
        restored = ((record.get("restored_export") or {}).get("claims") or {}).get("size")
        _need(type(restored) is int, "ISSUE_47_LEDGER_RESUME_CHAIN_INVALID")
        if offset < stated:
            _need(offset + len(line) <= stated and restored <= claims_size,
                  "ISSUE_47_LEDGER_RESUMES_ARE_NOT_THE_ONES_THE_EXTENSION_EXTENDS")
            reserve += record["lost_segment"]["reserve_sec_calls"]
        else:
            _need(restored >= claims_size,
                  "ISSUE_47_EXTENSION_STATE_LEAVES_OUT_AN_EARLIER_RESUME")
        offset += len(line)
    chain = b"".join(lines)
    _need(len(chain) >= stated and sha256_bytes(content=chain[:stated]) == resumes["sha256"],
          "ISSUE_47_LEDGER_RESUMES_ARE_NOT_THE_ONES_THE_EXTENSION_EXTENDS")
    return reserve


def _resume_reserve(root):
    """The SEC calls every resume of the ledger at ``root`` charged for a lost segment, summed.

    Read from the chain beside the root. Whether the chain is the one on the
    issue is the live path's check (``require_published_resume``), made before
    any session exists; here each record must at least be a resume of this
    root with a whole, non-negative reserve.
    """
    path = resume_chain_path(root)
    if not path.exists() and not path.is_symlink():
        return 0
    _need(path.is_file() and not path.is_symlink(), "ISSUE_47_LEDGER_RESUME_CHAIN_UNSAFE")
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        record = strict_json_loads(text=line)
        segment = record.get("lost_segment") if type(record) is dict else None
        reserve = segment.get("reserve_sec_calls") if type(segment) is dict else None
        _need(type(record) is dict and record.get("record_type") == RESUME_TYPE
              and record.get("budget_root") == str(Path(root))
              and type(reserve) is int and reserve >= 0,
              "ISSUE_47_LEDGER_RESUME_CHAIN_INVALID")
        total += reserve
    return total


def start_record_path(root):
    """Where the local half of a ledger's start lives: beside the root, with the anchor."""
    from .historical_ledger_start import start_record_path as path
    return path(root)


def _marker_record(body):
    """The SEC start record in a comment's first fenced json block, or None."""
    from .historical_ledger_start import marker_record
    return marker_record(_sec_start(), body)


def start_markers(*, allowance, reader):
    """This approval's SEC start markers on issue 47, oldest first."""
    from .historical_ledger_start import start_markers as markers
    return markers(_sec_start(), allowance=allowance, reader=reader)


def marker_comment_body(record):
    """The comment the executor posts on issue 47; its first json block is the record."""
    from .historical_ledger_start import marker_comment_body as body
    return body(_sec_start(), record)


def _exported_here(*, allowance, checkout):
    from .historical_ledger_start import exported_here
    return exported_here(_sec_start(), allowance=allowance, checkout=checkout)


def start_ledger(*, allowance, reader, now=None, checkout=None):
    """Start this approval's SEC ledger here, once; see historical_ledger_start.start_ledger."""
    from .historical_ledger_start import start_ledger as start
    return start(_sec_start(), allowance=allowance, reader=reader, now=now,
                 checkout=ROOT if checkout is None else checkout)


def require_published_start(*, allowance, reader, branch_export_index, checkout=None):
    """The SEC ledger was started - or resumed - here, is on GitHub and is not behind its export.

    A resume chain beside the root means the host that started the ledger was
    lost and this one rebuilt it from the branch's export; that is checked
    against the resume markers instead (``historical_sec_resume``).

    ``branch_export_index`` is the export index at the branch's remote tip as
    the caller fetched it, or None where the tip carries none; the checkout's
    must be the same. A snapshot restore can take the ledger, what is beside
    it and the checkout back together, and every check against the checkout
    alone would then pass while the requests since the snapshot are forgotten.
    """
    checkout = ROOT if checkout is None else checkout
    from .historical_source_export import EXPORT_DIRECTORY, INDEX_NAME
    local = Path(checkout) / EXPORT_DIRECTORY / INDEX_NAME
    _need(branch_export_index is None or type(branch_export_index) is bytes,
          "ISSUE_47_SEC_LEDGER_BRANCH_EXPORT_UNREADABLE")
    _need((local.read_bytes() if local.is_file() and not local.is_symlink() else None)
          == branch_export_index,
          "ISSUE_47_SEC_LEDGER_CHECKOUT_IS_NOT_THE_BRANCH_S_EXPORT:bring the checkout to the "
          "branch's tip; a checkout behind it would let a rolled-back ledger pass")
    chain = resume_chain_path(Path(allowance["budget_root"]))
    from .historical_sec_resume import require_published_resume, resume_markers
    if chain.exists() or chain.is_symlink():
        return require_published_resume(allowance=allowance, reader=reader, checkout=checkout)
    # A resume published for this approval means the ledger this host started
    # was declared lost and rebuilt elsewhere; a host that was only
    # unreachable, and still holds its start, would otherwise spend the same
    # allowance twice.
    resumed = resume_markers(allowance=allowance, reader=reader)
    _need(not resumed, "ISSUE_47_SEC_LEDGER_RESUMED_ELSEWHERE:"
          + str(resumed[0]["comment"].get("html_url") if resumed else "")
          + ": this approval's ledger was resumed from its export; the ledger started here "
            "may not spend again")
    from .historical_ledger_start import require_published_start as require
    return {**require(_sec_start(), allowance=allowance, reader=reader, checkout=checkout),
            "reserve_sec_calls": 0}


def _allowance_ledger(*, allowance, root, live):
    # The location is not in the binding: the live session separately requires
    # the ledger to be the granted root, and a binding that named its own path
    # would make an intact ledger unreadable wherever it was copied for review.
    body = {"record_type": LEDGER_TYPE, "requirement_id": REQUIREMENT_ID,
            "limits": list(allowance["maximum_additional_provider_paid_sec_calls"]),
            "purposes": list(allowance["scope"]["purposes"]),
            "execution_mode": "LIVE" if live else "RECORDED_TEST_ONLY"}
    return HistoricalCallLedger(factory=_FACTORY, root=root,
                                binding=_sealed(body, "binding_id"), live=live)


def live_historical_session(*, branch_tip):
    """Issue #47's granted session, or a refusal naming what is missing.

    ``acquisition_allowance`` never falls back to Issue #28's record, so while
    ``config/issue47_historical_calls_v1.json`` does not exist this raises and
    no transport is constructed. The rest of the chain is built and exercised
    regardless, because an execution path that first appears alongside its
    grant is a path nobody has run.

    ``branch_tip`` is called once the allowance and the wiring are verified,
    and returns the branch's remote tip as the caller fetched it
    (``{"export_index": bytes or None, ...}``): a missing grant refuses before
    anything is fetched.
    """
    # The live path always supplies the reader, so a grant is verified against
    # the comment on GitHub rather than against a second local file.
    from .historical_source_acquisition import live_github_reader
    reader = live_github_reader()
    allowance = acquisition_allowance(repo_root=ROOT, delegation_reader=reader)
    _need(allowance["delegation_body_sha256"] and allowance["delegation_url"],
          "ISSUE_47_ALLOWANCE_DELEGATION_INCOMPLETE:" + POLICY_PATH)
    verify_offline_wiring(receipt_path=allowance["sec_wiring_receipt_path"])
    tip = branch_tip()
    branch_export_index = tip["export_index"]

    # Before the session exists, so before any transport: a ledger with no
    # published start could be a second start of an allowance already begun.
    def published():
        return require_published_start(allowance=allowance, reader=reader,
                                       branch_export_index=branch_export_index)

    # The owner's extension of this approval, verified against GitHub the same
    # way, or None: the start, the resume chain and the export are the first
    # approval's, and the extension only raises the cap and names the grants
    # every request from here on is held to.
    from .historical_sec_extension import (acquisition_extension, extended_allowance,
                                           require_extension_on_branch)
    require_extension_on_branch(repo_root=ROOT, branch_files=tip.get("extension_files"))
    extension = acquisition_extension(repo_root=ROOT, allowance=allowance,
                                      delegation_reader=reader)
    effective = extended_allowance(allowance=allowance, extension=extension)
    ledger = live_ledger(allowance=effective, published=published())
    session = HistoricalSecSession(factory=_FACTORY, allowance=effective, ledger=ledger)
    session.published_check = published
    return session


def live_ledger(*, allowance, published):
    """The LIVE ledger at the granted root, held to the resume charge the published check verified.

    With an extension in ``allowance`` (``extended_allowance``), the ledger is
    also pinned to it - only if it is the ledger the extension continues.
    """
    ledger = _allowance_ledger(allowance=allowance, root=Path(allowance["budget_root"]), live=True)
    ledger.pin_resume_reserve(published["reserve_sec_calls"])
    if allowance.get("extension") is not None:
        _need(allowance["extension"].get("provenance_verified_against_github") is True,
              "ISSUE_47_LIVE_EXTENSION_NOT_READ_BACK_FROM_GITHUB")
        ledger.pin_extension(allowance["extension"])
    return ledger


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
                                earliest_report_end=date.min.isoformat(),
                                latest_report_end=date.max.isoformat(),
                                allowance_root=None, extension=None):
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
                               "latest_report_end": latest_report_end,
                               # One grant the size of the envelope: the
                               # recorded path is held to the same grant check
                               # as the live one, so it has to carry one.
                               "grants": [{"grant": "RECORDED_TEST",
                                           "company_ids": list(company_ids),
                                           "dependency_classes": list(dependency_classes),
                                           "earliest_report_end": earliest_report_end,
                                           "latest_report_end": latest_report_end}]},
                     "delegation_url": None, "delegation_body_sha256": None,
                     "recorded_test_allowance": True}
    # An extension comes from the tree the allowance came from - verified by
    # the same gate the live path uses, without the GitHub fetch - or, for a
    # case about the ledger or the passes rather than the approval, as a test
    # object in the verified extension's shape.
    from .historical_sec_extension import acquisition_extension, extended_allowance
    if allowance_root is not None:
        _need(extension is None, "ISSUE_47_TEST_EXTENSION_GIVEN_TWICE")
        extension = acquisition_extension(repo_root=Path(allowance_root), allowance=allowance)
    allowance = extended_allowance(allowance=allowance, extension=extension)
    ledger = _allowance_ledger(allowance={
        **allowance,
        "maximum_additional_provider_paid_sec_calls":
            allowance["maximum_additional_provider_paid_sec_calls"]},
        root=root, live=False)
    if allowance.get("extension") is not None:
        ledger.pin_extension(allowance["extension"])
    return HistoricalSecSession(
        factory=_FACTORY, allowance=allowance, ledger=ledger,
        recorded_response=response, recorded_status=status)
