"""List E01's candidate items in every reachable window, under the content meaning.

For each position of the twelve-period batch, resolves E01 through the
historical route (no SEC or model request) and records what the route read:
each candidate item's filing, code, span and size, or the window's zero, or
the named gap that stopped it. This is the demand a content-confirmation call
application has to cover: one confirmation per candidate item, asked of exactly
the span recorded here.

Usage:
    python3 docs/evidence/issue47_history/e01-content-confirmed/candidate_census.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
HERE = Path(__file__).resolve().parent
BATCH = REPO / "docs/evidence/issue47_history/native-run-batch-12-periods/measured.json"


def main():
    from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric
    from vnext.normal_period_selection import resolve_period_selection
    periods = [(row["case"], row["company_id"], row["report_end"])
               for row in json.loads(BATCH.read_text(encoding="utf-8"))["batch"]["per_period"]]
    windows, total = [], {"candidates": 0, "characters": 0, "by_code": {}}
    for case, company_id, report_end in periods:
        try:
            selection = resolve_period_selection(repo_root=REPO, company_id=company_id, report_end=report_end)
            component = resolve_historical_zero_ai_metric(repo_root=REPO, company_id=company_id, metric_id="E01",
                                                          period_selection=selection)
        except Exception as error:  # noqa: BLE001 - a window the route cannot reach is recorded, not dropped
            windows.append({"case": case, "stopped_before_the_route": type(error).__name__ + ": " + str(error)[:300]})
            continue
        result, chosen = component["result"], component["selection"]
        confirmation = chosen.get("content_confirmation")
        row = {"case": case, "company_id": company_id, "report_end": report_end,
               "window": {key: component["target_period"][key] for key in ("period_start", "period_end")},
               "publication": result["publication"], "value": result["value"],
               "reason_code": result["reason_code"], "category": chosen.get("category")}
        if confirmation is not None:
            row["status"] = confirmation["status"]
            row["candidates"] = [{key: item[key] for key in ("accession", "item_code", "heading", "characters",
                                                              "incorporates_an_exhibit", "shares_the_body_of",
                                                              "text_sha256")}
                                 for item in confirmation["candidates"]]
            for item in confirmation["candidates"]:
                total["candidates"] += 1
                total["characters"] += item["characters"]
                total["by_code"][item["item_code"]] = total["by_code"].get(item["item_code"], 0) + 1
        else:
            row["reason"] = str(chosen.get("reason", ""))[:300]
        windows.append(row)
        print(case, result["publication"], result["value"], result["reason_code"],
              len(row.get("candidates", [])), flush=True)
    body = {"record_type": "E01_CONTENT_CONFIRMATION_CANDIDATE_CENSUS",
            "what_this_is": ("every E01 candidate item the historical route reads in the twelve periods with "
                             "saved originals; one content confirmation is needed per candidate"),
            "windows": windows, "totals": total, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (HERE / "candidate-census.json").write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n",
                                                encoding="utf-8")
    print(json.dumps(total))


if __name__ == "__main__":
    main()
