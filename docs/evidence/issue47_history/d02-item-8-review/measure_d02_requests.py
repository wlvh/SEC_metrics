"""Measure the D02 Item 8 review requests the twelve saved D02 positions make; no call.

Each request is built by the route's own reading (``historical_text_input.d02_review_request``)
and measured with the pinned reference tokenizer the live path requires, so the
numbers describe the plan a live call would make. The ledger digest is what a
model approval names (``historical_model_calls.ledger_digest``).

The answer is measured too, because it has a hard ceiling (max_tokens 4096)
and D02's is the one answer that grows with the filing: one entry per
must-decide block. Counted with the same tokenizer on synthetic answers built
from the request - every must-decide block out, then the same with each block
counted in turn under a quote of the upper bound (300 characters, or the whole
block when shorter) - so the table says how many in-scope blocks a filing can
report before the ceiling, not a guess at how many it has.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/d02-item-8-review/measure_d02_requests.py
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
OUTPUT = "docs/evidence/issue47_history/d02-item-8-review/request-measurement.json"
POSITIONS = [("enphase_energy", "2025-12-31"), ("ford_motor_company", "2025-12-31"),
             ("lumen_technologies", "2025-12-31"), ("macys", "2026-01-31"),
             ("marriott_international", "2023-12-31"), ("marriott_international", "2024-12-31"),
             ("marriott_international", "2025-12-31"),
             ("paramount_skydance_paramount_global", "2024-12-31"),
             ("paramount_skydance_paramount_global", "2025-12-31"), ("pfizer", "2025-12-31"),
             ("salesforce", "2026-01-31"), ("southwest_airlines", "2025-12-31")]
TRANSPORT_FIELDS = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
                    "region": "provider-managed-no-residency-guarantee",
                    "retention": "provider-managed; no zero-retention claim",
                    "data_use": "provider-managed; no training or data-use guarantee",
                    "timeout_seconds": 120, "retry_count": 0, "maximum_payload_bytes": 8388608,
                    "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}


def main():
    from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
    from vnext.continuous_request_context import OUTPUT_RESERVE, _load_tokenizer, measure_request
    from vnext.historical_legal_review import QUOTE_CHARACTERS
    from vnext.continuous_semantic_calls import request_body
    from vnext.historical_model_calls import ledger_digest
    from vnext.historical_text_input import d02_review_request
    from vnext.normal_period_selection import resolve_period_selection
    policy = TransportPolicy.from_mapping(value={**TRANSPORT_FIELDS,
                                                 "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
    tokenizer, _ = _load_tokenizer()
    if tokenizer is None:
        raise SystemExit("THE_PINNED_REFERENCE_TOKENIZER_IS_REQUIRED")

    def answer_tokens(entries):
        text = json.dumps({"decisions": entries, "also_in_scope": []}, ensure_ascii=False)
        return len(tokenizer.encode(text, add_special_tokens=False).ids)

    rows = []
    for company_id, report_end in POSITIONS:
        started = time.time()
        selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                             report_end=report_end)
        request, _ = d02_review_request(repo_root=REPO, company_id=company_id,
                                        period_selection=selection)
        body = request_body(request, policy)
        measured = measure_request(body, require_reference=True)
        texts = {block["block_id"]: block["text"] for block in request["blocks"]}
        out = [{"block_id": identity, "decision": "OUT_OF_SCOPE", "quote": None}
               for identity in request["must_decide"]]
        all_out = answer_tokens(out)
        marginal = sorted(answer_tokens([{"block_id": identity, "decision": "IN_SCOPE",
                                          "quote": texts[identity][:QUOTE_CHARACTERS[1]]}])
                          - answer_tokens([entry]) for identity, entry
                          in zip(request["must_decide"], out)) if out else []
        # Filled with the costliest blocks first, the fewest that still fit.
        headroom, fit = OUTPUT_RESERVE - all_out, 0
        for cost in reversed(marginal):
            if headroom < cost:
                break
            headroom, fit = headroom - cost, fit + 1
        rows.append({"company_id": company_id, "report_end": report_end,
                     "request_id": request["request_id"],
                     "ledger_digest": ledger_digest(request, policy),
                     "blocks": len(request["blocks"]), "must_decide": len(request["must_decide"]),
                     "block_characters": sum(len(block["text"]) for block in request["blocks"]),
                     "provider_body_bytes": len(body),
                     "estimator_method": measured["estimator_method"],
                     "reference_input_tokens": measured["input_tokens"],
                     "max_output_tokens": OUTPUT_RESERVE,
                     "planned_context_tokens": measured["context_tokens"],
                     "fits_the_ceiling": measured["fits"],
                     "answer_tokens_every_block_out": all_out,
                     "answer_tokens_added_per_block_counted_in": (
                         {"min": marginal[0], "max": marginal[-1]} if marginal else None),
                     "must_decide_blocks_that_fit_counted_in_at_the_longest_quotes": (
                         min(fit, len(out)) if out else 0),
                     "seconds": round(time.time() - started, 1)})
        print(company_id, report_end, rows[-1]["reference_input_tokens"], flush=True)
    body = {"record_type": "ISSUE_47_D02_REVIEW_REQUEST_MEASUREMENT", "metric_id": "D02",
            "contract": "D02_ITEM_8_LEGAL_REVIEW_V1",
            "tokenizer": "the pinned reference tokenizer (continuous_request_context.measure_request)",
            "positions": rows,
            "totals": {"requests": len(rows),
                       "reference_input_tokens": sum(row["reference_input_tokens"] for row in rows),
                       "max_output_tokens": OUTPUT_RESERVE * len(rows),
                       "must_decide_blocks": sum(row["must_decide"] for row in rows),
                       "blocks": sum(row["blocks"] for row in rows)},
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (REPO / OUTPUT).write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
