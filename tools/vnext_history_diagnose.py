"""Ask the loaded historical route implementation what it does with a position.

Purpose:
    Answer "why does this position have no Run" for the implementation and the
    sources present now. It is a diagnostic and is deliberately separate from
    the coverage summary: it runs the real route assembly, which reaches the
    metric calculator, and the summary's contract is that it computes no metric
    outcome in any mode.

    It reports only on the present. Whether a position was ever attempted, and
    what a past attempt did, is in the batch's own records and is read by
    ``tools/vnext_history_coverage.py --attempts-root``.

Call relationships:
    Developers and the Issue #47 evidence archive call this script. It calls
    ``scripts/vnext/historical_route_refusal.py``, which calls the historical
    route assembly. It performs no SEC or model request and creates no Run or
    publication.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vnext.historical_route_refusal import diagnose_route  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True)
    parser.add_argument("--report-end", required=True)
    parser.add_argument("--metric", action="append", dest="metrics", required=True,
                        help="Metric id; repeatable.")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")):
        selection = resolve_period_selection(repo_root=REPO_ROOT,
                                             company_id=arguments.company,
                                             report_end=arguments.report_end)
        rows = [diagnose_route(repo_root=REPO_ROOT, company_id=arguments.company,
                               metric_id=metric, period_selection=selection)
                for metric in arguments.metrics]
    body = {"record_type": "HISTORICAL_ROUTE_DIAGNOSIS_SET",
            "company_id": arguments.company, "report_end": arguments.report_end,
            "what_this_cannot_say": rows[0]["what_this_cannot_say"],
            "business_execution_invoked": True,
            "diagnoses": rows}
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(body, ensure_ascii=False, indent=1,
                                               sort_keys=True) + "\n", encoding="utf-8")
    for row in rows:
        print("%-5s %-34s %s" % (row["metric_id"], row["outcome"],
                                 (row["reason"] or "")[:100]))
    print("execution identity:", rows[0]["execution_identity"]["requirement_closure_hash"])
    print("this diagnosis runs the route assembly, so it invokes business execution;"
          " it says nothing about past attempts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
