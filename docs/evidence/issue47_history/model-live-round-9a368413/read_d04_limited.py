"""Bind the paid D04 two-direction reading to the prior limited reference.

This reports the source text of the single emitted finding and the reverse
mandatory-candidate comparison. The prior phrase scan is not a full filing
semantic reading and cannot grant content acceptance. Requests are the original
sealed package's dump, not rebuilt from current development code.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "model-egress/dev-dry-run/d04-reference.json"
sys.path.insert(0, str(HERE.parents[3] / "scripts"))
from vnext.native_unit_index import restore_response


def main(requests):
    check = json.loads((HERE / "paid-read-final/check.json").read_text())
    reference = json.loads(REFERENCE.read_text())
    refs = {row["file"]: row for row in reference["requests"]}
    slots = {row["request"]: row for row in check["slots"]}
    contracts = {row["request"]: row for row in check["contracts_and_e01_d02_references"]}
    readings = []
    for compared in check["d04_against_the_reference"]:
        name = compared["request"]
        ref, slot = refs[name], slots[name]
        assert slot["terminal_status"] == "SUCCEEDED" and slot["stop_reason"] == ""
        assert slot["request_digest"] == ref["ledger_digest"]
        assert contracts[name]["contract_check"] == "PASSED"
        raw = (requests / (name + ".request.json")).read_bytes()
        request = json.loads(raw)
        answer_bytes = (HERE / "paid-read-final/answers" / (name + ".json")).read_bytes()
        assert hashlib.sha256(answer_bytes).hexdigest() == slot["answer_sha256"]
        _, normalized, _ = restore_response(request=request, raw_response=answer_bytes)
        answer = json.loads(normalized)
        findings = [{**f, "unit_id": u["unit_id"]}
                    for u in answer["units"] for f in u["findings"]]
        assert len(findings) == len(compared["findings"])
        forward = []
        for finding in findings:
            # The prior judgment permits this exact non-assessment category.
            # Any new shape requires a new actual reading, not inferred credit.
            assert name == "D04-paramount_skydance_paramount_global-2024-12-31-r1"
            assert finding["kind"] == "CONDITIONAL_OR_BOILERPLATE"
            assert finding["subject"] == "TARGET_REGISTRANT"
            evidence, = finding["evidence"]
            assert evidence == {"kind": "VISIBLE_BLOCK", "source_index": 340}
            unit, = [u for u in request["units"] if u["unit_id"] == finding["unit_id"]]
            layout = unit["payload"]["row_layout"]["columns"]
            block = dict(zip(layout, unit["payload"]["blocks"]["340"]))
            text = block["text"]
            assert "Streaming is intensely competitive and cash intensive" in text
            assert "ability to continue to attract" in text
            forward.append({"finding": finding, "source_block": block,
                            "reading": "The sentence concerns attracting streaming users and streaming profitability. It is a conditional business risk, not an assessment of the registrant's going-concern doubt.",
                            "disposition": "SUPPORTED_WITHIN_PRIOR_LIMITED_JUDGMENT"})
        assert compared["agrees_with_the_reference"]
        readings.append({"request": name, "ledger_slot": slot["slot"],
                         "request_digest": slot["request_digest"],
                         "request_file_sha256": hashlib.sha256(raw).hexdigest(),
                         "answer_sha256": slot["answer_sha256"],
                         "model_to_source": forward,
                         "source_to_model": {"required_candidates": compared["required_candidates"],
                                             "all_agree": True,
                                             "scope": "The pre-call reference's two phrase scans and explicitly judged cue contexts only."},
                         "full_content_acceptance": "NOT_PROVEN"})
    assert len(readings) == 16
    report = {"record_type": "ISSUE_47_D04_PAID_LIMITED_TWO_DIRECTION_READ",
              "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
              "requests": readings,
              "what_this_cannot_see": reference["what_this_cannot_see"],
              "full_filing_semantic_read_completed": False,
              "acceptance_entries_added": 0, "calls": [0, 0, 0],
              "production_authorized": False}
    (HERE / "d04-limited-two-direction-read.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"requests": 16, "forward_findings_read": sum(len(r["model_to_source"]) for r in readings),
                      "reverse_mandatory_candidates_read": sum(len(r["source_to_model"]["required_candidates"]) for r in readings),
                      "content_acceptance_added": 0}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
