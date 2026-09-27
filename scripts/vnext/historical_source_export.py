"""Carry an Issue #47 acquisition from the machine that made it to a checkout.

The approved ledger root is a path on the owner's machine, so that is where
the requests are made and counted. The historical Runs read their sources
from a data root, and the frozen reader trusts a data root's extended ledger
only through a checkpoint in the reading checkout's own journal
(``.git/ordinary-source-authority/acquired``). Neither the ledger root nor the
journal travels with a push. This module is how the acquired sources do.

``export_acquisition`` writes the rows the session appended, the response and
header files those rows cite, and the session's slot records into the
checkout, as deterministic gzip archives indexed by one sealed record. It
refuses unless the ledger as it stands is registered and the frozen replay
accepts it, so an export is never of something the machine that made it could
not itself validate.

``restore_acquisition`` rebuilds a data root from this checkout's trusted
baseline plus the export, checks every archive and member against the index,
and runs the same frozen replay over the result before it records the
checkpoint in this checkout's journal. What that establishes is exactly what
the replay establishes: the ledger extends the trusted baseline, every row is
bound to its slot, and every success's bytes are the immutable attempt its row
names. What it cannot establish is that the rows came from sec.gov rather than
from the machine that wrote them; that rests on the session records, the
approval on GitHub and the machine the owner ran it on, and the import record
says so rather than letting a journal entry imply more.

Archives are grouped by ledger row, closed at a row count or a raw size, and
written with fixed metadata, so exporting a longer ledger later rewrites only
the last group and adds new ones. Zero SEC or provider calls.
"""
from pathlib import Path, PurePosixPath
import gzip
import io
import os
import re
import subprocess
import tarfile

from sec_http import parse_request_log_rows
from .canonical import (canonical_json_bytes, content_hash, sha256_bytes, sha256_file,
                        strict_json_file, strict_json_loads)
from .historical_source_acquisition import (POLICY_PATH, REQUIREMENT_ID,
                                            HistoricalAcquisitionError)
from .historical_sec_session import ATTRIBUTION_TYPE, install_historical_source_inputs
from .normal_source_authority import MANIFEST_PATH, ROOT

EXPORT_TYPE = "ISSUE_47_HISTORICAL_ACQUISITION_EXPORT"
IMPORT_TYPE = "ISSUE_47_HISTORICAL_ACQUISITION_IMPORT"
EXPORT_DIRECTORY = "evidence/issue47_acquired"
INDEX_NAME = "export.json"
STATE_ARCHIVE = "ledger-state.tar.gz"
CHECKPOINT_MEMBER = "ledger/checkpoint.json"
LEDGER_FILES = ("evidence/requests_log.csv", "evidence/requests_log_manifest.json")
SLOT_FILES = ("intent.json", "sec-plan.json", "sec-receipt.json", "terminal.json")
# Closed at 100 rows or 160 MiB of raw bytes, whichever comes first. SEC HTML
# and JSON compress several times over, and GitHub refuses a file over
# 100 MB, so a group that still compresses past the ceiling below is a
# refusal to be looked at, not something to push.
CHUNK_ROWS = 100
CHUNK_RAW_BYTES = 160 * 1024 * 1024
MAX_ARCHIVE_BYTES = 95 * 1000 * 1000
_CHUNK_NAME = re.compile(r"^rows-[0-9]{5}-[0-9]{5}\.tar\.gz$")


class HistoricalExportError(HistoricalAcquisitionError):
    """An export or a restore that cannot be made to mean what it says."""


def _need(condition, reason):
    if not condition:
        raise HistoricalExportError(reason)


def _sealed(body, field):
    return {**body, field: content_hash(value=body)}


def _check_seal(value, field):
    _need(type(value) is dict and value.get(field) == content_hash(
        value={k: v for k, v in value.items() if k != field}),
        "ISSUE_47_EXPORT_RECORD_CHANGED:" + field)


def _safe_member(name):
    """A relative POSIX path with no parent steps, or a refusal."""
    path = PurePosixPath(name)
    _need(name == path.as_posix() and not path.is_absolute() and ".." not in path.parts
          and name and not name.startswith("./"), "ISSUE_47_EXPORT_MEMBER_PATH_UNSAFE:" + name)
    return path


