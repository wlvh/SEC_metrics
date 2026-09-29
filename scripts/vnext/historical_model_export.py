"""Carry Issue #47's model ledger from the container that holds it to the branch, and back.

Purpose: The owner decided the model calls run in the executor's cloud
container, and the ledger lives there too; the container's disk goes when it
is reclaimed. After each run the ledger - every slot, the claim log, the
binding, and the anchor and claim-log copy beside the root - is exported into
``evidence/issue47_model_calls/`` and pushed, so what was spent and what came
back survive the container. The export is checked by the ledger's own
``snapshot`` before it is written, and again, from the archive alone, before
anything is restored.

What restoring does not do: it never writes the start record. A restored
ledger is the record of what was spent; spending more from it is the owner's
decision, and until a start is published for it the live path refuses
(historical_ledger_start). And the start refuses once this checkout carries an
export of the approval's ledger, so a deleted marker comment cannot start the
allowance again from an empty ledger.

Call relationships: ``tools/vnext_historical_model_export.py`` calls it, in a
process of its own - never the one that sends requests, which may load only
the code its authorization binds. It reuses the SEC export's archive helpers.
"""
import tempfile
from pathlib import Path

from .canonical import canonical_json_bytes, sha256_bytes, strict_json_file
from .historical_model_calls import (MODEL_EXPORT_DIRECTORY, MODEL_EXPORT_INDEX,
                                     REQUIREMENT_ID, HistoricalModelCallError,
                                     HistoricalModelLedger, _FACTORY, _ledger, model_allowance)
from .normal_source_authority import ROOT

EXPORT_TYPE = "ISSUE_47_HISTORICAL_MODEL_LEDGER_EXPORT"
ARCHIVE_NAME = "model-ledger.tar.gz"
ROOT_PREFIX = "root/"
BESIDE = {"beside/anchor.json": HistoricalModelLedger.anchor_path,
          "beside/claims-mirror.jsonl": HistoricalModelLedger.mirror_path}


def _need(condition, reason):
    if not condition:
        raise HistoricalModelCallError(reason)


