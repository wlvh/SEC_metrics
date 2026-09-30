"""Build the D04 source and requests for pinned positions and count them. Zero calls.

Usage: python3 requests.py <restored source root> <out.json> company@report_end ...

Runs the historical route's own builders (``pinned_native_source``,
``pinned_requests``) on a root restored from the acquisition's export and
counts every request body with the pinned reference tokenizer, the count the
request builder compares with the model context. Records whether the document
entries carry ``single_object_bound`` and which units it names. Nothing is sent.
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
from vnext.historical_semantic_results import pinned_native_source, pinned_requests  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402


def main(root, out, positions):
    root, results = Path(root), {}
    policy = TransportPolicy.from_mapping(value={**TRANSPORT_FIELDS,
                                                 "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
    with checkpoint_replayed_once():
        for position in positions:
            company, end = position.split("@")
            started = time.time()
            try:
                selection = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
                source = pinned_native_source(repo_root=root, company_id=company, metric_id="D04",
                                              period_selection=selection)
                requests = []
                for request in pinned_requests(source):
                    body = request_body(request, policy)
                    measured = measure_request(body, require_reference=True)
                    requests.append({"units": len(request["units"]),
                                     "provider_body_bytes": len(body),
                                     "provider_body_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
                                     "reference_input_tokens": measured["input_tokens"],
                                     "planned_context_tokens": measured["context_tokens"],
                                     "fits_the_ceiling": measured["fits"]})
                bounds = [d["single_object_bound"] for d in source.get("documents", ())
                          if isinstance(d, dict) and "single_object_bound" in d]
                results[position] = {"semantic_source_id": source["semantic_source_id"],
                                     "single_object_bound": bounds, "requests": requests}
            except Exception as error:  # recorded, not hidden
                results[position] = {"error": type(error).__name__ + ":" + str(error)[:300]}
            results[position]["seconds"] = int(time.time() - started)
            print(position, json.dumps(results[position])[:600], flush=True)
    record = {"root_note": "restored from the committed export; not a data root the Runs use",
              "positions": results, "calls": [0, 0, 0]}
    Path(out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