def _archive(members):
    """Deterministic gzip tar of ``members`` (name -> bytes), sorted by name."""
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for name in sorted(members):
                data = members[name]
                info = tarfile.TarInfo(name=name)
                info.size, info.mtime, info.mode = len(data), 0, 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _binding(data):
    return {"sha256": sha256_bytes(content=data), "size": len(data)}


def _journal_checkpoint(*, ledger_sha256):
    from .continuous_sec_acquisition import _journal
    path = _journal() / (ledger_sha256 + ".json")
    _need(path.is_file(), "ISSUE_47_EXPORT_LEDGER_NOT_REGISTERED:" + ledger_sha256
          + " (register the ledger before exporting it)")
    return strict_json_file(path=path)


def _source_commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _approval(*, ledger_root, mode, policy_root):
    """The grant a LIVE ledger spent, read from the checkout that spent it."""
    path = Path(policy_root) / POLICY_PATH
    if mode != "LIVE":
        return None
    _need(path.is_file(), "ISSUE_47_EXPORT_LIVE_LEDGER_WITHOUT_ALLOWANCE:" + POLICY_PATH)
    policy = strict_json_file(path=path)
    _need(Path(policy["budget_root"]) == Path(ledger_root),
          "ISSUE_47_EXPORT_LEDGER_IS_NOT_THE_GRANTED_ROOT:" + str(ledger_root))
    return {key: policy[key] for key in ("delegation_url", "delegation_body_sha256",
                                         "delegation_record_path", "budget_root",
                                         "maximum_additional_provider_paid_sec_calls")}


def _groups(rows, first_index, data_root):
    """Row groups and the files each group carries, closed as described above."""
    groups, current, raw, seen = [], None, 0, set()
    for offset, row in enumerate(rows):
        files = {}
        for field in ("repo_relative_path", "headers_repo_relative_path"):
            relative = row[field]
            if not relative or relative in seen:
                continue
            _safe_member(relative)
            path = data_root / relative
            _need(path.is_file() and not path.is_symlink(),
                  "ISSUE_47_EXPORT_CITED_FILE_MISSING:" + relative)
            files[relative] = path.read_bytes()
            seen.add(relative)
        size = sum(len(data) for data in files.values())
        if current is not None and (len(current["rows"]) >= CHUNK_ROWS
                                    or raw + size > CHUNK_RAW_BYTES):
            groups.append(current)
            current = None
        if current is None:
            current, raw = {"rows": [], "files": {}}, 0
        current["rows"].append(first_index + offset)
        current["files"].update(files)
        raw += size
    if current is not None:
        groups.append(current)
    return groups


