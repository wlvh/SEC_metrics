"""Measure the D04 requests a model-call application would name, without any call.

For each pinned period, the D04 source is rebuilt from the saved filing by the
historical route's own builder, partitioned into the requests the frozen
contract defines, and each request's exact provider body is counted by the
pinned reference tokenizer - the count the live path compares the service's
own count with. Nothing is sent and no allowance is read: the transport policy
is the fixed one a #47 model allowance must name.

Run from the repository root:

    python3 docs/evidence/issue47_history/model-egress/measure_d04_requests.py \
        --position marriott_international:2023-12-31 ... --output <path>
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

# The fixed transport a #47 model allowance must carry (historical_model_calls.FIXED_TRANSPORT
# plus the adapter's fields); the endpoint host is the adapter's own constant.
TRANSPORT_FIELDS = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
                    "region": "provider-managed-no-residency-guarantee",
                    "retention": "provider-managed; no zero-retention claim",
                    "data_use": "provider-managed; no training or data-use guarantee",
                    "timeout_seconds": 120, "retry_count": 0, "maximum_payload_bytes": 8388608,
                    "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--position", action="append", required=True, help="<company_id>:<report_end>")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
    from vnext.continuous_request_context import OUTPUT_RESERVE, measure_request
    from vnext.continuous_semantic_calls import request_body
    from vnext.historical_model_calls import ledger_digest
    from vnext.historical_semantic_results import pinned_native_source, pinned_requests
    from vnext.normal_period_selection import resolve_period_selection
    policy = TransportPolicy.from_mapping(value={**TRANSPORT_FIELDS,
                                                 "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
    positions = {}
    for requested in arguments.position:
        company_id, report_end = requested.rsplit(":", 1)
        started = time.time()
        selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                             report_end=report_end)
        source = pinned_native_source(repo_root=REPO, company_id=company_id, metric_id="D04",
                                      period_selection=selection)
        requests = []
        for request in pinned_requests(source):
            body = request_body(request, policy)
            # The live path refuses any estimator but the pinned tokenizer, so
            # a measurement that fell back to a byte bound would describe a
            # plan the live path would not make.
            measured = measure_request(body, require_reference=True)
            # What an approval names: the exact bytes the call sends
            # (historical_model_calls.ledger_digest), not #28's semantic digest.
            requests.append({"ledger_digest": ledger_digest(request, policy),
                             "units": len(request["units"]),
                             "required_candidate_assessments": len(
                                 request.get("required_candidate_assessments") or ()),
                             "provider_body_bytes": len(body),
                             "provider_body_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
                             "estimator_method": measured["estimator_method"],
                             "reference_input_tokens": measured["input_tokens"],
                             "max_output_tokens": OUTPUT_RESERVE,
                             "planned_context_tokens": measured["context_tokens"],
                             "fits_the_ceiling": measured["fits"]})
        positions[requested] = {
            "semantic_source_id": source["semantic_source_id"],
            "filing_accessions": sorted({document["filing"]["accessionNumber"]
                                         for document in source.get("documents", ())
                                         if isinstance(document, dict) and "filing" in document}),
            "requests": requests,
            "reference_input_tokens": sum(row["reference_input_tokens"] for row in requests),
            "seconds": round(time.time() - started, 1)}
        print(requested, len(requests), positions[requested]["reference_input_tokens"], flush=True)
    body = {"record_type": "ISSUE_47_D04_REQUEST_MEASUREMENT", "metric_id": "D04",
            "tokenizer": "the pinned reference tokenizer (continuous_request_context.measure_request)",
            "positions": positions,
            "totals": {"requests": sum(len(p["requests"]) for p in positions.values()),
                       "reference_input_tokens": sum(p["reference_input_tokens"]
                                                     for p in positions.values()),
                       "max_output_tokens": OUTPUT_RESERVE * sum(len(p["requests"])
                                                                 for p in positions.values())},
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
    Path(arguments.output).write_text(json.dumps(body, indent=1, sort_keys=True) + "\n",
                                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
