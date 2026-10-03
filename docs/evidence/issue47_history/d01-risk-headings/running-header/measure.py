"""What the running-header successor moves, filing by filing, over a batch's D01 Runs.

Usage: python3 measure.py <runs root> <out.json>

For each D01 Run under the runs root the filing is rebuilt from the Run's own
SOURCE_REFERENCE and RAW_BLOB records, its bytes read from the checkout or, for
a file the acquisition saved, from the committed export (the reading tools'
``saved_bytes``). The document is built once by the D01 chain as it stands, and
both selectors run on that same document: the frozen derivation and the
successor. So the two candidates can differ only by what the successor's one
substitution decides.

Recorded per filing: whether the frozen candidate is the batch's (it need not
be: a later rule refuses a heading run over a page), the headings each
selector takes, the lines the successor drops or adds, and every
heading-marked block in Item 1A whose text begins with a part label, linked or
not, so the forms the filings print are listed rather than assumed. Zero calls.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import saved_bytes  # noqa: E402
from vnext import historical_risk_results as route  # noqa: E402
from vnext import text_results as frozen  # noqa: E402
from vnext.historical_results import TEXT_SPEC_PATHS  # noqa: E402
from vnext.historical_spec_revision import compile_historical_spec_file  # noqa: E402
from vnext.text_coverage import TextCoverageError  # noqa: E402
from vnext.text_results import TextResultError  # noqa: E402

PART_LABEL = re.compile(r"^\W*parts?\b", re.I)


def _lines(candidate):
    return [claim["text"] for claim in sorted(candidate["selected"].values(),
                                              key=lambda claim: claim["order"])]


def main(runs_root, out):
    spec = compile_historical_spec_file(repo_root=REPO, repo_relative_path=TEXT_SPEC_PATHS["D01"],
                                        dependency_specs={})
    rows = {}
    for run in sorted(path for path in Path(runs_root).glob("run-*-D01") if path.is_dir()):
        records = [json.loads(line) for line in (run / "records.jsonl").read_text(
            encoding="utf-8").splitlines() if line.strip()]
        candidates = [r for r in records if r.get("record_type") == "DETERMINISTIC_TEXT_CANDIDATE"]
        if not candidates:
            rows[run.name] = {"outcome": "NO_CANDIDATE_IN_THE_RUN"}
            continue
        batch = candidates[0]
        reference = next(r for r in records if r.get("record_type") == "SOURCE_REFERENCE"
                         and r.get("source_role") == "target_primary")
        blob = next(r for r in records if r.get("record_type") == "RAW_BLOB"
                    and r["raw_asset_id"] == reference["raw_asset_id"])
        target = batch["calculation_target"]
        raw = saved_bytes(repo_root=REPO, relative=blob["storage_uri"])
        row = {"company_id": target["company_id"], "period_end": target["period_end"],
               "batch_candidate_hash": batch["candidate_hash"]}
        try:
            documents, coverages = route.prepare_text_sources(
                compiled_spec=spec, target=target, source_references=[reference],
                raw_blobs={blob["raw_asset_id"]: blob}, raw_bytes_by_id={blob["raw_asset_id"]: raw})
        except (TextCoverageError, TextResultError) as refused:
            row.update(outcome="REFUSED_BEFORE_SELECTION", reason=str(refused))
            rows[run.name] = row
            print(run.name, row["outcome"], row["reason"], flush=True)
            continue
        document = documents[reference["source_reference_id"]]
        scope = document["sections"]["ITEM_1A"]["candidates"][0]
        row["part_labels_in_item_1a"] = [
            {"block_index": block["block_index"], "text": block["leading_emphasis"]["text"],
             "linked": block["linked"]}
            for block in document["blocks"][scope["start_block"]:scope["end_block_exclusive"]]
            if block["leading_emphasis"] and PART_LABEL.match(block["leading_emphasis"]["text"])]
        arguments = dict(compiled_spec=spec, target=target, source_references=[reference],
                         documents=documents, coverages=coverages)
        before = frozen._derive_deterministic_candidate(**arguments)
        after = route._derive_candidate(**arguments)
        before_lines, after_lines = _lines(before), _lines(after)
        row.update(outcome="BUILT", frozen_is_the_batch_s=before == batch,
                   frozen_candidate_hash=before["candidate_hash"],
                   successor_candidate_hash=after["candidate_hash"],
                   moved=before != after, frozen_lines=len(before_lines),
                   successor_lines=len(after_lines),
                   dropped=[line for line in before_lines if line not in after_lines],
                   added=[line for line in after_lines if line not in before_lines],
                   successor_keeps_the_frozen_order=[
                       line for line in before_lines if line in after_lines] == after_lines)
        rows[run.name] = row
        print(run.name, row["outcome"], row["moved"], row["dropped"], flush=True)
    built = [row for row in rows.values() if row["outcome"] == "BUILT"]
    Path(out).write_text(json.dumps(
        {"record_type": "ISSUE_47_D01_RUNNING_HEADER_EFFECT", "filings": len(rows),
         "built": len(built),
         "refused_before_selection": sorted(
             name for name, row in rows.items() if row["outcome"] == "REFUSED_BEFORE_SELECTION"),
         "moved": sorted(name for name, row in rows.items() if row.get("moved")),
         "frozen_differs_from_the_batch": sorted(
             name for name, row in rows.items()
             if row["outcome"] == "BUILT" and not row["frozen_is_the_batch_s"]),
         "part_label_forms_in_item_1a": sorted({entry["text"] for row in built
                                                for entry in row["part_labels_in_item_1a"]}),
         "per_run": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
