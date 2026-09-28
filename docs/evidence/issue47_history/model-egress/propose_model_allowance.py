"""Write the model-call approval the owner would post, and check it with the real gate.

The approval restates what a #47 model allowance grants - the cap, the ledger
root, the scope by grant, the exact requests each grant names, the fixed
transport and retry policy, and the id of the sealed offline verification the
calls must run on. Its numbers are read, not typed: the cap is the number of
requests measured for the proposed positions - D04's
(d04-request-measurement.json), E01's
(../e01-content-confirmed/request-measurement.json) and D02's
(../d02-item-8-review/request-measurement.json), grants that share the ledger
and the cap and borrow nothing else from each other - and the receipt id is
the sealed offline-verification.json's.

Each grant names the ledger digest of every request it allows. They are
computed here by ``planned_request_digests`` - the pinned source, its
partition into requests and ``ledger_digest``, the functions a claim uses -
and must equal the digests the three measurements recorded, so a request whose
prompt, contract or source bytes changed after it was measured is a different
digest the proposal refuses to write rather than one the approval silently
names.

Before anything is written the proposal is registered in a temporary tree as
if the owner had posted it (a fixture comment by the approver, unedited),
through register_model_approval and model_allowance - the functions the live
path uses - and every proposed request must be inside a grant that names it,
while each neighbouring position is refused, a request of one granted position
asked at another is refused, and a digest no grant names is refused at every
granted position. A proposal the gate would not accept is not written.

Nothing here posts to GitHub, reads the owner's ledger or makes a call.

Usage (from the repository root, after the verification is sealed):
    python3 docs/evidence/issue47_history/model-egress/propose_model_allowance.py
"""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
HERE = "docs/evidence/issue47_history/model-egress/"
MEASUREMENT = HERE + "d04-request-measurement.json"
E01_MEASUREMENT = "docs/evidence/issue47_history/e01-content-confirmed/request-measurement.json"
D02_MEASUREMENT = "docs/evidence/issue47_history/d02-item-8-review/request-measurement.json"
LEDGER_ROOT = "/Users/lyuhongwang/.local/state/sec_metrics/issue47-historical-model-v1"
# The fixed transport a #47 model allowance must name (historical_model_calls
# checks every field against its own constants and the adapter's host).
TRANSPORT = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
             "region": "provider-managed-no-residency-guarantee",
             "retention": "provider-managed; no zero-retention claim",
             "data_use": "provider-managed; no training or data-use guarantee",
             "timeout_seconds": 120, "retry_count": 0, "maximum_payload_bytes": 8388608,
             "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}
GRANTS = [
    {"grant": "D04_MARRIOTT_FY2023_FY2024", "metric_ids": ["D04"],
     "company_ids": ["marriott_international"],
     "earliest_report_end": "2023-12-31", "latest_report_end": "2024-12-31"},
    {"grant": "D04_PARAMOUNT_PREDECESSOR_FY2024", "metric_ids": ["D04"],
     "company_ids": ["paramount_skydance_paramount_global"],
     "earliest_report_end": "2024-12-31", "latest_report_end": "2024-12-31"},
    # E01: each window with candidate items, and no other. Grouped where the
    # windows share a period end, so each grant admits exactly its windows.
    {"grant": "E01_FY2025_CALENDAR_WINDOWS", "metric_ids": ["E01"],
     "company_ids": ["ford_motor_company", "lumen_technologies", "marriott_international",
                     "pfizer", "southwest_airlines"],
     "earliest_report_end": "2025-12-31", "latest_report_end": "2025-12-31"},
    {"grant": "E01_MACYS_FY2025", "metric_ids": ["E01"], "company_ids": ["macys"],
     "earliest_report_end": "2026-01-31", "latest_report_end": "2026-01-31"},
    {"grant": "E01_PARAMOUNT_PREDECESSOR_FY2024", "metric_ids": ["E01"],
     "company_ids": ["paramount_skydance_paramount_global"],
     "earliest_report_end": "2024-12-31", "latest_report_end": "2024-12-31"},
    # D02: every saved D02 position, the Item 8 review of each filing. Grouped
    # by period end so each grant admits exactly its positions.
    {"grant": "D02_FY2025_CALENDAR", "metric_ids": ["D02"],
     "company_ids": ["enphase_energy", "ford_motor_company", "lumen_technologies",
                     "marriott_international", "paramount_skydance_paramount_global", "pfizer",
                     "southwest_airlines"],
     "earliest_report_end": "2025-12-31", "latest_report_end": "2025-12-31"},
    {"grant": "D02_FISCAL_JANUARY_2026", "metric_ids": ["D02"], "company_ids": ["macys", "salesforce"],
     "earliest_report_end": "2026-01-31", "latest_report_end": "2026-01-31"},
    {"grant": "D02_MARRIOTT_FY2023_FY2024", "metric_ids": ["D02"],
     "company_ids": ["marriott_international"],
     "earliest_report_end": "2023-12-31", "latest_report_end": "2024-12-31"},
    {"grant": "D02_PARAMOUNT_PREDECESSOR_FY2024", "metric_ids": ["D02"],
     "company_ids": ["paramount_skydance_paramount_global"],
     "earliest_report_end": "2024-12-31", "latest_report_end": "2024-12-31"}]
