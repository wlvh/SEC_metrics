"""Measure what the widened fiscal-year definition forms change on every saved annual report.

Usage: python3 measure_fiscal_labels.py <code tree> <data root> <out.json> [company ...]

Zero calls: network and DNS blocked. For each company and each target period
whose original is saved, the period is selected and its original input
prepared, the frozen inspection (through the DEI view) and the widened one are
both taken, and their status and label recorded. A period the frozen scan
resolved must come back as the same object; anything else is reported.
"""
import csv
import json
import socket
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

CODE, SOURCE_ROOT, OUT = (Path(p) for p in sys.argv[1:4])
ONLY = sys.argv[4:]
sys.path.insert(0, str(CODE / "scripts"))

from vnext import historical_annual_input as annual  # noqa: E402
from vnext import historical_fiscal_labels as successor  # noqa: E402
from vnext.historical_dei import inspect_prepared_fiscal_year_labels as frozen  # noqa: E402
from vnext.normal_history_plan import plan_historical_sources  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

companies = [row["company_id"] for row in csv.DictReader(
    (SOURCE_ROOT / "config/company_registry.csv").open(encoding="utf-8"))]
companies = [c for c in companies if not ONLY or c in ONLY]
rows, started = [], time.time()


def write(final=False):
    body = {"rows": rows, "seconds": int(time.time() - started)}
    if final:
        body.update(calls=[0, 0, 0], code_tree=str(CODE), data_root=str(SOURCE_ROOT))
    OUT.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")


with patch.object(socket.socket, "connect", side_effect=AssertionError("net")), \
        patch.object(socket, "getaddrinfo", side_effect=AssertionError("dns")):
    for company in companies:
        try:
            plan = plan_historical_sources(repo_root=SOURCE_ROOT, company_id=company, count=5)
        except Exception as error:  # noqa: BLE001 - measured, reported
            rows.append({"company_id": company, "stage": "PLAN",
                         "error": type(error).__name__ + ":" + str(error)[:300]})
            write()
            continue
        ready = set(plan["annual_identity_ready_report_dates"])
        for candidate in plan["target_candidates"]:
            report_end = candidate["report_date"]
            row = {"company_id": company, "report_end": report_end}
            if report_end not in ready:
                row.update(stage="ORIGINAL_NOT_SAVED")
                rows.append(row)
                continue
            try:
                selection = resolve_period_selection(repo_root=SOURCE_ROOT, company_id=company,
                                                     report_end=report_end)
                original = annual.prepare_original_historical_input(
                    repo_root=SOURCE_ROOT, company_id=company, period_selection=selection)
                old = frozen(repo_root=SOURCE_ROOT, prepared=original)["inspection"]
                new = successor.inspect_prepared_fiscal_year_labels(
                    repo_root=SOURCE_ROOT, prepared=original)["inspection"]
                row.update(stage="MEASURED",
                           frozen={"status": old["status"],
                                   "label": old["source_defined_fiscal_year"],
                                   "dei": old["dei_fiscal_year"],
                                   "leads": [lead["reason"] for lead in
                                             old["unsupported_definition_leads"]]},
                           widened={"status": new["status"],
                                    "label": new["source_defined_fiscal_year"],
                                    "leads": [lead["reason"] for lead in
                                              new["unsupported_definition_leads"]],
                                    "added": [{"kind": item["kind"],
                                               "labels": [p["fiscal_year"]
                                                          for p in item["mapping"]]}
                                              for item in new.get(
                                                  "definitions_read_by_the_widened_forms", [])]},
                           unchanged=new == old,
                           inspection_id_unchanged=new["inspection_id"] == old["inspection_id"])
            except Exception as error:  # noqa: BLE001 - per position
                row.update(stage="FAILED", error=type(error).__name__ + ":" + str(error)[:300],
                           where=[f.name for f in traceback.extract_tb(error.__traceback__)][-4:])
            rows.append(row)
            print(company, report_end, row["stage"], row.get("frozen", {}).get("status"),
                  row.get("widened", {}).get("status"), row.get("widened", {}).get("label"),
                  row.get("unchanged"), row.get("error", "")[:120], flush=True)
            write()
write(final=True)
print("DONE", int(time.time() - started), flush=True)
