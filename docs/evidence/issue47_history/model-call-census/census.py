"""What the historical frame's model-reviewed metrics would ask for, request by request. Zero calls.

Usage: python3 census.py <restored source root> <frame-plan.tsv> <out.json>

For every reachable frame period (the batch's plan: case, company, report end)
this builds, with the historical route's own request builders and on a root
restored from the acquisition's export:

- D04: every request the pinned complete source partitions into
  (``pinned_native_source`` + ``pinned_requests``);
- E01: the window's content-confirmation request (``e01_confirmation_request``),
  or the route's reason no request exists (no candidate item, a source gap);
- D02: the Item 8 legal-disclosure review request (``d02_review_request``).

Each request body is counted with the pinned reference tokenizer, the count the
live path compares with the service's own. A D04 position listed in
``awaiting_issue_28.json`` (the owner's option A for the latest year) is not
built: #47 sends no call for it. Nothing here is a grant; the approved
requests are the 35 an owner comment names, and the digests below move with
the code (see ``../d04-single-object-bound/``).
"""
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "docs/evidence/issue47_history/model-egress"))

from measure_d04_requests import TRANSPORT_FIELDS  # noqa: E402
from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy  # noqa: E402
from vnext.continuous_request_context import measure_request  # noqa: E402
from vnext.continuous_semantic_calls import request_body  # noqa: E402
from vnext.historical_model_calls import ledger_digest  # noqa: E402
from vnext.historical_semantic_results import pinned_native_source, pinned_requests  # noqa: E402
from vnext.historical_text_input import d02_review_request  # noqa: E402
from vnext.historical_zero_ai_results import e01_confirmation_request  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

AWAITING = REPO / "docs/evidence/issue47_history/awaiting_issue_28.json"


def counted(request, policy):
    body = request_body(request, policy)
    measured = measure_request(body, require_reference=True)
    return {"ledger_digest": ledger_digest(request, policy), "provider_body_bytes": len(body),
            "provider_body_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
            "reference_input_tokens": measured["input_tokens"],
            "planned_context_tokens": measured["context_tokens"], "fits_the_ceiling": measured["fits"]}


def attempt(build):
    started = time.time()
    try:
        out = build()
    except Exception as error:  # recorded, not hidden: the route's own named refusal
        out = {"no_request": type(error).__name__ + ":" + str(error)[:300]}
    out["seconds"] = int(time.time() - started)
    return out


def main(root, plan, out):
    root = Path(root)
    policy = TransportPolicy.from_mapping(value={**TRANSPORT_FIELDS,
                                                 "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
    awaiting = {(p["company_id"], p["report_end"]) for p in
                json.loads(AWAITING.read_text(encoding="utf-8"))["positions"] if p["metric_id"] == "D04"}
    periods = [line.split("\t")[:3] for line in Path(plan).read_text(encoding="utf-8").splitlines() if line]
    rows = []
    with checkpoint_replayed_once():
        for case, company, end in periods:
            row = {"case": case, "company_id": company, "report_end": end}
            try:
                selection = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
            except Exception as error:  # recorded, not hidden
                row["period_not_selected"] = type(error).__name__ + ":" + str(error)[:300]
                rows.append(row)
                continue

            def d04():
                if (company, end) in awaiting:
                    return {"awaiting_issue_28_adoption": True}
                source = pinned_native_source(repo_root=root, company_id=company, metric_id="D04",
                                              period_selection=selection)
                bounds = [d["single_object_bound"] for d in source["documents"] if "single_object_bound" in d]
                return {"requests": [counted(r, policy) for r in pinned_requests(source)],
                        "single_object_bound": bounds}

            def e01():
                request, _ = e01_confirmation_request(repo_root=root, company_id=company,
                                                      period_selection=selection)
                return {"requests": [counted(request, policy)], "items": len(request["items"])}

            def d02():
                request, _ = d02_review_request(repo_root=root, company_id=company, period_selection=selection)
                return {"requests": [counted(request, policy)], "blocks": len(request["blocks"]),
                        "must_decide": len(request["must_decide"])}

            row.update(D04=attempt(d04), E01=attempt(e01), D02=attempt(d02))
            rows.append(row)
            print(case, {m: (len(row[m].get("requests", [])),
                             sum(r["reference_input_tokens"] for r in row[m].get("requests", [])),
                             row[m].get("no_request", "")[:80]) for m in ("D04", "E01", "D02")}, flush=True)
    totals = {}
    for metric in ("D04", "E01", "D02"):
        requests = [r for row in rows for r in row.get(metric, {}).get("requests", [])]
        totals[metric] = {"requests": len(requests),
                          "reference_input_tokens": sum(r["reference_input_tokens"] for r in requests),
                          "all_fit": all(r["fits_the_ceiling"] for r in requests),
                          "positions_with_requests": sum(1 for row in rows if row.get(metric, {}).get("requests")),
                          "positions_without": sum(1 for row in rows if "no_request" in row.get(metric, {}))}
    record = {"record_type": "ISSUE_47_MODEL_CALL_CENSUS", "calls": [0, 0, 0],
              "root_note": "restored from the committed export; not a data root the Runs use",
              "plan": [p[0] for p in periods], "totals": totals, "positions": rows}
    Path(out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
