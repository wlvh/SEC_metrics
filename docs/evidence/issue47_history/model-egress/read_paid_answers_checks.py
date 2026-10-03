"""Check read_paid_answers.py on synthetic ledgers before it reads a real one.

Each case builds a ledger slot the way the call path does (intent with the
request's ledger digest, the answer under ``wire/``, a terminal vouching for
it by hash) and states the outcome the reader must give: a D04 answer that
calls the target's going concern into doubt, leaves the required candidate
unresolved or does not answer it disagrees with the reference; one that gives
the candidate an acceptable category agrees; a slot whose answer differs from
its terminal's hash is refused. Synthetic answers, no call.

Usage (from a #47 tree, with the dry-run requests rendered):
    python3 docs/evidence/issue47_history/model-egress/read_paid_answers_checks.py <requests dir>
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import read_paid_answers as reader  # noqa: E402

CANDIDATE_REQUEST = "D04-paramount_skydance_paramount_global-2024-12-31-r1"


def _ledger(scratch, name, raw, *, vouch=None):
    digests = {row["file"]: row["ledger_digest"]
               for index in ("requests-index.json", "d04-requests-index.json")
               for row in json.loads((reader.DRY / index).read_text(encoding="utf-8"))}
    slot = Path(scratch) / "ledger" / "calls" / "0001"
    (slot / "wire").mkdir(parents=True)
    (slot / "intent.json").write_text(json.dumps({"request_digest": digests[name]}))
    (slot / "wire" / "assistant-output.bin").write_bytes(raw)
    (slot / "terminal.json").write_text(json.dumps({
        "status": "SUCCEEDED", "stop_reason": None,
        "evidence": {"wire/assistant-output.bin": "sha256:" + hashlib.sha256(vouch or raw).hexdigest()}}))
    return slot.parents[1]


def _answer(kind):
    units = [{"unit_index": i, "reviewed": True, "findings": [], "unresolved": []} for i in range(5)]
    if kind:
        units[0]["findings"] = [{"kind": kind, "subject": "TARGET_REGISTRANT", "timing": "CURRENT_REPORT",
                                 "evidence": [{"kind": "VISIBLE_BLOCK", "source_index": 340}],
                                 "reason": "synthetic"}]
    return json.dumps({"units": units}).encode()


def main(requests_dir):
    cases = [("the target's going concern in doubt", _answer("DOUBT_DISCLOSED"), False),
             ("the required candidate left unresolved", _answer("UNRESOLVED"), False),
             ("the required candidate not answered", _answer(None), False),
             ("the candidate as another meaning", _answer("VALUATION_OR_OTHER_MEANING"), True),
             ("the candidate as conditional boilerplate", _answer("CONDITIONAL_OR_BOILERPLATE"), True)]
    rows = []
    for label, raw, expected in cases:
        with tempfile.TemporaryDirectory() as scratch:
            ledger = _ledger(scratch, CANDIDATE_REQUEST, raw)
            reader.collect(ledger, Path(scratch) / "answers")
            got = reader.d04_against_reference(requests_dir, Path(scratch) / "answers")[0]
            rows.append({"case": label, "expected_agreement": expected,
                         "got": got["agrees_with_the_reference"],
                         "as_expected": got["agrees_with_the_reference"] is expected})
    with tempfile.TemporaryDirectory() as scratch:
        raw = _answer("VALUATION_OR_OTHER_MEANING")
        ledger = _ledger(scratch, CANDIDATE_REQUEST, raw, vouch=raw + b" ")
        try:
            reader.collect(ledger, Path(scratch) / "answers")
            got = "COPIED"
        except SystemExit as refusal:
            got = str(refusal).split(":", 1)[0]
        rows.append({"case": "an answer other than the one its terminal vouches for",
                     "expected": "PAID_ANSWER_DIFFERS_FROM_ITS_TERMINAL", "got": got,
                     "as_expected": got == "PAID_ANSWER_DIFFERS_FROM_ITS_TERMINAL"})
    result = {"record_type": "ISSUE_47_PAID_ANSWER_READER_CHECKS", "results": rows,
              "all_as_expected": all(row["as_expected"] for row in rows), "calls": [0, 0, 0]}
    (HERE / "read-paid-answers-checks.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result))
    return 0 if result["all_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
