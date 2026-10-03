"""Measure D01's heading count on every saved annual report reachable in a data root.

Usage: python3 measure_d01_bound.py <code tree> <data root> <out.json>

Zero calls: network and DNS blocked. For each company and each target period
whose original is saved, the period is selected, D01's pinned input prepared,
and the route's own successor preparation run; the frozen heading selector is
asked for its headings on each document. Records the heading count, the
rendered length (items joined by one newline, as ORDERED_NEWLINE_V1 does), and
what the route's candidate creation answers under the Spec it is routed to.
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
sys.path.insert(0, str(CODE / "scripts"))

from vnext.historical_results import TEXT_SPEC_PATHS  # noqa: E402
from vnext.historical_spec_revision import compile_historical_spec_file  # noqa: E402
from vnext.historical_text_input import prepare_historical_business_text_input  # noqa: E402
from vnext.historical_text_results import text_api  # noqa: E402
from vnext import historical_risk_results as successor  # noqa: E402
from vnext.normal_history_plan import plan_historical_sources  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402
from vnext.risk_signals import risk_factor_headings  # noqa: E402

ONLY = sys.argv[4:]
companies = [row["company_id"] for row in csv.DictReader(
    (SOURCE_ROOT / "config/company_registry.csv").open(encoding="utf-8"))]
companies = [c for c in companies if not ONLY or c in ONLY]
spec = compile_historical_spec_file(repo_root=CODE, repo_relative_path=TEXT_SPEC_PATHS["D01"],
                                    dependency_specs={})
rows, started = [], time.time()


def write(final=False):
    body = {"rows": rows, "seconds": int(time.time() - started)}
    if final:
        body.update(spec_path=TEXT_SPEC_PATHS["D01"], calls=[0, 0, 0])
    OUT.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")


with patch.object(socket.socket, "connect", side_effect=AssertionError("net")), \
        patch.object(socket, "getaddrinfo", side_effect=AssertionError("dns")):
    for company in companies:
        try:
            plan = plan_historical_sources(repo_root=SOURCE_ROOT, company_id=company, count=5)
        except Exception as error:  # noqa: BLE001 - measured, reported
            rows.append({"company_id": company, "stage": "PLAN",
                         "error": type(error).__name__ + ":" + str(error)[:300]})
            continue
        ready = set(plan["annual_identity_ready_report_dates"])
        for candidate in plan["target_candidates"]:
            report_end = candidate["report_date"]
            row = {"company_id": company, "report_end": report_end,
                   "target_ordinal": candidate["target_ordinal"]}
            if report_end not in ready:
                row.update(stage="ORIGINAL_NOT_SAVED",
                           metadata_status=candidate["metadata_status"])
                rows.append(row)
                continue
            stage = "SELECTION"
            try:
                selection = resolve_period_selection(repo_root=SOURCE_ROOT, company_id=company,
                                                     report_end=report_end)
                stage = "INPUT"
                prepared = prepare_historical_business_text_input(
                    repo_root=SOURCE_ROOT, company_id=company, metric_id="D01",
                    period_selection=selection)
                row["input_status"] = prepared.get("status")
                arguments = prepared.get("text_arguments")
                if not arguments:
                    row.update(stage="INPUT_NOT_READY",
                               reasons=prepared.get("reasons") or prepared.get("reason_code"))
                    rows.append(row)
                    continue
                stage = "DOCUMENTS"
                documents, _ = successor.prepare_text_sources(compiled_spec=spec, **arguments)
                counts = []
                for document in documents.values():
                    proposal = risk_factor_headings(document=document)
                    texts = [heading["text"] for heading in proposal["headings"]]
                    counts.append({"headings": len(texts),
                                   "rendered_chars": sum(map(len, texts)) + max(len(texts) - 1, 0),
                                   "longest_heading_chars": max(map(len, texts), default=0),
                                   "proposal_status": proposal["status"],
                                   "proposal_reasons": proposal["reasons"]})
                row["documents"] = counts
                stage = "CANDIDATE"
                api, _ = text_api("D01")
                try:
                    made = api.create_deterministic_text_candidate(compiled_spec=spec, **arguments)
                    row["candidate"] = {"selected": len(made["selected"])}
                except Exception as error:  # noqa: BLE001 - the answer being measured
                    row["candidate"] = {"refused": type(error).__name__ + ":" + str(error)[:200]}
                row["stage"] = "MEASURED"
            except Exception as error:  # noqa: BLE001 - per position
                row.update(stage="FAILED_AT_" + stage,
                           error=type(error).__name__ + ":" + str(error)[:300],
                           where=[f.name for f in traceback.extract_tb(error.__traceback__)][-4:])
            rows.append(row)
            print(company, report_end, row["stage"],
                  [c["headings"] for c in row.get("documents", [])], row.get("candidate"),
                  row.get("error", "")[:120], flush=True)
            write()
write(final=True)
print("DONE", int(time.time() - started), flush=True)