# Positions next to the granted ones that the scope must refuse: other periods,
# the windows with no request today, and each metric at the other's positions.
REFUSED = [("D04", "marriott_international", "2025-12-31"),
           ("D04", "marriott_international", "2022-12-31"),
           ("D04", "paramount_skydance_paramount_global", "2023-12-31"),
           ("D04", "paramount_skydance_paramount_global", "2025-12-31"), ("D04", "pfizer", "2024-12-31"),
           ("D04", "ford_motor_company", "2025-12-31"),
           ("E01", "marriott_international", "2023-12-31"),
           ("E01", "marriott_international", "2024-12-31"),
           ("E01", "paramount_skydance_paramount_global", "2025-12-31"),
           ("E01", "enphase_energy", "2025-12-31"), ("E01", "salesforce", "2026-01-31"),
           ("E01", "macys", "2025-01-31"), ("E01", "ford_motor_company", "2024-12-31"),
           ("D02", "marriott_international", "2022-12-31"), ("D02", "ford_motor_company", "2024-12-31"),
           ("D02", "jpmorgan_chase", "2025-12-31"), ("D02", "salesforce", "2025-01-31"),
           ("D02", "paramount_skydance_paramount_global", "2023-12-31")]


def _covering_grant(metric, company, end):
    """The one proposed grant a position falls in; a position in none or two is not proposed."""
    covering = [grant["grant"] for grant in GRANTS
                if metric in grant["metric_ids"] and company in grant["company_ids"]
                and grant["earliest_report_end"] <= end <= grant["latest_report_end"]]
    if len(covering) != 1:
        raise SystemExit("A_POSITION_IS_NOT_IN_EXACTLY_ONE_GRANT:" + metric + ":" + company + ":"
                         + end + ":" + ",".join(covering))
    return covering[0]


def _planned(calls, resolve_period_selection, transport, measured, e01, d02,
             positions):
    """Every proposed request's ledger digest, computed now and held to what was measured."""
    # Every measurement records the digest of the exact bytes each request
    # sends (historical_model_calls.ledger_digest), for all three contracts.
    recorded_by_metric = {
        "D04": {key: sorted(request["ledger_digest"] for request in row["requests"])
                for key, row in measured["positions"].items()},
        "E01": {row["company_id"] + ":" + row["report_end"]: [row["ledger_digest"]]
                for row in e01["windows"] if "ledger_digest" in row},
        "D02": {row["company_id"] + ":" + row["report_end"]: [row["ledger_digest"]]
                for row in d02["positions"]}}
    planned = {}
    for metric, company, end in positions:
        selection = resolve_period_selection(repo_root=REPO, company_id=company, report_end=end)
        digests = sorted(calls.planned_request_digests(company_id=company, metric_id=metric,
                                                       period_selection=selection,
                                                       transport=transport))
        recorded = recorded_by_metric[metric][company + ":" + end]
        if digests != sorted(recorded):
            raise SystemExit("THE_REQUESTS_ARE_NOT_THE_MEASURED_ONES:" + metric + ":" + company
                             + ":" + end)
        planned[(metric, company, end)] = digests
    every = [digest for digests in planned.values() for digest in digests]
    if len(every) != len(set(every)):
        raise SystemExit("TWO_POSITIONS_SHARE_A_REQUEST_DIGEST")
    return planned


