"""Take the paid answers out of a #47 model ledger and hold them to the contracts and the references.

Each claimed slot of the ledger (``calls/NNNN``) holds the intent (the
request's ledger digest), the terminal (status, stop reason, and the hash of
every file in the slot) and, for an answer received, ``wire/assistant-output.bin``.
This maps each slot to its request through the dry-run request indexes - the
digests the approval names - and copies an answer out only when the terminal's
own evidence hash matches the file. Then every answer goes through the
dry-run checker (``dev-dry-run/check_answers.py``: the contracts' own checks,
and the E01 and D02 references written before any paid answer), and each D04
answer is compared with ``dev-dry-run/d04-reference.json``, also written first:
no DOUBT_DISCLOSED, DOUBT_ALLEVIATED or NO_DOUBT_DECLARATION about the target,
and each required candidate in one of its acceptable categories.

A slot without an answer (a stop, a refused contract, an unknown outcome) is
listed with its terminal; nothing is inferred for it. Nothing is written into
the ledger and nothing is sent.

Usage (from the run package, after ``dump_requests.py <requests dir> E01,D02,D04``):
    python3 docs/evidence/issue47_history/model-egress/read_paid_answers.py \
        <ledger root> <requests dir> <output dir>
"""
import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRY = HERE / "dev-dry-run"
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(DRY))
WRONG_FOR_THE_TARGET = ("DOUBT_DISCLOSED", "DOUBT_ALLEVIATED", "NO_DOUBT_DECLARATION")


def _names():
    names = {}
    for index in ("requests-index.json", "d04-requests-index.json"):
        for row in json.loads((DRY / index).read_text(encoding="utf-8")):
            names[row["ledger_digest"]] = row["file"]
    return names


def collect(ledger_root, answers_dir):
    """One row per slot; an answer file for each slot whose terminal vouches for it."""
    names, rows = _names(), []
    answers_dir.mkdir(parents=True, exist_ok=False)
    for slot in sorted((Path(ledger_root) / "calls").iterdir()):
        intent = json.loads((slot / "intent.json").read_text(encoding="utf-8"))
        name = names.get(intent["request_digest"])
        if name is None:
            raise SystemExit("PAID_ANSWER_SLOT_NAMES_A_REQUEST_NO_INDEX_HAS: " + slot.name)
        row = {"slot": slot.name, "request": name, "request_digest": intent["request_digest"]}
        terminal_path = slot / "terminal.json"
        if not terminal_path.is_file():
            rows.append({**row, "terminal": None, "answer": "NO_TERMINAL"})
            continue
        terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
        row.update(terminal_status=terminal["status"], stop_reason=terminal["stop_reason"])
        output = slot / "wire" / "assistant-output.bin"
        vouched = terminal["evidence"].get("wire/assistant-output.bin")
        if not output.is_file() or vouched is None:
            rows.append({**row, "answer": "NO_ANSWER_IN_THE_SLOT"})
            continue
        raw = output.read_bytes()
        if vouched.split(":")[-1] != hashlib.sha256(raw).hexdigest():
            raise SystemExit("PAID_ANSWER_DIFFERS_FROM_ITS_TERMINAL: " + slot.name)
        if (answers_dir / (name + ".json")).exists():
            raise SystemExit("PAID_ANSWER_TWO_SLOTS_FOR_ONE_REQUEST: " + name)
        (answers_dir / (name + ".json")).write_bytes(raw)
        rows.append({**row, "answer": "COPIED", "answer_sha256": hashlib.sha256(raw).hexdigest()})
    return rows


def d04_against_reference(requests_dir, answers_dir):
    """Each D04 answer against the reference written before any paid answer."""
    from vnext.native_unit_index import restore_response
    reference = {row["file"]: row
                 for row in json.loads((DRY / "d04-reference.json").read_text(encoding="utf-8"))["requests"]}
    rows = []
    for path in sorted(Path(answers_dir).glob("D04-*.json")):
        name = path.stem
        request = json.loads((Path(requests_dir) / (name + ".request.json")).read_text(encoding="utf-8"))
        _, normalized, _ = restore_response(request=request, raw_response=path.read_bytes())
        answer = json.loads(normalized)
        findings = [{**finding, "unit_id": unit["unit_id"]}
                    for unit in answer["units"] for finding in unit["findings"]]
        wrong = [f for f in findings if f["kind"] in WRONG_FOR_THE_TARGET
                 and f["subject"] == "TARGET_REGISTRANT"]
        candidates = []
        for candidate in reference[name]["required_candidates"]:
            given = [f["kind"] for f in findings if f["unit_id"] == candidate["unit_id"]
                     and any(e == {"kind": candidate["kind"], "source_index": candidate["source_index"]}
                             for e in f["evidence"])]
            candidates.append({"source_index": candidate["source_index"], "given": given,
                               "acceptable": candidate["acceptable_categories"],
                               "agrees": bool(given) and all(kind in candidate["acceptable_categories"]
                                                             for kind in given)})
        rows.append({"request": name, "findings": [{k: f[k] for k in ("kind", "subject", "timing")}
                                                   for f in findings],
                     "wrong_for_the_target": [{k: f[k] for k in ("kind", "subject", "timing", "reason")}
                                              for f in wrong],
                     "required_candidates": candidates,
                     "agrees_with_the_reference": not wrong and all(c["agrees"] for c in candidates)})
    return rows


def main(ledger_root, requests_dir, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    slots = collect(ledger_root, output_dir / "answers")
    import check_answers
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        check_answers.main(requests_dir, str(output_dir / "answers"),
                           str(DRY / "e01-reference.json"), str(DRY / "d02-reference.json"))
    checked = json.loads(printed.getvalue())
    value = {"record_type": "ISSUE_47_PAID_ANSWERS_CHECK",
             "what_this_is": ("the paid answers taken out of the model ledger by the terminals' own "
                              "hashes, held to the contracts and to the references written before "
                              "any paid answer; a reading, not an acceptance"),
             "slots": slots, "contracts_and_e01_d02_references": checked["rows"],
             "d04_against_the_reference": d04_against_reference(requests_dir, output_dir / "answers"),
             "calls": [0, 0, 0]}
    (output_dir / "check.json").write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
    print(json.dumps({"slots": len(slots), "answers": sum(r["answer"] == "COPIED" for r in slots),
                      "d04_agree": sum(r["agrees_with_the_reference"]
                                       for r in value["d04_against_the_reference"])}))


if __name__ == "__main__":
    main(*sys.argv[1:])
