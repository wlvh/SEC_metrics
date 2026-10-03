"""Measure the E01 confirmation requests a model-call application would name, without any call.

For every window of the twelve-period batch whose E01 route reads candidate
items, the route itself builds the one confirmation request of that window
(``historical_zero_ai_results.e01_confirmation_request``), and the request's
exact provider body is counted by the pinned reference tokenizer - the count
the live path compares the service's own count with. Nothing is sent and no
allowance is read: the transport policy is the fixed one a #47 model allowance
must name. A window whose route stops before reading candidates is recorded
with the route's reason, not as a request.

Run from the repository root:

    python3 docs/evidence/issue47_history/e01-content-confirmed/measure_e01_requests.py
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
HERE = Path(__file__).resolve().parent
BATCH = REPO / "docs/evidence/issue47_history/native-run-batch-12-periods/measured.json"
TRANSPORT_FIELDS = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
                    "region": "provider-managed-no-residency-guarantee",
                    "retention": "provider-managed; no zero-retention claim",
                    "data_use": "provider-managed; no training or data-use guarantee",
                    "timeout_seconds": 120, "retry_count": 0, "maximum_payload_bytes": 8388608,
                    "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}


def main():
    from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
    from vnext.continuous_request_context import OUTPUT_RESERVE, measure_request
    from vnext.continuous_semantic_calls import request_body
    from vnext.historical_model_calls import ledger_digest
    from vnext.historical_zero_ai_results import NormalZeroAiError, e01_confirmation_request
    from vnext.normal_period_selection import resolve_period_selection
    policy = TransportPolicy.from_mapping(value={**TRANSPORT_FIELDS,
                                                 "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
    periods = [(row["case"], row["company_id"], row["report_end"])
               for row in json.loads(BATCH.read_text(encoding="utf-8"))["batch"]["per_period"]]
    windows = []
    for case, company_id, report_end in periods:
        row = {"case": case, "company_id": company_id, "report_end": report_end}
        try:
            selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                                 report_end=report_end)
            request, _proofs = e01_confirmation_request(repo_root=REPO, company_id=company_id,
                                                        period_selection=selection)
        except (NormalZeroAiError, ValueError) as error:
            row["no_request"] = type(error).__name__ + ": " + str(error)[:300]
            windows.append(row)
            print(case, "NO_REQUEST", str(error)[:120], flush=True)
            continue
        body = request_body(request, policy)
        # The live path refuses any estimator but the pinned tokenizer.
        measured = measure_request(body, require_reference=True)
        row.update({"request_id": request["request_id"], "source_id": request["source_id"],
                    "ledger_digest": ledger_digest(request, policy),
                    "items": len(request["items"]),
                    "item_codes": sorted({item["item_code"] for item in request["items"]}),
                    "item_text_characters": sum(len(item["text"]) for item in request["items"]),
                    "provider_body_bytes": len(body),
                    "provider_body_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
                    "estimator_method": measured["estimator_method"],
                    "reference_input_tokens": measured["input_tokens"],
                    "max_output_tokens": OUTPUT_RESERVE,
                    "planned_context_tokens": measured["context_tokens"],
                    "fits_the_ceiling": measured["fits"]})
        windows.append(row)
        print(case, row["items"], row["reference_input_tokens"], flush=True)
    requested = [row for row in windows if "request_id" in row]
    body = {"record_type": "E01_CONTENT_CONFIRMATION_REQUEST_MEASUREMENT",
            "what_this_is": ("the one confirmation request of each window whose E01 route reads "
                             "candidate items, built by the route and counted by the pinned "
                             "reference tokenizer; no request was sent"),
            "windows": windows,
            "totals": {"requests": len(requested), "items": sum(row["items"] for row in requested),
                       "reference_input_tokens": sum(row["reference_input_tokens"] for row in requested),
                       "provider_paid_sec_calls_if_each_is_called_once": [len(requested), len(requested), 0]},
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (HERE / "request-measurement.json").write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    print(json.dumps(body["totals"]))


if __name__ == "__main__":
    main()
