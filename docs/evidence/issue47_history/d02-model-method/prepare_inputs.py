"""Write D02's Item 8 review request for historical positions, exactly as a paid call would send it.

#47's D02 model method is its own Item 8 review contract
(``scripts/vnext/historical_legal_review.py``, D02_ITEM_8_LEGAL_REVIEW_V1): one
request per filing holding every Item 8 block the route could take, with the
blocks that carry a legal word listed as must-decide. The 35-request
application uses it for twelve positions. This writes the same request for
older positions, on a root restored from the committed SEC export, so a
development context can answer it and the answer can be held to the older-year
two-direction readings (``../d02-older-years/judgements/``).

The request is built by the route (``historical_text_input.d02_review_request``),
its provider body by ``request_body`` under the fixed transport, and the file a
development context reads is rendered from the body's own messages by the dry
run's ``render_input`` - so what it reads is what DeepSeek would receive.
Nothing is sent; D02 older years are not in the 35-request application.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/d02-model-method/prepare_inputs.py \
        --source-root <restored source-inputs> --out <dir> \
        --position <company_id>:<report_end> [--position ...]
Zero calls.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
DRY_RUN = REPO / "docs/evidence/issue47_history/model-egress/dev-dry-run/dump_requests.py"


def _dry_run():
    spec = importlib.util.spec_from_file_location("issue47_dev_dry_run_dump", DRY_RUN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(*, source_root, company_id, report_end, out):
    from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
    from vnext.continuous_request_context import measure_request
    from vnext.continuous_semantic_calls import request_body
    from vnext.historical_model_calls import ledger_digest
    from vnext.historical_text_input import d02_review_request
    from vnext.normal_history_plan import checkpoint_replayed_once
    from vnext.normal_period_selection import resolve_period_selection
    dry = _dry_run()
    policy = TransportPolicy.from_mapping(value={**dry.TRANSPORT_FIELDS,
                                                 "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
    from vnext.historical_text_input import prepare_historical_business_text_input
    from vnext.historical_text_results import _d02_parts, _prepare_corrected_sources
    with checkpoint_replayed_once():
        selection = resolve_period_selection(repo_root=source_root, company_id=company_id,
                                             report_end=report_end)
        request, _ = d02_review_request(repo_root=source_root, company_id=company_id,
                                        period_selection=selection)
        # The route's own Item 8 selection today (the keyword with the category
        # rule), read the way d02_review_request reads it, for the comparison.
        prepared = prepare_historical_business_text_input(
            repo_root=source_root, company_id=company_id, metric_id="D02",
            period_selection=selection, _without_reviews=True)
        _, _, proposal = _d02_parts(_prepare_corrected_sources(metric_id="D02",
                                                               **prepared["text_arguments"]))
    route_item_8 = sorted("b" + str(candidate["block_index"]) for candidate in proposal["D02"]["candidates"]
                          if candidate["section_id"] == "ITEM_8")
    body = request_body(request, policy)
    sent = json.loads(body.decode("utf-8"))
    text = dry.render_input(sent["messages"])
    measurement = measure_request(body, require_reference=True)
    name = company_id + "-" + report_end
    target = Path(out) / name
    target.mkdir(parents=True, exist_ok=False)
    (target / "request.json").write_text(json.dumps(request, ensure_ascii=False) + "\n", encoding="utf-8")
    (target / "input.txt").write_text(text, encoding="utf-8")
    (target / "context-measurement.json").write_text(json.dumps(measurement, indent=1) + "\n")
    metadata = {"record_type": "ISSUE_47_D02_DEV_INPUT", "company_id": company_id,
                "report_end": report_end, "contract": request["contract"],
                "request_id": request["request_id"], "ledger_digest": ledger_digest(request, policy),
                "provider_body_sha256": hashlib.sha256(body).hexdigest(),
                "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_document_id": request["filing"]["text_document_id"],
                "blocks": len(request["blocks"]), "must_decide": len(request["must_decide"]),
                "route_item_8_selection": route_item_8,
                "fits": measurement["fits"], "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (target / "metadata.json").write_text(json.dumps(metadata, indent=1) + "\n")
    print(name, metadata["blocks"], "blocks", metadata["must_decide"], "must decide",
          measurement.get("input_tokens"), "input tokens", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--position", action="append", required=True)
    arguments = parser.parse_args()
    for position in arguments.position:
        company_id, report_end = position.rsplit(":", 1)
        prepare(source_root=arguments.source_root, company_id=company_id,
                report_end=report_end, out=arguments.out)


if __name__ == "__main__":
    main()
