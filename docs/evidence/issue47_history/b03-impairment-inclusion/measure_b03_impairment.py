"""Ask the base's B03 impairment checks of the historical route's B03 on every saved period.

Usage: python3 measure_b03_impairment.py <data root> <out.json> [company ...]

Zero calls: network and DNS blocked. For each company and each target period
whose original is saved, the historical zero-AI route resolves B03; where it
publishes a value from a direct D&A concept, the base's
``assess_direct_depreciation_scope`` is asked whether the filing's own segment
table footnotes impairment-related depreciation into the selected total, and
where it does, ``prove_exact_impairment_relation`` whether the cash-flow
statement tags the exact split. Both are asked with a case assembled from the
historical component's own fields; nothing here decides anything.
"""
import csv
import json
import socket
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
SOURCE_ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
ONLY = sys.argv[3:]

from vnext.b03_depreciation_scope import assess_direct_depreciation_scope  # noqa: E402
from vnext.b03_exact_impairment_relation import prove_exact_impairment_relation  # noqa: E402
from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric  # noqa: E402
from vnext.normal_history_plan import plan_historical_sources  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

companies = [row["company_id"] for row in csv.DictReader(
    (SOURCE_ROOT / "config/company_registry.csv").open(encoding="utf-8"))]
companies = [c for c in companies if not ONLY or c in ONLY]
rows, started = [], time.time()


def short(error):
    return type(error).__name__ + ":" + str(error)[:300]


def write(final=False):
    body = {"rows": rows, "seconds": int(time.time() - started)}
    if final:
        body["calls"] = [0, 0, 0]
    OUT.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")


with patch.object(socket.socket, "connect", side_effect=AssertionError("net")), \
        patch.object(socket, "getaddrinfo", side_effect=AssertionError("dns")):
    for company in companies:
        try:
            plan = plan_historical_sources(repo_root=SOURCE_ROOT, company_id=company, count=5)
        except Exception as error:  # noqa: BLE001 - measured, reported
            rows.append({"company_id": company, "stage": "PLAN", "error": short(error)})
            continue
        ready = set(plan["annual_identity_ready_report_dates"])
        for candidate in plan["target_candidates"]:
            report_end = candidate["report_date"]
            row = {"company_id": company, "report_end": report_end}
            if report_end not in ready:
                row["stage"] = "ORIGINAL_NOT_SAVED"
                rows.append(row)
                continue
            stage = "SELECTION"
            try:
                selection = resolve_period_selection(repo_root=SOURCE_ROOT, company_id=company,
                                                     report_end=report_end)
                stage = "ROUTE"
                component = resolve_historical_zero_ai_metric(
                    repo_root=SOURCE_ROOT, company_id=company, metric_id="B03",
                    period_selection=selection)
                result = component["result"]
                direct = [o for o in component["observations"]
                          if o["semantic_role"] == "depreciation_and_amortization"]
                row.update(publication=result["publication"], quality=result["quality"],
                           reason_code=result["reason_code"], result_id=result["result_id"],
                           value=None if result["value"] is None else str(result["value"]),
                           selected_da=[{"concept": o["source_binding"]["concept"],
                                         "value": str(o["value"])} for o in direct],
                           historical_scope=(component["selection"].get("depreciation_scope")
                                             or {}).get("status"))
                case = {"primary_metric_id": "B03", "results": {"B03": result},
                        "observations": component["observations"],
                        "source_proofs": component["source_proofs"],
                        "target_period": component["target_period"]}
                stage = "BASE_SCOPE"
                scoped = assess_direct_depreciation_scope(case=case, data_root=SOURCE_ROOT)
                row["base_scope_status"] = scoped["status"]
                row["base_scope_blocked"] = scoped["blocked"]
                if scoped["status"] == "SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT":
                    proof = scoped["impairment_inclusion_proof"]
                    row["inclusion"] = {"included_component": proof["included_component"],
                                        "footnote": " ".join(proof["footnote"]["text"].split())[:400],
                                        "selected_visible_total": proof["selected_visible_total"]}
                    stage = "BASE_EXACT"
                    try:
                        exact = prove_exact_impairment_relation(case=case, data_root=SOURCE_ROOT)
                        row["exact"] = {k: exact[k] for k in (
                            "selected_total_usd", "exact_impairment_depreciation_usd",
                            "arithmetically_remaining_da_usd", "proof_id")}
                    except Exception as error:  # noqa: BLE001 - the answer measured
                        row["exact"] = {"refused": short(error)}
                elif scoped["blocked"]:
                    row["scope_detail"] = {k: scoped.get(k) for k in ("selected_fact", "selected_label")}
                row["stage"] = "MEASURED"
            except Exception as error:  # noqa: BLE001 - per position
                row.update(stage="FAILED_AT_" + stage, error=short(error),
                           where=[f.name for f in traceback.extract_tb(error.__traceback__)][-4:])
            rows.append(row)
            print(company, report_end, row["stage"], row.get("publication"), row.get("value"),
                  row.get("base_scope_status"), json.dumps(row.get("exact"))[:160],
                  row.get("error", "")[:140], flush=True)
            write()
write(final=True)
print("DONE", int(time.time() - started), flush=True)
