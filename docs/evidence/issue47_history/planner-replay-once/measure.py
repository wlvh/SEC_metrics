"""Compute each company's frame twice on one root - replay once per state, and frozen.

Usage: python3 measure.py <code tree> <data root> <out.json> <company> [<company> ...]

Zero calls: network and DNS blocked. For each company the whole declared frame
(planner, event and governance declarations) is computed first as it now is,
with the checkpoint replayed once per ledger state, then with the block's memo
replaced by the frozen replay itself. The frozen checkpoint replay
(continuous_sec_acquisition.validate_acquisition_checkpoint) is counted in
both, by wrapping the attribute the frozen code looks up at call time, and the
two frames are compared field by field; every differing field is recorded.

The planner hashes its own file when a plan ends, so a code file edited while
this runs changes the frame without the memo having changed anything - the
first run of this measurement overlapped an injection run and recorded exactly
that. The code files the frames depend on are hashed before and after each
company, and a company whose files moved is refused rather than compared.
"""
import hashlib
import json
import socket
import sys
import time
from pathlib import Path
from unittest.mock import patch

CODE, ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
COMPANIES = sys.argv[4:]
sys.path.insert(0, str(CODE / "scripts"))

from vnext import continuous_sec_acquisition as acquisition  # noqa: E402
from vnext import normal_history_plan as plan  # noqa: E402
from vnext.canonical import canonical_json_bytes, sha256_bytes  # noqa: E402
from vnext.historical_source_acquisition import declared_frame  # noqa: E402

CODE_FILES = ("scripts/vnext/normal_history_plan.py",
              "scripts/vnext/historical_source_acquisition.py",
              "scripts/vnext/historical_event_sources.py",
              "scripts/vnext/historical_governance_sources.py",
              "scripts/vnext/ordinary_source_authority.py",
              "scripts/vnext/continuous_sec_acquisition.py")
frozen_replay = acquisition.validate_acquisition_checkpoint
rows, started = [], time.time()


def code_hashes():
    return {name: hashlib.sha256((CODE / name).read_bytes()).hexdigest() for name in CODE_FILES}


def differences(left, right, path=""):
    if type(left) is not type(right):
        return [{"path": path, "once": repr(left)[:200], "frozen": repr(right)[:200]}]
    if isinstance(left, dict):
        found = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                found.append({"path": path + "/" + key, "once": repr(left.get(key))[:200],
                              "frozen": repr(right.get(key))[:200]})
            else:
                found.extend(differences(left[key], right[key], path + "/" + key))
        return found
    if isinstance(left, list):
        found = ([] if len(left) == len(right)
                 else [{"path": path + "#length", "once": len(left), "frozen": len(right)}])
        for index, (a, b) in enumerate(zip(left, right)):
            found.extend(differences(a, b, path + "[" + str(index) + "]"))
        return found
    return [] if left == right else [{"path": path, "once": repr(left)[:200],
                                      "frozen": repr(right)[:200]}]


def run(company, *, frozen):
    count = {"replays": 0}

    def counted(*arguments, **keywords):
        count["replays"] += 1
        return frozen_replay(*arguments, **keywords)

    patches = [patch.object(acquisition, "validate_acquisition_checkpoint", counted)]
    if frozen:
        patches.append(patch.object(plan, "_replayed_once", lambda replay: replay))
    began = time.time()
    for item in patches:
        item.start()
    try:
        frame = declared_frame(repo_root=ROOT, company_id=company, years=5)
    finally:
        for item in reversed(patches):
            item.stop()
    return frame, {"seconds": int(time.time() - began), "checkpoint_replays": count["replays"],
                   "frame_sha256": "sha256:" + sha256_bytes(
                       content=canonical_json_bytes(value=frame)),
                   "requirements": len(frame["requirements"]),
                   "verified_saved": sum(1 for row in frame["requirements"]
                                         if row.get("saved_status") == "VERIFIED_SAVED_SOURCE")}


with patch.object(socket.socket, "connect", side_effect=AssertionError("net")), \
        patch.object(socket, "getaddrinfo", side_effect=AssertionError("dns")):
    for company in COMPANIES:
        before = code_hashes()
        once_frame, once = run(company, frozen=False)
        frozen_frame, replayed = run(company, frozen=True)
        after = code_hashes()
        moved = sorted(name for name in CODE_FILES if before[name] != after[name])
        row = {"company_id": company, "replay_once": once, "frozen": replayed,
               "code_files_moved_during_the_run": moved}
        if moved:
            row["refused"] = "CODE_FILES_MOVED_DURING_THE_RUN"
        else:
            found = differences(once_frame, frozen_frame)
            row.update(frames_identical=not found, differences=found[:50],
                       difference_count=len(found))
        rows.append(row)
        print(company, json.dumps({k: row[k] for k in row
                                   if k in ("replay_once", "frozen", "frames_identical",
                                            "difference_count", "refused")}, sort_keys=True),
              flush=True)
        OUT.write_text(json.dumps({"rows": rows, "seconds": int(time.time() - started)},
                                  indent=1, sort_keys=True) + "\n", encoding="utf-8")
OUT.write_text(json.dumps({"rows": rows, "seconds": int(time.time() - started),
                           "calls": [0, 0, 0], "code_tree": str(CODE), "data_root": str(ROOT),
                           "code_files": code_hashes(),
                           "all_identical": all(r.get("frames_identical") for r in rows)},
                          indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("DONE", int(time.time() - started), flush=True)
