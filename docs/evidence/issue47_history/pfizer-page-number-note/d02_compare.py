"""D02 candidates under the page-number-aware navigation, compared with a batch's frozen Runs.

Usage: python3 d02_compare.py <restored source root> <batch dir> <out.json> company@report_end ...

For each position the D02 input and candidate are built through the current
historical route on a root restored from the committed export, and the
candidate's hash is compared with the candidate record in the batch's Run for
that position (``<batch>/<company-stem>-<year>/run-*-D02/records.jsonl``) when
there is one. The candidate hash carries the selected excerpts, their bytes
and the Spec closure, not code bytes, so equal hashes mean the same excerpts
were chosen. Zero calls.
"""
import glob
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext.historical_results import TEXT_SPEC_PATHS  # noqa: E402
from vnext.historical_spec_revision import compile_historical_spec_file  # noqa: E402
from vnext.historical_text_input import prepare_historical_business_text_input  # noqa: E402
from vnext.historical_text_results import shared_source_preparation, text_api  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402


def batch_candidate(batch, company, end):
    stem = company.split("_")[0]
    runs = glob.glob(str(Path(batch) / (stem + "-*") / "run-*-D02" / "records.jsonl"))
    for path in runs:
        records = [json.loads(line) for line in open(path, encoding="utf-8")]
        candidates = [r for r in records if r["record_type"] == "DETERMINISTIC_TEXT_CANDIDATE"]
        if candidates and candidates[0]["calculation_target"]["period_end"] == end:
            return candidates[0]
    return None


def main(root, batch, out, positions):
    root, results = Path(root), {}
    with checkpoint_replayed_once():
        for position in positions:
            company, end = position.split("@")
            started = time.time()
            try:
                with shared_source_preparation():
                    selection = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
                    prepared = prepare_historical_business_text_input(
                        repo_root=root, company_id=company, metric_id="D02", period_selection=selection)
                    spec = compile_historical_spec_file(
                        repo_root=root, repo_relative_path=TEXT_SPEC_PATHS["D02"], dependency_specs={})
                    api, _ = text_api("D02")
                    candidate = api.create_deterministic_text_candidate(
                        compiled_spec=spec, **prepared["text_arguments"])
            except Exception as error:  # recorded, not hidden
                results[position] = {"error": type(error).__name__ + ":" + str(error)[:300]}
                print(position, "ERROR", str(error)[:200], flush=True)
                continue
            earlier = batch_candidate(batch, company, end)
            results[position] = {
                "candidate_hash": candidate["candidate_hash"], "selected": len(candidate["selected"]),
                "batch_candidate_hash": earlier and earlier["candidate_hash"],
                "same_as_batch": None if earlier is None else earlier["candidate_hash"] == candidate["candidate_hash"],
                "seconds": int(time.time() - started)}
            print(position, results[position], flush=True)
    Path(out).write_text(json.dumps({"positions": results, "calls": [0, 0, 0]}, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
