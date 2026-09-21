"""Emit the Issue #47 historical coverage matrix and its status distribution.

Purpose:
    Fix the target denominator (companies x declared metrics x requested annual
    report ends) before any position is filled, and give every position exactly
    one status. It reads saved bytes only and makes no SEC or model request.

Call relationships:
    Developers and the Issue #47 evidence archive call this script. It calls
    ``scripts/vnext/historical_coverage.py``.
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

from vnext.historical_coverage import build_coverage_matrix  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", action="append", dest="companies",
                        help="Configured company_id; repeatable. Default: every company.")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--runs-root", type=Path,
                        help="Directory of frozen run directories. Outcomes are read "
                             "from their receipts; without it every implemented "
                             "position reports ROUTE_IMPLEMENTED_NOT_RUN.")
    parser.add_argument("--requirement-closure-hash",
                        help="Report receipts from this Requirement closure only. A "
                             "coordinate run under several closures has several "
                             "receipts; without this the position reports "
                             "RUN_RECEIPT_VERSION_AMBIGUOUS rather than picking one.")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")):
        matrix = build_coverage_matrix(repo_root=REPO_ROOT, company_ids=arguments.companies,
                                       years=arguments.years,
                                       runs_root=arguments.runs_root,
                                       requirement_closure_hash=(
                                           arguments.requirement_closure_hash))
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(matrix, ensure_ascii=False, indent=1,
                                               sort_keys=True) + "\n", encoding="utf-8")
    print("declared metrics %d, companies %d, requested years %d"
          % (matrix["declared_metric_count"], len(matrix["companies"]), matrix["requested_years"]))
    print("target frame positions %d, enumerated %d"
          % (matrix["target_frame_positions"], matrix["enumerated_positions"]))
    print("first blocking reason (NOT a count of remaining work per position):")
    for status, count in sorted(matrix["first_blocking_reason_counts"].items(),
                                key=lambda item: -item[1]):
        print("  %-38s %d" % (status, count))
    print("run receipts read %d (runs_root supplied: %s); this entry runs no metric"
          % (matrix["run_receipts_read"], matrix["runs_root_supplied"]))
    print("closure requested: %s"
          % (matrix["requested_requirement_closure_hash"] or "none - a coordinate with "
             "receipts under several closures reports RUN_RECEIPT_VERSION_AMBIGUOUS"))
    print("delivery layers (three separate facts, not one rate):")
    for name in ("native_run", "public_row", "content_acceptance"):
        print("  %-38s %d" % (name, matrix["delivery_layer_counts"][name]))
        for reason, count in sorted(matrix["delivery_layer_unproven_reasons"].get(name, {}).items(),
                                    key=lambda item: -item[1])[:4]:
            print("      not proven: %-28s %d" % (reason[:28], count))
    print("independent dimensions, each counted over the whole frame:")
    for name, count in sorted(matrix["dimension_counts"].items()):
        print("  %-38s %d" % (name, count))
    print("  %-38s %d" % ("missing BOTH a source and a route",
                          matrix["positions_missing_source_and_route"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