def main():
    from vnext import historical_model_calls as calls
    from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST
    from vnext.historical_source_acquisition import (APPROVED_BODY_PATH, POLICY_PATH,
                                                     TRUSTED_APPROVER)
    from vnext.normal_period_selection import resolve_period_selection
    measured = json.loads((REPO / MEASUREMENT).read_text(encoding="utf-8"))
    e01 = json.loads((REPO / E01_MEASUREMENT).read_text(encoding="utf-8"))
    d02 = json.loads((REPO / D02_MEASUREMENT).read_text(encoding="utf-8"))
    positions = sorted([("D04", *key.rsplit(":", 1)) for key in measured["positions"]]
                       + [("E01", row["company_id"], row["report_end"]) for row in e01["windows"]
                          if "request_id" in row]
                       + [("D02", row["company_id"], row["report_end"]) for row in d02["positions"]])
    requests = {"D04": measured["totals"]["requests"], "E01": e01["totals"]["requests"],
                "D02": d02["totals"]["requests"]}
    if sum(1 for position in positions if position[0] == "E01") != requests["E01"]:
        raise SystemExit("E01_WINDOWS_AND_REQUESTS_DISAGREE")
    total = sum(requests.values())
    receipt = json.loads((REPO / calls.WIRING_RECEIPT_PATH).read_text(encoding="utf-8"))
    if not receipt.get("all_checks_passed"):
        raise SystemExit("THE_OFFLINE_VERIFICATION_IS_NOT_SEALED_AS_PASSING")
    transport = {**TRANSPORT, "endpoint_host": _DEEPSEEK_ENDPOINT_HOST}
    planned = _planned(calls, resolve_period_selection, transport, measured, e01, d02,
                       positions)
    if sum(len(digests) for digests in planned.values()) != total:
        raise SystemExit("THE_PLANNED_REQUESTS_ARE_NOT_THE_CAP")
    named = {grant["grant"]: [] for grant in GRANTS}
    for (metric, company, end), digests in planned.items():
        named[_covering_grant(metric, company, end)].extend(digests)
    if any(not digests for digests in named.values()):
        raise SystemExit("A_GRANT_NAMES_NO_REQUEST")
    grants = [{**grant, "request_digests": sorted(named[grant["grant"]])} for grant in GRANTS]
    scope = {"purposes": [calls.PURPOSE], "metric_ids": sorted(requests),
             "company_ids": sorted({company for grant in GRANTS for company in grant["company_ids"]}),
             "earliest_report_end": min(grant["earliest_report_end"] for grant in GRANTS),
             "latest_report_end": max(grant["latest_report_end"] for grant in GRANTS),
             "grants": grants}
    body = {"record_type": calls.DELEGATION_TYPE, "requirement_id": calls.REQUIREMENT_ID,
            "maximum_additional_provider_paid_sec_calls": [total, total, 0],
            "budget_root": LEDGER_ROOT, "scope": scope,
            "transport": transport,
            "retry_policy": dict(calls.FIXED_RETRY_POLICY),
            "model_wiring_receipt_id": receipt["receipt_id"],
            "production_authorized": False}
    text = json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True)
    url = "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-1000000001"
    comment = {"id": 1000000001, "html_url": url,
               "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
               "user": {"login": TRUSTED_APPROVER, "id": 0, "type": "User"},
               "author_association": "OWNER", "body": text,
               "created_at": "2026-09-27T00:00:00Z", "updated_at": "2026-09-27T00:00:00Z"}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / calls.APPROVAL_BODY_PATH).parent.mkdir(parents=True)
        (root / calls.APPROVAL_BODY_PATH).write_text(text, encoding="utf-8")
        # The SEC allowance the owner is registering beside this one, so the
        # gate's check that the two ledgers neither coincide nor nest is made
        # against the SEC root actually proposed.
        (root / "config").mkdir()
        sec_root = json.loads((REPO / APPROVED_BODY_PATH).read_text(encoding="utf-8"))["budget_root"]
        (root / POLICY_PATH).write_text(json.dumps({"budget_root": sec_root}), encoding="utf-8")
        registered = calls.register_model_approval(repo_root=root, comment_url=url,
                                                   reader=lambda path: comment)
        allowance = calls.model_allowance(repo_root=root, delegation_reader=lambda path: comment)
        inside = {metric + ":" + company + ":" + end: {digest: calls.request_in_scope(
            allowance=allowance, metric_id=metric, company_id=company, report_end=end,
            request_digest=digest) for digest in planned[(metric, company, end)]}
            for metric, company, end in positions}
        # A request of one granted position asked at the next one, and a digest
        # no grant names asked at every granted position: both must be refused.
        order = list(planned)
        unnamed = "sha256:" + "f" * 64
        refused_requests = {}
        for index, (metric, company, end) in enumerate(order):
            other = order[(index + 1) % len(order)]
            for label, digest in (("REQUEST_OF_" + ":".join(other), planned[other][0]),
                                  ("UNNAMED_DIGEST", unnamed)):
                try:
                    calls.request_in_scope(allowance=allowance, metric_id=metric,
                                           company_id=company, report_end=end,
                                           request_digest=digest)
                except calls.HistoricalModelCallError as error:
                    refused_requests[metric + ":" + company + ":" + end + " <- " + label] = str(error)
                else:
                    raise SystemExit("A_REQUEST_NO_GRANT_NAMES_IS_INSIDE_THE_SCOPE:" + metric + ":"
                                     + company + ":" + end + ":" + label)
        refused = {}
        for metric, company, end in REFUSED:
            try:
                calls.request_in_scope(allowance=allowance, metric_id=metric, company_id=company,
                                       report_end=end)
            except calls.HistoricalModelCallError as error:
                refused[metric + ":" + company + ":" + end] = str(error)
            else:
                raise SystemExit("A_NEIGHBOURING_POSITION_IS_INSIDE_THE_SCOPE:" + metric + ":"
                                 + company + ":" + end)
    (REPO / calls.APPROVAL_BODY_PATH).write_text(text, encoding="utf-8")
    proposal = {"record_type": "ISSUE_47_MODEL_ALLOWANCE_PROPOSAL", "not_an_approval": True,
                "approval_body_path": calls.APPROVAL_BODY_PATH,
                "approval_body_sha256": registered["delegation_body_sha256"],
                "limits_from": [MEASUREMENT, E01_MEASUREMENT, D02_MEASUREMENT],
                "requests_measured": requests,
                "request_digests_by_grant": {grant["grant"]: grant["request_digests"]
                                             for grant in grants},
                "model_wiring_receipt_id": receipt["receipt_id"],
                "checked_by_the_real_gate_in_a_temporary_tree": {
                    "registered": registered["status"], "requests_inside_a_grant": inside,
                    "neighbouring_positions_refused": refused,
                    "requests_no_grant_names_refused": refused_requests},
                "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (REPO / HERE / "proposed-model-allowance.json").write_text(
        json.dumps(proposal, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"approval_body_sha256": proposal["approval_body_sha256"],
                      "limits": body["maximum_additional_provider_paid_sec_calls"],
                      "receipt_id": receipt["receipt_id"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
