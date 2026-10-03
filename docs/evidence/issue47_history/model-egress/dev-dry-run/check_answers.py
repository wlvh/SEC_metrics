"""Check development dry-run answers with the contracts' own checks, then against the reference.

Each answer file is the raw text a fresh-context development model wrote for one
request, having seen only that request's messages. It is held to exactly what a
DeepSeek answer would be held to: ``validate_answer`` and the counting of the
request's contract (E01 ``confirmed_count``; D02 ``reviewed_blocks``; D04 the
frozen ``d04_native_assessment.validate_response``), and the
output ceiling measured with the pinned reference tokenizer. Then the decisions
are compared with the development reference made from the filings. These are
development results - not DeepSeek, not LIVE, no call credit.

Usage (from a #47 tree at the sealed commit):
    python3 <this file> <requests dir> <answers dir> <e01 reference | -> [<d02 reference>] > out.json
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "scripts"))


def main(requests_dir, answers_dir, e01_reference, d02_reference=None):
    from vnext import historical_legal_review as d02
    from vnext import historical_ma_confirmation as e01
    from vnext.continuous_request_context import OUTPUT_RESERVE, _load_tokenizer
    tokenizer, _ = _load_tokenizer()
    references = ({(row["request"], row["item_id"]): row["reference"]
                   for row in json.loads(Path(e01_reference).read_text())["items"]}
                  if e01_reference != "-" else {})
    d02_refs = (json.loads(Path(d02_reference).read_text()) if d02_reference else {})
    rows = []
    for answer_path in sorted(Path(answers_dir).glob("*.json")):
        name = answer_path.stem
        request = json.loads((Path(requests_dir) / (name + ".request.json")).read_text())
        raw = answer_path.read_bytes()
        row = {"request": name, "answer_bytes": len(raw),
               "answer_tokens": len(tokenizer.encode(raw.decode("utf-8"), add_special_tokens=False).ids),
               "max_output_tokens": OUTPUT_RESERVE}
        row["fits_the_output_ceiling"] = row["answer_tokens"] <= OUTPUT_RESERVE
        if name.startswith("D04-"):
            # D04 answers go through the frozen native contract (#28's
            # d04_native_assessment.validate_response), as the call path does.
            from vnext.d04_native_assessment import validate_response
            try:
                checked = validate_response(request=request, raw_response=raw)
            except Exception as error:  # the contract raises its own named errors
                row["contract_check"] = "REFUSED: %s: %s" % (type(error).__name__, str(error)[:300])
                rows.append(row)
                continue
            row["contract_check"] = "PASSED"
            row["units"] = len(request["required_response_unit_ids"])
            row["required_candidate_assessments"] = len(request["required_candidate_assessments"])
            row["findings"] = [{"kind": f["kind"], "subject": f["subject"], "timing": f["timing"]}
                               for f in checked["findings"]]
            rows.append(row)
            continue
        contract = e01 if name.startswith("E01-") else d02
        error_type = getattr(contract, "ConfirmationContractError", None) or contract.LegalReviewContractError
        try:
            parsed = contract.validate_answer(request=request, raw_output=raw)
        except error_type as error:
            row["contract_check"] = "REFUSED: " + str(error)[:300]
            rows.append(row)
            continue
        row["contract_check"] = "PASSED"
        if contract is e01:
            value, reason, ids = e01.confirmed_count(request=request, decisions=parsed)
            row.update({"value": value, "withheld_reason": reason})
            disagreements = []
            for item in request["items"]:
                got = parsed[item["item_id"]]["decision"]
                want = references[(name, item["item_id"])]
                if got != want:
                    disagreements.append({"accession": item["accession"], "item_code": item["item_code"],
                                          "answer": got, "reference": want,
                                          "quote": parsed[item["item_id"]]["quote"][:300]})
            row["items"] = len(request["items"])
            row["disagreements"] = disagreements
            want_unsettled = [i for i in request["items"]
                              if references[(name, i["item_id"])] == "CANNOT_TELL_FROM_THE_ITEM_TEXT"]
            row["reference_value"] = (None if want_unsettled else
                                      sum(references[(name, i["item_id"])] == "REPORTS_A_TRANSACTION"
                                          for i in request["items"]))
        else:
            decisions, added = parsed
            row["must_decide"] = len(request["must_decide"])
            row["in_scope"] = sorted(b for b, d in decisions.items() if d["decision"] == "IN_SCOPE")
            row["cannot_tell"] = sorted(b for b, d in decisions.items()
                                        if d["decision"] == "CANNOT_TELL_FROM_THE_TEXT")
            row["also_in_scope"] = sorted(added)
            reference = d02_refs.get(name)
            if reference is not None:
                taken = set(row["in_scope"]) | set(row["also_in_scope"])
                row["reference_in"] = sorted(reference["in"])
                row["missed"] = sorted(set(reference["in"]) - taken)
                row["wrongly_taken"] = sorted(taken & set(reference.get("out", [])))
        rows.append(row)
    print(json.dumps({"record_type": "ISSUE_47_DEV_DRY_RUN_CHECK",
                      "what_this_is": ("development-model answers to the exact request messages, "
                                       "checked by the contracts' own validate_answer and counting "
                                       "and compared with a development reference; not DeepSeek, "
                                       "not LIVE, no call credit"),
                      "rows": rows}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