def export_acquisition(*, ledger_root, out_dir=None, policy_root=None):
    """Write the registered acquisition at ``ledger_root`` into ``out_dir``.

    ``out_dir`` defaults to ``evidence/issue47_acquired`` in this checkout.
    Stale row archives from an earlier, shorter export are removed; nothing
    else in the directory is touched. A LIVE ledger is exported only beside
    the allowance that granted its root, read from ``policy_root`` (this
    checkout by default).
    """
    from .continuous_sec_acquisition import validate_acquisition_checkpoint
    from .ordinary_source_authority import _prefix
    ledger_root = Path(ledger_root).resolve()
    out_dir = Path(out_dir) if out_dir is not None else ROOT / EXPORT_DIRECTORY
    data_root = ledger_root / "source-inputs"
    install_historical_source_inputs(root=data_root)
    baseline = strict_json_file(path=ROOT / MANIFEST_PATH)
    raw, rows, old = _prefix(data_root, baseline)
    ledger_sha = sha256_bytes(content=raw)
    checkpoint = _journal_checkpoint(ledger_sha256=ledger_sha)
    validate_acquisition_checkpoint(data_root, checkpoint, baseline)
    mode = checkpoint["execution_mode"]
    attribution_path = ledger_root / "acquisition-attribution" / (ledger_sha + ".json")
    _need(attribution_path.is_file(), "ISSUE_47_EXPORT_ATTRIBUTION_MISSING:" + ledger_sha)
    attribution = strict_json_file(path=attribution_path)
    _check_seal(attribution, "attribution_id")
    _need(attribution["record_type"] == ATTRIBUTION_TYPE
          and attribution["requirement_id"] == REQUIREMENT_ID
          and attribution["checkpoint_id"] == checkpoint["checkpoint_id"]
          and attribution["execution_mode"] == mode,
          "ISSUE_47_EXPORT_ATTRIBUTION_DISAGREES_WITH_CHECKPOINT")
    approval = _approval(ledger_root=ledger_root, mode=mode,
                         policy_root=ROOT if policy_root is None else policy_root)
    slots = sorted((ledger_root / "calls").iterdir())
    _need(len(slots) == len(checkpoint["captures"]) == len(rows) - len(old),
          "ISSUE_47_EXPORT_SLOTS_DIFFER_FROM_CHECKPOINT")
    state = {}
    for relative in LEDGER_FILES:
        state["source-inputs/" + relative] = (data_root / relative).read_bytes()
    for slot, capture in zip(slots, checkpoint["captures"]):
        for name in SLOT_FILES:
            path = slot / name
            _need(path.is_file() and not path.is_symlink(),
                  "ISSUE_47_EXPORT_SLOT_FILE_MISSING:" + slot.name + "/" + name)
            state["ledger/calls/" + slot.name + "/" + name] = path.read_bytes()
        _need(strict_json_file(path=slot / "intent.json") == capture["intent"],
              "ISSUE_47_EXPORT_SLOT_ORDER_DIFFERS:" + slot.name)
    state["ledger/acquisition-attribution/" + ledger_sha + ".json"] = \
        attribution_path.read_bytes()
    # The claim log and the binding travel with the slots, so the restoring
    # side can check the chain the ledger itself was held to.
    for name in ("claims.jsonl", "binding.json"):
        path = ledger_root / name
        _need(path.is_file() and not path.is_symlink(), "ISSUE_47_EXPORT_LEDGER_FILE_MISSING:" + name)
        state["ledger/" + name] = path.read_bytes()
    state[CHECKPOINT_MEMBER] = canonical_json_bytes(value=checkpoint)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    state_bytes = _archive(state)
    written[STATE_ARCHIVE] = state_bytes
    chunks = []
    for group in _groups(rows[len(old):], len(old), data_root):
        name = "rows-%05d-%05d.tar.gz" % (group["rows"][0], group["rows"][-1])
        data = _archive({"source-inputs/" + k: v for k, v in group["files"].items()})
        _need(len(data) <= MAX_ARCHIVE_BYTES, "ISSUE_47_EXPORT_ARCHIVE_TOO_LARGE:" + name)
        written[name] = data
        chunks.append({"name": name, "first_row": group["rows"][0],
                       "last_row": group["rows"][-1], **_binding(data),
                       "members": {"source-inputs/" + k: _binding(v)
                                   for k, v in sorted(group["files"].items())}})
    index = _sealed({
        "record_type": EXPORT_TYPE, "schema_version": 1, "requirement_id": REQUIREMENT_ID,
        "execution_mode": mode, "real_sec_credit": checkpoint["real_sec_credit"],
        "ledger_sha256": ledger_sha, "baseline_manifest_sha256":
            sha256_file(path=ROOT / MANIFEST_PATH),
        "baseline_row_count": len(old), "exported_row_count": len(rows) - len(old),
        "checkpoint_id": checkpoint["checkpoint_id"],
        "attribution_id": attribution["attribution_id"], "approval": approval,
        "state_archive": {"name": STATE_ARCHIVE, **_binding(state_bytes),
                          "members": {k: _binding(v) for k, v in sorted(state.items())}},
        "row_archives": chunks, "exported_from_commit": _source_commit(),
        "what_this_export_does_not_prove": (
            "that the rows came from sec.gov rather than from the machine that "
            "wrote them. The frozen replay proves the ledger extends the trusted "
            "baseline and every success's bytes are the attempt its row names; the "
            "origin rests on the session records, the approval on GitHub and the "
            "machine the owner ran it on."),
        "production_authorized": False}, "export_id")
    for stale in out_dir.iterdir():
        if _CHUNK_NAME.match(stale.name) and stale.name not in written:
            stale.unlink()
    for name, data in written.items():
        _replace(out_dir / name, data)
    _replace(out_dir / INDEX_NAME, canonical_json_bytes(value=index))
    return {"status": "EXPORTED", "export_id": index["export_id"], "out_dir": str(out_dir),
            "execution_mode": mode, "rows": index["exported_row_count"],
            "row_archives": len(chunks),
            "bytes": sum(len(data) for data in written.values()), "calls": [0, 0, 0]}


