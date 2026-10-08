"""C02's input and candidate for pinned periods whose proxy carries no inline XBRL.

Usage: python3 probe.py <restored source root> <out.json> company@report_end ...

Prepares each position's C02 input through the historical route on a root
restored from the acquisition's export, builds the candidate, and records the
proxy's cover identity from the input binding. Every position's binding must
carry ``proxy_cover_identity`` - that is the check that the input admission,
not only the preparation, read the cover (the injection script lists the one
change no unit case sees). Zero calls.
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext.historical_results import TEXT_SPEC_PATHS  # noqa: E402
from vnext.historical_spec_revision import compile_historical_spec_file  # noqa: E402
from vnext.historical_text_input import prepare_historical_business_text_input  # noqa: E402
from vnext.historical_text_results import (prepare_business_text_sources,  # noqa: E402
                                           shared_source_preparation, text_api)
from vnext.normal_history_plan import checkpoint_replayed_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402


def main(root, out, positions):
    root, results, missing = Path(root), {}, []
    with checkpoint_replayed_once():
        for position in positions:
            company, end = position.split("@")
            started = time.time()
            try:
                with shared_source_preparation():
                    selection = resolve_period_selection(repo_root=root, company_id=company,
                                                         report_end=end)
                    prepared = prepare_historical_business_text_input(
                        repo_root=root, company_id=company, metric_id="C02",
                        period_selection=selection)
                    if prepared["input_status"] == "BLOCKED":
                        results[position] = {"blocked": prepared["input_binding"]["limitations"]}
                        continue
                    spec = compile_historical_spec_file(
                        repo_root=root, repo_relative_path=TEXT_SPEC_PATHS["C02"], dependency_specs={})
                    api, _ = text_api("C02")
                    candidate = api.create_deterministic_text_candidate(
                        compiled_spec=spec, **prepared["text_arguments"])
                    built = prepare_business_text_sources(metric_id="C02", **prepared["text_arguments"])
            except Exception as error:  # recorded, not hidden
                results[position] = {"error": type(error).__name__ + ":" + str(error)[:300]}
                continue
            governance = next(iter(built["proposals"]))
            identity = prepared["input_binding"].get("proxy_cover_identity")
            if identity is None:
                missing.append(position)
            results[position] = {
                "proxy_accession": built["documents"][governance]["source_filing"]["accessionNumber"],
                "input_identity": identity,
                "coverage_identity": built["coverages"][governance].get("governance_identity"),
                "selected_excerpts": len(candidate["selected"]),
                "seconds": int(time.time() - started)}
            print(position, results[position]["selected_excerpts"], identity and identity["sec_names_on_filing_date"],
                  flush=True)
    record = {"root_note": "restored from the committed export; not a data root the Runs use",
              "positions": results, "positions_without_cover_identity": missing,
              "calls": [0, 0, 0]}
    Path(out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