def _files(root):
    """Every file under the ledger root, by relative path; no link, nothing but files and folders."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        _need(not path.is_symlink(), "ISSUE_47_MODEL_EXPORT_LINK_IN_THE_LEDGER:" + str(path))
        if path.is_file():
            found[ROOT_PREFIX + path.relative_to(root).as_posix()] = path.read_bytes()
        else:
            _need(path.is_dir(), "ISSUE_47_MODEL_EXPORT_UNEXPECTED_ENTRY:" + str(path))
    return found


def _state(ledger):
    with ledger.locked():
        return ledger.snapshot()


def export_model_ledger(*, ledger, out_dir):
    """Write ``ledger`` - checked by its own snapshot first - into ``out_dir``."""
    from .historical_source_export import _archive, _binding, _replace, _sealed, _source_commit
    state = _state(ledger)
    members = _files(ledger.root)
    for name, where in BESIDE.items():
        path = where(ledger.root)
        _need(path.is_file() and not path.is_symlink(), "ISSUE_47_MODEL_EXPORT_MISSING:" + name)
        members[name] = path.read_bytes()
    data = _archive(members)
    index = _sealed({
        "record_type": EXPORT_TYPE, "schema_version": 1, "requirement_id": REQUIREMENT_ID,
        "execution_mode": ledger.mode, "ledger_root": str(ledger.root),
        "ledger_binding": ledger.binding,
        "approval": ({"delegation_url": ledger.binding["delegation_url"],
                      "delegation_body_sha256": ledger.binding["delegation_body_sha256"]}
                     if ledger.live else None),
        "counts": state["counts"], "limits": state["limits"], "stopped": state["stopped"],
        "requests": state["requests"],
        "archive": {"name": ARCHIVE_NAME, **_binding(data),
                    "members": {name: _binding(content) for name, content in sorted(members.items())}},
        "exported_from_commit": _source_commit(),
        "what_this_export_does_not_prove": (
            "that the responses came from the provider rather than from the host that wrote "
            "them; the slots bind each response to the request that was sent, the controller's "
            "receipt and the wire journal, and the origin rests on the host, the approval and "
            "the start marker on GitHub. The container's egress proxy re-terminates TLS."),
        "production_authorized": False}, "export_id")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _replace(out_dir / ARCHIVE_NAME, data)
    _replace(out_dir / MODEL_EXPORT_INDEX, canonical_json_bytes(value=index))
    return {"status": "EXPORTED", "export_id": index["export_id"], "out_dir": str(out_dir),
            "counts": state["counts"], "slots": len(state["rows"]), "bytes": len(data),
            "calls": [0, 0, 0]}


def _read(export_dir):
    from .historical_source_export import _check_seal, _read_archive
    export_dir = Path(export_dir)
    index = strict_json_file(path=export_dir / MODEL_EXPORT_INDEX)
    _check_seal(index, "export_id")
    _need(index.get("record_type") == EXPORT_TYPE and index.get("requirement_id") == REQUIREMENT_ID
          and index.get("production_authorized") is False,
          "ISSUE_47_MODEL_RESTORE_INDEX_IS_NOT_AN_EXPORT")
    members = _read_archive(export_dir / ARCHIVE_NAME, index["archive"])
    _need(set(members) == set(index["archive"]["members"]),
          "ISSUE_47_MODEL_RESTORE_MEMBERS_DIFFER_FROM_THE_INDEX")
    return index, members


def _write(members, root):
    for name, content in members.items():
        if name.startswith(ROOT_PREFIX):
            target = Path(root) / name[len(ROOT_PREFIX):]
        else:
            _need(name in BESIDE, "ISSUE_47_MODEL_RESTORE_MEMBER_UNKNOWN:" + name)
            target = BESIDE[name](root)
        _need(not target.exists(), "ISSUE_47_MODEL_RESTORE_WOULD_OVERWRITE:" + str(target))
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open("xb") as handle:
            handle.write(content)


def verify_model_export(*, export_dir):
    """The export, rebuilt in a scratch root, is a ledger whose own snapshot is the index's."""
    index, members = _read(export_dir)
    with tempfile.TemporaryDirectory(prefix="issue47-model-export-") as scratch:
        root = Path(scratch) / "ledger"
        _write(members, root)
        ledger = HistoricalModelLedger(factory=_FACTORY, root=root, binding=index["ledger_binding"],
                                       live=index["execution_mode"] == "LIVE")
        # Not locked(): a LIVE ledger is locked only at its granted root, and
        # the snapshot is what checks the slots, the claim log and its copy.
        state = ledger.snapshot()
    _need([state["counts"], state["stopped"], state["requests"]]
          == [index["counts"], index["stopped"], index["requests"]],
          "ISSUE_47_MODEL_RESTORE_SNAPSHOT_DIFFERS_FROM_THE_INDEX")
    return index


def restore_model_ledger(*, export_dir, repo_root=ROOT):
    """Put a verified export of the granted LIVE ledger back at the granted root; never its start."""
    index = verify_model_export(export_dir=export_dir)
    _need(index["execution_mode"] == "LIVE", "ISSUE_47_MODEL_RESTORE_ONLY_A_LIVE_LEDGER")
    allowance = model_allowance(repo_root=repo_root)
    root = Path(allowance["budget_root"])
    ledger = _ledger(allowance=allowance, root=root, live=True)
    _need(ledger.binding == index["ledger_binding"] and str(root) == index["ledger_root"],
          "ISSUE_47_MODEL_RESTORE_IS_NOT_THE_GRANTED_LEDGER")
    _need(not root.exists() and not any(where(root).exists() for where in BESIDE.values()),
          "ISSUE_47_MODEL_RESTORE_TARGET_EXISTS:" + str(root))
    _, members = _read(export_dir)
    _write(members, root)
    state = _state(ledger)
    return {"status": "RESTORED", "root": str(root), "counts": state["counts"],
            "stopped": state["stopped"], "start_restored": False, "calls": [0, 0, 0]}