def _replace(path, data):
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
    os.replace(temporary, path)


def _read_archive(path, binding):
    data = path.read_bytes()
    _need(_binding(data) == {k: binding[k] for k in ("sha256", "size")},
          "ISSUE_47_EXPORT_ARCHIVE_CHANGED:" + path.name)
    members = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for info in tar.getmembers():
            _need(info.isfile(), "ISSUE_47_EXPORT_MEMBER_NOT_A_FILE:" + info.name)
            _safe_member(info.name)
            _need(info.name not in members, "ISSUE_47_EXPORT_MEMBER_REPEATED:" + info.name)
            members[info.name] = tar.extractfile(info).read()
    _need(set(members) == set(binding["members"]),
          "ISSUE_47_EXPORT_ARCHIVE_MEMBERS_DIFFER:" + path.name)
    for name, content in members.items():
        _need(_binding(content) == binding["members"][name],
              "ISSUE_47_EXPORT_MEMBER_CHANGED:" + name)
    return members


def restore_acquisition(*, export_dir, out_root):
    """Rebuild a data root from the trusted baseline plus an export, and register it.

    ``out_root`` must not exist. The data root is ``out_root/source-inputs``;
    the slot records land in ``out_root/ledger``. The checkpoint is recorded in
    this checkout's journal only after the frozen replay accepts the restored
    root, and ``out_root/import-record.json`` states what that does and does not
    establish.
    """
    from .continuous_sec_acquisition import _journal, validate_acquisition_checkpoint
    from .ordinary_source_authority import _immutable
    export_dir, out_root = Path(export_dir), Path(out_root).resolve()
    _need(not out_root.exists(), "ISSUE_47_RESTORE_TARGET_EXISTS:" + str(out_root))
    index = strict_json_file(path=export_dir / INDEX_NAME)
    _check_seal(index, "export_id")
    _need(index["record_type"] == EXPORT_TYPE and index["requirement_id"] == REQUIREMENT_ID
          and index["production_authorized"] is False,
          "ISSUE_47_RESTORE_INDEX_IS_NOT_AN_EXPORT")
    _need(index["baseline_manifest_sha256"] == sha256_file(path=ROOT / MANIFEST_PATH),
          "ISSUE_47_RESTORE_BASELINE_DIFFERS")
    state = _read_archive(export_dir / STATE_ARCHIVE, index["state_archive"])
    files = {}
    for chunk in index["row_archives"]:
        _need(_CHUNK_NAME.match(chunk["name"]), "ISSUE_47_RESTORE_ARCHIVE_NAME:" + chunk["name"])
        for name, content in _read_archive(export_dir / chunk["name"], chunk).items():
            _need(name not in files, "ISSUE_47_RESTORE_MEMBER_IN_TWO_ARCHIVES:" + name)
            files[name] = content
    data_root = out_root / "source-inputs"
    install_historical_source_inputs(root=data_root)
    for name in LEDGER_FILES:
        _replace(data_root / name, state["source-inputs/" + name])
    for name, content in files.items():
        relative = name[len("source-inputs/"):]
        _need(name.startswith("source-inputs/evidence/request_attempts/"),
              "ISSUE_47_RESTORE_MEMBER_OUTSIDE_ATTEMPTS:" + name)
        target = data_root / relative
        if target.exists():
            _need(target.read_bytes() == content, "ISSUE_47_RESTORE_WOULD_OVERWRITE:" + relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(content)
    ledger = out_root / "ledger"
    for name, content in state.items():
        if name.startswith("ledger/"):
            target = out_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(content)
    checkpoint = strict_json_loads(text=state[CHECKPOINT_MEMBER].decode("utf-8"))
    _check_seal(checkpoint, "checkpoint_id")
    _need(checkpoint["checkpoint_id"] == index["checkpoint_id"],
          "ISSUE_47_RESTORE_CHECKPOINT_IS_NOT_THE_INDEXED_ONE")
    baseline = strict_json_file(path=ROOT / MANIFEST_PATH)
    validate_acquisition_checkpoint(data_root, checkpoint, baseline)
    _need(checkpoint["ledger_sha256"] == index["ledger_sha256"]
          == sha256_file(path=data_root / "evidence/requests_log.csv"),
          "ISSUE_47_RESTORE_LEDGER_DIFFERS_FROM_INDEX")
    slots = sorted((ledger / "calls").iterdir())
    _need(len(slots) == len(checkpoint["captures"]), "ISSUE_47_RESTORE_SLOTS_DIFFER")
    claims = [strict_json_loads(text=line) for line in
              state["ledger/claims.jsonl"].decode("utf-8").splitlines()]
    binding = strict_json_loads(text=state["ledger/binding.json"].decode("utf-8"))
    _need(len(claims) == len(slots), "ISSUE_47_RESTORE_CLAIM_LOG_DIFFERS")
    previous = None
    for slot, capture in zip(slots, checkpoint["captures"]):
        records = {name: strict_json_file(path=slot / name) for name in SLOT_FILES}
        _need(records["intent.json"] == capture["intent"]
              and records["sec-receipt.json"] == capture["receipt"]
              and records["terminal.json"] == capture["terminal"],
              "ISSUE_47_RESTORE_SLOT_DIFFERS_FROM_CHECKPOINT:" + slot.name)
        intent, plan = records["intent.json"], records["sec-plan.json"]
        _need(intent["requirement_id"] == REQUIREMENT_ID
              and intent["execution_mode"] == checkpoint["execution_mode"],
              "ISSUE_47_RESTORE_SLOT_IS_FOR_ANOTHER_REQUIREMENT:" + slot.name)
        _need(claims[int(slot.name) - 1] == intent and intent["previous_intent_id"] == previous
              and intent["allowance_binding_id"] == binding["binding_id"],
              "ISSUE_47_RESTORE_CLAIM_CHAIN_BROKEN:" + slot.name)
        previous = intent["intent_id"]
        _need(intent["plan_id"] == content_hash(value=plan)
              and plan["request"]["url"] == capture["receipt"]["ledger_row"]["source_url"]
              and plan["source_dependency"]["source_url"] == plan["request"]["url"]
              and plan["scope_admission"]["grants"],
              "ISSUE_47_RESTORE_PLAN_DOES_NOT_BIND_ITS_REQUEST:" + slot.name)
    attribution = strict_json_file(
        path=ledger / "acquisition-attribution" / (index["ledger_sha256"] + ".json"))
    _check_seal(attribution, "attribution_id")
    _need(attribution["attribution_id"] == index["attribution_id"]
          and attribution["checkpoint_id"] == checkpoint["checkpoint_id"]
          and attribution["requirement_id"] == REQUIREMENT_ID,
          "ISSUE_47_RESTORE_ATTRIBUTION_DIFFERS")
    journaled = False
    if (ROOT / ".git").is_dir():
        _immutable(_journal() / (index["ledger_sha256"] + ".json"), checkpoint)
        journaled = True
    record = _sealed({
        "record_type": IMPORT_TYPE, "schema_version": 1, "requirement_id": REQUIREMENT_ID,
        "export_id": index["export_id"], "execution_mode": index["execution_mode"],
        "ledger_sha256": index["ledger_sha256"], "checkpoint_id": checkpoint["checkpoint_id"],
        "approval": index["approval"], "exported_from_commit": index["exported_from_commit"],
        "restored_row_count": index["exported_row_count"],
        "journaled_in_this_checkout": journaled,
        "established_here": (
            "every archive and member matches the sealed index; the restored ledger "
            "extends this checkout's trusted baseline; the frozen replay binds every "
            "row to its slot and every success to the immutable attempt it names; "
            "every slot's plan binds its request and carries the grant it was admitted under"),
        "not_established_here": index["what_this_export_does_not_prove"],
        "production_authorized": False}, "import_id")
    with (out_root / "import-record.json").open("xb") as handle:
        handle.write(canonical_json_bytes(value=record))
    return {"status": "RESTORED", "data_root": str(data_root), "import_id": record["import_id"],
            "execution_mode": index["execution_mode"], "rows": index["exported_row_count"],
            "journaled": journaled, "calls": [0, 0, 0]}

