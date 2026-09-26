"""How many model requests would D04 / B13 need at a pinned period? Zero calls.

The ordinary builders read "the latest annual input". Here the two annual
input functions they call are pointed at the pinned period's input, and the
request constructors #28 uses are run unchanged. Nothing is sent: the request
census and the pinned reference token measurement are all this counts.
"""
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from tests.vnext.test_normal_zero_ai_results import original_sources_only  # noqa: E402
from vnext import going_concern_source as gcs  # noqa: E402
from vnext import r6_semantic_source as r6  # noqa: E402
from vnext import historical_annual_input as hai  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402
from vnext.d04_native_assessment import native_source, requests_from_source  # noqa: E402
from vnext.continuous_request_context import FORMAT_VERSION  # noqa: E402


def pinned_inputs(company_id, report_end):
    selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                         report_end=report_end)
    v1 = hai.prepare_original_historical_input(repo_root=ROOT, company_id=company_id,
                                               period_selection=selection)
    v2 = hai.prepare_historical_annual_input(repo_root=ROOT, company_id=company_id,
                                             period_selection=selection)
    assert v2["original_input"] == v1
    return selection, v1, v2


def d04_requests(company_id, v1, v2):
    with patch.object(gcs, "prepare_saved_annual_input", lambda **_: v1), \
         patch.object(r6, "prepare_saved_annual_input", lambda **_: v2):
        source = r6.prepare_d04_semantic_source(repo_root=ROOT, company_id=company_id)
    native = native_source(source, request_context_format=FORMAT_VERSION,
                           complete_response_contract=True)
    return source, native, requests_from_source(native)


def b13_requests(company_id, v1, v2):
    from vnext import capacity_semantic_source as css
    from vnext.capacity_semantic_review import requests_from_source as b13_from
    with patch.object(gcs, "prepare_saved_annual_input", lambda **_: v1), \
         patch.object(r6, "prepare_saved_annual_input", lambda **_: v2):
        source = css.prepare_capacity_semantic_source(repo_root=ROOT, company_id=company_id,
                                                      request_context_format=FORMAT_VERSION)
    return source, b13_from(source)


def d03_requests(company_id, v1, v2):
    from vnext import r6_regulatory_semantics as d03
    with patch.object(gcs, "prepare_saved_annual_input", lambda **_: v1), \
         patch.object(r6, "prepare_saved_annual_input", lambda **_: v2):
        source = d03.prepare_regulatory_semantic_source(repo_root=ROOT, company_id=company_id,
                                                        request_context_format=FORMAT_VERSION)
    return source, d03.requests_from_source(source)


def main():
    positions = [tuple(p.split(":")) for p in sys.argv[2:]]
    out = Path(sys.argv[1])
    rows = json.loads(out.read_text()) if out.exists() else {}
    with original_sources_only():
        for company_id, report_end, metric in positions:
            key = "%s:%s:%s" % (company_id, report_end, metric)
            if key in rows:
                continue
            started = time.time()
            try:
                selection, v1, v2 = pinned_inputs(company_id, report_end)
                if metric == "D04":
                    source, native, requests = d04_requests(company_id, v1, v2)
                elif metric == "D03":
                    source, requests = d03_requests(company_id, v1, v2)
                else:
                    source, requests = b13_requests(company_id, v1, v2)
                rows[key] = {
                    "status": "MEASURED",
                    "filing_accessions": [d["filing"]["accessionNumber"] for d in source["documents"]],
                    "documents": len(source["documents"]),
                    "units": len(source["units"]),
                    "requests": len(requests),
                    "units_per_request": [len(r["units"]) for r in requests],
                    "required_candidate_assessments": sum(
                        len(r.get("required_candidate_assessments", [])) for r in requests),
                    "semantic_source_id": source["semantic_source_id"],
                    "request_ids": [r["request_id"] for r in requests],
                    "seconds": round(time.time() - started, 1)}
            except Exception as error:  # the probe records a refusal by its own words
                rows[key] = {"status": "REFUSED", "error_type": type(error).__name__,
                             "error": str(error)[:400],
                             "seconds": round(time.time() - started, 1)}
            out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
            print(key, rows[key]["status"], rows[key].get("requests"), rows[key].get("error", "")[:160],
                  flush=True)


if __name__ == "__main__":
    main()
