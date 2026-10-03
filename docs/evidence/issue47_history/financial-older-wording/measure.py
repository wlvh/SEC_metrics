"""Measure the financial witnesses' older-wording successors on the bank's five annual reports.

For each report (FY2021-FY2024 from the acquisition's export, FY2025 from the
checkout) and each of A03, A04, A11, A12 it runs the frozen inspector through
the release-aware view and the route's inspector (the frozen one first, the
older wording only where it does not resolve); for A09 it runs the HTML
fallback both ways. It records whether each resolves, the value, whether the
route's answer is the frozen answer itself, and the forms named. Zero calls.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/financial-older-wording/measure.py <output.json>
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from tools.acceptance_readings import saved_bytes  # noqa: E402
from vnext import historical_financial_wording as wording  # noqa: E402
from vnext import financial_relationships as frozen_relationships  # noqa: E402
from vnext.canonical import sha256_bytes  # noqa: E402
from vnext.historical_dei import overrides_of, release_aware  # noqa: E402
from vnext.normal_source_authority import ROOT  # noqa: E402

REPORTS = {
    2021: "evidence/request_attempts/7c/7c58f18f4348ede74dea11e95de81ff18634f45c50f22f6d1dccdd8abf36d478/jpm-20211231.htm",
    2022: "evidence/request_attempts/ce/ce5a7e360b2834d0e0eaa0b7872b64fee7f91f4b0696eb4a7fc2c4c83f42c7cb/jpm-20221231.htm",
    2023: "evidence/request_attempts/8b/8b49cc2426efed4b668d719014dd937ca10e5984120f18695c29dd37730ba301/jpm-20231231.htm",
    2024: "evidence/request_attempts/bd/bddc8acf8dfcb88885679b801ccf51e1a5934cf683b2935b6362e10397ac3ad4/jpm-20241231.htm",
    2025: "evidence/accession_materials/jpmorgan_chase_19617_000162828026008131/jpm-20251231.htm",
}
CIK = "0000019617"
ROUTE = {"A03": wording.inspect_lcr_disclosed_fact, "A04": wording.inspect_nim_relationships,
         "A11": wording.inspect_aum_balance, "A12": wording.inspect_total_var}


def _value(metric, fact):
    if not wording._resolved(metric, fact):
        return None
    if metric == "A04":
        return fact["relations"][0]["rate_check"]["disclosed_ratio"]
    if metric == "A12":
        return fact["totals"][0]["value"]["canonical_value"]
    return fact["value"]


def main():
    out = Path(sys.argv[1])
    older_html = overrides_of(wording._OLDER["A09"])["inspect_nonaccrual_loan_ratio"]
    frozen_html = release_aware(frozen_relationships.inspect_nonaccrual_loan_ratio)
    rows = []
    for year, relative in REPORTS.items():
        raw = saved_bytes(repo_root=REPO, relative=relative)
        arguments = {"repo_root": ROOT, "source_bytes": raw,
                     "expected_source_sha256": sha256_bytes(content=raw), "expected_cik": CIK,
                     "target_period": {"fiscal_year": year, "period_start": "%d-01-01" % year,
                                       "period_end": "%d-12-31" % year}}
        for metric, route in ROUTE.items():
            started = time.time()
            frozen = wording._FROZEN[metric](**arguments)
            got = route(**arguments)
            rows.append({"fiscal_year": year, "metric_id": metric, "source": relative,
                         "source_sha256": arguments["expected_source_sha256"],
                         "frozen_resolved": wording._resolved(metric, frozen),
                         "frozen_value": _value(metric, frozen),
                         "route_resolved": wording._resolved(metric, got), "route_value": _value(metric, got),
                         "route_answer_is_the_frozen_answer": got == frozen,
                         "older_wording": got.get("historical_older_wording"),
                         "seconds": round(time.time() - started, 1)})
            print(json.dumps(rows[-1]), flush=True)
        started = time.time()
        frozen, got = frozen_html(**arguments), older_html(**arguments)
        rows.append({"fiscal_year": year, "metric_id": "A09", "part": "HTML_FALLBACK_ONLY",
                     "source": relative, "source_sha256": arguments["expected_source_sha256"],
                     "frozen_resolved": frozen["status"] == wording.RESOLVED,
                     "frozen_value": frozen["value"] if frozen["status"] == wording.RESOLVED else None,
                     "older_resolved": got["status"] == wording.RESOLVED,
                     "older_value": got["value"] if got["status"] == wording.RESOLVED else None,
                     "older_answer_is_the_frozen_answer": got == frozen,
                     "older_dispositions": sorted({item["disposition"] for item in got["candidate_census"]}),
                     "seconds": round(time.time() - started, 1)})
        print(json.dumps(rows[-1]), flush=True)
    out.write_text(json.dumps({"record_type": "ISSUE_47_FINANCIAL_OLDER_WORDING_MEASUREMENT",
                               "rule": wording.RULE, "rows": rows,
                               "calls": {"provider": 0, "paid": 0, "sec": 0}},
                              indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
