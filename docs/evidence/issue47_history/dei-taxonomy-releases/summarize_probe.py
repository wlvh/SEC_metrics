"""Summarise run_probe.py outputs into run-probe-fy2021.json.

Usage: python3 summarize_probe.py <out.json> <probe.json> [<probe.json> ...]

Keeps, per position, what the probe measured and nothing it did not: the
stage reached, the Run's result (identity, quality, reason, value), the cold
read's status and result identity, and the DEI namespace rejections counted in
the creating process and in the cold-reading one, with their call chains.
"""
import collections
import json
import sys
from pathlib import Path


def main(out, paths):
    positions, chains = [], collections.Counter()
    for path in paths:
        probe = json.loads(Path(path).read_text(encoding="utf-8"))
        for row in probe["rows"]:
            cold = row.get("cold_read") or {}
            for chain, count in list(row["dei_chains"].items()) + list(
                    (cold.get("dei_chains") or {}).items()):
                chains[chain] += count
            positions.append({
                "company_id": row.get("company_id"), "report_end": row.get("report_end"),
                "metric_id": row["metric_id"], "stage": row["stage"],
                "result_id": row.get("result_id"), "quality": row.get("quality"),
                "reason_code": row.get("reason_code"),
                "value": None if row.get("value") is None else str(row["value"]),
                "error": row.get("error"), "where": row.get("where"),
                "cold_read_status": cold.get("status"),
                "cold_read_same_result": (cold.get("result_id") == row.get("result_id")
                                          if row["stage"] == "PUBLIC_ROW" else None),
                "dei_rejections_creating": sum(row["dei_chains"].values()),
                "dei_rejections_cold_read": sum((cold.get("dei_chains") or {}).values())})
    positions.sort(key=lambda p: (p["company_id"] or "", p["metric_id"] or ""))
    stages = collections.Counter(p["stage"] for p in positions)
    rows = [p for p in positions if p["stage"] == "PUBLIC_ROW"]
    summary = {
        "record_type": "ISSUE_47_DEI_FY2021_RUN_PROBE",
        "method": ("run_probe.py in a runtime tree carrying the registration patch: every "
                   "metric at the named period goes through install, native Run, freeze, public "
                   "row and a separate-process cold read, with every re.fullmatch rejection of a "
                   "DEI release namespace counted in both processes. Network and DNS blocked."),
        "positions": len(positions), "stages": dict(stages),
        "public_rows": len(rows),
        "with_value": sum(1 for p in rows if p["value"] is not None),
        "cold_reads_frozen_with_the_same_result": sum(
            1 for p in rows if p["cold_read_status"] == "FROZEN" and p["cold_read_same_result"]),
        "dei_rejections_total": sum(chains.values()),
        "dei_rejection_chains": dict(chains),
        "failures": [{k: p[k] for k in ("company_id", "metric_id", "stage", "error")}
                     for p in positions if p["stage"] != "PUBLIC_ROW"],
        "calls": [0, 0, 0],
        "rows": positions}
    Path(out).write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("positions", "stages", "public_rows", "with_value",
                                               "cold_reads_frozen_with_the_same_result",
                                               "dei_rejections_total")}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
