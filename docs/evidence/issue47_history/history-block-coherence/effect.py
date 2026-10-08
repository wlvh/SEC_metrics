"""What the block coherence rule moves on a source root: target periods, refreshes, remaining need.

Usage (from a tree whose journal registered SOURCE_ROOT):
    SOURCE_ROOT=<root> python3 effect.py <out.json>

For every company: each target period's metadata status and blocking reasons,
which periods can be read at all, the history blocks the catalog does not
trust (and why), the refresh rows the planner asks for, and the whole frame's
remaining acquisition need by dependency class. Run it once under the rule
before the change and once under the rule after it, on the same root; the
difference is the change's effect. Reads saved bytes only; zero calls.
"""
import json
import os
import socket
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.historical_source_acquisition import declared_frame  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once, plan_historical_sources  # noqa: E402
from vnext.projector import _load_registry  # noqa: E402

SOURCE_ROOT = Path(os.environ["SOURCE_ROOT"])


def conflicts(limitations):
    return [{"history_name": item["history_name"],
             "failed_checks": item.get("failed_checks", ["FROZEN_DATE_CHECK"]),
             "declared_filing_count": item.get("declared_filing_count"),
             "saved_filing_count": item.get("saved_filing_count"),
             "out_of_range_filings": len(item["out_of_range_filings"])}
            for item in limitations if item["kind"] == "HISTORY_SHARD_SNAPSHOT_CONFLICT"]


def company_effect(company_id):
    plan = plan_historical_sources(repo_root=SOURCE_ROOT, company_id=company_id, count=5)
    frame = declared_frame(repo_root=SOURCE_ROOT, company_id=company_id, years=5)
    due = {}
    for row in frame["requirements"]:
        if row["new_acquisition_required"]:
            key = row["dependency_class"] + ":" + row["acquisition_kind"]
            due[key] = due.get(key, 0) + 1
    limitations = list(plan["catalog_limitations"])
    for item in plan.get("predecessor_catalogs", []):
        limitations.extend(item["limitations"])
    return {
        "targets": [{"report_date": c.get("report_date"), "metadata_status": c["metadata_status"],
                     "metadata_blocking_reasons": c.get("metadata_blocking_reasons", [])}
                    for c in plan["target_candidates"]],
        "annual_identity_ready_report_dates": plan["annual_identity_ready_report_dates"],
        "untrusted_blocks": conflicts(limitations),
        "unsaved_blocks": sorted(item["history_name"] for item in limitations
                                 if item["kind"] == "HISTORY_SHARD_NOT_SAVED"),
        "snapshot_refresh": sorted(url.rsplit("/", 1)[-1] for url in plan["snapshot_refresh_urls"]),
        "frame_declared": len(frame["requirements"]),
        "frame_due_by_class": dict(sorted(due.items())),
        "frame_due": sum(due.values()),
        "event_declaration_limitations": len(frame["event_declaration_limitations"]),
        "governance_declaration_limitations": len(frame["governance_declaration_limitations"]),
    }


def main(out):
    result = {}
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")), \
            checkpoint_replayed_once():
        for company in _load_registry(repo_root=ROOT):
            company_id = company["company_id"]
            try:
                result[company_id] = company_effect(company_id)
            except (AssertionError, AttributeError, IndexError, KeyError, NameError, TypeError):
                raise  # a program fault is not a refusal
            except Exception as error:  # a refusal is part of the effect, named
                result[company_id] = {"refused": type(error).__name__ + ":" + str(error)[:300]}
            print(company_id, json.dumps({k: v for k, v in result[company_id].items()
                                          if k in ("annual_identity_ready_report_dates",
                                                   "snapshot_refresh", "frame_due", "refused")}),
                  flush=True)
    Path(out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
