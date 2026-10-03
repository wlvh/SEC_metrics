"""After the port: every D01 filing of a batch rebuilt with the refusal in place.

Usage: python3 measure_after.py <runs root> <source root> <out.json>

For each D01 Run under the runs root, the filing is rebuilt from the Run's own
SOURCE_REFERENCE and RAW_BLOB records and the saved bytes under the source root
with D01's successor builder as it stands now, which refuses a heading the
filing runs over a page (D01_MULTISPAN_HEADING_UNSUPPORTED) instead of joining
it. A filing the builder accepts must give the document the Run's candidate
read and, through the route, the candidate the Run recorded, byte for byte; a
filing it refuses is listed with the reason. Zero calls.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "scripts"))

from vnext import historical_risk_results as route  # noqa: E402
from vnext import historical_text_emphasis as builder  # noqa: E402
from vnext.historical_results import TEXT_SPEC_PATHS  # noqa: E402
from vnext.historical_spec_revision import compile_historical_spec_file  # noqa: E402
from vnext.text_coverage import TextCoverageError  # noqa: E402


def main(runs_root, source_root, out):
    spec = compile_historical_spec_file(repo_root=REPO, repo_relative_path=TEXT_SPEC_PATHS["D01"],
                                        dependency_specs={})
    rows = {}
    for run in sorted(Path(runs_root).glob("run-*-D01")):
        records = [json.loads(line) for line in (run / "records.jsonl").read_text(
            encoding="utf-8").splitlines() if line.strip()]
        candidates = [r for r in records if r.get("record_type") == "DETERMINISTIC_TEXT_CANDIDATE"]
        if not candidates:
            continue
        candidate = candidates[0]
        reference = next(r for r in records if r.get("record_type") == "SOURCE_REFERENCE"
                         and r.get("source_role") == "target_primary")
        blob = next(r for r in records if r.get("record_type") == "RAW_BLOB"
                    and r["raw_asset_id"] == reference["raw_asset_id"])
        target = candidate["calculation_target"]
        raw = (Path(source_root) / blob["storage_uri"]).read_bytes()
        batch_documents = sorted({claim["document_id"] for claim in candidate["selected"].values()})
        row = {"batch_document_id": batch_documents[0] if len(batch_documents) == 1 else None,
               "batch_candidate_hash": candidate["candidate_hash"]}
        try:
            document = builder.build_text_document_admitting_underline(
                raw_bytes=raw, raw_blob=blob, source_reference=reference,
                expected_company_id=reference["company_id"], expected_cik=target["entity"],
                expected_period_end=target["period_end"])
        except TextCoverageError as refused:
            row.update(outcome="REFUSED", reason=str(refused))
        else:
            rebuilt = route.create_deterministic_text_candidate(
                compiled_spec=spec, target=target, source_references=[reference],
                raw_blobs={blob["raw_asset_id"]: blob}, raw_bytes_by_id={blob["raw_asset_id"]: raw})
            row.update(outcome="BUILT", document_id=document["text_document_id"],
                       same_document=document["text_document_id"] == row["batch_document_id"],
                       candidate_hash=rebuilt["candidate_hash"],
                       same_candidate=rebuilt == candidate)
        rows[run.name] = row
        print(run.name, row["outcome"], row.get("same_candidate"), row.get("reason"), flush=True)
    built = [row for row in rows.values() if row["outcome"] == "BUILT"]
    Path(out).write_text(json.dumps(
        {"record_type": "ISSUE_47_D01_PAGE_BOUNDARY_AFTER_PORT", "runs_root": str(runs_root),
         "filings": len(rows),
         "refused": sorted(name for name, row in rows.items() if row["outcome"] == "REFUSED"),
         "built": len(built),
         "built_with_the_batch_s_document_and_candidate": sum(
             1 for row in built if row["same_document"] and row["same_candidate"]),
         "per_run": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
