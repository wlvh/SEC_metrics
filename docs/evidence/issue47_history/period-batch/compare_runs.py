"""Compare the Runs two period experiments created, file by file.

Usage: python3 compare_runs.py <dir A> <dir B> <out.json>

For every run-* directory present in both: every file's bytes; where they
differ, the manifest's differing keys and whether the difference is confined
to the review decision (a text Run's system decision carries its creation
time). The row receipts' row and evidence are compared too.
"""
import hashlib
import json
import sys
from pathlib import Path

TIME_BOUND = {"review_decisions_file_hash", "audit_manifest_hash", "validation_file_hash"}


def files(run):
    return {p.relative_to(run).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(run.rglob("*")) if p.is_file()}


def main(a, b, out):
    a, b = Path(a), Path(b)
    report = {}
    for run in sorted(p.name for p in a.glob("run-*") if p.is_dir()):
        if not (b / run).is_dir():
            report[run] = {"only_in": str(a)}
            continue
        fa, fb = files(a / run), files(b / run)
        differing = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
        entry = {"files": len(fa), "differing_files": differing}
        if differing:
            ma = json.loads((a / run / "manifest.json").read_text())
            mb = json.loads((b / run / "manifest.json").read_text())
            keys = sorted(k for k in set(ma) | set(mb) if ma.get(k) != mb.get(k))
            entry["manifest_keys_differing"] = keys
            da = [json.loads(x) for x in (a / run / "review_decisions.jsonl").read_text().splitlines()] \
                if (a / run / "review_decisions.jsonl").exists() else []
            db = [json.loads(x) for x in (b / run / "review_decisions.jsonl").read_text().splitlines()] \
                if (b / run / "review_decisions.jsonl").exists() else []
            strip = lambda rows: [{k: v for k, v in r.items()
                                   if k not in ("decided_at_utc", "review_decision_id")}
                                  for r in rows]
            entry["decisions_equal_apart_from_time"] = strip(da) == strip(db)
            va = json.loads((a / run / "validation.json").read_text())
            vb = json.loads((b / run / "validation.json").read_text())
            for v in (va, vb):
                v.pop("validation_receipt_id", None)
                v.get("artifact_hashes", {}).pop("review_decisions.jsonl", None)
            entry["validation_equal_apart_from_the_decisions"] = va == vb
            entry["only_the_decision_time_differs"] = (
                set(differing) <= {"manifest.json", "review_decisions.jsonl", "validation.json"}
                and set(keys) <= TIME_BOUND and entry["decisions_equal_apart_from_time"]
                and entry["validation_equal_apart_from_the_decisions"])
        ra, rb = a / (run + ".row_receipt.json"), b / (run + ".row_receipt.json")
        if ra.exists() and rb.exists():
            xa, xb = json.loads(ra.read_text()), json.loads(rb.read_text())
            entry["row_equal"] = xa["row"] == xb["row"]
            entry["evidence_equal"] = xa["evidence"] == xb["evidence"]
        report[run] = entry
    summary = {"runs_compared": len(report),
               "identical": sum(1 for e in report.values() if e.get("differing_files") == []),
               "only_the_decision_time_differs": sum(1 for e in report.values()
                                                    if e.get("only_the_decision_time_differs")),
               "rows_and_evidence_equal": sum(1 for e in report.values()
                                              if e.get("row_equal") and e.get("evidence_equal"))}
    Path(out).write_text(json.dumps({"summary": summary, "runs": report}, indent=1,
                                    sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main(*sys.argv[1:4])
